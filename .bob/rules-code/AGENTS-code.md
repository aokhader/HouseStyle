# House Style — Code Mode Context

Extends the root `AGENTS.md` with guidance specific to writing and editing code.

## Where to write code

| Phase | Directory | Notes |
|---|---|---|
| Harvest | `harvest/` | Pure Python 3.11+, `httpx` only |
| Distill | `distill/` | Pure Python 3.11+, `httpx` only |
| Evaluation | `eval/` | May use lightweight test deps |
| Dashboard | `dashboard/` | Next.js / TypeScript |

## Python conventions

- Use `async`/`await` throughout `harvest/` and `distill/`; all I/O is async via `httpx.AsyncClient`.
- Type-annotate every function signature. Use `TypedDict` or `dataclasses` for structured data.
- No `print()` in library code — use `logging` with named loggers.
- Keep modules small (< 300 lines). Split by concern, not by phase.

## File output conventions

- Harvested raw data goes to `data/<repo_slug>/` as line-delimited JSON (`.jsonl`).
- Rule files go to `.bob/rules/NN-<slug>.md` following the schema in `00-project.md`.
- Never write to `data/` from within `.bob/` scripts — keep phases separate.

## Testing

- Unit tests live alongside source in `harvest/tests/` and `distill/tests/`.
- Use `pytest`. No test framework beyond that.
- Do not write tests for network calls — mock `httpx` responses instead.
