# Bob prompt pack

Every prompt handed to IBM Bob on this project, in order, with status. Completed phases
keep their prompts for the record — together with `bob_sessions/` they are the audit trail
of how the project was built.

| Phase | What | Status |
|---|---|---|
| 0 | Scaffold + project rules | complete |
| 0b | Privacy rules correction | complete |
| 1 | Harvester | complete |
| 1b | Body backfill | complete |
| 2a | Batching into tranches | complete |
| 2b-map | Subagent fan-out | **validated by pilot** |
| 2b-critic | Chunked reduce | not yet validated |
| 2c | Contrast corpus | pending |
| 3 | AGENTS.md cross-check | pending |
| 4 | The Skill | pending |
| 5 | Evaluation | pending |
| 6 | Dashboard | pending |

**Target repos:** `apache/airflow` (primary, Apache-2.0), `home-assistant/core`
(contrast, Apache-2.0).

**The rule that has held all project:** Bob writes the code, you run the code. Phase 1
produced a 5,520-comment corpus for roughly zero coins because the harvester ran outside
the agent.

**Task naming.** Each prompt below gives a task title. Use it verbatim so the
`bob_sessions/` screenshots read as a narrative.

---

## Phase 0 — Scaffold and rules — COMPLETE

**Task:** `housestyle_task00_scaffold_and_rules` · **Mode:** Agent

```
Set up a new project called House Style. Run /init first to generate AGENTS.md.

Purpose, so you can make good judgement calls later: House Style mines the unwritten
code-review conventions of a specific repository out of its merged pull request history,
and emits them as an enforceable Bob Skill that reviews diffs and cites the historical
PRs justifying each comment.

Create this structure:

  harvest/          Python — GitHub API extraction (Phase 1)
  distill/          Python — batching + subagent orchestration helpers (Phase 2)
  .bob/rules/       generated rule files (Phase 2 output)
  .bob/skills/      the /house-style Skill
  eval/             evaluation harness
  dashboard/        Next.js app
  data/             gitignored — raw harvested JSON
  bob_sessions/     screenshots, committed

Then write .bob/rules/00-project.md as a custom rules file containing these
project-wide constraints:

- Python 3.11+, standard library plus `httpx` only in harvest/ and distill/.
  No pandas, no heavy deps.
- Never store GitHub usernames in any committed artifact. Hash reviewer logins with
  sha256 truncated to 12 chars and store only the hash.
- Never reproduce a review comment body verbatim in a committed artifact. Store the
  comment URL and at most a 15-word excerpt.
- Everything under data/ is gitignored. Everything under .bob/ is committed.
- Every generated rule must carry evidence: a list of PR numbers and comment URLs.
  A rule with fewer than 3 independent supporting comments is a candidate, not a rule.

Set up .gitignore and a uv-managed venv. Do not write any harvest logic yet.
```

Stating the privacy constraints as *custom rules* rather than following them by hand is
itself a demonstration of Bob 2.0's rules feature. Screenshot the rules file.

---

## Phase 0b — Privacy rules correction — COMPLETE

The Phase 0 wording above was ambiguous about *where* the no-verbatim rule applies. Bob
enforced it at the harvest layer, so `comments.jsonl` stored only 15-word excerpts and the
corpus had to be re-fetched. The constraint belongs at the artifact boundary.

**Task:** `housestyle_task00b_rules_correction` · **Mode:** Agent

```
Amend .bob/rules/00-project.md. The current rule reads as if comment bodies must never
be stored in full anywhere; that caused the harvester to discard them, and cost us a
re-fetch. Restate it as:

- data/ is gitignored working storage. Full comment bodies and full diff hunks are
  stored there in full — they are the raw material for distillation.
- Committed artifacts (.bob/rules/**, dashboard/**, eval/results.*, anything in git)
  must never reproduce a review comment verbatim. They carry the comment URL and at
  most a 15-word excerpt.
- Reviewer logins are hashed everywhere, including data/. That rule is unchanged.
```

---

## Phase 1 — Harvester — COMPLETE

**Task:** `housestyle_task01_harvest_pipeline` · **Mode:** Plan first, then Agent

