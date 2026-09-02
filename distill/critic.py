"""
distill/critic.py — the deterministic half of the Phase 2 reduce step.

The critic is a hybrid on purpose.  Deciding that two candidate rules express the
*same* expectation is a judgement call and is done by an LLM (a critic subagent,
see ``distill/prompts/critic_chunk.md``).  Everything downstream of that judgement
— counting support, generalising scope paths, applying the promotion threshold,
assigning ids — is arithmetic, and arithmetic done by a language model is a number
nobody can check.  So the subagent only ever emits *clusters of candidate keys*;
this module computes every number that ends up in the rulebook.

Pipeline
--------
    prep     candidates/   -> a compact chunk file for one critic subagent
    reduce   cluster files -> .bob/rules/<slug>-conventions.{md,json} + saturation
    verify   candidates/   -> evidence-URL resolution report

Candidate keys
--------------
Every candidate has a stable key ``<tranche>/<batch>#<index>`` (e.g.
``t1/batch_007#3``).  Subagents cluster by key, never by restating the rule, so a
cluster cannot silently invent or lose a candidate.

Usage
-----
    python -m distill.critic verify  --candidates distill/candidates --repo apache-airflow
    python -m distill.critic prep    --candidates distill/candidates/t1 \
                                     --batches 1-10 --out distill/critic/t1/chunk_A.json
    python -m distill.critic reduce  --repo apache-airflow --slug airflow \
                                     --candidates distill/candidates/t1 \
                                     --clusters distill/critic/t1/clusters_merged.json \
                                     --tranche 1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_EXCERPT_WORDS = 15
SUPPORT_THRESHOLD = 3

CATEGORIES = [
    "correctness", "api-design", "async", "testing", "naming", "database",
    "security", "performance", "providers", "docs", "commit-hygiene",
]


# --------------------------------------------------------------------------- io

def read_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str | Path, obj: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_text(path: str | Path, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------------- corpus

def repo_name(repo_slug: str) -> str:
    """Real ``owner/name`` for a slug, from the harvest manifest.

    Never reconstruct this by replacing a hyphen: ``home-assistant-core`` would become
    ``home/assistant-core``. The manifest recorded the true name at harvest time.
    """
    if "/" in repo_slug:
        return repo_slug
    manifest = Path("data") / repo_slug / "manifest.json"
    if manifest.exists():
        return read_json(manifest).get("repo", repo_slug)
    return repo_slug


def load_corpus(repo_slug: str) -> dict[str, dict]:
    """url -> harvested comment record.

    The corpus is the only source of truth for a comment's path, PR, reviewer and
    signal strength.  Anything a subagent asserted about a comment is re-derived
    from here rather than trusted.
    """
    path = Path("data") / repo_slug / "comments.jsonl"
    idx: dict[str, dict] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                idx[rec["url"]] = rec
    return idx


def load_candidates(roots: str | Path | list[str | Path]) -> dict[str, dict]:
    """Load candidates from one or more roots, keyed by ``<tranche>/<batch>#<i>``.

    Keys are scoped by the batch's parent directory name only, so two roots holding
    directories of the same name (``candidates/t1`` for Airflow and
    ``candidates/home-assistant-core/t1`` for Home Assistant) would silently overwrite
    each other. Pass tranche directories explicitly, and a collision is reported loudly
    rather than quietly dropping half a corpus.
    """
    if isinstance(roots, (str, Path)):
        roots = [roots]
    out: dict[str, dict] = {}
    collisions: list[str] = []
    for root in roots:
        for path in sorted(Path(root).rglob("batch_*.json")):
            stem = f"{path.parent.name}/{path.stem}"
            try:
                arr = read_json(path)
            except json.JSONDecodeError as exc:  # a malformed batch must be loud
                print(f"MALFORMED {path}: {exc}", file=sys.stderr)
                continue
            for i, cand in enumerate(arr):
                key = f"{stem}#{i}"
                if key in out:
                    collisions.append(f"{key} ({path})")
                    continue
                cand["_key"] = key
                cand["_batch"] = stem
                out[key] = cand
    if collisions:
        raise SystemExit(
            f"candidate key collision across roots ({len(collisions)}); "
            f"pass tranche directories explicitly. First: {collisions[:3]}"
        )
    return out


# -------------------------------------------------------------------- excerpts

def clip_excerpt(text: str, max_words: int = MAX_EXCERPT_WORDS) -> str:
    """Committed artifacts carry at most 15 words of any review comment."""
    words = (text or "").split()
    clipped = " ".join(words[:max_words])
    return clipped + ("…" if len(words) > max_words else "")


# --------------------------------------------------------- scope generalisation

def _dir_components(path: str) -> list[str]:
    """Directory components of a file path, dropping the filename."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    return parts[:-1] if parts else []


