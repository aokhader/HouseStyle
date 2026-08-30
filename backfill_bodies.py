#!/usr/bin/env python3
"""
backfill_bodies.py — add full `body` text to an existing comments.jsonl.

The harvester stored only body_excerpt (first 15 words), which is too little to
distil conventions from. Every record carries pr_number and a URL ending in
#discussion_r<id>, so bodies can be recovered with one paginated REST call per
PR rather than a full re-harvest.

Usage:
    python backfill_bodies.py --repo apache/airflow
    python backfill_bodies.py --repo home-assistant/core

Idempotent and resumable: fetched bodies are cached to bodies_cache.json, and
records that already have a `body` are left alone.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

import httpx

GITHUB_REST = "https://api.github.com"
DISCUSSION_RE = re.compile(r"#discussion_r(\d+)\s*$")


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


def comment_id_of(record: dict) -> int | None:
    m = DISCUSSION_RE.search(record.get("url", "") or "")
    return int(m.group(1)) if m else None


async def fetch_pr_comment_bodies(
    client: httpx.AsyncClient, owner: str, repo: str, pr: int
) -> dict[int, str]:
    """Return {comment_id: body} for every review comment on one PR."""
    out: dict[int, str] = {}
    url = f"{GITHUB_REST}/repos/{owner}/{repo}/pulls/{pr}/comments"
    params: dict | None = {"per_page": 100}
    while url:
        for attempt in range(1, 6):
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                break
            if resp.status_code in (403, 429):
                reset = resp.headers.get("X-RateLimit-Reset")
                retry_after = resp.headers.get("Retry-After")
                if retry_after:
                    wait = int(retry_after) + 1
                elif reset:
                    wait = max(int(reset) - int(time.time()), 0) + 5
                else:
                    wait = 2 ** attempt
                _log(f"  [rate-limit] sleeping {wait}s")
                await asyncio.sleep(wait)
                continue
            if resp.status_code == 404:
                return out  # PR or comments gone
            if attempt == 5:
                resp.raise_for_status()
            await asyncio.sleep(2 ** attempt)

        for c in resp.json():
            cid = c.get("id")
            if cid is not None:
                out[int(cid)] = c.get("body", "") or ""

        nxt = None
        for part in resp.headers.get("Link", "").split(","):
            seg = [s.strip() for s in part.split(";")]
            if len(seg) == 2 and seg[1] == 'rel="next"':
                nxt = seg[0].strip("<>")
        url, params = nxt, None
    return out


async def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/name")
    ap.add_argument("--data-dir", default=None)
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("ERROR: set GITHUB_TOKEN")

    owner, name = args.repo.split("/", 1)
    data_dir = Path(args.data_dir) if args.data_dir else Path("data") / slug(args.repo)
    jsonl = data_dir / "comments.jsonl"
    if not jsonl.exists():
        sys.exit(f"ERROR: {jsonl} not found")

    records = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    _log(f"[load] {len(records)} records from {jsonl}")

    already = sum(1 for r in records if r.get("body"))
    if already:
        _log(f"[load] {already} already have a body; they will be left alone")

    cache_path = data_dir / "bodies_cache.json"
    cache: dict[str, str] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        _log(f"[cache] {len(cache)} bodies cached")

    need = [r for r in records if not r.get("body") and str(comment_id_of(r)) not in cache]
    prs = sorted({r["pr_number"] for r in need})
    _log(f"[plan] {len(need)} records need bodies across {len(prs)} PRs")

    if prs:
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "house-style-backfill/1.0",
        }
        async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
            for i, pr in enumerate(prs, 1):
                try:
                    bodies = await fetch_pr_comment_bodies(client, owner, name, pr)
                    for cid, body in bodies.items():
                        cache[str(cid)] = body
                except Exception as e:
                    _log(f"  [warn] PR #{pr} failed: {e}")
                if i % 25 == 0 or i == len(prs):
                    _log(f"  [fetch] {i}/{len(prs)} PRs  ({len(cache)} bodies cached)")
                    cache_path.write_text(json.dumps(cache), encoding="utf-8")
        cache_path.write_text(json.dumps(cache), encoding="utf-8")

    filled = missing = 0
    for r in records:
        if r.get("body"):
            continue
        cid = comment_id_of(r)
        body = cache.get(str(cid)) if cid is not None else None
        if body:
            r["body"] = body
            filled += 1
        else:
            r["body"] = r.get("body_excerpt", "")
            r["body_backfill_failed"] = True
            missing += 1

    tmp = jsonl.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(jsonl)

    lens = [len(r["body"]) for r in records if not r.get("body_backfill_failed")]
    med = sorted(lens)[len(lens) // 2] if lens else 0
    _log(f"[done] filled={filled}  already_had={already}  unrecoverable={missing}")
    _log(f"[done] median body length now {med} chars "
         f"(was ~90 for a 15-word excerpt)")
    if missing:
        _log(f"[done] {missing} records flagged body_backfill_failed — exclude them in batch.py")


if __name__ == "__main__":
    asyncio.run(main())