```
Build harvest/harvest.py — a GitHub merged-PR review-comment extractor.

Sampling is stratified, NOT most-recent-N. These repos merge hundreds of PRs per week,
so a recent-N window would capture a single sprint and mistake it for the repo's
conventions.

Input:
  --repo owner/name
  --months 12              how far back to stratify
  --holdout 30             most recent QUALIFIED merged PRs, reserved and never sampled
  --out data/<slug>/

LISTING — one single descending pass, not per-month.
Page pullRequests(first:100, states:MERGED, orderBy:{field:CREATED_AT, direction:DESC})
via GraphQL, returning per node: number, createdAt, mergedAt, author, authorAssociation,
reviewThreads{totalCount}, files(first:20){nodes{path}}. Bucket each PR by its mergedAt
month. Stop when createdAt drops below (oldest target month - 3 months); that tail catches
long-lived PRs created before a window but merged inside it. Cache the index to
pr_index.json so a resumed run does not re-page.

Do NOT page per month restarting from the newest PR — that walks ~12k PRs twelve times
(~780 pages) and blows the 5000/hr GraphQL point budget around month two.

QUALIFY BEFORE SAMPLING. Select only PRs with reviewThreads.totalCount >= 3, then apply
an anti-domination cap: no single top_prefix may exceed 35% of a month's selected PRs.
Take all qualified PRs; do not subsample further.

DETAIL FETCH. For each selected PR, one GraphQL query returning reviewThreads(first:50)
with isResolved, isOutdated, and comments(first:20) carrying databaseId, body, diffHunk,
path, originalPosition, createdAt, authorAssociation, replyTo, author.

Resolution state, not commit-walking: store addressed as resolved | outdated | open.
Report threads_addressed/threads_total — counting each thread ONCE, since isResolved and
isOutdated are independent and frequently both true.

FILTER (record a drop count per stage):
  bots (codecov, dependabot, pre-commit, coderabbit, sonar, renovate, *[bot])
  body < 120 chars
  ^(lgtm|nit|thanks|done|\+1|ok|typo)\W*$
  self-review
  maintainer-to-maintainer ONLY when the comment is under 200 chars — on an ASF project
  committer-to-committer review is often the most substantive commentary
  PR-level gate: skip a PR yielding < 3 surviving comments, and count the comments
  discarded that way (do not drop them silently)

TIER, DON'T DROP: signal_strength = strong (resolved or outdated) | medium (has replies)
| weak (neither). Everything survives; the distillation decides.

RECORD: body (full), diff_hunk, diff_hunk_trimmed (±6 lines around the anchor), path,
position, in_reply_to_id, created_at, url, author_association, reviewer_hash, addressed,
signal_strength, pr_number.

MANIFEST (a hackathon compliance deliverable): repo, SPDX license id, sampling params,
per-month candidates_seen / candidates_with_3plus_threads / prs_selected /
prs_yielding_records / comments_accepted, prefix distribution of both the qualified pool
and the selected set, filter drop counts, holdout PR list.

RATE LIMITS: GitHub delivers GraphQL limits as HTTP 200 with errors[].type ==
"RATE_LIMITED" — a status-code handler cannot see it. Request rateLimit{remaining resetAt
cost} in every query, sleep until resetAt on RATE_LIMITED, and throttle proactively below
150 points. Log a preflight budget line at startup.

HOLDOUT: the 30 most recently merged PRs WITH reviewThreads.totalCount >= 3. An
unqualified holdout gives the evaluation no ground truth to score against.

Progress to stderr only, every 10 pages and every 10 PRs. Resumable by month.
Test with --months 2 before anything at scale.
```

Run it yourself:

```bash
python -m harvest.harvest --repo apache/airflow --months 12
python -m harvest.harvest --repo home-assistant/core --months 6
```

---

## Phase 1b — Body backfill — COMPLETE

`backfill_bodies.py` recovers full comment bodies from the REST API (one paginated call
per PR, ~15 min, no re-harvest) after the Phase 0 wording caused the harvester to store
only 15-word excerpts. Written in Bob, run outside it.

```bash
python backfill_bodies.py --repo apache/airflow
python backfill_bodies.py --repo home-assistant/core
```