def generalise_scope(paths: list[str]) -> list[str]:
    """Shallowest DIRECTORY prefix that still covers every evidence path.

    Amendment 1 of the Phase 2b critic spec: a scope pointing at one file almost
    never intersects a future diff, so the rule would never fire.  Evidence paths
    are grouped by top-level component first — a rule evidenced in both
    ``airflow-core/`` and ``providers/`` gets two scopes rather than one useless
    ``/`` that would match the entire repository.
    """
    groups: dict[str, list[list[str]]] = defaultdict(list)
    for p in paths:
        comps = _dir_components(p)
        if not comps:
            groups["_root"].append([])
        else:
            groups[comps[0]].append(comps)

    scopes: list[str] = []
    for top, members in sorted(groups.items()):
        if top == "_root":
            scopes.append("./")
            continue
        common = members[0]
        for comps in members[1:]:
            n = 0
            while n < min(len(common), len(comps)) and common[n] == comps[n]:
                n += 1
            common = common[:n]
        if not common:
            common = [top]
        scopes.append("/".join(common) + "/")
    return scopes


# ------------------------------------------------------------------ stable ids

def rule_key(rule_text: str) -> str:
    """Normalised key that keeps an id attached to a rule across re-runs."""
    return re.sub(r"[^a-z0-9]+", " ", (rule_text or "").lower()).strip()


def assign_ids(rules: list[dict], slug: str, id_map: dict[str, str]) -> dict[str, str]:
    """Assign ``<slug>-rNNN``, reusing the id a rule already had.

    Ids appear in review findings and in the eval, so they must survive a re-run
    that adds a tranche.  The map is persisted next to the rulebook.
    """
    used = {int(m.group(1)) for v in id_map.values() if (m := re.search(r"r(\d+)$", v))}
    nxt = max(used) + 1 if used else 1
    for rule in sorted(rules, key=lambda r: (r["category"], rule_key(r["rule"]))):
        key = rule_key(rule["rule"])
        if key not in id_map:
            id_map[key] = f"{slug}-r{nxt:03d}"
            nxt += 1
        rule["id"] = id_map[key]
    return id_map


# ------------------------------------------------------------------- contested

_STOP = set("the a an is are be to of in on for and or with that this it not must "
            "should when if from as by at into via use using do does".split())


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z_][a-z0-9_]{2,}", (text or "").lower())
            if w not in _STOP}


def _scopes_intersect(a: list[str], b: list[str]) -> bool:
    return any(x.startswith(y) or y.startswith(x) for x in a for y in b)


def find_contested(rules: list[dict], threshold: float = 0.45) -> list[dict]:
    """Overlapping-trigger pairs, flagged rather than silently resolved."""
    out = []
    for i, a in enumerate(rules):
        for b in rules[i + 1:]:
            if a["category"] != b["category"]:
                continue
            if not _scopes_intersect(a["scope_paths"], b["scope_paths"]):
                continue
            ta = _tokens(a["trigger"] + " " + a["rule"])
            tb = _tokens(b["trigger"] + " " + b["rule"])
            if not ta or not tb:
                continue
            jac = len(ta & tb) / len(ta | tb)
            if jac >= threshold:
                out.append({"a": a["id"], "b": b["id"], "overlap": round(jac, 3),
                            "category": a["category"]})
    return out


# ---------------------------------------------------------------------- verify

