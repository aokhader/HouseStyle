#!/usr/bin/env python3
"""
harvest.py — stratified GitHub merged-PR review-comment extractor.

Usage:
    export GITHUB_TOKEN=ghp_...
    python -m harvest.harvest --repo apache/airflow --months 2 --per-month 10

Output:
    data/<slug>/comments.jsonl   — one comment record per line
    data/<slug>/manifest.json    — sampling metadata and compliance record
"""

from __future__ import annotations

import argparse
import asyncio
import calendar
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, date, timedelta
from pathlib import Path
from typing import Any, AsyncIterator

import httpx

# ---------------------------------------------------------------------------
# Load .env (stdlib only — no python-dotenv dependency)
# ---------------------------------------------------------------------------

def _load_dotenv(path: Path = Path(".env")) -> None:
    """Parse a simple KEY=VALUE .env file and inject into os.environ."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val

_load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_REST = "https://api.github.com"
GITHUB_GRAPHQL = "https://api.github.com/graphql"
USER_AGENT = "house-style-harvest/1.0"
MAX_RETRIES = 5

BOT = re.compile(
    r"(\[bot\]|codecov|dependabot|pre-commit|sonar|coderabbit|greptile|sourcery|renovate)",
    re.I,
)
TRIVIAL = re.compile(r"^\s*(lgtm|nit|thanks?|done|\+1|ok(ay)?|👍|typo|same)\W*$", re.I)

MAINTAINER_ASSOCS = {"OWNER", "MEMBER"}

# GraphQL query: list merged PRs for a month window with lightweight fields
# used for pre-qualification (reviewThreads.totalCount >= 3) and stratification.
# files(first:20) is enough to determine a dominant top-level prefix cheaply.
PR_LIST_QUERY = """
query($owner: String!, $repo: String!, $after: String) {
  rateLimit { remaining resetAt cost }
  repository(owner: $owner, name: $repo) {
    pullRequests(
      first: 100
      states: MERGED
      orderBy: { field: CREATED_AT, direction: DESC }
      after: $after
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        mergedAt
        author { login }
        authorAssociation
        reviewThreads { totalCount }
        files(first: 20) { nodes { path } }
      }
    }
  }
}
"""

# GraphQL query: fetch full review threads + comments for one sampled PR.
# We parameterise owner/repo/number at call time via variables.
REVIEW_THREAD_QUERY = """
query($owner: String!, $repo: String!, $number: Int!) {
  rateLimit { remaining resetAt cost }
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      author { login }
      authorAssociation
      reviewThreads(first: 50) {
        pageInfo { hasNextPage }
        totalCount
        nodes {
          isResolved
          isOutdated
          comments(first: 20) {
            totalCount
            nodes {
              databaseId
              body
              diffHunk
              path
              originalPosition
              createdAt
              authorAssociation
              replyTo { databaseId }
              author { login }
            }
          }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GitHub merged-PR review-comment harvester.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--repo", required=True, help="owner/name e.g. apache/airflow")
    p.add_argument("--months", type=int, default=12, help="How far back to look")
    p.add_argument("--per-month", type=int, default=40, dest="per_month",
                   help="(unused in primary path; kept for CLI compat)")
    p.add_argument("--holdout", type=int, default=30,
                   help="Most-recent QUALIFIED merged PRs reserved and never sampled")
    p.add_argument("--out", default=None,
                   help="Output directory (default: data/<slug>/)")
    return p.parse_args()


# ---------------------------------------------------------------------------
# HTTP client factory
# ---------------------------------------------------------------------------


def make_client() -> httpx.AsyncClient:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        sys.exit("ERROR: Set GITHUB_TOKEN before running harvest.")
    return httpx.AsyncClient(
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        },
        timeout=60.0,
    )


# ---------------------------------------------------------------------------
# Rate-limit / retry helpers
# ---------------------------------------------------------------------------


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


async def _handle_rate_limit(response: httpx.Response, attempt: int) -> None:
    """Sleep if rate-limited; raise after MAX_RETRIES attempts."""
    if response.status_code == 429 or (
        response.status_code == 403
        and int(response.headers.get("X-RateLimit-Remaining", "1")) == 0
    ):
        retry_after = response.headers.get("Retry-After")
        reset_ts = response.headers.get("X-RateLimit-Reset")
        if retry_after:
            wait = int(retry_after) + 1
        elif reset_ts:
            wait = max(int(reset_ts) - int(time.time()), 0) + 5
        else:
            wait = 2 ** attempt
        _log(f"  [rate-limit] sleeping {wait}s (attempt {attempt}/{MAX_RETRIES})")
        await asyncio.sleep(wait)
        return
    # Exponential backoff for transient 5xx errors
    if response.status_code >= 500:
        wait = 2 ** attempt
        _log(f"  [{response.status_code}] sleeping {wait}s before retry")
        await asyncio.sleep(wait)
        return
    response.raise_for_status()


async def rest_get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> Any:
    """Single REST GET with retry/backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        resp = await client.get(url, params=params)
        if resp.status_code in (200, 201):
            return resp.json()
        if attempt == MAX_RETRIES:
            resp.raise_for_status()
        await _handle_rate_limit(resp, attempt)
    return {}  # unreachable


async def rest_paged(
    client: httpx.AsyncClient, url: str, params: dict | None = None
) -> AsyncIterator[Any]:
    """Follow Link: rel='next' pages, yielding each page's list."""
    is_search = "/search/" in url
    current_url: str | None = url
    current_params = params
    while current_url:
        for attempt in range(1, MAX_RETRIES + 1):
            resp = await client.get(current_url, params=current_params)
            if resp.status_code in (200, 201):
                break
            if attempt == MAX_RETRIES:
                resp.raise_for_status()
            await _handle_rate_limit(resp, attempt)

        data = resp.json()
        yield data  # yield the whole page so caller can read total_count / items

        # Advance to next page
        link_header = resp.headers.get("Link", "")
        next_url = _parse_next_link(link_header)
        current_url = next_url
        current_params = None  # params are baked into next_url

        if is_search and next_url:
            await asyncio.sleep(2)  # Search API: 30 req/min limit


def _parse_next_link(link_header: str) -> str | None:
    """Extract the URL for rel='next' from a Link header."""
    for part in link_header.split(","):
        segments = [s.strip() for s in part.split(";")]
        if len(segments) == 2 and segments[1] == 'rel="next"':
            return segments[0].strip("<>")
    return None


async def _sleep_until_reset(reset_at: str | None, attempt: int = 1) -> None:
    """Sleep until a GraphQL rateLimit resetAt timestamp (ISO-8601 Z)."""
    wait = 60 * attempt
    if reset_at:
        try:
            reset_dt = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
            wait = max(int((reset_dt - datetime.now(timezone.utc)).total_seconds()), 0) + 5
        except ValueError:
            pass
    mins = wait / 60
    _log(f"  [rate-limit] GraphQL budget exhausted \u2014 sleeping {wait}s "
         f"({mins:.1f} min, until {reset_at or 'unknown'})")
    await asyncio.sleep(wait)


async def preflight_rate_limit(client: httpx.AsyncClient) -> None:
    """Log the GraphQL point budget before committing to a run."""
    try:
        resp = await client.post(
            GITHUB_GRAPHQL,
            json={"query": "{ rateLimit { limit remaining resetAt } }"},
            headers={"Content-Type": "application/json"},
        )
        rl = (resp.json().get("data") or {}).get("rateLimit") or {}
        _log(f"[init] GraphQL budget: {rl.get('remaining')}/{rl.get('limit')} points, "
             f"resets {rl.get('resetAt')}")
    except Exception as e:
        _log(f"[init] WARNING: could not read GraphQL rate limit: {e}")


async def graphql(
    client: httpx.AsyncClient, query: str, variables: dict
) -> dict:
    """
    Execute a GraphQL query with retry/backoff.

    GitHub delivers GraphQL rate limits as HTTP 200 with errors[].type ==
    "RATE_LIMITED", which _handle_rate_limit (written for REST status codes)
    cannot see. We handle that case here and additionally throttle proactively
    when the remaining point budget runs low.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        resp = await client.post(
            GITHUB_GRAPHQL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            payload = data.get("data") or {}
            rl = payload.get("rateLimit") or {}

            if "errors" in data:
                errs = data["errors"]
                if any(e.get("type") == "RATE_LIMITED" for e in errs):
                    if attempt == MAX_RETRIES:
                        raise RuntimeError(
                            f"GraphQL RATE_LIMITED after {MAX_RETRIES} retries"
                        )
                    await _sleep_until_reset(rl.get("resetAt"), attempt)
                    continue
                raise RuntimeError(f"GraphQL errors: {errs}")

            # Proactive throttle: stop before we trip the limit mid-page.
            remaining = rl.get("remaining")
            if isinstance(remaining, int) and remaining < 150:
                await _sleep_until_reset(rl.get("resetAt"))

            return payload
        if attempt == MAX_RETRIES:
            resp.raise_for_status()
        await _handle_rate_limit(resp, attempt)
    return {}  # unreachable


# Privacy helpers
# ---------------------------------------------------------------------------


def pseudonymise(login: str) -> str:
    return hashlib.sha256(login.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Sub-Task 2: Holdout fence and month iterator
# ---------------------------------------------------------------------------


# Holdout GraphQL query — fetches recently merged PRs with their thread counts and
# file paths so we can require the same qualification threshold as the training set.
HOLDOUT_QUERY = """
query($owner: String!, $repo: String!, $after: String) {
  rateLimit { remaining resetAt cost }
  repository(owner: $owner, name: $repo) {
    pullRequests(
      first: 100
      states: MERGED
      orderBy: { field: UPDATED_AT, direction: DESC }
      after: $after
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        mergedAt
        reviewThreads { totalCount }
        files(first: 20) { nodes { path } }
      }
    }
  }
}
"""


async def fetch_holdout(client: httpx.AsyncClient, owner: str, repo: str, n: int) -> list[int]:
    """
    Return the n most-recently MERGED PRs that have reviewThreads.totalCount >= 3,
    sorted by mergedAt descending.  Pages through PRs ordered by updatedAt DESC until
    n qualified PRs are found (or 500 candidates examined without reaching n).
    """
    _log(f"[holdout] fetching {n} most-recent QUALIFIED PRs for {owner}/{repo} …")
    qualified: list[tuple[str, int]] = []  # (mergedAt, number)
    cursor: str | None = None
    examined = 0
    MAX_EXAMINE = 500  # safety cap

    while len(qualified) < n and examined < MAX_EXAMINE:
        data = await graphql(client, HOLDOUT_QUERY, {"owner": owner, "repo": repo, "after": cursor})
        prs_conn = data.get("repository", {}).get("pullRequests", {})
        nodes = prs_conn.get("nodes", [])
        page_info = prs_conn.get("pageInfo", {})

        for node in nodes:
            if examined >= MAX_EXAMINE or len(qualified) >= n:
                break
            examined += 1
            merged_at = node.get("mergedAt") or ""
            if not merged_at:
                continue
            thread_count = (node.get("reviewThreads") or {}).get("totalCount", 0)
            if thread_count < 3:
                continue
            qualified.append((merged_at, node["number"]))

        if not page_info.get("hasNextPage") or len(qualified) >= n:
            break
        cursor = page_info.get("endCursor")

    # Sort by mergedAt descending; take the n most recent
    qualified.sort(key=lambda x: x[0], reverse=True)
    holdout = [num for _, num in qualified[:n]]
    if holdout:
        _log(
            f"[holdout] {len(holdout)} qualified PRs  "
            f"(examined {examined} candidates)"
        )
    else:
        _log(f"[holdout] WARNING: found 0 qualified PRs in {examined} examined")
    return holdout


def iter_months(months_back: int) -> list[tuple[int, int]]:
    """Return list of (year, month) from oldest to newest, excluding current month."""
    today = date.today()
    result = []
    for i in range(months_back, 0, -1):
        # subtract i months from current
        total_months = today.year * 12 + today.month - 1 - i
        y = total_months // 12
        m = total_months % 12 + 1
        result.append((y, m))
    return result


def _month_key_of(iso_ts: str) -> str:
    """'2026-07-14T09:12:00Z' -> '2026-07'"""
    return iso_ts[:7]


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


async def build_pr_index(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    months: list[tuple[int, int]],
    holdout_set: set[int],
    out_dir: Path,
    tail_months: int = 3,
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """
    ONE descending pass over merged PRs, bucketed by merge month.

    The previous per-month implementation re-paged from the newest PR for every
    month, so reaching month -12 walked ~12k PRs and repeated that walk each
    month (~780 pages for a 12-month run). At ~21 points per page that blows the
    5000/hr GraphQL budget around month two. A single pass costs ~120 pages.

    We page by CREATED_AT DESC and stop once createdAt drops below the oldest
    target month start minus `tail_months`. That tail catches long-lived PRs
    created before a window but merged inside it, which the old per-month break
    silently dropped.

    The index is cached to pr_index.json so a resumed run does not re-page.

    Returns (qualified_by_month, candidates_seen_by_month).
    """
    cache_path = out_dir / "pr_index.json"
    target_months = {f"{y:04d}-{m:02d}" for y, m in months}

    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if set(cached.get("target_months", [])) == target_months:
            _log(f"[index] reusing cached PR index ({cache_path})")
            return (
                {k: v for k, v in cached["qualified_by_month"].items()},
                {k: int(v) for k, v in cached["candidates_by_month"].items()},
            )
        _log("[index] cached index covers different months \u2014 rebuilding")

    oldest_y, oldest_m = months[0]
    floor_y, floor_m = _shift_month(oldest_y, oldest_m, -tail_months)
    floor_iso = f"{floor_y:04d}-{floor_m:02d}-01T00:00:00Z"
    _log(f"[index] single descending pass; createdAt floor = {floor_iso}")

    qualified_by_month: dict[str, list[dict]] = defaultdict(list)
    candidates_by_month: dict[str, int] = defaultdict(int)
    seen_numbers: set[int] = set()
    cursor: str | None = None
    pages = 0

    while True:
        data = await graphql(
            client, PR_LIST_QUERY, {"owner": owner, "repo": repo, "after": cursor}
        )
        prs_conn = (data.get("repository") or {}).get("pullRequests") or {}
        nodes = prs_conn.get("nodes") or []
        page_info = prs_conn.get("pageInfo") or {}
        pages += 1

        if not nodes:
            break

        for node in nodes:
            merged_at = node.get("mergedAt") or ""
            if not merged_at:
                continue
            mkey = _month_key_of(merged_at)
            if mkey not in target_months:
                continue

            pr_num = node["number"]
            if pr_num in seen_numbers:
                continue
            seen_numbers.add(pr_num)

            candidates_by_month[mkey] += 1

            if pr_num in holdout_set:
                continue
            thread_count = (node.get("reviewThreads") or {}).get("totalCount", 0)
            if thread_count < 3:
                continue

            files = [f["path"] for f in ((node.get("files") or {}).get("nodes") or [])]
            qualified_by_month[mkey].append({
                "number": pr_num,
                "merged_at": merged_at,
                "user_login": (node.get("author") or {}).get("login", ""),
                "author_association": node.get("authorAssociation", "NONE"),
                "top_prefix": top_prefix(files),
                "thread_count": thread_count,
            })

        oldest_on_page = nodes[-1].get("createdAt") or ""
        if pages % 10 == 0 or not page_info.get("hasNextPage"):
            total_q = sum(len(v) for v in qualified_by_month.values())
            _log(f"  [index] page {pages}  \u2022 oldest createdAt {oldest_on_page[:10]}  "
                 f"\u2022 {len(seen_numbers)} in-window PRs  \u2022 {total_q} qualified")

        if oldest_on_page and oldest_on_page < floor_iso:
            _log(f"  [index] reached createdAt floor after {pages} pages")
            break
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    cache_path.write_text(json.dumps({
        "target_months": sorted(target_months),
        "pages_fetched": pages,
        "qualified_by_month": {k: v for k, v in qualified_by_month.items()},
        "candidates_by_month": {k: v for k, v in candidates_by_month.items()},
    }, indent=2), encoding="utf-8")
    _log(f"[index] complete: {pages} pages, {len(seen_numbers)} in-window PRs, "
         f"{sum(len(v) for v in qualified_by_month.values())} qualified \u2192 {cache_path}")

    return dict(qualified_by_month), dict(candidates_by_month)


# ---------------------------------------------------------------------------
# Sub-Task 3: GraphQL PR fetcher and path-prefix stratified sampler
# ---------------------------------------------------------------------------


def top_prefix(filenames: list[str]) -> str:
    """Return the most-common top-level directory prefix, or '_root'."""
    counts: dict[str, int] = defaultdict(int)
    for f in filenames:
        parts = f.split("/")
        prefix = parts[0] if len(parts) > 1 else "_root"
        counts[prefix] += 1
    if not counts:
        return "_root"
    return max(counts, key=lambda k: counts[k])


def apply_domination_cap(
    prs: list[dict],
    cap_frac: float = 0.35,
    seed_key: str = "",
    month_key: str = "",
) -> list[dict]:
    """
    Take ALL qualified PRs, then randomly subsample within any prefix whose share
    of the total would exceed cap_frac.  Seeds with seed_key for reproducibility.

    Note: cap_frac is applied against the qualified-pool size (len(prs)), not the
    selected set, so the effective ceiling in the output can exceed cap_frac when
    other prefixes are underrepresented.  This intentionally favours substantive
    prefixes (airflow-core, providers) over CI/docs noise.

    Emits a stderr warning if any selected prefix exceeds 50% of the selected set.

    Returns the (possibly trimmed) list sorted by PR number.
    """
    if not prs:
        return []

    random.seed(seed_key)

    # Group by prefix
    buckets: dict[str, list[dict]] = defaultdict(list)
    for pr in prs:
        buckets[pr.get("top_prefix", "_root")].append(pr)

    total = len(prs)
    selected: list[dict] = []

    for prefix, bucket in buckets.items():
        max_allowed = math.ceil(total * cap_frac)
        if len(bucket) > max_allowed:
            # Randomly subsample within the over-represented prefix
            selected.extend(random.sample(bucket, max_allowed))
        else:
            selected.extend(bucket)

    selected.sort(key=lambda pr: pr["number"])

    # Warn if any prefix dominates the selected set (> 50%)
    if selected:
        sel_total = len(selected)
        sel_by_prefix: dict[str, int] = defaultdict(int)
        for pr in selected:
            sel_by_prefix[pr.get("top_prefix", "_root")] += 1
        for prefix, cnt in sel_by_prefix.items():
            if cnt / sel_total > 0.50:
                tag = f"[{month_key}] " if month_key else ""
                _log(
                    f"  [domination-warn] {tag}prefix '{prefix}' = "
                    f"{cnt}/{sel_total} ({cnt/sel_total:.0%}) of selected PRs — "
                    f"exceeds 50% warning threshold"
                )

    return selected


async def fetch_pr_data(
    client: httpx.AsyncClient, owner: str, repo: str, pr_number: int
) -> dict:
    """Fetch full review threads + comments for a single sampled PR."""
    data = await graphql(
        client,
        REVIEW_THREAD_QUERY,
        {"owner": owner, "repo": repo, "number": pr_number},
    )
    pr_node = data.get("repository", {}).get("pullRequest") or {}
    if pr_node.get("reviewThreads", {}).get("pageInfo", {}).get("hasNextPage"):
        _log(f"  [graphql] WARNING: PR #{pr_number} has >50 review threads; first 50 only")
    return pr_node


# ---------------------------------------------------------------------------
# Sub-Task 4: Filter pipeline, signal_strength, addressed, output records
# ---------------------------------------------------------------------------


def trimmed_hunk(diff_hunk: str, context: int = 6) -> str:
    """
    Return ±context lines around the last anchored (+ or -) line in the hunk.
    Falls back to the last context*2+1 lines if no anchored line is found.
    """
    lines = diff_hunk.split("\n")
    anchor_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("+") or line.startswith("-"):
            anchor_idx = i
    if anchor_idx == -1:
        return "\n".join(lines[-(context * 2 + 1):])
    start = max(0, anchor_idx - context)
    end = min(len(lines), anchor_idx + context + 1)
    return "\n".join(lines[start:end])


def body_excerpt(body: str) -> str:
    return " ".join(body.split()[:15])


async def resolve_addressed_commit_walk(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    pr_number: int,
    pr_author_login: str,
    comment_path: str,
    comment_created_at: str,
) -> str:
    """
    Fallback: walk non-merge commits by PR author after comment_created_at.
    Returns 'resolved' if comment_path was touched, else 'open'.
    """
    commits_url = f"{GITHUB_REST}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    commits = await rest_get(client, commits_url, {"per_page": 100})
    if not isinstance(commits, list):
        return "open"

    comment_dt = datetime.fromisoformat(comment_created_at.rstrip("Z")).replace(tzinfo=timezone.utc)

    # Cache sha -> changed files
    sha_files: dict[str, set[str]] = {}

    for commit in commits:
        # Skip merge commits (> 1 parent)
        if len(commit.get("parents", [])) > 1:
            continue
        # Require commit author matches PR author
        commit_author = (commit.get("author") or {}).get("login", "")
        if commit_author != pr_author_login:
            continue
        # Check timestamp
        commit_date_str = (commit.get("commit", {}).get("author") or {}).get("date", "")
        if not commit_date_str:
            continue
        commit_dt = datetime.fromisoformat(commit_date_str.rstrip("Z")).replace(tzinfo=timezone.utc)
        if commit_dt <= comment_dt:
            continue

        sha = commit["sha"]
        if sha not in sha_files:
            try:
                detail = await rest_get(client, f"{GITHUB_REST}/repos/{owner}/{repo}/commits/{sha}")
                sha_files[sha] = {f["filename"] for f in detail.get("files", [])}
            except Exception:
                sha_files[sha] = set()

        if comment_path in sha_files[sha]:
            return "resolved"

    return "open"


def filter_and_build_records(
    pr_node: dict,
    pr_number: int,
    owner: str,
    repo: str,
    drop_counts: dict[str, int],
    addressed_method: str,
) -> list[dict]:
    """
    Run the filter pipeline over threads/comments, assign signal_strength and addressed.
    Returns a list of output records (may be empty if PR-level gate triggers).
    Does NOT do commit-walk (that needs async); sets addressed='pending_walk' as placeholder.
    """
    pr_author_login = (pr_node.get("author") or {}).get("login", "")
    pr_author_assoc = pr_node.get("authorAssociation", "NONE")
    threads = (pr_node.get("reviewThreads") or {}).get("nodes", [])

    records: list[dict] = []

    for thread in threads:
        is_resolved = thread.get("isResolved", False)
        is_outdated = thread.get("isOutdated", False)
        thread_comment_count = (thread.get("comments") or {}).get("totalCount", 0)
        comments = (thread.get("comments") or {}).get("nodes", [])

        # signal_strength tiers:
        #   resolved  → strong  (PR author explicitly resolved the thread)
        #   outdated  → medium  (superseded by a force-push; author touched the area
        #                        but GitHub lost the line anchor — likely addressed)
        #   open      → weak    (no evidence of follow-up)
        if is_resolved:
            signal_strength = "strong"
        elif is_outdated:
            signal_strength = "medium"
        else:
            signal_strength = "weak"

        # Determine addressed from GraphQL resolution state
        if is_resolved:
            addressed_gql = "resolved"
        elif is_outdated:
            addressed_gql = "outdated"
        else:
            addressed_gql = "open"

        for comment in comments:
            login = (comment.get("author") or {}).get("login", "") or ""
            body = comment.get("body", "") or ""

            # Stage 0: bot
            if BOT.search(login):
                drop_counts["bot"] = drop_counts.get("bot", 0) + 1
                continue

            # Stage 1: length
            if len(body) < 120:
                drop_counts["length"] = drop_counts.get("length", 0) + 1
                continue

            # Stage 2: trivial
            if TRIVIAL.match(body):
                drop_counts["trivial"] = drop_counts.get("trivial", 0) + 1
                continue

            # Stage 3: self-review
            if login and login == pr_author_login:
                drop_counts["self_review"] = drop_counts.get("self_review", 0) + 1
                continue

            # Stage 4: maintainer-to-maintainer shorthand
            # Only drop if the comment is short (< 200 chars) — longer committer-to-committer
            # review is often substantive on ASF projects and should be kept.
            reviewer_assoc = comment.get("authorAssociation", "NONE")
            if (
                reviewer_assoc in MAINTAINER_ASSOCS
                and pr_author_assoc in MAINTAINER_ASSOCS
                and len(body) < 200
            ):
                drop_counts["maintainer_to_maintainer"] = drop_counts.get("maintainer_to_maintainer", 0) + 1
                continue

            # Addressed
            if addressed_method == "graphql_resolution":
                addressed = addressed_gql
            else:
                # Placeholder; will be resolved by async commit-walk caller
                addressed = "__pending__"

            db_id = comment.get("databaseId") or 0
            reply_to_id = (comment.get("replyTo") or {}).get("databaseId")
            diff_hunk_full = comment.get("diffHunk", "") or ""

            record = {
                "body_excerpt": body_excerpt(body),
                "diff_hunk": diff_hunk_full,
                "diff_hunk_trimmed": trimmed_hunk(diff_hunk_full),
                "path": comment.get("path", ""),
                "position": comment.get("originalPosition"),
                "in_reply_to_id": reply_to_id,
                "created_at": comment.get("createdAt", ""),
                "url": f"https://github.com/{owner}/{repo}/pull/{pr_number}#discussion_r{db_id}",
                "author_association": reviewer_assoc,
                "reviewer_hash": pseudonymise(login) if login else "",
                "addressed": addressed,
                "signal_strength": signal_strength,
                "pr_number": pr_number,
                # Internal fields used for commit-walk; stripped before writing
                "_pr_author_login": pr_author_login,
                "_comment_path": comment.get("path", ""),
                "_comment_created_at": comment.get("createdAt", ""),
            }
            records.append(record)

    # PR-level gate: require >= 3 surviving comments
    if len(records) < 3:
        drop_counts["pr_rubber_stamp"] = drop_counts.get("pr_rubber_stamp", 0) + 1
        drop_counts["discarded_by_pr_gate"] = drop_counts.get("discarded_by_pr_gate", 0) + len(records)
        return []

    return records


async def resolve_pending_addressed(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    records: list[dict],
) -> list[dict]:
    """Fill in addressed for records with '__pending__' (commit-walk fallback)."""
    for rec in records:
        if rec.get("addressed") == "__pending__":
            rec["addressed"] = await resolve_addressed_commit_walk(
                client,
                owner,
                repo,
                rec["pr_number"],
                rec.pop("_pr_author_login", ""),
                rec.pop("_comment_path", ""),
                rec.pop("_comment_created_at", ""),
            )
        else:
            # Clean up internal fields
            rec.pop("_pr_author_login", None)
            rec.pop("_comment_path", None)
            rec.pop("_comment_created_at", None)
    return records


# ---------------------------------------------------------------------------
# Sub-Task 5: Output writer and manifest
# ---------------------------------------------------------------------------


def slug(repo: str) -> str:
    return repo.replace("/", "-")


def load_manifest(out_dir: Path) -> dict:
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    return {}


def save_manifest(out_dir: Path, manifest: dict) -> None:
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def append_comments(out_dir: Path, records: list[dict]) -> None:
    path = out_dir / "comments.jsonl"
    with path.open("a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _flush_manifest(
    out_dir: Path,
    manifest: dict,
    args: argparse.Namespace,
    spdx_license: str,
    holdout_prs: list[int],
    per_month_counts: dict,
    drop_counts: dict,
    total_threads_all: int,
    resolved_threads_all: int,
    outdated_threads_all: int,
    addressed_method: str,
) -> None:
    """Write manifest.json after each completed month."""
    rate = (
        (resolved_threads_all + outdated_threads_all) / total_threads_all * 100
        if total_threads_all > 0
        else 0.0
    )
    open_threads = total_threads_all - resolved_threads_all - outdated_threads_all
    manifest.update({
        "repo": args.repo,
        "spdx_license": spdx_license,
        "sampling_params": {
            "months": args.months,
            "per_month": args.per_month,
            "holdout": args.holdout,
        },
        "holdout_prs": holdout_prs,
        "per_month_counts": per_month_counts,
        "filter_drop_counts": drop_counts,
        "thread_resolution_rate_pct": round(rate, 2),
        "thread_resolution_detail": (
            f"resolved={resolved_threads_all} outdated={outdated_threads_all} "
            f"open={open_threads} total={total_threads_all}"
        ),
        "addressed_method": addressed_method,
        "_total_threads_raw": total_threads_all,
        "_resolved_threads_raw": resolved_threads_all,
        "_outdated_threads_raw": outdated_threads_all,
    })
    save_manifest(out_dir, manifest)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def main() -> None:
    args = parse_args()
    owner, repo_name = args.repo.split("/", 1)
    out_dir = Path(args.out) if args.out else Path("data") / slug(args.repo)
    out_dir.mkdir(parents=True, exist_ok=True)

    async with make_client() as client:
        # Load existing manifest (resumability)
        manifest = load_manifest(out_dir)
        completed_months: set[str] = set((manifest.get("per_month_counts") or {}).keys())
        drop_counts: dict[str, int] = dict(manifest.get("filter_drop_counts") or {})

        # Fetch repo metadata (license)
        await preflight_rate_limit(client)
        _log(f"[init] fetching repo metadata for {args.repo} \u2026")
        repo_meta = await rest_get(client, f"{GITHUB_REST}/repos/{args.repo}")
        spdx_license = (repo_meta.get("license") or {}).get("spdx_id") or "NOASSERTION"
        _log(f"[init] license: {spdx_license}")

        # Holdout fence — n most-recently merged PRs with >= 3 review threads
        holdout_prs: list[int] = manifest.get("holdout_prs") or []
        if not holdout_prs:
            holdout_prs = await fetch_holdout(client, owner, repo_name, args.holdout)
        holdout_set = set(holdout_prs)

        # Month iterator
        months = iter_months(args.months)
        per_month_counts: dict[str, dict] = dict(manifest.get("per_month_counts") or {})

        # Accumulators for thread resolution rate (persist across months for resume)
        total_threads_all = int(manifest.get("_total_threads_raw", 0))
        resolved_threads_all = int(manifest.get("_resolved_threads_raw", 0))
        outdated_threads_all = int(manifest.get("_outdated_threads_raw", 0))
        # addressed_method is locked in after the first month with real thread data
        addressed_method: str = manifest.get("addressed_method", "unknown")

        # Single descending pass over merged PRs, bucketed by merge month.
        qualified_by_month, candidates_by_month = await build_pr_index(
            client, owner, repo_name, months, holdout_set, out_dir
        )

        for year, month in months:
            month_key = f"{year:04d}-{month:02d}"
            if month_key in completed_months:
                _log(f"[month] {month_key} already done, skipping")
                continue

            _log(f"[month] processing {month_key} \u2026")

            # Step 1: read this month's bucket from the single-pass index.
            qualified_prs = list(qualified_by_month.get(month_key, []))
            candidates_seen = candidates_by_month.get(month_key, 0)
            pct_qual = 100 * len(qualified_prs) // max(candidates_seen, 1)
            _log(
                f"  [month] candidates_seen={candidates_seen}  "
                f"candidates_with_3plus_threads={len(qualified_prs)} ({pct_qual}%)"
            )

            # Build qualified-pool prefix distribution (before any capping)
            pool_prefix_counts: dict[str, int] = defaultdict(int)
            for pr in qualified_prs:
                pool_prefix_counts[pr["top_prefix"]] += 1

            if not qualified_prs:
                per_month_counts[month_key] = {
                    "candidates_seen": candidates_seen,
                    "candidates_with_3plus_threads": 0,
                    "prs_selected": 0,
                    "prs_yielding_records": 0,
                    "comments_accepted": 0,
                    "per_prefix_pool": {},
                    "per_prefix_selected": {},
                }
                completed_months.add(month_key)
                _flush_manifest(
                    out_dir, manifest, args, spdx_license, holdout_prs,
                    per_month_counts, drop_counts,
                    total_threads_all, resolved_threads_all, outdated_threads_all, addressed_method,
                )
                continue

            # Step 2: take all qualified PRs, apply anti-domination cap (35%)
            seed_key = f"{args.repo}{month_key}"
            sampled = apply_domination_cap(qualified_prs, seed_key=seed_key, month_key=month_key)
            n_capped = len(qualified_prs) - len(sampled)
            _log(
                f"  [month] prs_selected={len(sampled)}"
                + (f"  ({n_capped} capped by domination limit)" if n_capped else "")
            )

            # Step 3: record per_prefix from selected PRs (post-cap)
            prefix_counts: dict[str, int] = defaultdict(int)
            for pr in sampled:
                prefix_counts[pr["top_prefix"]] += 1

            # Step 4: full GraphQL fetch (threads+comments) for each sampled PR
            _log(f"  [month] fetching full review threads for {len(sampled)} PRs \u2026")
            for i, pr in enumerate(sampled, 1):
                try:
                    if i % 10 == 0 or i == len(sampled):
                        _log(f"  [graphql] {i}/{len(sampled)} PRs fetched")
                    pr["_node"] = await fetch_pr_data(client, owner, repo_name, pr["number"])
                except Exception as e:
                    _log(f"  [graphql] PR #{pr['number']} failed: {e}")
                    pr["_node"] = {}

            # Step 5: accumulate thread resolution stats (resolved vs outdated separately)
            for pr in sampled:
                threads = (pr["_node"].get("reviewThreads") or {}).get("nodes", [])
                total_threads_all += len(threads)
                resolved_threads_all += sum(1 for t in threads if t.get("isResolved"))
                outdated_threads_all += sum(1 for t in threads if t.get("isOutdated"))

            combined_addressed = resolved_threads_all + outdated_threads_all
            # Lock in addressed_method after the first month that has thread data
            if total_threads_all > 0 and addressed_method == "unknown":
                rate = combined_addressed / total_threads_all * 100
                addressed_method = "graphql_resolution" if rate >= 60 else "commit_walk"
                _log(
                    f"  [month] addressed_method locked: "
                    f"{combined_addressed}/{total_threads_all} = {rate:.1f}% "
                    f"(resolved={resolved_threads_all} outdated={outdated_threads_all}) "
                    f"\u2192 {addressed_method}"
                )
            elif total_threads_all > 0:
                rate = combined_addressed / total_threads_all * 100
                _log(
                    f"  [month] thread resolution: "
                    f"{combined_addressed}/{total_threads_all} = {rate:.1f}% "
                    f"(resolved={resolved_threads_all} outdated={outdated_threads_all}  "
                    f"method={addressed_method})"
                )

            # Step 6: filter pipeline + build output records
            month_records: list[dict] = []
            prs_yielding = 0

            for pr in sampled:
                records = filter_and_build_records(
                    pr["_node"],
                    pr["number"],
                    owner,
                    repo_name,
                    drop_counts,
                    addressed_method,
                )
                if not records:
                    continue
                prs_yielding += 1

                if addressed_method == "commit_walk":
                    records = await resolve_pending_addressed(
                        client, owner, repo_name, records
                    )
                else:
                    for rec in records:
                        rec.pop("_pr_author_login", None)
                        rec.pop("_comment_path", None)
                        rec.pop("_comment_created_at", None)

                month_records.extend(records)

            _log(
                f"  [month] prs_yielding_records={prs_yielding}  "
                f"comments_accepted={len(month_records)}"
            )
            append_comments(out_dir, month_records)

            per_month_counts[month_key] = {
                "candidates_seen": candidates_seen,
                "candidates_with_3plus_threads": len(qualified_prs),
                "prs_selected": len(sampled),
                "prs_yielding_records": prs_yielding,
                "comments_accepted": len(month_records),
                "per_prefix_pool": dict(pool_prefix_counts),
                "per_prefix_selected": dict(prefix_counts),
            }
            completed_months.add(month_key)
            _flush_manifest(
                out_dir, manifest, args, spdx_license, holdout_prs,
                per_month_counts, drop_counts,
                total_threads_all, resolved_threads_all, outdated_threads_all, addressed_method,
            )

        # Final summary log
        combined_addressed = resolved_threads_all + outdated_threads_all
        final_rate = (
            combined_addressed / total_threads_all * 100
            if total_threads_all > 0
            else 0.0
        )
        _log(
            f"\n[done] thread_resolution_rate_pct = {final_rate:.1f}%  "
            f"(resolved={resolved_threads_all} outdated={outdated_threads_all} "
            f"total={total_threads_all})  "
            f"addressed_method = {addressed_method}"
        )
        _log(f"[done] output: {out_dir}")
        _flush_manifest(
            out_dir, manifest, args, spdx_license, holdout_prs,
            per_month_counts, drop_counts,
            total_threads_all, resolved_threads_all, outdated_threads_all, addressed_method,
        )

    _log(f"\nManifest: {(out_dir / 'manifest.json').resolve()}")


if __name__ == "__main__":
    asyncio.run(main())