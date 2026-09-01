#!/usr/bin/env python3
"""
house_style.py — the deterministic scaffolding of the /house-style Skill.

The Skill is a division of labour. Deciding whether a rule is actually violated by a
hunk is judgement, and the agent does that. Everything around it is mechanical and
lives here, because these are the steps where an agent quietly goes wrong:

  select   pick the rules whose scope intersects the diff, and emit them with the
           hunks — so a two-file diff never drags 200 rules into context
  render   format findings, and DROP any finding whose rule has no resolvable
           precedent. "A finding with no precedent links is a bug" is enforced in
           code rather than asked for in prose
  explain  print one rule, its full evidence, and its AGENTS.md cross-check label

Commands:
    house_style.py select  [--rules P] [--diff REF | --patch-file F] [--out F]
    house_style.py render  --findings F [--rules P]
    house_style.py explain RULE_ID [--rules P]
    house_style.py rules   [--rules P] [--category C] [--label L]

Exit codes: 0 ok, 1 findings suppressed for missing precedent, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_RULES = ".bob/rules/airflow-conventions.json"
DEFAULT_CROSSCHECK = ".bob/rules/airflow-agents-md-crosscheck.json"

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


# --------------------------------------------------------------------------- io

def read_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_rules(path: str) -> dict:
    data = read_json(path)
    return data if isinstance(data, dict) else {"rules": data}


def load_crosscheck(path: str = DEFAULT_CROSSCHECK) -> dict[str, str]:
    """rule id -> CONFIRMED | IMPLIED | TRIBAL, if the Phase 3 cross-check has run."""
    p = Path(path)
    if not p.exists():
        return {}
    data = read_json(p)
    rows = data.get("mined_rules", data) if isinstance(data, dict) else data
    return {r["id"]: r.get("label", "") for r in rows if isinstance(r, dict) and "id" in r}


# ------------------------------------------------------------------ diff parsing

def git_diff(ref: str) -> str:
    """Working tree vs merge-base with ``ref``."""
    try:
        base = subprocess.run(["git", "merge-base", "HEAD", ref],
                              capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        base = ref
    return subprocess.run(["git", "diff", "--unified=6", base],
                          capture_output=True, text=True, check=True).stdout


def parse_diff(text: str, default_path: str = "") -> list[dict]:
    """Unified diff -> [{path, hunks:[{header, new_start, lines, text}]}].

    Line numbers are the post-image (new file) numbers, because that is what a
    reviewer comments on and what the eval matches against.

    ``default_path`` names the file when the text is a bare patch fragment with no
    ``diff --git`` header — which is exactly what GitHub's ``/pulls/{n}/files`` returns
    per file. Without it such a fragment parses to a file with no path and is discarded.
    """
    files: list[dict] = []
    cur: dict | None = None
    hunk: dict | None = None
    new_line = 0

    for line in text.splitlines():
        if line.startswith("diff --git "):
            cur = {"path": line.split(" b/", 1)[-1].strip(), "hunks": []}
            files.append(cur)
            hunk = None
            continue
        if line.startswith("+++ b/"):
            if cur is not None:
                cur["path"] = line[6:].strip()
            continue
        if line.startswith("+++ ") or line.startswith("--- "):
            continue
        m = HUNK_RE.match(line)
        if m:
            if cur is None:                      # patch fragment with no diff header
                cur = {"path": default_path, "hunks": []}
                files.append(cur)
            new_line = int(m.group(3))
            hunk = {"header": line, "new_start": new_line, "lines": [], "text": [line]}
            cur["hunks"].append(hunk)
            continue
        if hunk is None:
            continue
        hunk["text"].append(line)
        if line.startswith("+"):
            hunk["lines"].append({"n": new_line, "kind": "+", "text": line[1:]})
            new_line += 1
        elif line.startswith("-"):
            hunk["lines"].append({"n": new_line, "kind": "-", "text": line[1:]})
        elif line.startswith("\\"):
            continue
        else:
            hunk["lines"].append({"n": new_line, "kind": " ", "text": line[1:]})
            new_line += 1

    for f in files:
        for h in f["hunks"]:
            h["text"] = "\n".join(h["text"])
    return [f for f in files if f["path"]]


def files_from_patch_json(path: str) -> list[dict]:
    """Read a held-out PR record (or any {files:[{path,patch}]}) as diff files."""
    data = read_json(path)
    files = data.get("files", data) if isinstance(data, dict) else data
    out: list[dict] = []
    for f in files:
        patch = f.get("patch") or ""
        if not patch:
            continue
        parsed = parse_diff(patch, default_path=f["path"])
        hunks = parsed[0]["hunks"] if parsed else []
        out.append({"path": f["path"], "hunks": hunks})
    return out


# ------------------------------------------------------------------ scope filter

def scope_matches(scope: str, path: str) -> bool:
    scope = scope.rstrip("/") + "/"
    if scope == "./":
        return "/" not in path
    return (path + "/").startswith(scope)


def applicable_rules(rules: list[dict], paths: list[str]) -> list[dict]:
    """Rules whose scope_paths intersect the diff's touched files.

    This is the step that keeps the Skill usable: without it a two-file diff loads
    the entire rulebook and the agent reviews against rules that cannot apply.
    """
    out = []
    for r in rules:
        hit = sorted({p for p in paths
                      for s in r.get("scope_paths", []) if scope_matches(s, p)})
        if hit:
            out.append({**r, "_matched_paths": hit})
    return out


def hunk_listing(hunk: dict) -> str:
    """A hunk as numbered text: ``<post-image line> <+|-| > <source>``.

    Emitting each diff line as a JSON object costs roughly four times the raw patch,
    which pushed a 30-PR review set past what any single agent could read. This keeps
    the one thing the JSON was for — an exact post-image line number on every line, so
    a finding can be anchored precisely — at close to the size of the patch itself.
    Removed lines carry no post-image number and are marked ``----``.
    """
    out = []
    for ln in hunk["lines"]:
        num = "----" if ln["kind"] == "-" else f"{ln['n']:>4}"
        out.append(f"{num} {ln['kind']}{ln['text']}")
    return "\n".join(out)


# ----------------------------------------------------------------------- select

def cmd_select(args: argparse.Namespace) -> int:
    if args.patch_file:
        files = files_from_patch_json(args.patch_file)
    else:
        files = parse_diff(git_diff(args.diff))

    paths = [f["path"] for f in files]
    book = load_rules(args.rules)
    all_rules = book.get("rules", [])
    if args.ignore_scope:
        # For the evaluation's cross-repo ablation only. Another repository's rules have
        # scope paths that cannot intersect this repo's tree, so the scope filter would
        # reject all of them before their content was ever tested. Disabling it asks the
        # sharper question: do those conventions actually fire on this code?
        rules = [{**r, "_matched_paths": paths} for r in all_rules]
    else:
        rules = applicable_rules(all_rules, paths)
    rules.sort(key=lambda r: -r.get("support_count", 0))

    payload = {
        "rules_path": args.rules,
        "diff_files": len(files),
        "rules_total": len(book.get("rules", [])),
        "rules_applicable": len(rules),
        "files": [
            {"path": f["path"],
             "hunks": [{"header": h["header"], "listing": hunk_listing(h)}
                       for h in f["hunks"]]}
            for f in files
        ],
        "rules": [
            {
                "id": r["id"],
                "rule": r["rule"],
                "category": r["category"],
                "trigger": r["trigger"],
                "rationale": r["rationale"],
                "scope_paths": r["scope_paths"],
                "support_count": r["support_count"],
                "matched_paths": r["_matched_paths"],
            }
            for r in rules
        ],
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8", newline="\n")
        print(f"{args.out}: {len(rules)}/{len(book.get('rules', []))} rules applicable "
              f"to {len(files)} changed files", file=sys.stderr)
    else:
        print(text)
    return 0


# ----------------------------------------------------------------------- render

def cmd_render(args: argparse.Namespace) -> int:
    book = load_rules(args.rules)
    by_id = {r["id"]: r for r in book.get("rules", [])}
    findings = read_json(args.findings)
    if isinstance(findings, dict):
        findings = findings.get("findings", [])

    kept, suppressed = [], []
    for f in findings:
        rule = by_id.get(f.get("rule_id", ""))
        if rule is None or not rule.get("evidence"):
            suppressed.append(f)          # no precedent -> not a finding
            continue
        kept.append((f, rule))

    kept.sort(key=lambda pair: -pair[1].get("support_count", 0))

    out: list[str] = []
    for f, rule in kept:
        prs = sorted({e["pr"] for e in rule["evidence"]}, reverse=True)[:3]
        out += [
            f"[{rule['id']}] {f.get('path')}:{f.get('line')}  {rule['category']}",
            f"{f.get('message') or rule['rule']}",
            f"Why: {rule['rationale']}",
            f"Precedent: {', '.join('PR #%d' % p for p in prs)}"
            f"  (support: {rule['support_count']} reviews)",
            "",
        ]

    print("\n".join(out).rstrip())
    if kept:
        top = max(kept, key=lambda pair: pair[1].get("support_count", 0))[1]
        print(f"\n{len(kept)} findings across {len({r['id'] for _, r in kept})} rules. "
              f"Highest-support rule that fired: {top['id']} "
              f"(support {top['support_count']}).")
    else:
        print("\n0 findings.")
    if suppressed:
        print(f"{len(suppressed)} finding(s) suppressed: no resolvable precedent.",
              file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------- explain

def cmd_explain(args: argparse.Namespace) -> int:
    book = load_rules(args.rules)
    pools = [("RULE", book.get("rules", [])),
             ("CANDIDATE", book.get("candidates", [])),
             ("INCIDENT", book.get("incidents", []))]
    for status, pool in pools:
        for r in pool:
            if r.get("id") == args.rule_id:
                labels = load_crosscheck(args.crosscheck)
                print(f"{r['id']}  [{r['category']}]  status: {status}")
                print(f"  {r['rule']}\n")
                print(f"  Trigger : {r['trigger']}")
                print(f"  Why     : {r['rationale']}")
                print(f"  Scope   : {', '.join(r['scope_paths'])}")
                print(f"  Support : {r['support_count']} distinct PRs, "
                      f"{r.get('distinct_reviewers', 0)} distinct reviewers")
                print(f"  vs AGENTS.md: {labels.get(r['id'], 'not cross-checked')}\n")
                print("  Evidence:")
                for e in r["evidence"]:
                    print(f"    PR #{e['pr']}  {e['path']}")
                    print(f"      {e['excerpt']}")
                    print(f"      {e['url']}")
                return 0
    print(f"no rule with id {args.rule_id} in {args.rules}", file=sys.stderr)
    return 2


# ------------------------------------------------------------------------ rules

def cmd_rules(args: argparse.Namespace) -> int:
    book = load_rules(args.rules)
    labels = load_crosscheck(args.crosscheck)
    rows = book.get("rules", [])
    if args.category:
        rows = [r for r in rows if r["category"] == args.category]
    if args.label:
        rows = [r for r in rows if labels.get(r["id"], "") == args.label.upper()]
    for r in sorted(rows, key=lambda r: -r["support_count"]):
        tag = labels.get(r["id"], "")
        print(f"{r['id']}  {r['support_count']:>3}  {r['category']:<15} "
              f"{tag:<10} {r['rule'][:90]}")
    print(f"\n{len(rows)} rules", file=sys.stderr)
    return 0


# -------------------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    # Rules contain em dashes and backticks; the Windows console defaults to cp1252
    # and would render them as mojibake in a finding a developer is meant to read.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    p = argparse.ArgumentParser(prog="house-style")
    p.add_argument("--rules", default=DEFAULT_RULES)
    p.add_argument("--crosscheck", default=DEFAULT_CROSSCHECK)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("select", help="rules applicable to a diff, with the hunks")
    s.add_argument("--diff", default="main")
    s.add_argument("--patch-file", default="")
    s.add_argument("--out", default="")
    s.add_argument("--ignore-scope", action="store_true",
                   help="offer every rule regardless of scope (cross-repo ablation)")
    s.set_defaults(func=cmd_select)

    r = sub.add_parser("render", help="format findings, dropping any without precedent")
    r.add_argument("--findings", required=True)
    r.set_defaults(func=cmd_render)

    e = sub.add_parser("explain", help="one rule, its evidence and cross-check label")
    e.add_argument("rule_id")
    e.set_defaults(func=cmd_explain)

    ls = sub.add_parser("rules", help="list the rulebook")
    ls.add_argument("--category", default="")
    ls.add_argument("--label", default="")
    ls.set_defaults(func=cmd_rules)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
