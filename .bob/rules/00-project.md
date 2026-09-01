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

**Amendment (Phase 2b).** The `strong`-comment promotion gate below is **disabled**, and
`signal_strength` is recorded on every rule's evidence rather than gated on. Measured on
the harvested corpus, `apache/airflow` is 98.8% `strong` (5,454 of 5,520) — the tier
admits essentially everything and discriminates nothing, so gating on it would be a filter
that reads as rigour without doing any work. It is not universal: `home-assistant/core` is
78.1% `strong`, 12.7% `weak`, 9.2% `medium`, where the tier does carry information. The
field stays in the schema and in the emitted rules; whether to gate on it is a per-repo
decision, and for Airflow the answer is no.

Support is instead the number of **distinct PRs** in a rule's merged evidence, which
does discriminate.

## Evidence requirements for rules

- Every generated rule file must carry an `## Evidence` section listing:
  - PR numbers (e.g. `#12345`)
  - Comment URLs (GitHub permalink form)
- A pattern supported by **fewer than 3 distinct PRs** is classified as a **candidate
  rule** and is written to `<slug>-candidates.md`, not to the enforceable rulebook.
- "Independent" means from different PRs, not just different comments in the same review
  thread. `distinct_reviewers` (by pseudonymised hash) is recorded alongside, so a rule
  supported by three PRs that one reviewer raised alone is visible as such.
- Support counts are computed by `distill/critic.py` from the harvested corpus, never
  asserted by a language model. A subagent emits clusters of candidate keys; the code
  resolves each key's evidence against `comments.jsonl` and counts. Evidence whose URL
  does not resolve to a real harvested comment is **dropped**, not counted.

## Rule file format

**Amendment (Phase 2b).** One file per rule was the Phase 0 plan, written before we knew
the yield. A tranche promotes on the order of a hundred rules, and a hundred `NN-slug.md`
files is not a rulebook anyone reads or edits. The generated rulebook is emitted per repo
instead, by `distill/critic.py`:

| File | Contents |
|---|---|
| `<slug>-conventions.md` | promoted rules, grouped by category, evidence in a `<details>` block |
| `<slug>-conventions.json` | the same rules, machine-readable — what the Skill loads |
| `<slug>-candidates.md` | below-threshold candidates, and incidents |
| `<slug>-ids.json` | rule-text → stable id map, so ids survive a re-run |
| `saturation.json` | new-rule rate by tranche |
| `<slug>-agents-md-crosscheck.{md,json}` | Phase 3, both directions |

Each rule section carries the rule as an imperative sentence, its `trigger`, its
rationale, `scope_paths`, support counts, and an evidence list of PR permalinks with
≤15-word excerpts.

`00-project.md` (this file) is hand-written and is not generated. Generated files are
safe to delete and regenerate; edits to them are the user's rulebook decisions and are
tracked in git.

## Naming

- Generated rulebooks: `<slug>-conventions.{md,json}`, where `<slug>` names the mined
  repository (`airflow`, `hass`). Superseded by the amendment above; the per-rule
  `NN-<slug>.md` scheme is not used.
- Rule ids: `<slug>-rNNN`, zero-padded to three digits, assigned by `distill/critic.py`
  and stable across re-runs via `<slug>-ids.json`. Ids appear in review findings and in
  the evaluation, so they must not be renumbered.
- `00-project.md` (this file) is reserved for project-wide constraints.

## What Bob should do with these rules

When acting as the `/house-style` reviewer Skill, Bob must:

1. Load rules from `<slug>-conventions.json`, **filtered to those whose `scope_paths`
   intersect the diff's changed files**. Never load the whole rulebook for a small diff —
   rules that cannot apply are where false positives come from.
2. Cite precedent on every finding: the rule id and the PR numbers from its evidence.
   **A finding with no precedent is suppressed, not emitted.** This is enforced by
   `render` in `scripts/house_style.py` rather than left to judgement.
3. Treat entries in `<slug>-candidates.md` as advisory only — they did not clear the
   support threshold. Never emit them as findings.
4. Never fire a rule because the diff touches its scope. Scope narrows the candidate set;
   the rule's `trigger` decides.