def cmd_verify(args: argparse.Namespace) -> int:
    corpus = load_corpus(args.repo)
    cands = load_candidates(args.candidates)
    total = resolved = mismatch = 0
    unresolved: list[tuple[str, str]] = []
    for key, cand in cands.items():
        for ev in cand.get("evidence", []):
            total += 1
            rec = corpus.get(ev.get("url", ""))
            if rec is None:
                unresolved.append((key, ev.get("url", "")))
            else:
                resolved += 1
                if rec["pr_number"] != ev.get("pr"):
                    mismatch += 1
    pct = f"{resolved / total:.1%}" if total else "n/a"
    print(f"candidates      : {len(cands)}")
    print(f"evidence entries: {total}")
    print(f"resolved        : {resolved} ({pct})")
    print(f"unresolved      : {len(unresolved)}")
    print(f"pr mismatch     : {mismatch}")
    for key, url in unresolved[: args.show]:
        print(f"  MISS {key}  {url}")
    return 0


# ------------------------------------------------------------------------ prep

def _parse_range(spec: str) -> set[int]:
    out: set[int] = set()
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            out |= set(range(int(lo), int(hi) + 1))
        else:
            out.add(int(part))
    return out


def cmd_prep(args: argparse.Namespace) -> int:
    """Emit the compact view one critic subagent sees.

    Rationale prose and full evidence lists are dropped here: the subagent's only
    job is to say which candidates express the same expectation, and reduce
    re-attaches the real evidence from the corpus afterwards.
    """
    corpus = load_corpus(args.repo)
    cands = load_candidates(args.candidates)
    wanted = _parse_range(args.batches) if args.batches else None

    rows = []
    for key in sorted(cands):
        cand = cands[key]
        match = re.search(r"batch_(\d+)", cand["_batch"])
        num = int(match.group(1)) if match else -1
        if wanted is not None and num not in wanted:
            continue
        paths = [corpus[e["url"]]["path"] for e in cand.get("evidence", [])
                 if e.get("url") in corpus]
        rows.append({
            "key": key,
            "rule": cand.get("rule", ""),
            "category": cand.get("category", ""),
            "trigger": cand.get("trigger", ""),
            "evidence_prs": sorted({e["pr"] for e in cand.get("evidence", []) if e.get("pr")}),
            "evidence_paths": sorted(set(paths)),
        })

    write_json(args.out, {
        "chunk": Path(args.out).stem,
        "source": str(args.candidates),
        "batches": args.batches or "all",
        "n_candidates": len(rows),
        "candidates": rows,
    })
    print(f"{args.out}: {len(rows)} candidates from batches {args.batches or 'all'}")
    return 0


# ----------------------------------------------------------------- merge stage

def _cluster_id(chunk: str, i: int) -> str:
    return f"{chunk}:{i}"


def load_chunk_clusters(paths: list[str]) -> dict[str, dict]:
    """cluster id -> cluster, across the per-chunk critic outputs.

    The id carries the tranche directory as well as the chunk letter (``t1/A:0``, not
    ``A:0``). A cross-tranche merge reads ``t1/clusters_A.json`` and
    ``t2/clusters_A.json`` together, and keying by letter alone silently overwrote one
    tranche with the other — 874 clusters collapsing to 457 with no error raised.
    """
    out: dict[str, dict] = {}
    collisions: list[str] = []
    for path in paths:
        blob = read_json(path)
        clusters = blob["clusters"] if isinstance(blob, dict) else blob
        p = Path(path)
        # "t1" + "A" from t1/clusters_A.json -> "t1/A"
        chunk = f"{p.parent.name}/{p.stem.replace('clusters_', '')}"
        for i, cl in enumerate(clusters):
            cid = _cluster_id(chunk, i)
            if cid in out:
                collisions.append(cid)
                continue
            out[cid] = cl
    if collisions:
        raise SystemExit(f"cluster id collision ({len(collisions)}): {collisions[:5]}")
    return out


