#!/usr/bin/env python3
"""
distill/fetch_docs.py — fetch a repository's hand-written agent rules and contributor
documentation, for the Phase 3 cross-check.

Phase 3 asks the question that makes the mined rulebook arguable: of the conventions
review history proves the project enforces, how many are written down anywhere? And in
reverse — of the rules the project *did* write down by hand, how many does review
history actually support?

The Phase 3 prompt says to clone the repo into a separate workspace and add ``AGENTS.md``
to ``.bobignore`` there first, so the agent cannot edit the artifact it is meant to
evaluate. We fetch read-only copies into gitignored ``data/`` instead: same protection,
without a multi-gigabyte clone. Nothing here ever writes to the source repository.

Runs unauthenticated — ``raw.githubusercontent.com`` needs no token, and listing a
directory costs one API call against the 60/hour anonymous budget.

Output (gitignored):
    data/<slug>/docs/AGENTS.md
    data/<slug>/docs/contributing-docs/*.rst|md
    data/<slug>/docs/index.json

Usage:
    python -m distill.fetch_docs --repo apache/airflow
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

RAW = "https://raw.githubusercontent.com"
API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "house-style-docs/1.0"}

# Files worth reading for conventions, beyond the directory listings below.
ROOT_FILES = ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.rst", "CONTRIBUTING.md"]

DEFAULT_DIRS = ["contributing-docs"]


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def slug(repo: str) -> str:
    return repo.replace("/", "-")


def fetch_raw(client: httpx.Client, repo: str, ref: str, path: str) -> str | None:
    r = client.get(f"{RAW}/{repo}/{ref}/{path}", follow_redirects=True, timeout=60)
    return r.text if r.status_code == 200 else None


def list_dir(client: httpx.Client, repo: str, ref: str, path: str) -> list[dict]:
    r = client.get(f"{API}/repos/{repo}/contents/{path}", params={"ref": ref},
                   headers=HEADERS, timeout=60)
    if r.status_code != 200:
        _log(f"  listing {path} -> {r.status_code}")
        return []
    return [e for e in r.json() if e.get("type") == "file"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch hand-written project docs.")
    ap.add_argument("--repo", default="apache/airflow")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--dirs", nargs="*", default=DEFAULT_DIRS)
    ap.add_argument("--max-bytes", type=int, default=400_000,
                    help="skip any single document larger than this")
    args = ap.parse_args()

    out_dir = Path("data") / slug(args.repo) / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []

    with httpx.Client() as client:
        for name in ROOT_FILES:
            text = fetch_raw(client, args.repo, args.ref, name)
            if text is None:
                continue
            (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
            index.append({"path": name, "bytes": len(text), "lines": text.count("\n") + 1})
            _log(f"{name}: {len(text)} bytes")

        for d in args.dirs:
            entries = list_dir(client, args.repo, args.ref, d)
            _log(f"{d}/: {len(entries)} files")
            sub = out_dir / d
            sub.mkdir(parents=True, exist_ok=True)
            for e in entries:
                if e.get("size", 0) > args.max_bytes:
                    _log(f"  skip {e['name']} ({e['size']} bytes)")
                    continue
                if not e["name"].lower().endswith((".md", ".rst", ".txt")):
                    continue
                text = fetch_raw(client, args.repo, args.ref, f"{d}/{e['name']}")
                if text is None:
                    continue
                (sub / e["name"]).write_text(text, encoding="utf-8", newline="\n")
                index.append({"path": f"{d}/{e['name']}", "bytes": len(text),
                              "lines": text.count("\n") + 1})

    (out_dir / "index.json").write_text(
        json.dumps({"repo": args.repo, "ref": args.ref, "n_documents": len(index),
                    "total_bytes": sum(i["bytes"] for i in index), "documents": index},
                   indent=2) + "\n",
        encoding="utf-8", newline="\n")
    _log(f"\n{len(index)} documents, "
         f"{sum(i['bytes'] for i in index) / 1024:.0f} KB -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
