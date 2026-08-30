# House Style — Project Context

## Purpose
House Style mines the unwritten code-review conventions of a specific repository out of its
merged pull-request history, and emits them as an enforceable Bob Skill that reviews diffs
and cites the historical PRs justifying each comment.

## Repository layout

| Path | Language / role |
|---|---|
| `harvest/` | Python 3.11 — GitHub API extraction (Phase 1) |
| `distill/` | Python 3.11 — batching + subagent orchestration helpers (Phase 2) |
| `.bob/rules/` | Generated rule files (Phase 2 output) + project rules |
| `.bob/skills/` | The `/house-style` Bob Skill (Phase 3) |
| `eval/` | Evaluation harness (Phase 4) |
| `dashboard/` | Next.js application (Phase 5) |
| `data/` | **gitignored** — raw harvested JSON (never committed) |
| `bob_sessions/` | Screenshots — committed |

## Target repositories
- `home-assistant/core` — EXCELLENT signal
- `apache/airflow` — EXCELLENT signal

## Key constraints (see `.bob/rules/00-project.md` for full detail)
- Python 3.11+; `httpx` only external dependency in `harvest/` and `distill/`.
- GitHub usernames are **never** stored. Hash reviewer logins with SHA-256, keep 12-char prefix.
- Review comment bodies are **never** reproduced verbatim. Store URL + ≤15-word excerpt only.
- `data/` is gitignored; `.bob/` is committed.
- Every emitted rule requires ≥ 3 independent supporting comments; otherwise it is a *candidate*.

## Phase overview
1. **Harvest** — pull merged PRs + review comments via GitHub REST API, store raw JSON in `data/`.
2. **Distill** — cluster comments into candidate rules, attach PR/comment evidence.
3. **Emit** — write `.bob/rules/` files that Bob reads as context.
4. **Skill** — write `.bob/skills/house-style.md` that reviews diffs citing rules.
5. **Eval** — score the Skill against held-out PRs.
6. **Dashboard** — Next.js UI to explore rules and evidence.

## Current status
Project scaffolded. No harvest logic written yet.
