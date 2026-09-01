# Conditions B and C — review against a mined rulebook

You are reviewing one pull request diff against conventions mined from a repository's
merged-PR review history. This is the House Style condition of an evaluation.

In **condition B** the rules were mined from the same repository the PR belongs to.
In **condition C** they were mined from a *different* repository — a deliberate ablation.
You are not told which. Review against the rules you are given, exactly as you would
either way. If the rules do not fit the diff, the honest answer is few findings or none,
and that result is the point of the experiment.

## Input

`eval/inputs/<condition>/pr_<N>.json`, produced by the Skill's own `select` step:

- `files` — the changed files, with hunks already parsed. Each hunk line carries `n` (the
  post-image line number) and `kind` (`+` added, `-` removed, ` ` context).
- `rules` — only the rules whose `scope_paths` intersect this diff, each with `id`,
  `rule`, `trigger`, `rationale`, `category`, `support_count` and `matched_paths`.

Read with UTF-8 encoding.

## Your task

For each rule, check its `trigger` against the hunks in the files listed in that rule's
`matched_paths`. Emit a finding only where the diff actually exhibits the pattern the
trigger describes.

- **The trigger must match, not the topic.** A rule scoped to `providers/` is not violated
  merely because the diff touches `providers/`. Scope narrows the candidate set; the
  trigger decides.
- **Judge added lines.** Report on what this diff introduces (`kind: "+"`), not on
  pre-existing code in the same hunk.
- **One finding per rule per location.** Do not restate a rule at five lines.
- **Prefer silence.** If you are unsure whether the rule fires, it does not fire.
  Precision is the scarce resource.
- **Anchor precisely.** `line` must be the post-image line number from the hunk — the
  number a reviewer would attach a comment to on GitHub. The evaluation matches findings
  to real human comments within a five-line window, so a sloppy line number scores as a
  miss.
- **Do not review off-rulebook.** If you notice a genuine bug that no supplied rule
  covers, do not report it. This condition measures the rulebook, and a finding with no
  rule behind it would be suppressed by the Skill anyway.

## Output

Write `eval/findings/<condition>/pr_<N>.json`:

```json
{"pr": 12345,
 "findings": [
   {"rule_id": "airflow-r014",
    "path": "airflow-core/src/airflow/api/routes/dags.py",
    "line": 212,
    "category": "api-design",
    "message": "the rule applied to THIS hunk, as an actionable request"}
 ]}
```

`rule_id` and `category` must come from the rule you are firing — copy them, do not
invent them. `message` is the rule made concrete: "fetch `limit + 1` rows here so
`next_cursor` can be null on the final page", not a paraphrase of the rule in the
abstract. Do not write citations yourself; the Skill attaches precedent from the rulebook.

An empty `findings` array is a legitimate answer, and in condition C it may well be the
right one.

Escape double quotes inside strings as `\"`. Write UTF-8, no BOM. Validate the JSON with
`.venv/Scripts/python.exe` before finishing.
