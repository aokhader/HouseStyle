# House Style — Ask Mode Context

Extends the root `AGENTS.md` with guidance for answering questions about the project.

## Key concepts to understand

- **Harvest**: fetching merged PR metadata + review comments via GitHub REST API.
- **Distill**: grouping comments by inferred convention, scoring confidence, writing rule files.
- **Skill**: a Bob Skill (`/house-style`) that reviews a diff against the generated rules.
- **Evidence threshold**: a pattern needs ≥ 3 independent supporting comments to become a Rule;
  below that it is a Candidate.

## Privacy model

Hash = `sha256(github_login)[:12]`. Comment bodies are never stored verbatim; only a ≤15-word
excerpt and the permalink URL are committed.

## Target repositories

`home-assistant/core` and `apache/airflow` were selected because they have very high human
review rates, long median comment lengths, and over 2 000 merged PRs per month — providing
excellent training signal. See `projectReadme.md` for the full selection table.

## Common questions

- *Why no pandas?* — keeps the tool installable anywhere without a C-extension build chain.
- *Why httpx?* — async-first, minimal, well-typed; fits the single-dep constraint.
- *Why store only excerpts?* — avoids reproducing copyrighted or personally identifiable
  reviewer prose in a committed artifact.