Median body length should land in the 300-600 char range. Near 90 means the fill failed.

---

## Phase 2 — Tranched distillation

**Status:** 2a complete. 2b subagent prompt validated by pilot (45 candidates from 3
batches). Critic amendments below are NOT yet validated.

**Bob task titles:** `housestyle_task02a_batching`,
`housestyle_task02b_tranche1_fanout`, `housestyle_task02c_tranche2_fanout`,
`housestyle_task02d_tranche1_critic`.
**Mode:** Agent, with subagents

This is the phase that earns "orchestrate, don't autocomplete," and the only phase that
spends real coins. Say out loud in the demo that map-reduce over ~5,500 review comments
is something a single prompt structurally cannot do — it does not fit in a context window.

**Budget reality:** a ~10k-token subagent batch runs roughly 0.06-0.1 coins, so a 30-batch
map is ~2-3 and a chunked critic ~0.5-1. All three tranches land around 10-12 of 40.
Coins are not the constraint. **Unvalidated prompts run at scale are.**

### 2a — Batching — COMPLETE

`distill/batch.py` produced 3 x 30 batches of 25 from 5,520 eligible comments (30 holdout
PRs excluded), stratified by `(month, prefix)` so each tranche is a miniature of the
corpus. Zero cross-tranche duplicates. Median body 285-307 chars, p90 675-735.

Two things that had to be fixed here, recorded so they don't recur:

- **Batches carry `body`, not `body_excerpt`.** The harvester originally stored only a
  15-word excerpt; distilling from fragments would have produced confident, wrong rules.
  Bodies were recovered with `backfill_bodies.py` (~900 REST calls, no re-harvest).
- **`data/` is working storage, not a committed artifact.** Full bodies and full diff
  hunks live there. The no-verbatim rule applies to `.bob/rules/**`, `dashboard/**` and
  anything in git — those carry a URL and a <=15-word excerpt. Reviewer logins are hashed
  everywhere, including `data/`.

Batches carry `diff_hunk_trimmed` only. Records flagged `body_backfill_failed` are
excluded.

### 2b — Map: fan-out (VALIDATED — run t1 and t2 concurrently)

Run each tranche's map as its OWN Bob task, concurrently. Not one task spawning 60
subagents: separate tasks give separate session-summary screenshots for `bob_sessions/`,
and a failure in one doesn't poison the other's context. Parallel tasks are also named in
the hackathon theme, so this demonstrates the capability rather than claiming it.

**Hold tranche 3.** The map is the expensive part of a tranche, so skipping t3's map is
the only saving saturation can actually buy. The saturation curve comes from cumulative
merges, so it is identical whether maps ran in parallel or in sequence.

```
Spawn one subagent per batch in distill/tranches/t<N>/. Each subagent gets exactly one
batch file and nothing else, and returns candidate rules in this schema:

{
  "rule": "imperative sentence stating what this repo requires or forbids",
  "category": "correctness|api-design|async|testing|naming|database|security|performance|providers|docs|commit-hygiene",
  "trigger": "the diff pattern that should cause this rule to fire",
  "rationale": "why this repo cares, in the reviewers' own reasoning",
  "evidence": [{"pr": 64845, "url": "...", "excerpt": "<=15 words"}],
  "scope_paths": ["airflow-core/src/airflow/api_fastapi/core_api/routes/"]
}

1. EMIT SINGLE-INSTANCE CANDIDATES. Do NOT require a pattern to repeat within your
   batch. You see 25 of ~5,500 comments; a convention appearing once in your batch may
   appear in ten others. Emit any genuine convention you can evidence from even ONE
   comment. The critic aggregates across all batches and applies the support threshold —
   that is not your job. An empty array means "no convention here at all", not "nothing
   repeated". Do NOT emit support_count; the critic computes it.

2. REJECT UNIVERSAL SOFTWARE ADVICE. A rule must be specific to THIS repo. "Names should
   reflect what they represent", "add type hints", "avoid bare except", "handle errors"
   are generic advice or linter territory — they fire on everything and mean nothing.
   The test: could this rule have been written by someone who had never seen Airflow?
   If yes, discard it. "Cursor tokens that fail to parse must raise HTTP 400 rather than
   falling back to the raw string" passes. "Use accurate variable names" does not.

3. SKIP WHAT TOOLING CATCHES. Airflow gates review behind green static checks, so
   formatting, import order and line length are already automated and are noise here.
   Prefer project-specific judgement: architectural boundaries between airflow-core,
   providers and task-sdk; async and scheduler-loop constraints; provider compatibility;
   required test patterns; deprecation and breaking-change obligations.

4. `trigger` must be concrete enough to evaluate against a diff hunk. `scope_paths` is
   required — derive it from the paths of the comments backing the rule.

Note: batches are sorted by path, so several comments may come from the same PR. Record
the PR on each evidence entry; the critic counts distinct PRs.

Emit raw candidates to distill/candidates/t<N>/. Do NOT run the critic.
```

