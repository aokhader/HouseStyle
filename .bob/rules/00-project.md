# House Style — Project-Wide Constraints

These rules apply to every mode and every phase of the project.

## Language & dependencies

- All code in `harvest/` and `distill/` must target **Python 3.11+**.
- The only permitted external dependency in `harvest/` and `distill/` is **`httpx`** (async HTTP).
  No `pandas`, no `numpy`, no ML/data-science libs, no heavy frameworks.
- `eval/` and `dashboard/` may introduce their own dependencies, declared separately.

## Privacy — GitHub identity

- **Never store a GitHub username** (login, display name, or any derivative) anywhere — including
  `data/`. This applies to committed artifacts, rule files, Skill files, dashboard assets, and
  raw harvested JSON alike.
- Reviewer identity must be pseudonymised at harvest time: compute `sha256(login)`, take the
  first 12 hex characters, and store only that hash.
- Example: `alice` → `sha256("alice")[:12]` → `"2bd806c97f09"`.

## Privacy — comment content

`data/` is gitignored working storage. Full comment bodies and full diff hunks are stored there
in full — they are the raw material for distillation and must be preserved faithfully.

Committed artifacts (`.bob/rules/**`, `dashboard/**`, `eval/results.*`, and anything else tracked
by git) must never reproduce a review comment verbatim. They carry only the comment URL and an
excerpt of **at most 15 words** (truncated mid-sentence is fine).

## Data storage

- Everything under `data/` is **gitignored**. Raw harvested JSON (including full comment bodies
  and diff hunks) never leaves the local machine unless the developer explicitly decides otherwise.
- Everything under `.bob/` (rules, skills, mode AGENTS files) is **committed** and version-controlled.

## Filtering philosophy

Apply destructive filters only for definite noise (bots, LGTM-class responses, self-review,
maintainer-to-maintainer shorthand). For everything else, assign a `signal_strength` tier
(`strong`, `medium`, `weak`) and defer the decision to the distillation phase.

- `strong` — thread was marked resolved or outdated by a reviewer (`isResolved` or `isOutdated`).
- `medium` — thread has at least one reply (≥ 2 comments in the thread).
- `weak` — standalone comment with no resolution signal.

A rule must have at least one `strong` comment in its evidence before being promoted from
CANDIDATE to RULE.

## Evidence requirements for rules

- Every generated rule file must carry an `## Evidence` section listing:
  - PR numbers (e.g. `#12345`)
  - Comment URLs (GitHub permalink form)
- A pattern supported by **fewer than 3 independent supporting comments** is classified as a
  **candidate rule** (prefix the file or section with `CANDIDATE:`), not an enforceable rule.
- "Independent" means from different PR authors or reviewers (by pseudonymised hash), not just
  different comments in the same review thread.
- At least one supporting comment must have `signal_strength: strong` for the pattern to be
  promoted from CANDIDATE to RULE.

## Rule file format

Each rule file in `.bob/rules/` must follow this structure:

```
# <Rule title>

## Pattern
<One-paragraph description of the convention, written in present tense.>

## Rationale
<Why reviewers enforce this — inferred from comment context.>

## Evidence
- PR #NNNNN — <15-word excerpt> — <comment URL>
- PR #NNNNN — <15-word excerpt> — <comment URL>
- ...

## Status
RULE | CANDIDATE
```

## Naming

- Rule files: `NN-<slug>.md` where `NN` is zero-padded (e.g. `01-type-annotations.md`).
- Candidate rules: same naming, with `CANDIDATE:` in the `## Status` section.
- `00-project.md` (this file) is reserved for project-wide constraints.

## What Bob should do with these rules

When acting as the `/house-style` reviewer Skill, Bob must:
1. Read all files in `.bob/rules/` with status `RULE` as enforceable conventions.
2. For each finding in a diff, cite the rule file and at least one PR number from its evidence.
3. Treat `CANDIDATE:` rules as advisory only — mention them but do not block.
