# House Style — Plan Mode Context

Extends the root `AGENTS.md` with guidance specific to planning and architecture decisions.

## Phase sequencing

Phases are intentionally sequential. Do not design Phase 2 (distill) before Phase 1 (harvest)
produces representative data. Each phase should have a concrete acceptance criterion before
the next begins.

## Data model design principles

- Keep the data model as flat as possible. A single `.jsonl` row per review comment is the
  right granularity for harvest output.
- Clustering/distillation should operate on comment text embeddings or keyword heuristics —
  decide based on what's available without heavy deps.
- Rule files are the stable interface between distill and skill phases; their schema (defined
  in `00-project.md`) must not change without a migration plan.

## Dependency decisions

- Any proposal to add a dependency beyond `httpx` to `harvest/` or `distill/` requires an
  explicit rationale and must be noted as a constraint violation if approved without update
  to `00-project.md`.

## Dashboard architecture

- The dashboard is a read-only Next.js app that consumes generated rule files and evidence
  JSON. It does not call GitHub APIs directly.
- Static generation (SSG) is preferred over SSR for the dashboard.
