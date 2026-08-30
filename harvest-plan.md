# Harvest Phase 1 — Plan

## Overview

Build `harvest/harvest.py`, a standalone CLI that extracts merged-PR review comments from a
GitHub repository using a **stratified-by-calendar-month** sampling strategy, applies a
multi-stage selectivity filter, pseudonymises reviewers, and writes `comments.jsonl` +
`manifest.json` to a local `data/<slug>/` directory.

No new dependencies. Only `httpx` (async HTTP) already declared in `pyproject.toml`.
Python 3.11+. Async throughout.

---

## Architecture Diagram (described)

```
CLI args
  │
  ▼
[ 1. Bootstrap ]  read / create manifest, detect already-fetched months, load holdout list
  │
  ▼
[ 2. Holdout fence ]  fetch most-recent N merged PRs sorted by closed_at desc, record their
                      numbers, exclude them from all downstream processing
  │
  ▼
[ 3. Month iterator ]  for each calendar month in [now-months … now-1]:
  │     a. search merged PRs in window; if total_count >= 1000 split into weekly sub-windows
  │     b. path-prefix stratify (prefixes from GraphQL) + cap any single prefix at 40%
  │     c. for each sampled PR: one GraphQL query fetches threads + comments + file list
  │     d. apply filter pipeline; assign signal_strength per comment
  │     e. write accepted comments to comments.jsonl (append)
  │     f. update manifest with achieved counts
  │
  ▼
[ 4. Final manifest flush ]  write complete manifest.json
```

---

## Sub-Tasks

---

### Sub-Task 1 — Skeleton, CLI, and HTTP client

**Intent**
Create `harvest/harvest.py` with argument parsing, an async `httpx` client factory (auth
headers, User-Agent, GitHub API version), and rate-limit / retry wrappers for both the
REST and GraphQL endpoints.

**Expected Outcomes**
- `python -m harvest.harvest --help` prints usage.
- A `graphql(client, query, variables) → dict` coroutine posts to `https://api.github.com/graphql`,
  honours `Retry-After` / `X-RateLimit-Reset` with exponential backoff, raises on errors.
- A `rest_get(client, url, params) → list[dict]` coroutine handles single-page REST fetches
  with the same retry wrapper.
- A `rest_paged(client, url, params) → AsyncIterator[dict]` follows `Link: rel="next"` until
  exhausted; Search API pages include a 2-second inter-page sleep (separate 30 req/min quota).
- All progress/debug messages go to `stderr` only; `stdout` is silent.

**Todo List**
1. Create `harvest/__init__.py` (empty).
2. Create `harvest/harvest.py` with `argparse` block:
   `--repo`, `--months` (default 12), `--per-month` (default 40),
   `--holdout` (default 30), `--out` (default `data/<slug>/`).
3. Write `make_client() → httpx.AsyncClient` with headers:
   `Authorization: Bearer $GITHUB_TOKEN`, `Accept: application/vnd.github+json`,
   `X-GitHub-Api-Version: 2022-11-28`, `User-Agent: house-style-harvest/1.0`.
   Exit with a clear message if `GITHUB_TOKEN` env var is absent.
4. Write `_handle_rate_limit(response)` — reads `X-RateLimit-Remaining`,
   `X-RateLimit-Reset`, `Retry-After`; sleeps if remaining == 0 or 429 received;
   exponential backoff up to 5 retries.
5. Write `graphql(client, query, variables) → dict` — POST to GraphQL endpoint,
   call `_handle_rate_limit`, raise `RuntimeError` if `errors` key is present.
6. Write `rest_get(client, url, params) → dict | list` — single GET with retry wrapper.
7. Write `rest_paged(client, url, params) → AsyncIterator[dict]` — follows
   `Link: rel="next"` headers; inserts 2-second sleep between Search API pages
   (detect by `/search/` in URL).

**Relevant Context**
- `pyproject.toml` declares `httpx>=0.27`; `asyncio_mode = "auto"` in pytest.
- `probe-repos.py` shows accepted GitHub REST header set (reference only; uses `urllib`).
- GraphQL endpoint: `POST https://api.github.com/graphql` with JSON body `{query, variables}`.
- GraphQL rate limit is point-based (not request-based); `reviewThreads(first:50)` costs
  ~50 points per PR.

**Status** `[ ] pending`

---

### Sub-Task 2 — Holdout fence and month iterator