**Expected yield:** ~15 candidates per batch, so ~450 per tranche. Early batches skew
heavily to docs because path-sorting puts `.github/` and `airflow-core/docs/` at the
alphabetical head; batches from `api_fastapi/` onward look completely different. Across
all 30 you get the corpus's real ~41% airflow-core / ~37% providers shape.

### 2b-critic — Reduce (NOT yet validated — run on t1 only, then inspect)

Run this on tranche 1 alone. Both amendments below are untested; running them three times
before reading the output triples the cost of getting them wrong, and you would be
unpicking bad merges out of a promoted rule set rather than a candidate list.

```
Run the critic over distill/candidates/t1/.

CHUNK IT. ~450 raw candidates will not survive one task, and silent truncation drops
rules invisibly. Run:
  - critic-A over batches 001-010
  - critic-B over batches 011-020
  - critic-C over batches 021-030
  - critic-MERGE over the three outputs, applying the support threshold ONLY at this
    final stage
Report candidates in/out at every stage so I can see nothing vanished.

AMENDMENT 1 — GENERALISE scope_paths WHEN MERGING.
Subagents emit single-file scopes like ".../routes/public/task_instances.py". Phase 4
filters rules by scope intersection with a diff's touched files, so a single-file scope
almost never fires and condition B would come back near-empty. When merging a rule's
evidence, set scope_paths to the shallowest DIRECTORY prefix that still covers every
evidence path — e.g. "airflow-core/src/airflow/api_fastapi/core_api/routes/" — so the
rule can fire on sibling routes. Never leave a scope pointing at one file. Never widen
to "airflow-core/" unless the evidence genuinely spans that much.

AMENDMENT 2 — SEPARATE CONVENTIONS FROM INCIDENTS.
Some candidates are one-off bug fixes phrased as rules ("Note-content filters on
DagRunNote and TaskInstanceNote must be consistent"). Do NOT merge these into a broader
rule just because they touch the same file — that inflates a real rule's support_count
with unrelated evidence. Merge only when two candidates express the SAME expectation. A
candidate stating a one-time correction with no generalisable expectation goes to
candidates.md labelled INCIDENT, not into the promoted set.

Then, as before:
  - support_count = number of DISTINCT PRs in the merged evidence
  - promote at support_count >= 3; everything else to candidates.md
    (do NOT gate on signal_strength — 99% of Airflow threads are resolved, it admits
    everything)
  - flag overlapping-trigger conflicts into a "contested" section, never silently pick
  - stable ids: airflow-r014

Emit:
  .bob/rules/airflow-conventions.md     grouped by category
  .bob/rules/airflow-conventions.json   machine-readable
  .bob/rules/saturation.json            append {"tranche": N, "batches": 30,
     "rules_before": X, "rules_after": Y, "new_rules": Y-X, "new_rule_rate": (Y-X)/Y}

STOP and report: per-stage counts, promoted rule count, new_rule_rate, and 5 sample
promoted rules with their final scope_paths so I can check the generalisation is landing
at a useful depth.
```

**The stopping rule:** when `new_rule_rate` drops below ~10%, stop and bank the coins.
The saturation curve is itself a slide — "rule discovery saturated at N comments" answers
the scaling question in the rubric's effectiveness criterion before a judge asks it.

