#!/usr/bin/env python3
"""
eval/fetch_holdout.py — pull the evaluation set: diffs + real human review comments
for the 30 held-out PRs recorded in ``data/<slug>/manifest.json``.

These PRs were fenced off before sampling and never entered the corpus, so their
review comments are unseen ground truth. Each one qualified at ``reviewThreads >= 3``,
so every held-out PR has something to score against.

REST rather than GraphQL on purpose: ``/pulls/{n}/comments`` returns ``line`` and
``original_line`` — a real file line — whereas the GraphQL ``originalPosition`` is an
offset into the diff. The eval matches findings to comments "within 5 lines", which
needs file lines.

Ground truth uses the same noise filters as the harvester (bots, sub-120-char bodies,
LGTM-class replies, self-review) so a finding is scored against the same class of
comment the rules were mined from. The maintainer-to-maintainer filter is deliberately
NOT applied here: it exists to keep shorthand out of the training corpus, and dropping
real reviewer comments from the ground truth would inflate recall.

Output (gitignored working storage — carries full bodies):
    data/<slug>/holdout/pr_<number>.json
    data/<slug>/holdout/index.json

Usage:
    python -m eval.fetch_holdout --repo apache/airflow
    python -m eval.fetch_holdout --repo apache/airflow --limit 3     # smoke test
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

GITHUB_REST = "https://api.github.com"
USER_AGENT = "house-style-eval/1.0"
MAX_RETRIES = 5

# Kept byte-identical to harvest/harvest.py so the ground truth and the training
# corpus admit the same class of comment.
BOT = re.compile(
    r"(\[bot\]|codecov|dependabot|pre-commit|sonar|coderabbit|greptile|sourcery|renovate)",
    re.I,
)
TRIVIAL = re.compile(r"^\s*(lgtm|nit|thanks?|done|\+1|ok(ay)?|👍|typo|same)\W*$", re.I)
MIN_BODY_CHARS = 120


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def slug(repo: str) -> str:
    return repo.replace("/", "-")


def pseudonymise(login: str) -> str:
    return hashlib.sha256(login.encode()).hexdigest()[:12]


def make_client() -> httpx.AsyncClient:
    """Authenticated when a token is available, anonymous when it is not.

    Anonymous works — every repo here is public — but the budget drops from 5,000
    requests an hour to 60, and this fetch needs roughly three per PR. Rather than
    refuse, we warn and let the caller decide: the run is resumable, so an anonymous
    fetch simply takes several passes.
    """
    _load_dotenv()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        _log("WARNING: no GITHUB_TOKEN - running anonymously at 60 requests/hour.")
        _log("         This fetch needs ~3 requests per PR. It is resumable; re-run to")
        _log("         continue after each rate-limit window.")
    return httpx.AsyncClient(headers=headers, timeout=60.0)


async def check_auth(client: httpx.AsyncClient) -> None:
    """Fail fast and clearly on an expired token, rather than 401-ing per PR."""
    r = await client.get(f"{GITHUB_REST}/rate_limit")
    if r.status_code == 401:
        _log("ERROR: GITHUB_TOKEN is set but rejected (401 Bad credentials).")
        _log("       Refresh it in .env, or remove it to run anonymously.")
        raise SystemExit(2)
    if r.status_code == 200:
        core = r.json()["resources"]["core"]
        _log(f"rate limit: {core['remaining']}/{core['limit']} requests remaining")


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> Any:
    for attempt in range(1, MAX_RETRIES + 1):
        resp = await client.get(url, params=params)
        if resp.status_code == 200:
            return resp
        if resp.status_code in (403, 429):
            reset = resp.headers.get("x-ratelimit-reset")
            wait = 60.0
            if reset:
                import time as _t
                wait = max(5.0, float(reset) - _t.time() + 2)
            _log(f"  rate limited, sleeping {wait:.0f}s (attempt {attempt})")
            await asyncio.sleep(min(wait, 900))
            continue
        if resp.status_code >= 500:
            await asyncio.sleep(2 * attempt)
            continue
        resp.raise_for_status()
    raise RuntimeError(f"giving up on {url}")


async def _paged(client: httpx.AsyncClient, url: str) -> list[dict]:
    out: list[dict] = []
    params: dict | None = {"per_page": 100}
    while url:
        resp = await _get(client, url, params)
        out.extend(resp.json())
        params = None
        url = _next_link(resp.headers.get("link", ""))
    return out


def _next_link(link_header: str) -> str:
    for part in link_header.split(","):
        seg = part.split(";")
        if len(seg) >= 2 and 'rel="next"' in seg[1]:
            return seg[0].strip().strip("<>")
    return ""


def build_ground_truth(comments: list[dict], pr_author: str,
                       drops: dict[str, int]) -> list[dict]:
    """Apply the harvester's noise filters and shape the surviving comments."""
    out: list[dict] = []
    for c in comments:
        login = ((c.get("user") or {}).get("login")) or ""
        body = c.get("body") or ""
        if BOT.search(login):
            drops["bot"] = drops.get("bot", 0) + 1
            continue
        if len(body) < MIN_BODY_CHARS:
            drops["length"] = drops.get("length", 0) + 1
            continue
        if TRIVIAL.match(body):
            drops["trivial"] = drops.get("trivial", 0) + 1
            continue
        if login and login == pr_author:
            drops["self_review"] = drops.get("self_review", 0) + 1
            continue
        # `line` is null on an outdated comment; `original_line` still anchors it.
        line = c.get("line") or c.get("original_line") or c.get("original_position")
        out.append({
            "comment_id": c.get("id"),
            "path": c.get("path"),
            "line": line,
            "start_line": c.get("start_line"),
            "side": c.get("side"),
            "body": body,
            "url": c.get("html_url"),
            "in_reply_to_id": c.get("in_reply_to_id"),
            "author_association": c.get("author_association"),
            "reviewer_hash": pseudonymise(login) if login else "",
            "created_at": c.get("created_at"),
        })
    return out


