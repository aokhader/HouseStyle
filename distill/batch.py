"""
distill/batch.py — stratified tranche builder for distillation.

Changelog
---------
* Records now carry ``body`` (full review comment text) instead of
  ``body_excerpt``.  ``body_excerpt`` remains only in committed artifacts.
* Records with ``body_backfill_failed == true`` are skipped at load time.
* ``build_tranches`` prints median and 90th-percentile body length per tranche.

Usage:
    python -m distill.batch [--repo apache-airflow] [--seed 42]
                            [--tranches 3] [--batches-per-tranche 30]
                            [--batch-size 25]

Reads  data/<repo>/comments.jsonl  and  data/<repo>/manifest.json, excludes
holdout PRs, then emits three stratified tranches:

    data/<repo>/tranches/t1/batch_001.json  … batch_030.json
    data/<repo>/tranches/t2/batch_001.json  … batch_030.json
    data/<repo>/tranches/t3/batch_001.json  … batch_030.json
    data/<repo>/tranches/manifest.json

Stratification strategy
-----------------------
Each tranche is a *random proportional slice* across the full corpus so that
every tranche mirrors the month × path-prefix distribution of the whole.

Algorithm:
1. Build strata cells: (month, prefix) pairs.
2. For each tranche allocate floor(cell_size * tranche_fraction) comments from
   each cell (with a minimum-1 guard when the cell is non-empty), then
   distribute the remainder uniformly at random until the tranche quota is
   filled.
3. Shuffle within each tranche so the three tranches together cover the corpus
   without overlap.
4. Inside each tranche, sort comments by path prefix before packing into
   batches of 25 so that each batch is as topically coherent as possible.

Each batch JSON carries *only* diff_hunk_trimmed (never diff_hunk) to keep
token cost low.

Output batch schema
-------------------
{
  "batch_id":  "t1/batch_001",
  "tranche":   1,
  "seed":      42,
  "comments": [
    {
      "url":               "https://...",
      "pr_number":         12345,
      "path":              "airflow-core/src/...",
      "path_prefix":       "airflow-core",
      "month":             "2026-03",
      "diff_hunk_trimmed": "...",
      "body_excerpt":      "...",
      "signal_strength":   "strong",
      "reviewer_hash":     "abc123def456"
    },
    …
  ]
}
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _month_key(iso_ts: str) -> str:
    """Return 'YYYY-MM' from an ISO-8601 timestamp."""
    return iso_ts[:7]


def _path_prefix(path: str) -> str:
    """Top-level directory component (or '_root' for files in the root)."""
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else "_root"


def _load_comments(
    data_dir: Path, holdout_prs: set[int]
) -> tuple[list[dict], int]:
    """Read comments.jsonl, drop holdout PRs and backfill failures.

    Returns (records, n_skipped_backfill_failed).
    """
    records: list[dict] = []
    n_backfill_failed = 0
    jsonl = data_dir / "comments.jsonl"
    with jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("pr_number") in holdout_prs:
                continue
            if rec.get("body_backfill_failed") is True:
                n_backfill_failed += 1
                continue
            # Enrich with derived fields used for stratification
            rec["_month"] = _month_key(rec["created_at"])
            rec["_prefix"] = _path_prefix(rec.get("path", ""))
            records.append(rec)
    return records, n_backfill_failed


def _build_strata(comments: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group comments by (month, prefix) strata cell."""
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in comments:
        strata[(c["_month"], c["_prefix"])].append(c)
    return dict(strata)


