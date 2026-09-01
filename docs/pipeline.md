# Pipeline runbook

Every command, in order, from an empty checkout to a scored evaluation.

The division that holds throughout: **agents make judgement calls, code does arithmetic.**
Anything that produces a number in the rulebook or the results table is a Python script you
can read and re-run. Anything requiring taste — is this a convention or a one-off bug, do
these two comments mean the same thing — is a subagent working from a versioned prompt.

Prerequisites: Python 3.11+, `uv`, Node 22+, a `GITHUB_TOKEN` in `.env`.
Windows note: use `.venv/Scripts/python.exe`; on POSIX, `.venv/bin/python`.

```bash
uv sync
export PY=.venv/Scripts/python.exe
```

---

## Phase 1 — Harvest

Stratified across 12 months, pre-qualified to PRs with at least three review threads, with
the 30 most recent qualified PRs fenced off as holdout.

```bash
$PY -m harvest.harvest --repo apache/airflow --months 12
$PY -m harvest.harvest --repo home-assistant/core --months 6
```

Then recover full comment bodies (one paginated REST call per PR):

```bash
$PY backfill_bodies.py --repo apache/airflow
$PY backfill_bodies.py --repo home-assistant/core
```

Median body length should land in the 300–600 character range. Near 90 means the backfill
failed and the distillation would be working from fragments.

## Phase 2a — Batch

```bash
$PY -m distill.batch --repo apache-airflow
$PY -m distill.batch --repo home-assistant-core --tranches 1 --batches-per-tranche 20
```

Airflow: 3 tranches × 30 batches × 25 comments, stratified by `(month, prefix)` so each
tranche mirrors the corpus. Home Assistant: a single 20-batch tranche, which is all
condition C needs.

## Phase 2b — Map

One subagent per batch, each given exactly one batch file and
`distill/prompts/map_subagent.md`. Batches are independent, so run them in parallel.

Output: `distill/candidates/<tranche>/batch_NNN.json`.

Check that the agents cited real comments before spending anything on the reduce:

```bash
$PY -m distill.critic verify --repo apache-airflow --candidates distill/candidates
```

Anything below ~95% resolution means the map prompt is letting agents invent permalinks,
and the prompt needs fixing before the critic merges fabricated evidence into rules.

## Phase 2b — Reduce

Chunk the candidates so no critic sees more than ~180 at once:

```bash
$PY -m distill.critic prep --candidates distill/candidates/t1 --batches 1-10 \
    --out distill/critic/t1/chunk_A.json
$PY -m distill.critic prep --candidates distill/candidates/t1 --batches 11-20 \
    --out distill/critic/t1/chunk_B.json
$PY -m distill.critic prep --candidates distill/candidates/t1 --batches 21-30 \
    --out distill/critic/t1/chunk_C.json
```

Run one critic subagent per chunk with `distill/prompts/critic_chunk.md`, producing
`clusters_A.json`, `clusters_B.json`, `clusters_C.json`. Each must account for every input
key exactly once.

No chunk critic can see the other two, so the same convention appears up to three times.
The merge pass joins them:

```bash
$PY -m distill.critic merge-prep \
    --clusters distill/critic/t1/clusters_{A,B,C}.json \
    --out distill/critic/t1/merge_input.json
```

Run critic-MERGE with `distill/prompts/critic_merge.md`. It emits **only** groups that
merge; singletons are derived in code:

```bash
$PY -m distill.critic merge-expand \
    --clusters distill/critic/t1/clusters_{A,B,C}.json \
    --merged distill/critic/t1/merged.json \
    --out distill/critic/t1/clusters_merged.json
```

Then the reduce, which computes every number in the rulebook:

```bash
$PY -m distill.critic reduce --repo apache-airflow --slug airflow \
    --candidates distill/candidates/t1 \
    --clusters distill/critic/t1/clusters_merged.json \
    --tranche 1 --batches-count 30 --comments-seen 750
```

Writes `.bob/rules/airflow-conventions.{md,json}`, `airflow-candidates.md`,
`airflow-ids.json` and appends to `saturation.json`.

Repeat for the contrast corpus with `--slug hass --repo home-assistant-core`.

**The stopping rule:** when `new_rule_rate` in `saturation.json` drops below ~10%,
additional tranches have stopped buying new conventions. Stop there.

## Phase 3 — Cross-check against the hand-written AGENTS.md

```bash
$PY -m distill.fetch_docs --repo apache/airflow
$PY -m distill.crosscheck prep --rules .bob/rules/airflow-conventions.json \
    --out distill/crosscheck/airflow_input.json
```

Run a subagent with `distill/prompts/crosscheck.md`, then:

```bash
$PY -m distill.crosscheck render --labels distill/crosscheck/airflow_labels.json \
    --rules .bob/rules/airflow-conventions.json --slug airflow
```

`fetch_docs.py` only ever reads. It writes into gitignored `data/`, never to the source
repository — the document being evaluated must not be edited by the thing evaluating it.

## Phase 4 — The Skill

```bash
$PY .bob/skills/house-style/scripts/house_style.py rules --label TRIBAL
$PY .bob/skills/house-style/scripts/house_style.py explain airflow-r014
$PY .bob/skills/house-style/scripts/house_style.py select --diff main --out /tmp/sel.json
```

In the IDE, `/house-style` runs the procedure in `.bob/skills/house-style/SKILL.md`.

## Phase 5 — Evaluate

```bash
$PY -m eval.fetch_holdout --repo apache/airflow
$PY -m eval.run_eval prepare --condition A_baseline
$PY -m eval.run_eval prepare --condition B_housestyle
$PY -m eval.run_eval prepare --condition C_generic
```

Run reviewer subagents over `eval/inputs/<condition>/pr_*.json` — condition A with
`eval/prompts/review_baseline.md`, B and C with `eval/prompts/review_housestyle.md` — each
writing `eval/findings/<condition>/pr_<N>.json`. The two prompts are deliberately symmetric
in discipline and output schema; an asymmetry there would rig the comparison.

Then score:

```bash
$PY -m eval.run_eval score --judge watsonx          # IBM Granite, verdicts cached
$PY -m eval.run_eval score --judge agent            # queue pairs for an agent judge
$PY -m eval.run_eval score --ingest eval/judge_verdicts.json
```

`--judge watsonx` needs `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`. Without
them it falls back to the agent judge automatically. Both write to the same cache, so
adding credentials later fills in the gaps without re-judging anything already decided.

Writes `eval/results.{md,json}`.

## Phase 6 — Dashboard

```bash
cd dashboard && npm install && npm run build && npm start
```

Reads the generated JSON from disk at build time. No database, no API layer. Every view
degrades to an explanatory placeholder when its artifact does not exist yet, so it builds
against a partially-run pipeline.

## Tests

```bash
$PY -m pytest -q
```

60 tests over the deterministic core — scope generalisation, excerpt clipping, id
stability, diff parsing, the scope filter, precedent suppression, the matcher, the judge
cache. These are the places where a silent error would move a number in the results table
without raising anything.
