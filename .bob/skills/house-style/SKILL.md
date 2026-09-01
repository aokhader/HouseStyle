---
name: house-style
description: Review a diff against conventions mined from this repository's own merged-PR review history. Every finding cites the historical PRs that justify it. Use when reviewing a branch, a pull request, or working-tree changes, or when asked what this repo's unwritten review conventions are. Supports --explain <rule-id> to show a rule's full evidence.
---

# /house-style

Reviews a diff against `.bob/rules/*-conventions.json` — conventions distilled from what
human reviewers actually flagged in this repository's merged pull requests.

```
/house-style [--rules <path>] [--diff <ref>]
/house-style --explain <rule-id>
```

Defaults: rules `.bob/rules/airflow-conventions.json`, diff working tree vs merge-base
with `main`.

## Why this exists

Every finding this Skill emits is backed by review comments from real merged PRs. That is
the whole point. Teams abandon AI review tools because the findings are unjustifiable —
you cannot argue with a model's opinion, so you either accept every comment or ignore all
of them. A finding with precedent is arguable: you can open PR #64845 and see a
maintainer of this project asking for exactly this.

So: **a finding with no precedent is not a finding.** `render` drops those, and that is
enforced in code rather than requested in prose.

## Procedure

### 1. Select the applicable rules

```bash
python .bob/skills/house-style/scripts/house_style.py \
    --rules .bob/rules/airflow-conventions.json \
    select --diff main --out .bob/skills/house-style/.work/selected.json
```

This emits only the rules whose `scope_paths` intersect the diff's changed files, plus
the parsed hunks with post-image line numbers. Do not load the whole rulebook — a
two-file diff has no business dragging 200 rules into context, and rules that cannot
apply produce false positives.

Use `--patch-file <json>` instead of `--diff` to review a PR record fetched from the API
(`{"files": [{"path": ..., "patch": ...}]}`) rather than the working tree.

### 2. Evaluate each applicable rule against each hunk

Read `selected.json`. For every rule, check its `trigger` against the hunks in the files
listed in its `matched_paths`. A rule fires only when the diff actually exhibits the
pattern the trigger describes.

Hold the line on these:

- **The trigger must match, not the topic.** A rule scoped to `providers/` is not
  violated merely because the diff touches `providers/`. Scope narrows the candidate set;
  the trigger decides.
- **Judge added lines.** Report on what this diff introduces (`kind: "+"`), not on
  pre-existing code that happens to sit in the same hunk.
- **One finding per rule per location.** Do not restate the same rule at five lines.
- **Prefer silence.** Precision is the scarce resource. If you are unsure whether the
  rule fires, it does not fire.

Write findings as JSON:

```json
{"findings": [
  {"rule_id": "airflow-r014",
   "path": "airflow-core/src/airflow/api_fastapi/core_api/routes/public/dags.py",
   "line": 212,
   "message": "the rule, restated as an actionable request for THIS hunk"}
]}
```

`message` is the rule applied to what you are looking at — "fetch `limit + 1` rows here so
`next_cursor` can be null on the final page", not a paraphrase of the rule in the
abstract. Cite nothing yourself; `render` attaches the precedent.

### 3. Render

```bash
python .bob/skills/house-style/scripts/house_style.py \
    --rules .bob/rules/airflow-conventions.json \
    render --findings .bob/skills/house-style/.work/findings.json
```

Output, sorted by support descending:

```
[airflow-r014] .../routes/public/dags.py:212  api-design
Fetch limit+1 rows so next_cursor can be null on the last page.
Why: computing next_cursor from the last item makes it non-null even when no
     further rows exist, breaking the pagination contract.
Precedent: PR #64845, PR #64963, PR #63994  (support: 7 reviews)
```

It closes with the finding count, the number of rules that fired, and the
highest-support rule among them. Report that summary; do not invent your own.

## --explain

```bash
python .bob/skills/house-style/scripts/house_style.py explain airflow-r014
```

Prints the rule, every supporting comment with its permalink, and the rule's
`AGENTS.md` cross-check label — `CONFIRMED` (the project documents it), `IMPLIED` (the
docs gesture at it), or `TRIBAL` (documented nowhere; it exists only in review history).

`rules --category testing` and `rules --label TRIBAL` list the rulebook.

## Disagreeing with a rule

Delete it from `.bob/rules/airflow-conventions.md` and commit. The rulebook is a text
file under version control, not a model's memory — a rule your team does not hold is
supposed to be removable in one line, with the deletion visible in review. Re-running the
distillation will propose it again from the same evidence; the rulebook is the record of
what your team decided to keep.

Rules carry `support_count` (distinct PRs) so you can raise the bar: if a rule with
support 3 feels like noise, filter the rulebook to support >= 5 and see what survives.

## What this Skill does not do

It cannot see conventions nobody ever violated. Rules are mined from what reviewers
*commented on*, so a convention so well understood that it never comes up in review leaves
no trace in the history and is invisible here. This complements a hand-written
`AGENTS.md`; it does not replace one.
