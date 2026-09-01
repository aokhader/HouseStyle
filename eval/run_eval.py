#!/usr/bin/env python3
"""
eval/run_eval.py — score three review conditions against real human review comments
on the 30 held-out PRs.

    A_baseline    stock review, no mined rules
    B_housestyle  /house-style with the repo's own mined rules
    C_generic     another repo's mined rules applied to these PRs

C is the ablation that carries the argument. Airflow and Home Assistant are both large
async Python infrastructure projects, so if C scored near B, House Style would only be
detecting generic Python smells and the "repo-specific" claim would be empty.

Ground truth is the real review comments on each held-out PR, which never entered the
mining corpus. A finding matches a comment when it is in the same file, within
``--line-window`` lines, and judged semantically equivalent (see ``eval/judge.py``).

    prepare   build per-condition review inputs from the held-out PRs
    score     match findings to ground truth and write results.{md,json}

Usage:
    python -m eval.run_eval prepare --condition B
    python -m eval.run_eval score --judge agent
    python -m eval.run_eval score --judge watsonx --lenient
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from eval.judge import Judge, ingest_verdicts

HOLDOUT_DIR = "data/{slug}/holdout"
INPUT_DIR = Path("eval/inputs")
FINDINGS_DIR = Path("eval/findings")
SKILL = ".bob/skills/house-style/scripts/house_style.py"

CONDITIONS = {
    "A_baseline": {"rules": None, "ignore_scope": False,
                   "label": "stock review, no mined rules"},
    "B_housestyle": {"rules": ".bob/rules/airflow-conventions.json",
                     "ignore_scope": False,
                     "label": "House Style, Airflow rules"},
    # The cross-repo ablation runs UNSCOPED on purpose. Home Assistant's scope paths
    # (homeassistant/components/...) cannot intersect Airflow's tree, so with the scope
    # filter on, all 27 rules are rejected before their content is ever tested and C
    # scores zero for a trivial reason. That path-level result is real and is reported
    # separately; this condition asks the sharper question — offered every Home Assistant
    # convention against Airflow diffs, how many actually fire correctly?
    "C_generic": {"rules": ".bob/rules/hass-conventions.json",
                  "ignore_scope": True,
                  "label": "House Style, Home Assistant rules on Airflow PRs (unscoped)"},
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def slug(repo: str) -> str:
    return repo.replace("/", "-")


def read_json(path: str | Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def holdout_prs(repo: str) -> list[Path]:
    d = Path(HOLDOUT_DIR.format(slug=slug(repo)))
    return sorted(d.glob("pr_*.json"), key=lambda p: int(p.stem.split("_")[1]))


# ---------------------------------------------------------------------- prepare

def cmd_prepare(args: argparse.Namespace) -> int:
    """Build the review input each condition's reviewer agent will read.

    B and C go through the Skill's own ``select`` so the eval measures exactly what
    the Skill does — same scope filter, same rule payload. A gets the diff alone.
    """
    prs = holdout_prs(args.repo)
    if not prs:
        _log(f"no held-out PRs on disk. Run: python -m eval.fetch_holdout --repo {args.repo}")
        return 2

    cond = args.condition
    spec = CONDITIONS[cond]
    out_dir = INPUT_DIR / cond
    out_dir.mkdir(parents=True, exist_ok=True)

    prepared = 0
    for p in prs:
        rec = read_json(p)
        dest = out_dir / p.name
        if spec["rules"] is None:
            write_json(dest, {
                "pr": rec["number"],
                "title": rec["title"],
                "condition": cond,
                "files": [{"path": f["path"], "patch": f["patch"]}
                          for f in rec["files"] if f["patch"]],
            })
        else:
            if not Path(spec["rules"]).exists():
                _log(f"rules file missing: {spec['rules']}")
                return 2
            cmd = [sys.executable, SKILL, "--rules", spec["rules"],
                   "select", "--patch-file", str(p), "--out", str(dest)]
            if spec.get("ignore_scope"):
                cmd.append("--ignore-scope")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            blob = read_json(dest)
            blob.update({"pr": rec["number"], "title": rec["title"], "condition": cond})
            write_json(dest, blob)
        prepared += 1

    _log(f"{cond}: prepared {prepared} review inputs in {out_dir}")
    if spec["rules"]:
        counts = [read_json(out_dir / p.name)["rules_applicable"] for p in prs]
        _log(f"  applicable rules per PR: min {min(counts)} median "
             f"{sorted(counts)[len(counts) // 2]} max {max(counts)}")
    return 0


# ------------------------------------------------------------------------- plan

def cmd_plan(args: argparse.Namespace) -> int:
    """Group held-out PRs into balanced batches for reviewer subagents.

    Patch sizes are wildly uneven — one held-out PR is 64 files and 270k characters
    while another is two files. Handing each agent a fixed *count* of PRs would give
    one of them an impossible job and the rest nothing to do, so batches are packed by
    cumulative character budget instead. Deterministic, so a re-run fans out the same way.
    """
    in_dir = INPUT_DIR / args.condition
    prs = holdout_prs(args.repo)
    sized: list[tuple[int, int]] = []
    for p in prs:
        src = in_dir / p.name
        if not src.exists():
            _log(f"missing input {src}; run: run_eval prepare --condition {args.condition}")
            return 2
        sized.append((int(p.stem.split("_")[1]), src.stat().st_size))

    sized.sort(key=lambda r: -r[1])
    batches: list[list[int]] = []
    loads: list[int] = []
    for number, size in sized:                 # longest-processing-time first
        if not batches or (size > args.max_chars and loads[-1] > 0):
            target = -1
        else:
            target = min(range(len(batches)), key=lambda i: loads[i], default=-1)
        if target < 0 or loads[target] + size > args.max_chars:
            batches.append([number])
            loads.append(size)
        else:
            batches[target].append(number)
            loads[target] += size

    for i, (batch, load) in enumerate(zip(batches, loads), 1):
        print(f"group {i}: {len(batch)} PRs, {load:,} bytes -> "
              f"{' '.join('pr_%d' % n for n in sorted(batch))}")
    print(f"\n{len(prs)} PRs in {len(batches)} groups for {args.condition}",
          file=sys.stderr)
    return 0


# ------------------------------------------------------------------------ score

class CorruptFindings(Exception):
    """A findings file that cannot be trusted must stop the scoring run."""


def load_findings(cond: str, number: int) -> list[dict]:
    """Load one PR's findings, refusing anything that fails to parse or is mislabelled.

    Reviewer agents write these files, and during this project one wrote a plain-text
    scratch rendering over an input path. Returning [] for an unreadable file would have
    scored that PR as "reviewer found nothing" — a silent zero that looks exactly like a
    clean diff. Fail loudly instead: a missing file is legitimately no findings, a
    corrupt one is not.
    """
    p = FINDINGS_DIR / cond / f"pr_{number}.json"
    if not p.exists():
        return []
    try:
        data = read_json(p)
    except json.JSONDecodeError as exc:
        raise CorruptFindings(f"{p}: not valid JSON ({exc})") from exc
    if isinstance(data, dict):
        if data.get("pr") not in (None, number):
            raise CorruptFindings(
                f"{p}: pr field says {data['pr']}, filename says {number}")
        findings = data.get("findings")
        if findings is None:
            raise CorruptFindings(f"{p}: object has no 'findings' key")
        return findings
    if isinstance(data, list):
        return data
    raise CorruptFindings(f"{p}: expected an object or a list, got {type(data).__name__}")


def candidate_pairs(findings: list[dict], truth: list[dict], window: int):
    """(finding, comment) pairs close enough to possibly be the same review."""
    for fi, f in enumerate(findings):
        fl = f.get("line")
        for ti, t in enumerate(truth):
            if f.get("path") != t.get("path"):
                continue
            tl = t.get("line")
            if fl is None or tl is None:
                continue
            if abs(int(fl) - int(tl)) <= window:
                yield fi, ti, f, t


RANK = {"MATCH": 0, "PARTIAL": 1}


def match_pr(findings, truth, judge, window, lenient):
    """Greedy one-to-one assignment, strongest verdicts first."""
    scored = []
    unresolved = 0
    for fi, ti, f, t in candidate_pairs(findings, truth, window):
        v = judge.verdict(f, t)
        if v is None:
            unresolved += 1
            continue
        if v["verdict"] == "MATCH" or (lenient and v["verdict"] == "PARTIAL"):
            scored.append((RANK[v["verdict"]], fi, ti, v))

    scored.sort(key=lambda r: r[0])
    used_f: set[int] = set()
    used_t: set[int] = set()
    pairs = []
    for _rank, fi, ti, v in scored:
        if fi in used_f or ti in used_t:
            continue
        used_f.add(fi)
        used_t.add(ti)
        pairs.append({"finding": findings[fi], "comment_index": ti,
                      "verdict": v["verdict"], "why": v.get("why", "")})
    return pairs, unresolved


def cmd_score(args: argparse.Namespace) -> int:
    if args.ingest:
        cache_judge = Judge(backend="cache")
        n = ingest_verdicts(Path(args.ingest), cache_judge.cache)
        _log(f"ingested {n} verdicts into eval/cache/")

    prs = holdout_prs(args.repo)
    if not prs:
        _log("no held-out PRs on disk; run eval.fetch_holdout first")
        return 2

    judge = Judge(backend=args.judge)
    results: dict[str, dict] = {}
    per_pr_rows: list[dict] = []
    total_unresolved = 0

    for cond in args.conditions:
        n_findings = n_truth = n_matched = 0
        cat_hits: Counter = Counter()
        cat_findings: Counter = Counter()
        rule_hits: Counter = Counter()
        prs_with_findings = 0

        for p in prs:
            rec = read_json(p)
            truth = rec["ground_truth"]
            findings = load_findings(cond, rec["number"])
            pairs, unresolved = match_pr(findings, truth, judge,
                                         args.line_window, args.lenient)
            total_unresolved += unresolved

            n_findings += len(findings)
            n_truth += len(truth)
            n_matched += len(pairs)
            prs_with_findings += 1 if findings else 0

            for f in findings:
                cat_findings[f.get("category") or _cat_of(cond, f)] += 1
            for m in pairs:
                cat = m["finding"].get("category") or _cat_of(cond, m["finding"])
                cat_hits[cat] += 1
                if m["finding"].get("rule_id"):
                    rule_hits[m["finding"]["rule_id"]] += 1

            per_pr_rows.append({
                "condition": cond, "pr": rec["number"],
                "findings": len(findings), "ground_truth": len(truth),
                "matched": len(pairs), "unresolved_pairs": unresolved,
            })

        results[cond] = {
            "label": CONDITIONS[cond]["label"],
            "prs": len(prs),
            "findings": n_findings,
            "ground_truth": n_truth,
            "matched": n_matched,
            "recall": round(n_matched / n_truth, 4) if n_truth else 0.0,
            "precision": round(n_matched / n_findings, 4) if n_findings else 0.0,
            # The highest recall this condition could reach even if every finding it
            # made matched a distinct human comment. Reporting it stops a low recall
            # being read as "the rules are bad" when it is really "the reviewer spoke
            # rarely", which is a different fact about a different design choice.
            "recall_ceiling": round(min(n_findings, n_truth) / n_truth, 4) if n_truth else 0.0,
            "findings_per_pr": round(n_findings / len(prs), 2),
            "prs_with_at_least_one_finding": prs_with_findings,
            "by_category": {
                c: {"findings": cat_findings[c], "matched": cat_hits[c],
                    "precision": round(cat_hits[c] / cat_findings[c], 4)
                    if cat_findings[c] else 0.0}
                for c in sorted(cat_findings)
            },
            "top_rules_by_matches": rule_hits.most_common(10),
        }

    queued = judge.flush_queue()
    payload = {
        "repo": args.repo,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "held_out_prs": len(prs),
        "line_window": args.line_window,
        "match_rule": ("MATCH or PARTIAL" if args.lenient else "MATCH only"),
        "judge": {"backend": judge.backend, **judge.stats,
                  "unresolved_pairs": total_unresolved},
        "conditions": results,
        "per_pr": per_pr_rows,
    }
    write_json("eval/results.json", payload)
    Path("eval/results.md").write_text(render_results(payload), encoding="utf-8",
                                       newline="\n")

    print(json.dumps({c: {k: v for k, v in r.items()
                          if k in ("recall", "precision", "findings_per_pr",
                                   "findings", "matched", "ground_truth")}
                      for c, r in results.items()}, indent=2))
    if queued:
        _log(f"\n{queued} pairs still need a verdict. Judge them, then:\n"
             f"  python -m eval.run_eval score --ingest eval/judge_verdicts.json")
        return 1
    return 0


def _cat_of(cond: str, finding: dict) -> str:
    """A baseline finding has no rule, so it has no mined category."""
    return "uncategorised" if cond == "A_baseline" else "unknown"


# --------------------------------------------------------------------- markdown

def render_results(payload: dict) -> str:
    conds = payload["conditions"]
    lines = [
        "# Evaluation — A/B/C on held-out PRs",
        "",
        f"Generated {payload['generated_at']}.",
        "",
        f"Scored on **{payload['held_out_prs']} held-out {payload['repo']} PRs**, fenced "
        "off before sampling and never mined. Every one qualified at three or more review "
        "threads, so every one has real ground truth.",
        "",
        f"A finding matches a human comment when it is in the same file, within "
        f"{payload['line_window']} lines, and the judge rules them semantically "
        f"equivalent ({payload['match_rule']}). Judge: "
        f"`{payload['judge']['backend']}`, {payload['judge']['cache_hit']} cached "
        f"verdicts reused.",
        "",
        "| Condition | Recall | Ceiling | Precision | Findings/PR | Findings | Matched |",
        "|---|---|---|---|---|---|---|",
    ]
    for cond in ("A_baseline", "B_housestyle", "C_generic"):
        r = conds.get(cond)
        if not r:
            continue
        lines.append(
            f"| {cond} — {r['label']} | {r['recall']:.1%} | "
            f"{r.get('recall_ceiling', 0):.1%} | {r['precision']:.1%} | "
            f"{r['findings_per_pr']} | {r['findings']} | {r['matched']} |"
        )
    lines += [
        "",
        "## What this evaluation found",
        "",
        "**The mined rules did not outperform the baseline here.** Condition A — the same "
        "reviewer with no mined rules — anticipated more real human comments than condition "
        "B did, both strictly and leniently. The project's central claim, that mining a "
        "repository's review history produces better review than stock review of the same "
        "diffs, is **not supported by this run**. That is the result; it is not dressed up "
        "elsewhere in this report.",
        "",
        "Two readings are consistent with the data, and this evaluation cannot separate "
        "them:",
        "",
        "1. **The rulebook is too small.** One tranche promoted 14 rules, of which only a "
        "handful ever fired. The below-threshold candidates file holds roughly thirty more "
        "patterns sitting at support 2 — one tranche short of promotion. A rulebook that "
        "rarely fires cannot beat a reviewer that always speaks.",
        "2. **The method has a ceiling.** Rules mined from what reviewers *did* comment on "
        "may simply not predict what reviewers *will* comment on next. Review is driven by "
        "what a specific maintainer noticed in a specific diff, and much of it is not "
        "convention at all.",
        "",
        "What the run does support: **condition C confirms the rules are repo-specific.** "
        "Another repository's rulebook, offered unscoped against these diffs, matched "
        "nothing. Whatever the Airflow rulebook is doing, it is not detecting generic "
        "Python smells.",
        "",
        "## Reading these numbers",
        "",
        "**Precision is measured against what a reviewer actually wrote, which is a subset "
        "of what they noticed.** A correct finding that no human bothered to comment on "
        "scores as a false positive here. The precision column is therefore a lower bound, "
        "and comparing precision *between* conditions is more meaningful than any single "
        "value.",
        "",
        "**A_baseline isolates the lift as coming from the mining rather than the model.** "
        "Same reviewer, same diffs, no mined rules.",
        "",
        "**Recall here is bounded by finding volume, not by rule quality.** Both reviewer "
        "prompts instruct the reviewer to prefer silence, because precision is what makes "
        "a review tool tolerable in practice. That decision caps recall arithmetically: a "
        "reviewer emitting well under one finding per PR cannot match a few hundred human "
        "comments however good those findings are. The ceiling is "
        "`findings / ground_truth`, and every condition here sits near it. Read recall as "
        "*of the few things it chose to say, how often was a human saying the same thing* "
        "— not as coverage of the review. A higher-verbosity run would trade this the "
        "other way, and the two settings measure different products.",
        "",
        "The instruction is identical in both prompts, so the comparison between "
        "conditions is unaffected; only the absolute recall scale is.",
        "",
        "**Thirty PRs do not exercise a whole rulebook.** Only a handful of mined rules "
        "fired at all here, and they were the ones the project already documents "
        "(CONFIRMED or IMPLIED in the cross-check). No TRIBAL rule fired — the undocumented "
        "conventions are the product, but they are also the rarer ones, and a 30-PR sample "
        "is too small to encounter most of them. That is a limit of the evaluation's size, "
        "not evidence about those rules. Scoring the rulebook properly would need a "
        "held-out set sized to the rules rather than to the calendar.",
        "",
        "**C_generic is the ablation, and it is run deliberately unscoped.** Home "
        "Assistant rules applied to Airflow PRs. Both are large async Python "
        "infrastructure projects, so a C score near B would mean the rules are generic "
        "Python smells wearing a repository's name.",
        "",
        "Run *with* the normal scope filter, condition C scores zero for an uninteresting "
        "reason: Home Assistant's scope paths (`homeassistant/components/...`, `tests/...`) "
        "cannot intersect Airflow's tree, so **all 27 rules are rejected before their "
        "content is ever examined** — 0 applicable rules on all 30 held-out PRs. That is a "
        "real result about path specificity, but it proves only that the *paths* differ. "
        "So C is scored with the scope filter disabled, offering every Home Assistant "
        "convention against every Airflow diff. That asks the question worth asking: do "
        "these conventions actually fire on another repository's code?",
        "",
    ]
    for cond in ("B_housestyle", "C_generic"):
        r = conds.get(cond)
        if not r or not r["by_category"]:
            continue
        lines += [f"## {cond} — by category", "",
                  "| Category | Findings | Matched | Precision |", "|---|---|---|---|"]
        for cat, c in sorted(r["by_category"].items(),
                             key=lambda kv: -kv[1]["findings"]):
            lines.append(f"| {cat} | {c['findings']} | {c['matched']} | "
                         f"{c['precision']:.1%} |")
        lines.append("")
        if r["top_rules_by_matches"]:
            lines += ["Rules that matched the most human comments:", ""]
            for rid, n in r["top_rules_by_matches"][:5]:
                lines.append(f"- `{rid}` — {n} matched comments")
            lines.append("")
    if payload["judge"]["unresolved_pairs"]:
        lines += [f"> {payload['judge']['unresolved_pairs']} candidate pairs were never "
                  "judged and are counted as non-matches. Re-run once they are "
                  "adjudicated.", ""]
    return "\n".join(lines).rstrip() + "\n"


# -------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="eval.run_eval")
    p.add_argument("--repo", default="apache/airflow")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("prepare", help="build review inputs for one condition")
    pr.add_argument("--condition", choices=list(CONDITIONS), required=True)
    pr.set_defaults(func=cmd_prepare)

    pl = sub.add_parser("plan", help="group PRs into balanced reviewer batches")
    pl.add_argument("--condition", choices=list(CONDITIONS), required=True)
    pl.add_argument("--max-chars", type=int, default=140_000)
    pl.set_defaults(func=cmd_plan)

    sc = sub.add_parser("score", help="match findings to ground truth")
    sc.add_argument("--judge", choices=["watsonx", "agent", "cache"], default="watsonx")
    sc.add_argument("--conditions", nargs="+", default=list(CONDITIONS))
    sc.add_argument("--line-window", type=int, default=5)
    sc.add_argument("--lenient", action="store_true",
                    help="count PARTIAL as a match as well as MATCH")
    sc.add_argument("--ingest", default="", help="load an agent verdict file first")
    sc.set_defaults(func=cmd_score)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
