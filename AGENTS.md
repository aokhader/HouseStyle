# House Style — Project Context

## Purpose
House Style mines the unwritten code-review conventions of a specific repository out of its
merged pull-request history, and emits them as an enforceable Bob Skill that reviews diffs
and cites the historical PRs justifying each comment.

## Repository layout

| Path | Language / role |
|---|---|
| `harvest/harvest.py` | GraphQL harvester — stratified, pre-qualified sampling (Phase 1) |
| `backfill_bodies.py` | recovers full comment bodies via REST (Phase 1b) |
| `distill/batch.py` | stratified tranche + batch construction (Phase 2a) |
| `distill/critic.py` | the reduce: support counting, scope generalisation, ids (Phase 2b) |
| `distill/crosscheck.py` | mined rules vs hand-written `AGENTS.md`, both directions (Phase 3) |
| `distill/fetch_docs.py` | read-only fetch of the target repo's own docs (Phase 3) |
| `distill/prompts/` | the subagent prompts, versioned as files |
| `distill/candidates/` | raw per-batch candidate rules from the map |
| `distill/critic/` | chunk inputs and cluster outputs from the reduce |
| `.bob/rules/` | generated rulebooks + project rules — committed |
| `.bob/skills/house-style/` | the `/house-style` Skill (Phase 4) |
| `eval/` | A/B/C harness, watsonx Granite judge, reviewer prompts (Phase 5) |
| `dashboard/` | Next.js App Router viewer (Phase 6) |
| `data/` | **gitignored** — raw harvested JSON, PR patches, fetched docs |
| `bob_sessions/` | Bob task session screenshots — committed, a submission deliverable |

## Target repositories
- `home-assistant/core` — EXCELLENT signal
- `apache/airflow` — EXCELLENT signal

## Key constraints (see `.bob/rules/00-project.md` for full detail)
- Python 3.11+; `httpx` is the only external dependency in `harvest/`, `distill/`, `eval/`.
- GitHub usernames are **never** stored. Hash reviewer logins with SHA-256, keep 12-char prefix.
- Committed artifacts **never** reproduce a review comment verbatim: URL + ≤15-word excerpt.
  `data/` is gitignored working storage and holds full bodies.
- Every emitted rule requires ≥ 3 **distinct PRs** of evidence; otherwise it is a *candidate*.
- **Support counts are computed from the corpus, never asserted by a model.** Subagents emit
  clusters of candidate keys; `distill/critic.py` resolves and counts. Evidence whose
  permalink does not resolve to a harvested comment is dropped, not counted.

## Working in this repo
- Use the venv: `.venv/Scripts/python.exe`. Tests: `.venv/Scripts/python.exe -m pytest -q`.
- **Always pass `encoding="utf-8"` to `open()`.** On Windows the default is cp1252, which
  mangles non-ASCII in the corpus and produces confusing JSON parse errors.
- Subagent prompts live in `distill/prompts/` and `eval/prompts/`. Change the file, not the
  invocation.

## Phase overview
1. **Harvest** — merged PRs + review comments via GitHub GraphQL, stratified across 12
   months, 30 most-recent qualified PRs fenced off as holdout.
2. **Distill** — map: one subagent per 25-comment batch emits candidate rules. Reduce:
   chunked critics cluster, a merge pass joins across chunks, code counts support.
3. **Cross-check** — mined rules vs the repo's hand-written `AGENTS.md`, both directions.
4. **Skill** — `/house-style` reviews a diff, citing precedent on every finding.
5. **Eval** — A/B/C on the 30 held-out PRs against real human comments.
6. **Dashboard** — Next.js viewer for rules, evidence, cross-check and results.

## Current status
Phases 0–4 and 6 complete. Phase 5 harness complete; scoring needs a valid `GITHUB_TOKEN`
in `.env` to fetch held-out PR ground truth, and optionally watsonx credentials for the
Granite judge (an agent-judge fallback covers its absence). Tranche 3's map was
deliberately not run — see the stopping rule in `docs/bob_prompts.md`.