def cmd_merge_prep(args: argparse.Namespace) -> int:
    """Compact view for critic-MERGE.

    The merge sees only cluster summaries, never the raw candidates — the chunk critics
    already did that reading. Its single job is to spot the same convention arriving
    from different chunks or tranches.
    """
    clusters = load_chunk_clusters(args.clusters)
    rows = [
        {
            "cluster_id": cid,
            "rule": cl.get("rule", ""),
            "category": cl.get("category", ""),
            "trigger": cl.get("trigger", ""),
            "kind": cl.get("kind", "convention"),
            "n_candidates": len(cl.get("members", [])),
        }
        for cid, cl in clusters.items()
    ]
    if args.categories:
        # A cross-tranche merge spans ~830 clusters, more than one agent can hold in
        # mind at once. Merges essentially never cross a category boundary, so the merge
        # partitions cleanly by category — each agent sees a coherent slice and the
        # union of slices still covers every cluster. merge-expand accepts several
        # merged files and derives singletons for anything nobody claimed.
        wanted = set(args.categories)
        rows = [r for r in rows if r["category"] in wanted]
    write_json(args.out, {"n_clusters": len(rows), "clusters": rows})
    kinds = Counter(r["kind"] for r in rows)
    print(f"{args.out}: {len(rows)} clusters from {len(args.clusters)} chunks "
          f"({dict(kinds)})")
    return 0


def cmd_merge_expand(args: argparse.Namespace) -> int:
    """Expand critic-MERGE's output back to candidate keys.

    The merge agent emits ONLY the groups that actually merge (two or more clusters).
    Every cluster it does not mention becomes a singleton here, in code. That inversion
    matters: asking an agent to restate all ~450 clusters produces an enormous output it
    can fail partway through, and a truncated restatement silently drops rules. Emitting
    ~50 merges and deriving the rest makes loss structurally impossible.
    """
    chunk_clusters = load_chunk_clusters(args.clusters)
    blob = read_json(args.merged)
    merges = blob.get("merges", blob.get("clusters", [])) if isinstance(blob, dict) else blob
    demote = set(blob.get("demote", [])) if isinstance(blob, dict) else set()

    used: Counter = Counter()
    unknown: list[str] = []
    out: list[dict] = []

    for group in merges:
        members: list[str] = []
        ids = group.get("cluster_ids", [])
        for cid in ids:
            used[cid] += 1
            cl = chunk_clusters.get(cid)
            if cl is None:
                unknown.append(cid)
                continue
            members.extend(cl.get("members", []))
        if not members:
            continue
        # A group containing any incident is an incident: never let a one-off defect
        # merge into a convention and inflate its support.
        kind = group.get("kind", "convention")
        if any(chunk_clusters[c].get("kind") == "incident"
               for c in ids if c in chunk_clusters):
            kind = "incident"
        out.append({
            "rule": group["rule"],
            "category": group.get("category", "correctness"),
            "trigger": group.get("trigger", ""),
            "rationale": group.get("rationale", ""),
            "kind": kind,
            "cluster_ids": ids,
            "members": sorted(set(members)),
        })

    singletons = 0
    for cid, cl in chunk_clusters.items():
        if used[cid]:
            continue
        singletons += 1
        out.append({
            "rule": cl.get("rule", ""),
            "category": cl.get("category", "correctness"),
            "trigger": cl.get("trigger", ""),
            "rationale": cl.get("rationale", ""),
            "kind": "incident" if cid in demote else cl.get("kind", "convention"),
            "cluster_ids": [cid],
            "members": sorted(set(cl.get("members", []))),
        })

    dupes = [c for c, n in used.items() if n > 1]
    covered = sorted({m for c in out for m in c["members"]})

    write_json(args.out, {
        "n_chunk_clusters": len(chunk_clusters),
        "n_merge_groups": len(merges),
        "n_singletons": singletons,
        "n_clusters_out": len(out),
        "n_candidates_covered": len(covered),
        "duplicate_cluster_ids": dupes,
        "unknown_cluster_ids": unknown,
        "demoted": sorted(demote),
        "clusters": out,
    })
    print(f"{args.out}: {len(chunk_clusters)} chunk clusters "
          f"-> {len(merges)} merge groups + {singletons} singletons = {len(out)}")
    print(f"  candidates covered: {len(covered)}")
    if dupes:
        print(f"  ERROR {len(dupes)} cluster ids used in more than one merge: "
              f"{dupes[:10]}", file=sys.stderr)
    if unknown:
        print(f"  ERROR {len(unknown)} unknown cluster ids: {unknown[:10]}",
              file=sys.stderr)
    return 1 if (dupes or unknown) else 0