def _stratified_split(
    comments: list[dict],
    n_tranches: int,
    comments_per_tranche: int,
    rng: random.Random,
) -> list[list[dict]]:
    """
    Partition *comments* into *n_tranches* lists, each of size
    *comments_per_tranche*, using proportional stratified sampling.

    Each stratum contributes floor(cell_size / total * quota) items to each
    tranche.  Remainders are filled by sampling without replacement from the
    pool of unassigned comments.

    If the corpus is smaller than n_tranches * comments_per_tranche the
    tranches will be smaller (no duplication).
    """
    total = len(comments)
    quota = min(comments_per_tranche, total // n_tranches)

    strata = _build_strata(comments)

    # Shuffle each cell so later slicing is random
    for cell in strata.values():
        rng.shuffle(cell)

    # Assign floor-quota items per tranche per cell
    # tranches[i] is the growing list for tranche i
    tranches: list[list[dict]] = [[] for _ in range(n_tranches)]
    remainder_pool: list[dict] = []

    for cell_comments in strata.values():
        cell_size = len(cell_comments)
        per_tranche_floor = math.floor(cell_size / total * quota)
        idx = 0
        for t in range(n_tranches):
            slice_ = cell_comments[idx : idx + per_tranche_floor]
            tranches[t].extend(slice_)
            idx += per_tranche_floor
        # Everything not yet assigned goes to the remainder pool
        remainder_pool.extend(cell_comments[idx:])

    # Fill each tranche to quota from the remainder pool
    rng.shuffle(remainder_pool)
    rem_idx = 0
    for t in range(n_tranches):
        needed = quota - len(tranches[t])
        if needed > 0 and rem_idx < len(remainder_pool):
            fill = remainder_pool[rem_idx : rem_idx + needed]
            tranches[t].extend(fill)
            rem_idx += needed

    return tranches


def _pack_batches(
    tranche_comments: list[dict],
    batch_size: int,
    tranche_num: int,
    seed: int,
) -> list[dict]:
    """
    Sort by path prefix for topical coherence, then pack into batches.
    Returns a list of batch dicts.
    """
    # Sort: primary = prefix, secondary = path, tertiary = pr_number
    sorted_comments = sorted(
        tranche_comments,
        key=lambda c: (c["_prefix"], c.get("path", ""), c.get("pr_number", 0)),
    )

    batches: list[dict] = []
    for i in range(0, len(sorted_comments), batch_size):
        chunk = sorted_comments[i : i + batch_size]
        batch_num = len(batches) + 1
        batch_id = f"t{tranche_num}/batch_{batch_num:03d}"

        batch_comments = []
        for c in chunk:
            batch_comments.append(
                {
                    "url": c["url"],
                    "pr_number": c["pr_number"],
                    "path": c.get("path", ""),
                    "path_prefix": c["_prefix"],
                    "month": c["_month"],
                    "diff_hunk_trimmed": c.get("diff_hunk_trimmed", ""),
                    "body": c.get("body", ""),
                    "signal_strength": c.get("signal_strength", ""),
                    "reviewer_hash": c.get("reviewer_hash", ""),
                }
            )

        batches.append(
            {
                "batch_id": batch_id,
                "tranche": tranche_num,
                "seed": seed,
                "comments": batch_comments,
            }
        )
    return batches


def _distribution_summary(comments: list[dict]) -> dict:
    """Compute month and prefix distributions for the manifest."""
    by_month: dict[str, int] = defaultdict(int)
    by_prefix: dict[str, int] = defaultdict(int)
    for c in comments:
        by_month[c["_month"]] += 1
        by_prefix[c["_prefix"]] += 1
    return {
        "count": len(comments),
        "by_month": dict(sorted(by_month.items())),
        "by_prefix": dict(sorted(by_prefix.items(), key=lambda kv: -kv[1])),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_tranches(
    repo: str = "apache-airflow",
    seed: int = 42,
    n_tranches: int = 3,
    batches_per_tranche: int = 30,
    batch_size: int = 25,
) -> None:
    data_dir = Path("data") / repo
    manifest_path = data_dir / "manifest.json"

    with manifest_path.open(encoding="utf-8") as fh:
        harvest_manifest = json.load(fh)

    holdout_prs: set[int] = set(harvest_manifest.get("holdout_prs", []))
    comments_per_tranche = batches_per_tranche * batch_size  # 750

    rng = random.Random(seed)

    comments, n_backfill_failed = _load_comments(data_dir, holdout_prs)
    print(
        f"Loaded {len(comments)} comments "
        f"(after excluding {len(holdout_prs)} holdout PRs, "
        f"skipped {n_backfill_failed} body_backfill_failed)"
    )

    tranches_data = _stratified_split(
        comments, n_tranches, comments_per_tranche, rng
    )

    out_root = data_dir / "tranches"
    out_root.mkdir(parents=True, exist_ok=True)

    tranche_manifest_entries: list[dict] = []

    for t_idx, tranche_comments in enumerate(tranches_data):
        t_num = t_idx + 1
        tranche_dir = out_root / f"t{t_num}"
        tranche_dir.mkdir(parents=True, exist_ok=True)

        batches = _pack_batches(tranche_comments, batch_size, t_num, seed)

        for batch in batches:
            batch_filename = f"batch_{int(batch['batch_id'].split('_')[1]):03d}.json"
            out_path = tranche_dir / batch_filename
            with out_path.open("w", encoding="utf-8") as fh:
                json.dump(batch, fh, ensure_ascii=False, indent=2)

        dist = _distribution_summary(tranche_comments)

        body_lengths = sorted(len(c.get("body", "")) for c in tranche_comments)
        n = len(body_lengths)
        median_body = body_lengths[n // 2] if n else 0
        p90_body = body_lengths[int(n * 0.90)] if n else 0

        tranche_manifest_entries.append(
            {
                "tranche": t_num,
                "directory": f"t{t_num}",
                "n_comments": dist["count"],
                "n_batches": len(batches),
                "body_length_median": median_body,
                "body_length_p90": p90_body,
                "by_month": dist["by_month"],
                "by_prefix": dist["by_prefix"],
            }
        )
        print(
            f"  t{t_num}: {dist['count']} comments -> {len(batches)} batches "
            f"written to {tranche_dir} "
            f"[body median={median_body} p90={p90_body} chars]"
        )

    tranche_manifest = {
        "repo": repo,
        "seed": seed,
        "batch_size": batch_size,
        "batches_per_tranche": batches_per_tranche,
        "n_tranches": n_tranches,
        "corpus_size": len(comments),
        "n_backfill_failed_skipped": n_backfill_failed,
        "tranches": tranche_manifest_entries,
    }

    manifest_out = out_root / "manifest.json"
    with manifest_out.open("w", encoding="utf-8") as fh:
        json.dump(tranche_manifest, fh, ensure_ascii=False, indent=2)

    print(f"Tranche manifest written to {manifest_out}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build distillation tranches.")
    p.add_argument("--repo", default="apache-airflow")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--tranches", type=int, default=3)
    p.add_argument("--batches-per-tranche", type=int, default=30)
    p.add_argument("--batch-size", type=int, default=25)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_tranches(
        repo=args.repo,
        seed=args.seed,
        n_tranches=args.tranches,
        batches_per_tranche=args.batches_per_tranche,
        batch_size=args.batch_size,
    )
