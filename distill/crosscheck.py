#!/usr/bin/env python3
"""
distill/crosscheck.py — Phase 3, the mined rulebook against the project's hand-written
agent rules, in both directions.

Forward: for each mined rule, is it written down anywhere?
    CONFIRMED  explicitly stated in AGENTS.md or contributing-docs
    IMPLIED    the docs gesture at it but do not state it as a requirement
    TRIBAL     documented nowhere; it exists only in review history

Reverse — and this is the direction that matters: for each rule the project wrote by
hand, does review history support it?
    SUPPORTED     mined evidence backs it
    UNSUPPORTED   no evidence in review history
    CONTRADICTED  review history pushes the other way

CONFIRMED is the correctness check — the mining agrees with the documentation where the
documentation exists. TRIBAL is the product. UNSUPPORTED is the argument: hand-written
agent rules are guesses, and this names the ones review history does not back.

As everywhere in this project, the labelling is judgement (a subagent, see
``distill/prompts/crosscheck.md``) and the counting is code.

    prep     rulebook -> compact input for the cross-check subagent
    render   labelled output -> .bob/rules/<slug>-agents-md-crosscheck.{md,json}

Usage:
    python -m distill.crosscheck prep --rules .bob/rules/airflow-conventions.json \
                                      --out distill/crosscheck/airflow_input.json
    python -m distill.crosscheck render --labels distill/crosscheck/airflow_labels.json \
                                        --rules .bob/rules/airflow-conventions.json \
                                        --slug airflow
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

FORWARD_LABELS = ("CONFIRMED", "IMPLIED", "TRIBAL")
REVERSE_LABELS = ("SUPPORTED", "UNSUPPORTED", "CONTRADICTED")


def read_json(path: str | Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str | Path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def cmd_prep(args: argparse.Namespace) -> int:
    book = read_json(args.rules)
    rows = [
        {
            "id": r["id"],
            "rule": r["rule"],
            "category": r["category"],
            "trigger": r["trigger"],
            "scope_paths": r["scope_paths"],
            "support_count": r["support_count"],
            "evidence_prs": sorted({e["pr"] for e in r["evidence"]}, reverse=True)[:6],
        }
        for r in book["rules"]
    ]
    write_json(args.out, {"repo": book.get("repo"), "n_rules": len(rows), "rules": rows})
    print(f"{args.out}: {len(rows)} mined rules to cross-check")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    book = read_json(args.rules)
    labels = read_json(args.labels)
    by_id = {r["id"]: r for r in book["rules"]}

    mined = labels.get("mined_rules", [])
    theirs = labels.get("their_rules", [])

    unknown = [m["id"] for m in mined if m["id"] not in by_id]
    missing = sorted(set(by_id) - {m["id"] for m in mined})
    bad_forward = [m["id"] for m in mined if m.get("label") not in FORWARD_LABELS]
    bad_reverse = [t.get("statement", "")[:40] for t in theirs
                   if t.get("label") not in REVERSE_LABELS]

    fwd = Counter(m["label"] for m in mined if m.get("label") in FORWARD_LABELS)
    rev = Counter(t["label"] for t in theirs if t.get("label") in REVERSE_LABELS)

    for m in mined:
        rule = by_id.get(m["id"])
        if rule:
            m["rule"] = rule["rule"]
            m["category"] = rule["category"]
            m["support_count"] = rule["support_count"]

    payload = {
        "repo": book.get("repo"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "mined_rules": len(mined),
            "forward": dict(fwd),
            "their_rules": len(theirs),
            "reverse": dict(rev),
            "unlabelled_mined_rules": len(missing),
            "unknown_ids": len(unknown),
            "invalid_forward_labels": len(bad_forward),
            "invalid_reverse_labels": len(bad_reverse),
        },
        "mined_rules": mined,
        "their_rules": theirs,
    }
    write_json(Path(args.rules_dir) / f"{args.slug}-agents-md-crosscheck.json", payload)
    Path(args.rules_dir, f"{args.slug}-agents-md-crosscheck.md").write_text(
        render_markdown(payload), encoding="utf-8", newline="\n")

    print(json.dumps(payload["counts"], indent=2))
    for name, bad in (("unknown ids", unknown), ("unlabelled", missing),
                      ("invalid forward", bad_forward), ("invalid reverse", bad_reverse)):
        if bad:
            print(f"WARNING {name}: {bad[:10]}")
    return 0


def render_markdown(p: dict) -> str:
    c = p["counts"]
    fwd, rev = c["forward"], c["reverse"]
    total_fwd = sum(fwd.values()) or 1
    total_rev = sum(rev.values()) or 1

    lines = [
        f"# {p['repo']} — mined rules vs the hand-written AGENTS.md",
        "",
        f"Generated {p['generated_at']}.",
        "",
        "Two questions, and the second is the interesting one.",
        "",
        "## Forward — is each mined rule written down anywhere?",
        "",
        "| Label | Rules | Share | Meaning |",
        "|---|---|---|---|",
        f"| CONFIRMED | {fwd.get('CONFIRMED', 0)} | "
        f"{fwd.get('CONFIRMED', 0) / total_fwd:.0%} | "
        "stated in AGENTS.md or contributing-docs |",
        f"| IMPLIED | {fwd.get('IMPLIED', 0)} | {fwd.get('IMPLIED', 0) / total_fwd:.0%} | "
        "the docs gesture at it, without requiring it |",
        f"| TRIBAL | {fwd.get('TRIBAL', 0)} | {fwd.get('TRIBAL', 0) / total_fwd:.0%} | "
        "documented nowhere; lives only in review history |",
        "",
        "CONFIRMED is the correctness check: where the project documented a convention, "
        "the mining found it independently from review comments alone. **TRIBAL is the "
        "product** — conventions this project enforces in review and has never written "
        "down.",
        "",
        "## Reverse — does review history support each hand-written rule?",
        "",
        "| Label | Rules | Share |",
        "|---|---|---|",
        f"| SUPPORTED | {rev.get('SUPPORTED', 0)} | "
        f"{rev.get('SUPPORTED', 0) / total_rev:.0%} |",
        f"| UNSUPPORTED | {rev.get('UNSUPPORTED', 0)} | "
        f"{rev.get('UNSUPPORTED', 0) / total_rev:.0%} |",
        f"| CONTRADICTED | {rev.get('CONTRADICTED', 0)} | "
        f"{rev.get('CONTRADICTED', 0) / total_rev:.0%} |",
        "",
        "**UNSUPPORTED is the argument.** A hand-written agent rules file is a set of "
        "guesses about what a team enforces, written by whoever had the energy to write "
        "it. These are the entries that a year of review history does not back. They may "
        "still be right — a rule so well obeyed it never needs stating leaves no trace "
        "either — but nobody could tell you which without this comparison.",
        "",
        "### Hand-written rules review history does not support",
        "",
    ]
    for t in p["their_rules"]:
        if t.get("label") == "UNSUPPORTED":
            src = t.get("source", "")
            lines.append(f"- **{t.get('statement', '')}** — {src}  \n  {t.get('why', '')}")
    lines.append("")

    contradicted = [t for t in p["their_rules"] if t.get("label") == "CONTRADICTED"]
    if contradicted:
        lines += ["### Contradicted by review history", ""]
        for t in contradicted:
            prs = ", ".join(f"#{n}" for n in t.get("evidence_prs", []))
            lines.append(f"- **{t.get('statement', '')}** — {t.get('why', '')}"
                         + (f"  ({prs})" if prs else ""))
        lines.append("")

    lines += ["## Mined rules, by label", ""]
    for label in FORWARD_LABELS:
        group = [m for m in p["mined_rules"] if m.get("label") == label]
        lines += [f"### {label} ({len(group)})", ""]
        for m in sorted(group, key=lambda r: -r.get("support_count", 0)):
            cite = f" — {m['doc_reference']}" if m.get("doc_reference") else ""
            lines.append(f"- `{m['id']}` **[{m.get('category', '')}]** "
                         f"(support {m.get('support_count', 0)}) "
                         f"{m.get('rule', '')}{cite}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="distill.crosscheck")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("prep")
    pr.add_argument("--rules", default=".bob/rules/airflow-conventions.json")
    pr.add_argument("--out", default="distill/crosscheck/airflow_input.json")
    pr.set_defaults(func=cmd_prep)

    rd = sub.add_parser("render")
    rd.add_argument("--rules", default=".bob/rules/airflow-conventions.json")
    rd.add_argument("--labels", required=True)
    rd.add_argument("--slug", default="airflow")
    rd.add_argument("--rules-dir", default=".bob/rules")
    rd.set_defaults(func=cmd_render)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