# ---------------------------------------------------------------------- reduce

def _build_rule(cluster: dict, cands: dict[str, dict], corpus: dict[str, dict],
                stats: Counter) -> dict | None:
    """Turn one cluster of candidate keys into a rule with computed support."""
    evidence: dict[str, dict] = {}
    prs: set[int] = set()
    reviewers: set[str] = set()
    paths: list[str] = []
    strengths: Counter = Counter()

    for key in cluster.get("members", []):
        cand = cands.get(key)
        if cand is None:
            stats["unknown_member_keys"] += 1
            continue
        for ev in cand.get("evidence", []):
            rec = corpus.get(ev.get("url", ""))
            if rec is None:            # unverifiable precedent is not precedent
                stats["evidence_dropped_unresolvable"] += 1
                continue
            evidence[rec["url"]] = {
                "pr": rec["pr_number"],
                "url": rec["url"],
                "path": rec["path"],
                "excerpt": clip_excerpt(rec["body"]),
                "signal_strength": rec.get("signal_strength", "weak"),
            }
            prs.add(rec["pr_number"])
            reviewers.add(rec.get("reviewer_hash", ""))
            paths.append(rec["path"])
            strengths[rec.get("signal_strength", "weak")] += 1

    if not evidence:
        stats["clusters_without_evidence"] += 1
        return None

    return {
        "rule": cluster["rule"].strip(),
        "category": cluster.get("category", "correctness"),
        "trigger": (cluster.get("trigger") or "").strip(),
        "rationale": (cluster.get("rationale") or "").strip(),
        "scope_paths": generalise_scope(paths),
        "support_count": len(prs),
        "distinct_reviewers": len({r for r in reviewers if r}),
        "signal": dict(strengths),
        "evidence": sorted(evidence.values(), key=lambda e: -e["pr"]),
        "member_candidates": sorted(cluster.get("members", [])),
        "kind": cluster.get("kind", "convention"),
    }


def cmd_reduce(args: argparse.Namespace) -> int:
    corpus = load_corpus(args.repo)
    cands = load_candidates(args.candidates)

    clusters: list[dict] = []
    for cpath in args.clusters:
        blob = read_json(cpath)
        clusters.extend(blob["clusters"] if isinstance(blob, dict) else blob)

    stats: Counter = Counter()
    seen_keys: set[str] = set()
    built: list[dict] = []
    incidents: list[dict] = []

    for cluster in clusters:
        for key in cluster.get("members", []):
            if key in seen_keys:
                stats["duplicate_memberships"] += 1
            seen_keys.add(key)
        rule = _build_rule(cluster, cands, corpus, stats)
        if rule is None:
            continue
        (incidents if rule["kind"] == "incident" else built).append(rule)

    orphans = sorted(set(cands) - seen_keys)

    promoted = [r for r in built if r["support_count"] >= SUPPORT_THRESHOLD]
    weak = [r for r in built if r["support_count"] < SUPPORT_THRESHOLD]

    id_map_path = Path(args.rules_dir) / f"{args.slug}-ids.json"
    id_map = read_json(id_map_path) if id_map_path.exists() else {}
    for group in (promoted, weak, incidents):
        assign_ids(group, args.slug, id_map)
    write_json(id_map_path, id_map)

    promoted.sort(key=lambda r: (-r["support_count"], r["category"], r["id"]))
    weak.sort(key=lambda r: (-r["support_count"], r["category"], r["id"]))
    incidents.sort(key=lambda r: (r["category"], r["id"]))

    contested = find_contested(promoted)

    # ---- saturation -------------------------------------------------------
    # Per slug: two repos both start at tranche 1, and a shared file would have the
    # second reduce silently overwrite the first repo's curve.
    sat_path = Path(args.rules_dir) / f"{args.slug}-saturation.json"
    sat = read_json(sat_path) if sat_path.exists() else []
    prior = [s for s in sat if s["tranche"] < args.tranche]
    before = prior[-1]["rules_after"] if prior else 0
    after = len(promoted)
    sat = [s for s in sat if s["tranche"] != args.tranche]
    sat.append({
        "tranche": args.tranche,
        "batches": args.batches_count,
        "comments_seen": args.comments_seen,
        "candidates_in": len(cands),
        "clusters": len(clusters),
        "rules_before": before,
        "rules_after": after,
        "new_rules": after - before,
        "new_rule_rate": round((after - before) / after, 4) if after else 0.0,
    })
    sat.sort(key=lambda s: s["tranche"])
    write_json(sat_path, sat)

    # ---- emit -------------------------------------------------------------
    payload = {
        "repo": repo_name(args.repo),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "support_threshold": SUPPORT_THRESHOLD,
        "support_definition": "number of distinct PRs in the merged evidence",
        "counts": {
            "candidates_in": len(cands),
            "clusters_in": len(clusters),
            "rules_promoted": len(promoted),
            "rules_candidate": len(weak),
            "incidents": len(incidents),
            "orphan_candidates": len(orphans),
            "duplicate_memberships": stats["duplicate_memberships"],
            "unknown_member_keys": stats["unknown_member_keys"],
            "evidence_dropped_unresolvable": stats["evidence_dropped_unresolvable"],
            "clusters_without_evidence": stats["clusters_without_evidence"],
        },
        "contested": contested,
        "rules": promoted,
        "candidates": weak,
        "incidents": incidents,
    }
    write_json(Path(args.rules_dir) / f"{args.slug}-conventions.json", payload)
    write_text(Path(args.rules_dir) / f"{args.slug}-conventions.md", render_markdown(payload))
    write_text(Path(args.rules_dir) / f"{args.slug}-candidates.md", render_candidates(payload))

    print(json.dumps(payload["counts"], indent=2))
    print("contested pairs:", len(contested))
    print("saturation:", json.dumps(sat[-1]))
    if orphans:
        print(f"WARNING {len(orphans)} candidates were in no cluster; "
              f"first 10: {orphans[:10]}", file=sys.stderr)
    return 0