### 2c — Contrast corpus (one tranche only)

```
Repeat 2a and 2b for data/home-assistant-core/ with a SINGLE tranche of 20 batches,
using the validated subagent prompt and whichever critic prompt tranche 1 proved out.

This corpus exists only to supply condition C in the evaluation — a plausible-but-wrong
rule set. It does not need saturation. Emit .bob/rules/hass-conventions.json.

Do check whether signal_strength discriminates here: report the resolved/outdated/open
split. Airflow was 99% resolved, which killed the field. Home Assistant may differ.
```

---

## Phase 3 — Head-to-head against Airflow's own AGENTS.md

**Bob task title:** `housestyle_task03_agents_md_crosscheck`
**Mode:** Agent — this is the document-understanding demonstration

```
Clone apache/airflow to a separate workspace. Add AGENTS.md to .bobignore there FIRST —
we are comparing against that file, not editing it. Overwriting it would destroy the
artifact this phase exists to evaluate.

Read the repo's hand-written AGENTS.md and the contributing-docs/ directory. Treat them as
source documents to understand, not code to change.

Cross-check every rule in .bob/rules/airflow-conventions.json and label each:

  CONFIRMED   explicitly stated in AGENTS.md or contributing-docs — cite file and section
  IMPLIED     the docs gesture at it but do not state it as a requirement
  TRIBAL      nothing in the documentation covers this; it exists only in review history

Then run the comparison in reverse, which is the part that matters: for every rule in
their hand-written AGENTS.md, did we find supporting evidence in review history?
Label each UNSUPPORTED, SUPPORTED, or CONTRADICTED, with PR citations.

Write .bob/rules/airflow-agents-md-crosscheck.md with both directions and counts.
```

CONFIRMED is your correctness proof. TRIBAL is your product. **UNSUPPORTED is your
argument** — hand-written agent rules are guesses, and any of theirs that review history
doesn't back is a guess you can name. Every judge in the room maintains a hand-written
rules file.

---

## Phase 4 — The Skill

**Bob task title:** `housestyle_task04_skill_authoring`
**Mode:** Agent

```
Create a Bob Skill at .bob/skills/house-style/ that reviews a diff against mined rules.

Invocation: /house-style [--rules <path>] [--diff <ref>]
Default rules: .bob/rules/airflow-conventions.json
Default diff:  working tree vs merge-base with main

Behaviour:
1. Load rules, filtered to those whose scope_paths intersect the diff's touched files.
   Do not load 200 rules into context for a two-file diff.
2. Evaluate applicable rules against each changed hunk.
3. Every finding MUST render as:

     [airflow-r014] <file>:<line>  <category>
     <the rule, stated as an actionable request>
     Why: <rationale>
     Precedent: PR #12345, PR #12902, PR #13337  (support: 7 reviews)

   A finding with no precedent links is a bug — suppress it rather than emit it.
4. Sort by support_count descending.
5. Close with: N findings across M rules, and the highest-support rule that fired.

Also support --explain <rule-id>: prints the rule, full evidence list, and its
AGENTS.md cross-check label.

Rules stay editable markdown/JSON. A reviewer who disagrees deletes a line and commits.
Document that in the Skill README as the intended workflow.
```

**The citations are the whole design score.** Unjustified AI review comments are why teams
abandon these tools; precedent makes a finding arguable instead of oracular.

---

## Phase 5 — Evaluate

**Bob task title:** `housestyle_task05_eval_harness`
**Mode:** Plan first, then Agent