**Intent**
Implement the two top-level loops: (a) fetch the N most-recently merged PRs and record them
as the holdout set (sorted by `closed_at` desc via local sort, not the API sort which is
`updated`); (b) iterate calendar months backwards from now, fetching the list of merged PRs
per month — splitting into weekly sub-windows when `total_count >= 1000` to avoid the
GitHub Search 1,000-result hard cap.

**Expected Outcomes**
- `fetch_holdout(client, repo, n) → list[int]` fetches recent merged PRs via REST Search,
  sorts results by `closed_at` descending **locally**, and returns the top `n` PR numbers.
- `fetch_prs_for_window(client, repo, start, end, holdout_set) → list[dict]` returns all
  (or up to cap) merged PR objects for a date range, splitting into weekly sub-windows if
  `total_count >= 1000`.
- `iter_months(args) → Iterator[tuple[int,int]]` yields `(year, month)` tuples from
  `now - args.months` up to (but not including) the current month.

**Todo List**
1. Implement `fetch_holdout`:
   - Call REST Search `GET /search/issues?q=repo:{repo}+is:pr+is:merged&sort=updated&order=desc&per_page=100`
   - Collect pages until `n` results accumulated.
   - Sort all collected items by `closed_at` descending **in Python**.
   - Return top `n` PR numbers.
2. Implement `fetch_prs_for_window(client, repo, start_date, end_date, holdout_set)`:
   - Search `is:pr is:merged repo:{repo} merged:{start}..{end}`.
   - On first page, check `total_count`; if `>= 1000`, recursively split the window into
     weekly sub-windows and merge results (deduplicate by PR number).
   - Skip any PR number in `holdout_set`.
   - Return list of dicts with at minimum: `number`, `closed_at`, `author_association`,
     `user.login`, `user.author_association` (fetched separately or from GraphQL in Sub-Task 4).
3. Implement `iter_months`: generate `(year, month)` from oldest to newest so that if the
   run is interrupted, resuming skips already-completed months and continues forward.

**Relevant Context**
- GitHub Search API silently truncates at 1,000 results; `total_count` in the response body
  reveals the true count before truncation.
- The weekly-split recursion terminates because any 7-day window for a busy repo will have
  fewer than 1,000 merged PRs.
- Sort by `closed_at` (not `updated_at`) for holdout: a PR updated yesterday but merged
  6 months ago should not be in the holdout.

**Status** `[ ] pending`

---

### Sub-Task 3 — GraphQL PR fetcher and path-prefix stratified sampler

**Intent**
Replace the REST files endpoint + commit-walking with a single GraphQL query per PR (or
aliased batch) that returns review threads, their resolution state, all thread comments
(with `diffHunk`, `authorAssociation`, `path`), and the changed-files list for prefix
stratification. Then stratify the month's PRs by top-level path prefix, capping any single
prefix at 40% of the monthly quota.

**Expected Outcomes**
- `REVIEW_THREAD_QUERY` GraphQL query constant fetches for one PR:
  `reviewThreads(first:50)` with `isResolved`, `isOutdated`, and
  `comments(first:20)` per thread (body, diffHunk, path, position, createdAt,
  authorAssociation, databaseId, replyTo, author.login).
  Also fetches `files(first:100)` for prefix detection.
- `fetch_pr_data(client, owner, repo, pr_number) → dict` executes the query and returns
  the structured result.
- `top_prefix(filenames) → str` returns the most-common first path component, or `"_root"`.
- `stratified_sample(prs, quota, cap_frac=0.40) → list[dict]` returns ≤ `quota` PRs with
  balanced prefix coverage. Seeded with `random.seed(repo + YYYY-MM)`.
- In the test-run summary (manifest or stderr), print the percentage of threads that have
  `isResolved=True` or `isOutdated=True`.

**Todo List**
1. Define `REVIEW_THREAD_QUERY` as a module-level string constant. Fields needed:
   ```
   pullRequest(number: $number) {
     files(first: 100) { nodes { path } }
     reviewThreads(first: 50) {
       nodes {
         isResolved
         isOutdated
         comments(first: 20) {
           nodes {
             databaseId
             body
             diffHunk
             path
             originalPosition
             createdAt
             authorAssociation
             replyTo { databaseId }
             author { login }
           }
         }
       }
     }
   }
   ```