# -------------------------------------------------------------------- markdown

def render_markdown(payload: dict) -> str:
    counts = payload["counts"]
    lines = [
        f"# {payload['repo']} — mined review conventions",
        "",
        f"Generated {payload['generated_at']} by `distill/critic.py` from "
        f"{counts['candidates_in']} candidate rules that map subagents extracted from "
        "merged-PR review comments.",
        "",
        "**Support** is the number of distinct PRs in a rule's merged evidence. A pattern "
        f"is promoted to a rule at support >= {payload['support_threshold']}; everything "
        "below that stays a candidate, in the companion candidates file.",
        "",
        "Review comments are never reproduced here. Each evidence line carries a permalink "
        "and an excerpt of at most 15 words.",
        "",
        "| | |",
        "|---|---|",
        f"| rules promoted | {counts['rules_promoted']} |",
        f"| candidates (support below threshold) | {counts['rules_candidate']} |",
        f"| incidents (one-off fixes, not conventions) | {counts['incidents']} |",
        f"| contested pairs | {len(payload['contested'])} |",
        "",
        "To disagree with a rule, delete its section and commit. This file is the "
        "rulebook, not a cache.",
        "",
    ]
    if payload["contested"]:
        lines += [
            "## Contested",
            "",
            "Rule pairs with overlapping triggers in the same scope. Flagged, never "
            "silently merged — a human decides which one the repo actually means.",
            "",
        ]
        for c in payload["contested"]:
            lines.append(f"- `{c['a']}` vs `{c['b']}` — trigger overlap "
                         f"{c['overlap']} ({c['category']})")
        lines.append("")

    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in payload["rules"]:
        by_cat[r["category"]].append(r)

    ordered = [c for c in CATEGORIES if c in by_cat] + sorted(set(by_cat) - set(CATEGORIES))
    for cat in ordered:
        lines += [f"## {cat}", ""]
        for r in by_cat[cat]:
            lines += _render_rule(r)
    return "\n".join(lines).rstrip() + "\n"


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _render_rule(r: dict) -> list[str]:
    scopes = " ".join(f"`{s}`" for s in r["scope_paths"])
    shown = r["evidence"][:8]
    prs = ", ".join(f"[#{e['pr']}]({e['url']})" for e in shown)
    more = "" if len(r["evidence"]) <= 8 else f" (+{len(r['evidence']) - 8} more)"
    out = [
        f"### `{r['id']}` — {r['rule']}",
        "",
        f"- **Trigger** — {r['trigger']}",
        f"- **Why** — {r['rationale']}",
        f"- **Scope** — {scopes}",
        f"- **Support** — {_plural(r['support_count'], 'distinct PR')}, "
        f"{_plural(r['distinct_reviewers'], 'distinct reviewer')}",
        "",
        "<details><summary>Evidence</summary>",
        "",
    ]
    for e in r["evidence"]:
        out.append(f"- PR [#{e['pr']}]({e['url']}) — `{e['path']}` — {e['excerpt']}")
    out += ["", "</details>", "", f"Precedent: {prs}{more}", ""]
    return out


