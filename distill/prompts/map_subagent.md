# Phase 2b map — per-batch candidate extraction

You are given exactly ONE batch file of review comments harvested from a repository's
merged pull requests. Read it and return candidate conventions in this schema:

```json
{
  "rule": "imperative sentence stating what this repo requires or forbids",
  "category": "correctness|api-design|async|testing|naming|database|security|performance|providers|docs|commit-hygiene",
  "trigger": "the diff pattern that should cause this rule to fire",
  "rationale": "why this repo cares, in the reviewers' own reasoning",
  "evidence": [{"pr": 64845, "url": "...", "excerpt": "<=15 words"}],
  "scope_paths": ["airflow-core/src/airflow/api_fastapi/core_api/routes/"]
}
```

1. EMIT SINGLE-INSTANCE CANDIDATES. Do NOT require a pattern to repeat within your
   batch. You see 25 of ~5,500 comments; a convention appearing once in your batch may
   appear in ten others. Emit any genuine convention you can evidence from even ONE
   comment. The critic aggregates across all batches and applies the support threshold —
   that is not your job. An empty array means "no convention here at all", not "nothing
   repeated". Do NOT emit support_count; the critic computes it.

2. REJECT UNIVERSAL SOFTWARE ADVICE. A rule must be specific to THIS repo. "Names should
   reflect what they represent", "add type hints", "avoid bare except", "handle errors"
   are generic advice or linter territory — they fire on everything and mean nothing.
   The test: could this rule have been written by someone who had never seen this
   codebase? If yes, discard it. "Cursor tokens that fail to parse must raise HTTP 400
   rather than falling back to the raw string" passes. "Use accurate variable names"
   does not.

3. SKIP WHAT TOOLING CATCHES. This project gates review behind green static checks, so
   formatting, import order and line length are already automated and are noise here.
   Prefer project-specific judgement: architectural boundaries between subpackages;
   async and scheduler-loop constraints; provider/integration compatibility; required
   test patterns; deprecation and breaking-change obligations.

4. `trigger` must be concrete enough to evaluate against a diff hunk. `scope_paths` is
   required — derive it from the paths of the comments backing the rule.

Note: batches are sorted by path, so several comments may come from the same PR. Record
the PR on each evidence entry; the critic counts distinct PRs.

## Output contract

- Write a JSON ARRAY (top level `[...]`) of candidate objects to the output path given.
- The `excerpt` field is at most 15 words taken from the comment body.
- **Escape any double quote inside a string value as `\"`.** A malformed file is a
  failed batch. Validate with `python -c "import json;json.load(open(PATH,encoding='utf-8'))"`
  before you finish.
- Write the file UTF-8 with no BOM.
- Do not run the critic. Do not read any batch other than the one assigned.