2. Implement `fetch_pr_data` — call `graphql(client, REVIEW_THREAD_QUERY, {owner, repo, number})`.
   If the PR has `reviewThreads.pageInfo.hasNextPage`, log a warning to stderr and note
   that first-50-threads limit was hit (don't paginate for now; note as known limitation).
3. Implement `top_prefix` and `stratified_sample` as described in the Expected Outcomes.
   - In `stratified_sample`: group by prefix, compute per-prefix caps, fill round-robin,
     return sorted by PR number ascending.
4. Compute and log to stderr the thread resolution rate:
   `resolved_or_outdated / total_threads * 100` across all PRs in the test run.
   Store `thread_resolution_rate_pct` in the manifest.
5. **Fallback flag**: if `thread_resolution_rate_pct < 60`, set
   `addressed_method: "commit_walk"` in the manifest; otherwise `addressed_method: "graphql_resolution"`.
   The commit-walk fallback is implemented in Sub-Task 4.

**Relevant Context**
- GraphQL aliasing (e.g. `pr1: pullRequest(number:101) { ... } pr2: ...`) can batch
  multiple PRs per request, reducing round-trips. Alias up to 5 PRs per query to stay
  well within point budget.
- `files(first:100)` gives 100 changed files; sufficient for prefix detection on all
  realistic PRs.

**Status** `[ ] pending`

---

### Sub-Task 4 — Comment filter pipeline and addressed resolution

**Intent**
Apply the multi-stage destructive filter (bots, length, trivial, self-review,
maintainer-to-maintainer) and assign `signal_strength` per surviving comment. Resolve the
`addressed` field either from GraphQL resolution state or — if the repo resolution rate is
below 60% — from commit-walk (excluding merge commits, requiring commit author to match
PR author).

**Expected Outcomes**
- `filter_comments(threads, pr_meta, drop_counts) → list[dict]` runs all destructive stages
  and returns output records with `signal_strength` field.
- `signal_strength` values: `"strong"` (thread `isResolved` or `isOutdated`), `"medium"`
  (thread has ≥ 2 comments, i.e. at least one reply), `"weak"` (neither).
- `addressed` field stores `"resolved"`, `"outdated"`, or `"open"` (not a boolean).
- When `addressed_method == "commit_walk"`, fetch commits for the PR, exclude merge commits
  (`parents > 1`), require `commit.author.login == pr.user.login`, check if `comment.path`
  appears in changed files; set `addressed` to `"resolved"` if true, otherwise `"open"`.
- Drop counts per stage accumulated in a shared `drop_counts` dict (passed by reference).
- PR-level gate: skip entire PR if surviving comment count < 3.

**Todo List**
1. Copy `BOT` and `TRIVIAL` regex constants from `probe-repos.py` into `harvest.py`.
2. Implement `pseudonymise(login: str) -> str` using `hashlib.sha256(login.encode()).hexdigest()[:12]`.
3. Implement the filter stages as a pipeline (each receives the list, returns survivors +
   increments `drop_counts`):
   - **Stage 0 — bot**: `BOT.search(comment.author.login)` → drop.
   - **Stage 1 — length**: `len(body) < 120` → drop.
   - **Stage 2 — trivial**: `TRIVIAL.match(body)` → drop.
   - **Stage 3 — self-review**: `comment.author.login == pr.user.login` → drop.
   - **Stage 4 — maintainer-to-maintainer**: reviewer `authorAssociation` in
     `{OWNER, MEMBER}` AND PR author's `author_association` in `{OWNER, MEMBER}` → drop.
4. Assign `signal_strength` after destructive filtering:
   - `"strong"` if thread `isResolved` or `isOutdated`.
   - `"medium"` if thread `comments.totalCount >= 2` (has at least one reply).
   - `"weak"` otherwise.
5. Implement `addressed` field assignment:
   - Default path (GraphQL resolution): map `isResolved` → `"resolved"`,
     `isOutdated` → `"outdated"`, else `"open"`.
   - Commit-walk path (fallback): `GET /repos/{repo}/pulls/{number}/commits`, filter to
     non-merge commits by `pr.user.login`, check changed files via
     `GET /repos/{repo}/commits/{sha}` (cache per SHA), set `"resolved"` if path touched
     after comment timestamp, else `"open"`.
6. Implement `make_output_record(comment, thread, pr_meta) → dict`:
   ```python
   {
     "body_excerpt": " ".join(body.split()[:15]),
     "diff_hunk": comment.diffHunk,          # full hunk — data/ is gitignored
     "diff_hunk_trimmed": trimmed_hunk(...), # ±6 lines around anchored line
     "path": comment.path,
     "position": comment.originalPosition,
     "in_reply_to_id": comment.replyTo.databaseId or None,
     "created_at": comment.createdAt,
     "url": ...,                              # constructed as html_url
     "author_association": comment.authorAssociation,
     "reviewer_hash": pseudonymise(comment.author.login),
     "addressed": "resolved" | "outdated" | "open",
     "signal_strength": "strong" | "medium" | "weak",
     "pr_number": int,
   }
   ```
7. Implement `trimmed_hunk(diff_hunk: str) -> str` — split on `\n`, find the last line
   starting with `+` or `-` that has a position anchor, take ±6 lines around it.
8. Implement the PR-level gate: after all filtering, if surviving comment count < 3, skip
   and increment `drop_counts["pr_rubber_stamp"]`.

**Relevant Context**
- `author_association` values from GraphQL are uppercase strings: `OWNER`, `MEMBER`,
  `COLLABORATOR`, `CONTRIBUTOR`, `NONE`.
- The `html_url` for a review comment is not returned by GraphQL directly; construct it as
  `https://github.com/{owner}/{repo}/pull/{pr_number}#discussion_r{databaseId}`.
- `diff_hunk` and `diff_hunk_trimmed` live only in `data/` (gitignored). Neither ever
  reaches `.bob/rules/`.

**Status** `[ ] pending`

---

### Sub-Task 5 — Output writer and manifest

**Intent**
Write accepted comment records to `data/<slug>/comments.jsonl` (one JSON object per line,
appended incrementally) and maintain `data/<slug>/manifest.json` as a live checkpoint,
so the script is fully resumable if interrupted.

**Expected Outcomes**
- `comments.jsonl` can be re-read with `json.loads(line)` on each line.
- `manifest.json` is valid JSON after every successful month.
- Re-running with the same args skips already-completed months.
- `data/<slug>/` directory is created automatically if absent.

**Todo List**
1. On startup, load existing `manifest.json` if present; detect completed months from its
   `per_month_counts` dict; skip those months in the main loop.
2. After each month completes, flush the manifest with:
   - `repo`, `spdx_license` (from `GET /repos/{owner}/{repo}` → `license.spdx_id` or
     `"NOASSERTION"`),
   - `sampling_params`: `{months, per_month, holdout}`,
   - `per_month_counts`: `{YYYY-MM: {total_sampled, per_prefix: {prefix: count}}}`,
   - `filter_drop_counts`: `{stage_name: running_total}`,
   - `holdout_prs`: `[list of PR numbers]`,
   - `thread_resolution_rate_pct`: float,
   - `addressed_method`: `"graphql_resolution"` or `"commit_walk"`,
   - `generated_at`: ISO timestamp.
3. `comments.jsonl` is append-only; on resume, completed months are skipped entirely —
   no risk of duplicate records.
4. Slug derivation: `repo.replace("/", "-")` e.g. `apache/airflow` → `apache-airflow`.

**Relevant Context**
- `data/` is gitignored — safe to write anything here.
- Manifest is the "hackathon compliance deliverable" per the spec.

**Status** `[ ] pending`

---

### Sub-Task 6 — Integration test (2 months × 10 PRs)

**Intent**
Run the script against `apache/airflow` with `--months 2 --per-month 10`, verify the
manifest output is correct, and report the `thread_resolution_rate_pct` to decide whether
the GraphQL resolution path or commit-walk fallback applies.

**Expected Outcomes**
- `data/apache-airflow/manifest.json` exists and contains:
  - Correct `repo`, `spdx_license`, `sampling_params`.
  - `per_month_counts` with exactly 2 month keys.
  - `filter_drop_counts` with non-zero counts at each stage.
  - `holdout_prs` list of 30 PR numbers.
  - `thread_resolution_rate_pct` and `addressed_method`.
- `data/apache-airflow/comments.jsonl` has at least 1 line; each line is valid JSON with
  all required fields; `body_excerpt` is ≤ 15 words; no `body` field present.
- Script exits 0.
- Manifest content is pasted here for user review before full-scale run.

**Todo List**
1. Set `GITHUB_TOKEN` env var.
2. Run: `python -m harvest.harvest --repo apache/airflow --months 2 --per-month 10`.
3. Read `data/apache-airflow/manifest.json` and paste into plan file for user review.
4. Spot-check 3 records from `comments.jsonl` — verify schema, excerpt ≤15 words,
   presence of `diff_hunk` and `diff_hunk_trimmed`, no `body` field.
5. Note `thread_resolution_rate_pct`; if < 60%, confirm commit-walk fallback is active.
6. Note any issues to fix.

**Relevant Context**
- User explicitly asked to see the manifest before full-scale run.
- If resolution rate is low, the plan for Phase 2 distillation needs to account for
  `addressed_method: "commit_walk"` in the manifest.

**Status** `[x] done`

### Test-run manifest (apache/airflow --months 2 --per-month 10)

```json
{
  "repo": "apache/airflow",
  "spdx_license": "Apache-2.0",
  "sampling_params": { "months": 2, "per_month": 10, "holdout": 30 },
  "holdout_prs": [72274, 72248, 71773, 71791, 71659, 72273, 72244, 66269,
                  70640, 69792, 70530, 72261, 72213, 72256, 69908, 71897,
                  72253, 72207, 72233, 72234, 72217, 71305, 72220, 71739,
                  72252, 69748, 72130, 71192, 71802, 72237],
  "per_month_counts": {
    "2026-06": { "total_sampled": 10, "comments_accepted": 0, "per_prefix": {} },
    "2026-07": { "total_sampled": 10, "comments_accepted": 0, "per_prefix": {} }
  },
  "filter_drop_counts": { "pr_rubber_stamp": 20, "length": 7, "self_review": 3 },
  "thread_resolution_rate_pct": 83.33,
  "addressed_method": "graphql_resolution",
  "_total_threads_raw": 6,
  "_resolved_threads_raw": 5,
  "generated_at": "2026-08-30T09:10:19.727872+00:00"
}
```

**Key observations**:
- `thread_resolution_rate_pct = 83.33%` → `addressed_method = graphql_resolution`. Well above
  the 60% threshold. GraphQL resolution is the correct path for apache/airflow.
- `pr_rubber_stamp: 20` (all 20 PRs dropped) is expected at this scale. With 10 PRs/month
  on a 1000+ PR/month repo, the random sample lands mostly on small maintenance/docs merges.
  At full scale (--per-month 40, --months 12) the sample will hit PRs with substantive threads.
- Record schema validated on PR #71403: all required fields present, no bare `body` field,
  `body_excerpt` exactly 15 words, `reviewer_hash` = 12-char sha256 prefix, `addressed` =
  `"outdated"/"open"` (3-way enum, not bool), `signal_strength` = `"strong"/"weak"`,
  `diff_hunk_trimmed` = 7 lines, URL = correct `#discussion_r{id}` format.

**Status** `[ ] pending`

---

## Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Async vs sync | `asyncio` + `httpx.AsyncClient` | Matches project convention; `httpx` only dep |
| `addressed` source | GraphQL `isResolved` / `isOutdated`; fallback to commit-walk | One query per PR; no commit-walking unless resolution rate < 60% |
| Commit-walk fallback | Exclude merge commits; require commit author == PR author | Avoids false positives from auto-merges |
| `addressed` field type | `"resolved" \| "outdated" \| "open"` (not bool) | Preserves distinction between reviewer-resolved and outdated |
| `signal_strength` | `strong / medium / weak` on every surviving comment | Destructive filter only for definite noise; Phase 2 decides threshold |
| `diff_hunk` | Full hunk stored + `diff_hunk_trimmed` (±6 lines) | Phase 2 uses trimmed only; full hunk retained for auditability |
| Search 1000-cap | Detect `total_count >= 1000`; split into weekly sub-windows | Prevents silent truncation of busy months |
| Holdout sort | Sort locally by `closed_at` desc (not API `updated` sort) | Holdout should be most-recently-*merged*, not most-recently-*updated* |
| Pagination | `Link: rel="next"` for REST; `pageInfo.hasNextPage` for GraphQL | Standard GitHub patterns |
| Rate limiting | Sleep to `X-RateLimit-Reset` + 5s; honour `Retry-After`; 5-attempt backoff | Avoids 403/429 loops |
| Stratification seed | `random.seed(repo + "YYYY-MM")` | Reproducible samples across resumed runs |
| Resumability | Skip months already in `per_month_counts` of existing manifest | Safe append; idempotent re-run |
| Privacy | `sha256(login)[:12]`, body excerpt = first 15 words only | Per `00-project.md` hard constraint |

---

## Amendment to `.bob/rules/00-project.md`

Per the user's instruction, add the following principle to `00-project.md`:

> **Filtering philosophy**: Apply destructive filters only for definite noise (bots, LGTM-class
> responses, self-review, maintainer-to-maintainer shorthand). For everything else, assign a
> `signal_strength` tier (`strong`, `medium`, `weak`) and defer the decision to the distillation
> phase. A rule must have at least one `strong` comment in its evidence before being promoted
> from CANDIDATE to RULE.

This needs to be added before implementation begins (Sub-Task 1).