async def fetch_one(client: httpx.AsyncClient, owner: str, repo: str,
                    number: int) -> dict:
    base = f"{GITHUB_REST}/repos/{owner}/{repo}/pulls/{number}"
    pr = (await _get(client, base)).json()
    files = await _paged(client, f"{base}/files")
    comments = await _paged(client, f"{base}/comments")

    drops: dict[str, int] = {}
    pr_author = ((pr.get("user") or {}).get("login")) or ""
    ground_truth = build_ground_truth(comments, pr_author, drops)

    return {
        "number": number,
        "repo": f"{owner}/{repo}",
        "title": pr.get("title"),
        "body": pr.get("body") or "",
        "merged_at": pr.get("merged_at"),
        "base_sha": ((pr.get("base") or {}).get("sha")),
        "head_sha": ((pr.get("head") or {}).get("sha")),
        "author_hash": pseudonymise(pr_author) if pr_author else "",
        "changed_files": pr.get("changed_files"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "files": [
            {
                "path": f.get("filename"),
                "status": f.get("status"),
                "additions": f.get("additions"),
                "deletions": f.get("deletions"),
                "patch": f.get("patch") or "",
            }
            for f in files
        ],
        "ground_truth": ground_truth,
        "ground_truth_dropped": drops,
        "review_comments_raw": len(comments),
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch held-out PR diffs and ground truth.")
    ap.add_argument("--repo", default="apache/airflow")
    ap.add_argument("--limit", type=int, default=0, help="fetch only the first N (smoke test)")
    ap.add_argument("--force", action="store_true", help="re-fetch PRs already on disk")
    args = ap.parse_args()

    owner, _, repo = args.repo.partition("/")
    out_dir = Path("data") / slug(args.repo) / "holdout"
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads(
        (Path("data") / slug(args.repo) / "manifest.json").read_text(encoding="utf-8")
    )
    holdout = manifest["holdout_prs"]
    if args.limit:
        holdout = holdout[: args.limit]

    index = []
    async with make_client() as client:
        await check_auth(client)
        for i, number in enumerate(holdout, 1):
            dest = out_dir / f"pr_{number}.json"
            if dest.exists() and not args.force:
                rec = json.loads(dest.read_text(encoding="utf-8"))
                _log(f"[{i}/{len(holdout)}] PR #{number} cached "
                     f"({len(rec['ground_truth'])} ground-truth comments)")
            else:
                rec = await fetch_one(client, owner, repo, number)
                dest.write_text(json.dumps(rec, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8", newline="\n")
                _log(f"[{i}/{len(holdout)}] PR #{number}: {len(rec['files'])} files, "
                     f"{rec['review_comments_raw']} raw comments -> "
                     f"{len(rec['ground_truth'])} ground truth")
            index.append({
                "number": number,
                "title": rec["title"],
                "files": len(rec["files"]),
                "additions": rec["additions"],
                "deletions": rec["deletions"],
                "ground_truth": len(rec["ground_truth"]),
                "paths": sorted({f["path"] for f in rec["files"]})[:50],
            })

    total_gt = sum(e["ground_truth"] for e in index)
    (out_dir / "index.json").write_text(
        json.dumps({"repo": args.repo, "n_prs": len(index),
                    "total_ground_truth": total_gt, "prs": index},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    _log(f"\n{len(index)} PRs, {total_gt} ground-truth comments "
         f"({total_gt / len(index):.1f} per PR)")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