def render_candidates(payload: dict) -> str:
    lines = [
        f"# {payload['repo']} — candidates and incidents",
        "",
        "Patterns that did not clear the support threshold, plus one-off corrections "
        "deliberately kept out of the promoted set.",
        "",
        f"## Candidates (support below {payload['support_threshold']})",
        "",
    ]
    for r in payload["candidates"]:
        refs = ", ".join("#%d" % pr for pr in
                         sorted({e["pr"] for e in r["evidence"]}, reverse=True)[:5])
        lines.append(f"- `{r['id']}` **[{r['category']}]** {r['rule']} — "
                     f"support {r['support_count']} ({refs})")
    lines += [
        "",
        "## Incidents",
        "",
        "A one-time correction with no generalisable expectation. Recorded so its "
        "evidence never inflates a real rule's support count.",
        "",
    ]
    for r in payload["incidents"]:
        refs = ", ".join("#%d" % pr for pr in
                         sorted({e["pr"] for e in r["evidence"]}, reverse=True)[:5])
        lines.append(f"- `{r['id']}` **[{r['category']}]** {r['rule']} ({refs})")
    return "\n".join(lines).rstrip() + "\n"


# -------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="distill.critic")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="check every evidence URL resolves in the corpus")
    v.add_argument("--repo", default="apache-airflow")
    v.add_argument("--candidates", nargs="+", default=["distill/candidates"])
    v.add_argument("--show", type=int, default=10)
    v.set_defaults(func=cmd_verify)

    pr = sub.add_parser("prep", help="build one critic chunk input")
    pr.add_argument("--repo", default="apache-airflow")
    pr.add_argument("--candidates", nargs="+", required=True)
    pr.add_argument("--batches", default="")
    pr.add_argument("--out", required=True)
    pr.set_defaults(func=cmd_prep)

    mp = sub.add_parser("merge-prep", help="compact cluster summaries for critic-MERGE")
    mp.add_argument("--clusters", nargs="+", required=True)
    mp.add_argument("--out", required=True)
    mp.add_argument("--categories", nargs="*", default=None,
                    help="restrict to these categories (partitions a large merge)")
    mp.set_defaults(func=cmd_merge_prep)

    me = sub.add_parser("merge-expand",
                        help="expand merged cluster-ids back to candidate keys")
    me.add_argument("--clusters", nargs="+", required=True,
                    help="the per-chunk clusters_*.json files")
    me.add_argument("--merged", required=True, help="critic-MERGE output")
    me.add_argument("--out", required=True)
    me.set_defaults(func=cmd_merge_expand)

    rd = sub.add_parser("reduce", help="merge clusters into the rulebook")
    rd.add_argument("--repo", default="apache-airflow")
    rd.add_argument("--slug", default="airflow")
    rd.add_argument("--candidates", nargs="+", required=True)
    rd.add_argument("--clusters", nargs="+", required=True)
    rd.add_argument("--rules-dir", default=".bob/rules")
    rd.add_argument("--tranche", type=int, required=True)
    rd.add_argument("--batches-count", type=int, default=30)
    rd.add_argument("--comments-seen", type=int, default=0)
    rd.set_defaults(func=cmd_reduce)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
