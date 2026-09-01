# Condition A — baseline review, no mined rules

You are reviewing one pull request diff from a large open-source Python project. This is
the control condition of an evaluation: the same model, the same diffs, no mined rules.
It isolates whether House Style's lift comes from the mining or just from the model.

## Input

`eval/inputs/A_baseline/pr_<N>.json` — `{"pr", "title", "files": [{"path", "patch"}]}`.
Patches are unified diffs. Read with UTF-8 encoding.

## Your task

Review the diff as an experienced maintainer of this project would. Report substantive
problems a human reviewer would leave a comment about.

Worth a comment:

- correctness bugs, edge cases, error handling that will fail in practice
- API and interface design problems
- async, concurrency and event-loop hazards
- missing or wrong tests for the behaviour being changed
- database, migration and transaction problems
- security and credential handling
- performance problems that matter at this project's scale
- deprecation and backward-compatibility obligations

Not worth a comment: formatting, import order, line length, or anything a linter or type
checker already enforces. This project gates review behind green static checks, so those
comments would be noise.

## Discipline

These constraints are identical to those the House Style condition operates under, so
that the comparison is between the rules and no rules, not between two different review
temperaments:

- **Judge added lines.** Report on what this diff introduces, not on pre-existing code
  that happens to sit in the same hunk.
- **One finding per issue per location.** Do not restate the same concern at five lines.
- **Prefer silence.** If you are unsure whether something is really a problem, it is not
  a finding. Precision is the scarce resource in code review.
- **Anchor precisely.** `line` must be the post-image (new file) line number the comment
  is about — the number a reviewer would attach a comment to on GitHub. The evaluation
  matches findings to real comments within a five-line window, so a sloppy line number
  scores as a miss.

## Output

Write `eval/findings/A_baseline/pr_<N>.json`:

```json
{"pr": 12345,
 "findings": [
   {"path": "airflow-core/src/airflow/api/routes/dags.py",
    "line": 212,
    "category": "correctness",
    "message": "what you would say to the author, one or two sentences"}
 ]}
```

`category` is one of: correctness, api-design, async, testing, naming, database,
security, performance, providers, docs, commit-hygiene.

An empty `findings` array is a legitimate answer for a clean diff.

Escape double quotes inside strings as `\"`. Write UTF-8, no BOM. Validate the JSON with
`.venv/Scripts/python.exe` before finishing.