```
Build eval/run_eval.py scoring three conditions on the 30 held-out qualified PRs
(they all have >=3 review threads, so every one has real ground truth):

  A_baseline    Bob's stock /review, no mined rules
  B_housestyle  /house-style with airflow-conventions.json
  C_generic     home-assistant rules applied to Airflow PRs

C is the ablation proving repo-specificity. Both repos are large async Python
infrastructure projects, so if C scored near B we would only be detecting generic Python
smells. I expect C to score badly and I want that number in the report.

Ground truth is the real human review comments on each held-out PR. A finding matches if
it refers to the same file, within 5 lines, and is semantically equivalent.

Use IBM watsonx.ai for the equivalence judgement — Granite chat model via the watsonx.ai
API, credentials from WATSONX_API_KEY / WATSONX_PROJECT_ID / WATSONX_URL. Judge returns
MATCH / PARTIAL / NO_MATCH plus one sentence. Cache every verdict to eval/cache/ keyed by
a hash of the pair; we re-run this harness and must not re-bill inference.
Do NOT use llama-3-405b-instruct, mistral-medium-2505, or
mistral-small-3-1-24b-instruct-2503 — out of scope for this hackathon.

Report per condition: recall, precision, findings-per-PR, plus a per-category breakdown.
Write eval/results.md and eval/results.json.
```

**Expect precision to look bad**, because a real reviewer comments on a subset of what
they notice. Say so in the writeup rather than hiding it. Judges reward a team that
understands its own metric.

---

## Phase 6 — Dashboard

**Bob task title:** `housestyle_task06_dashboard`
**Mode:** Agent

```
Build dashboard/ as Next.js App Router + TypeScript, reading the generated JSON from disk
at build time. No database, no API layer.

Four views:

1. Rules — mined conventions as cards, filterable by category and cross-check label.
   Each shows the rule, support count, and evidence PRs linking out to GitHub. Make the
   TRIBAL badge visually prominent; that group is the point of the product.

2. vs AGENTS.md — their hand-written rules beside ours, with the UNSUPPORTED ones called
   out. This is the money screen.

3. Compare — Airflow rules beside Home Assistant rules by category. The takeaway in three
   seconds should be that the lists barely overlap.

4. Results — the A/B/C eval table, per-category recall bars, and the Phase 2 saturation
   curve (new_rule_rate by tranche).

Visually restrained: one accent colour, generous whitespace, monospace for rule ids and
paths. A developer tool, not a marketing site. Legible in a screen-share at 1080p, so err
large on type.
```

---

## Appendix — pilot prompts

Two prompts used to de-risk the expensive phase. Both are reusable whenever a subagent
prompt changes.

**Pilot before scaling.** Three batches costs ~0.2 coins to learn a prompt is wrong;
thirty costs ten times that, and the critic will have merged bad rules into the promoted
set where they are painful to unpick.

```
Run tranche 1 as a PILOT: spawn subagents for batch_001, batch_002 and batch_003 only.
Do NOT run the critic pass. Show me the raw candidate rules from all three and stop.
```

**Judge pilot output against these, not by eyeballing:**

- Airflow-specific, not Python-generic. "Use type hints" is a failure — that is ruff's
  job. "Provider code must not import from airflow-core internals" is a pass.
- Has a firing trigger. A rule you could not evaluate against a diff hunk is a principle,
  not a rule.
- Evidence resolves. Spot-check three URLs. A 404, or a comment that does not support the
  rule, means the extraction is hallucinating and the prompt needs tightening first.
- Not already in `AGENTS.md`. Some overlap is good and becomes the CONFIRMED bucket in
  Phase 3, but if *everything* is documented there is no product.

If two or more fail, fix the prompt and re-pilot on the next three batches.

---

## Coin discipline

Phases 0, 1, 3, 5, 6 are cheap — Bob writes ordinary code and you run it. That split is
why Phase 1 produced a 5,520-comment corpus for roughly zero coins, and it holds for the
backfill, the batcher, the eval harness and the dashboard build.

Phase 2 is the spend, at roughly 3-4 coins per tranche. All three land near 10-12 of 40,
leaving 10-15 for the Skill, eval and dashboard with real headroom.

So parallelise for wall-clock, not to conserve budget. What actually needs protecting is
running an unvalidated prompt at scale: pilot 3 batches before 30, and critic one tranche
before three. Never re-run a full tranche to fix a prompt — fix it on the next one.

---

## Cut list, in order

1. Home Assistant contrast → lose the Compare view and condition C
2. Dashboard → fall back to generated markdown rendered in the IDE
3. Precision half of the eval → report recall only

**Never cut:** the A_baseline condition (the entire impact argument), the evidence
citations in findings (the design score), or `bob_sessions/` (a submission requirement).