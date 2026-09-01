# apache/airflow — mined rules vs the hand-written AGENTS.md

Generated 2026-09-01T04:59:46.602802+00:00.

Two questions, and the second is the interesting one.

## Forward — is each mined rule written down anywhere?

| Label | Rules | Share | Meaning |
|---|---|---|---|
| CONFIRMED | 6 | 43% | stated in AGENTS.md or contributing-docs |
| IMPLIED | 3 | 21% | the docs gesture at it, without requiring it |
| TRIBAL | 5 | 36% | documented nowhere; lives only in review history |

CONFIRMED is the correctness check: where the project documented a convention, the mining found it independently from review comments alone. **TRIBAL is the product** — conventions this project enforces in review and has never written down.

## Reverse — does review history support each hand-written rule?

| Label | Rules | Share |
|---|---|---|
| SUPPORTED | 14 | 35% |
| UNSUPPORTED | 24 | 60% |
| CONTRADICTED | 2 | 5% |

**UNSUPPORTED is the argument.** A hand-written agent rules file is a set of guesses about what a team enforces, written by whoever had the energy to write it. These are the entries that a year of review history does not back. They may still be right — a rule so well obeyed it never needs stating leaves no trace either — but nobody could tell you which without this comparison.

### Hand-written rules review history does not support

- **Do not spell out 'Directed Acyclic Graph' except for historical context.** — AGENTS.md § Naming  
  No mined rule or below-threshold candidate touches the expanded spelling; the Dag/DAG casing half of the same section produced airflow-r010, so reviewers clearly do police the section — this specific clause simply never came up, which reads like a rule nobody violates.
- **The Scheduler reads serialized Dags and must never run user code.** — AGENTS.md § Architecture Boundaries (3)  
  No mined rule or candidate covers the scheduler/user-code boundary; this is an invariant enforced by software guards and by where the code physically lives, so a violation would be a design-level PR rather than a line a reviewer flags — the well-obeyed case, not evidence the rule is wrong.
- **Workers execute tasks via the Task SDK and communicate with the API server through the Execution API — they must never access the metadata DB directly.** — AGENTS.md § Architecture Boundaries (4)  
  Nothing in the mined set enforces the worker/metadata-DB boundary; the nearest evidence is below-threshold candidate airflow-r086 (support 2, #59883, #53389), which polices a different boundary — airflow-core must not import Task SDK internals.
- **Always format and check Python files with ruff immediately after writing or editing them (uv run ruff format <file>, uv run ruff check --fix <file>).** — AGENTS.md § Coding Standards  
  No mined rule or candidate; ruff runs as a prek hook and in CI, so unformatted code is fixed before a human reviewer sees it — a rule whose enforcement layer keeps it out of review history.
- **No assert in production code.** — AGENTS.md § Coding Standards  
  No mined rule or candidate flags an assert in production code, despite the rule also being spelled out in contributing-docs/05_pull_requests.rst § Don't Use Asserts Outside Tests — this looks like a long-settled convention contributors already follow.
- **Comment sparingly — code says what, comments say why. No narrating comments that restate the next line, no multi-line prose padding logic, no repeating the same rationale at several sites.** — AGENTS.md § Coding Standards  
  No mined rule asks anyone to delete a redundant comment; the mined history runs the other way in tone but not in substance — several below-threshold candidates (airflow-r260, r235, r392, r202, r185) demand an explanatory why-comment at a non-obvious site, which is the half of this rule AGENTS.md endorses. Reviewers evidently police missing rationale, not over-commenting.
- **Guard heavy type-only imports (e.g. kubernetes.client) with TYPE_CHECKING in multi-process code paths.** — AGENTS.md § Coding Standards  
  No mined rule or candidate about import cost in multi-process paths; candidate airflow-r018 (support 1) mentions a TYPE_CHECKING import but for annotation correctness, not startup weight.
- **Translate domain-layer exceptions to HTTPException at FastAPI route boundaries — catch e.g. ValueError from domain code and re-raise as 404 for not-found or 400 for invalid input, rather than letting it become a 500.** — AGENTS.md § Coding Standards  
  No mined rule covers exception translation at route boundaries; the nearest is below-threshold candidate airflow-r141 (support 2, #64845, #64610), which requires HTTP 400 for an invalid query parameter instead of a silent fallback — the same status-code instinct, but about validation rather than about where domain exceptions get caught.
- **Bulk DELETE/UPDATE in the scheduler loop or any synchronous interval task must be batched with LIMIT and committed between batches, never issued as one unbounded bulk write, and the filter columns must be indexed.** — AGENTS.md § Coding Standards  
  No mined rule or candidate covers unbounded bulk writes or lock-hold time in the scheduler loop; below-threshold candidate airflow-r244 (support 2) is about the opposite failure — per-row queries inside a loop — so it is not evidence for this one.
- **Name functions and methods with action verbs (get_, extract_, find_, compute_, build_); avoid noun-only names like _serialize_keys or _base_names. Predicates (is_, has_) are the exception.** — AGENTS.md § Coding Standards  
  Nothing in the mined set or the naming candidates (airflow-r236, r237, r238, r239, r240, r393, r394) is about verb-vs-noun naming for callables; every mined naming comment is about the semantics a specific name carries, not its part of speech.
- **Apache License header on all new files.** — AGENTS.md § Coding Standards  
  No mined evidence — AGENTS.md itself says prek enforces it, so a missing header is fixed automatically before review; the well-obeyed/auto-fixed case.
- **Whenever you change a rule in dev/breeze/src/airflow_breeze/utils/selective_checks.py, update dev/breeze/doc/ci/04_selective_checks.md and add or adjust tests in dev/breeze/tests/test_selective_checks.py in the same PR.** — AGENTS.md § Coding Standards  
  No mined rule requires the selective-checks doc/test to move with the code; below-threshold candidate airflow-r355 (support 1, #67012) touches selective_checks.py content (a missing file-group pattern) but says nothing about keeping its documentation in sync.
- **Do not add tests for pre-existing logic that was already present before the PR, and do not test standard-library or third-party functions — target exactly 100% coverage of what the PR changes, no more.** — AGENTS.md § Testing Standards  
  The mined history is entirely about missing tests, never about surplus ones; the closest signal is incident airflow-r362 (#64503), where a reviewer objected to an unrelated test-tightening hunk on scope grounds rather than coverage grounds.
- **Use pytest patterns, not unittest.TestCase.** — AGENTS.md § Testing Standards  
  No mined rule or candidate; the migration away from unittest.TestCase appears to be complete enough in the reviewed window that no PR reintroduced it.
- **Prefer @mock.patch decorators over with mock.patch(...) context managers for patching.** — AGENTS.md § Testing Standards  
  No mined rule or candidate expresses a preference between the decorator and context-manager forms; mined mock feedback is about specs (airflow-r014) and call assertions (candidate airflow-r402), not patch style.
- **Use conf_vars (tests_common.test_utils.config) for Airflow config overrides — as a decorator when the value is fixed, as a context manager when it varies via parametrize.** — AGENTS.md § Testing Standards  
  No mined rule or candidate mentions conf_vars; below-threshold candidate airflow-r139 (support 2) is about reading config with conf.getboolean in production code, not about overriding config in tests.
- **Use @pytest.mark.db_test for tests that require database access.** — AGENTS.md § Testing Standards  
  No mined rule or candidate mentions the marker; a missing db_test marker surfaces as a CI failure in the no-db test run rather than as a review comment.
- **Test location mirrors source: airflow/cli/cli_parser.py maps to tests/cli/test_cli_parser.py.** — AGENTS.md § Testing Standards  
  No mined rule about mirroring directories; the nearest is below-threshold candidate airflow-r086 (support 2, #59883, #53389), which places tests in the distribution that owns the code under test — the same instinct at distribution granularity, not the file-path mirroring rule.
- **Write commit messages focused on user impact, not implementation details.** — AGENTS.md § Commits and PRs  
  No mined rule covers commit-message content; the mined corpus is line-level review comments on merged PRs, where commit subjects are squashed at merge and rarely draw a comment — an evidence-source gap more than a signal about the rule.
- **Do not use Conventional Commits prefixes (feat:, fix:, chore:, docs:, refactor:) in commit subjects or PR titles; use the imperative mood and plain prose (area tags like UI: / API: / Helm: are fine).** — AGENTS.md § Commits and PRs  
  No mined rule; AGENTS.md itself notes a commit-msg prek hook (check-no-conventional-commit-message) plus a CI check rejects these, so violations never reach a reviewer's comment.
- **The commit message body must describe why the change is made, never what it does.** — AGENTS.md § Commits and PRs  
  No mined rule or candidate; same evidence-source gap as commit-message content generally — the mining looked at diff review comments, not at commit bodies.
- **Never add a Co-Authored-By trailer naming the agent as co-author of a commit.** — AGENTS.md § Commits and PRs  
  No mined rule or candidate; trailers are not part of the reviewed diff, so review history could not have caught this either way.
- **Never edit generated files by hand when a generation workflow exists, and never edit the .apache-magpie snapshot directly — adopter-specific changes go in .apache-magpie-overrides/.** — AGENTS.md § Boundaries / § apache-magpie framework  
  No mined rule or candidate about hand-edited generated files; the generated artifacts (the OpenAPI spec, provider dependency blocks) are regenerated by prek hooks that overwrite manual edits, so the mistake corrects itself before review.
- **Never commit secrets, credentials, or tokens.** — AGENTS.md § Boundaries  
  No mined rule about committed secrets; the nearest is below-threshold candidate airflow-r316 (support 2, #57744, #56191), which forbids logging or printing a connection, its URI or any credential string — an adjacent exposure route, not this one. Secret scanning and the suspicious-changes triage path handle committed secrets outside code review.

### Contradicted by review history

- **Never add newsfragments for providers/ or airflow-ctl/ — edit providers/<provider>/docs/changelog.rst or airflow-ctl/RELEASE_NOTES.rst directly instead.** — Below-threshold candidate airflow-r190 (support 1) records a reviewer on #63614 asking a provider PR for a providers/<pkg>/newsfragments/<pr>.feature.rst alongside the RST update — the exact file AGENTS.md forbids; the changelog-editing half is separately backed by candidate airflow-r188 (support 2, #66424, #60706), so the contradiction is narrow and rests on a single PR.  (#63614)
- **If you have a conflict with uv.lock, delete it and run uv lock to regenerate it.** — Regenerating the whole lock file is exactly what produced the churn a reviewer rejected on #61550 ('362 lines of churn here looks unrelated to this feature. Please revert or split'); the instruction is safe only if the resulting diff is then trimmed to the dependency actually changed, which AGENTS.md does not say.  (#61550)

## Mined rules, by label

### CONFIRMED (6)

- `airflow-r009` **[correctness]** (support 5) Put imports at module scope; an import inside a function, method, test helper or fixture body is acceptable only to break a genuine circular import or for deliberate lazy loading (worker isolation, TYPE_CHECKING), and must carry a comment naming the reason. — AGENTS.md § Coding Standards
- `airflow-r014` **[testing]** (support 5) Mocks that stand in for a real interface must be specced — `MagicMock(spec=...)`, `spec_set=`, or `create_autospec` — including nested attributes; `MagicMock(autospec=True)` is a no-op keyword and does not spec anything. — AGENTS.md § Testing Standards
- `airflow-r007` **[correctness]** (support 4) Distinguish absence from a legitimate falsy value: test with `is not None` in Python and an explicit undefined/null check in TypeScript, and do not collapse None into an empty container with `param or []`, wherever 0, False, an empty string or an empty collection carry meaning. — contributing-docs/05_pull_requests.rst § Coding style and best practices → Templated fields in Operator's __init__ method
- `airflow-r005` **[commit-hygiene]** (support 3) Keep a PR scoped to the change its title and description claim: unrelated uv.lock churn must be reverted, an Alembic migration that fixes a pre-existing schema issue must go in its own PR, and a second independent feature must either be split out or added to the PR description with its own rationale and compatibility notes. — contributing-docs/05_pull_requests.rst § Pull Request guidelines (and § Pull Request quality criteria, item 6 'Coherent changes')
- `airflow-r010` **[docs]** (support 3) Spell the Airflow concept and its Python class as `Dag`/`Dags` in prose - user-facing docs, newsfragments, release notes, config.yml descriptions, docstrings and test names - reserving all-caps `DAG` for code identifiers and quoted strings. — AGENTS.md § Naming
- `airflow-r013` **[providers]** (support 3) Raise the native Python exception that fits - ValueError, TypeError, RuntimeError - for argument validation, bad user input, unexpected internal state and third-party service failures in provider code and triggers, rather than AirflowException. — AGENTS.md § Coding Standards; contributing-docs/05_pull_requests.rst § Don't raise AirflowException directly

### IMPLIED (3)

- `airflow-r002` **[api-design]** (support 6) Keep the public surface of provider operators, hooks, executors and extractors backward compatible: a renamed attribute or method keeps a deprecated forwarding property, a removed parameter is deprecated with its values mapped onto the replacement, and a changed return value, changed traversal or new constructor keyword is opt-in through a parameter that defaults to the existing behaviour. — contributing-docs/12_provider_distributions.rst § Breaking changes in the community managed providers
- `airflow-r003` **[api-design]** (support 3) Put behaviour that every concrete subclass needs in the shared base class or mixin - BaseExecutor, BaseCoordinator, BaseNotifier - rather than re-implementing it, or repeating the version guard, in each concrete implementation. — contributing-docs/30_new_language_sdk.rst § Choosing an implementation path / SubprocessCoordinator: implementing _build_execute_task_command
- `airflow-r011` **[docs]** (support 3) When a provider operator or hook gains a new parameter or changes its documented behaviour, update the class docstring - a `:param name:` entry describing the type, and for a Callable what each positional argument means - and the matching provider RST guide, in the same PR. — contributing-docs/05_pull_requests.rst § Pull Request guidelines; contributing-docs/12_provider_distributions.rst § Documentation for the community managed providers

### TRIBAL (5)

- `airflow-r001` **[api-design]** (support 4) Do not add or keep public surface that nothing consumes: a parameter, field or property must have a real consumer in the repository and a real effect; if it is unimplemented or no longer used, remove it from the signature and docstring, or make supplying it warn or raise.
- `airflow-r004` **[async]** (support 3) A trigger's run() must yield a distinct terminal TriggerEvent for every terminal condition it can reach: separate success and failure events rather than one collapsed success, and a timeout event carrying the timeout status and a descriptive reason rather than a bare break or return - with any cancellation side-effect in the timeout branch wrapped in its own try/except so a failed cancel cannot replace the event.
- `airflow-r006` **[correctness]** (support 3) A broad `except Exception` must not swallow or re-wrap an exception that is deliberately raised to propagate: re-raise the specific type before the generic handler, and when introducing such an exception, update every enclosing fall-through loop to let it through in the same change.
- `airflow-r008` **[correctness]** (support 3) Do not write an inline try/except ImportError compatibility shim where a central layer already handles the import - airflow.utils.sqlalchemy for SQLAlchemy 1.4/2.0 differences, airflow.providers.common.compat for provider redirects - or where the import cannot fail in the supported version.
- `airflow-r012` **[naming]** (support 3) Reuse Airflow's established name for a concept instead of inventing a synonym: `run_after` for the DAG run scheduling timestamp, `wait_for_completion` for the wait-for-finish flag, and an `a`-prefixed method name (`aget_connection`) for the async variant of an existing method.
