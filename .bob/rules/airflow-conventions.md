# apache/airflow — mined review conventions

Generated 2026-09-01T22:30:40.604080+00:00 by `distill/critic.py` from 954 candidate rules that map subagents extracted from merged-PR review comments.

**Support** is the number of distinct PRs in a rule's merged evidence. A pattern is promoted to a rule at support >= 3; everything below that stays a candidate, in the companion candidates file.

Review comments are never reproduced here. Each evidence line carries a permalink and an excerpt of at most 15 words.

| | |
|---|---|
| rules promoted | 26 |
| candidates (support below threshold) | 659 |
| incidents (one-off fixes, not conventions) | 115 |
| contested pairs | 0 |

To disagree with a rule, delete its section and commit. This file is the rulebook, not a cache.

## correctness

### `airflow-r427` — Put imports at module scope; an import inside a function, method, fixture or test body is acceptable only to break a genuine circular import or for deliberate lazy loading (worker isolation, `TYPE_CHECKING`), and must carry a comment naming the reason — stdlib modules always go at the top of the file.

- **Trigger** — An `import` / `from ... import` statement inside a function, method, test helper or fixture body — `importlib`, `logging` and other stdlib modules included — with no adjacent comment explaining the cycle or lazy-loading reason it avoids.
- **Why** — A body-level import hides the module's real dependency graph and repeats the import machinery on every call; the exceptions are narrow and known, so the ones that are legitimate say why, and everything else moves to the top.
- **Scope** — `airflow-core/` `providers/common/ai/tests/unit/common/ai/toolsets/` `task-sdk/src/airflow/sdk/`
- **Support** — 6 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#68118](https://github.com/apache/airflow/pull/68118#discussion_r3367146276) — `airflow-core/tests/unit/dag_processing/test_manager.py` — The test adds an import inside the test function body. In this repo imports are…
- PR [#66161](https://github.com/apache/airflow/pull/66161#discussion_r3176620527) — `airflow-core/src/airflow/dag_processing/bundles/manager.py` — Per [AGENTS.md](https://github.com/apache/airflow/blob/main/AGENTS.md) "Imports at top of file": these stdlib imports don't need to be lazy.…
- PR [#64563](https://github.com/apache/airflow/pull/64563#discussion_r3025276601) — `task-sdk/src/airflow/sdk/definitions/decorators/__init__.py` — `is_decorated_task` is imported inside `result()`, but this module already imports from `airflow.sdk.bases.decorator` at the top,…
- PR [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669149) — `providers/common/ai/tests/unit/common/ai/toolsets/test_datafusion.py` — Imports inside helper functions make dependency and linting behavior harder to reason about. Since this…
- PR [#62696](https://github.com/apache/airflow/pull/62696#discussion_r2973215185) — `task-sdk/src/airflow/sdk/configuration.py` — `AirflowSDKConfigParser.__init__` now performs a local import of `ProvidersManagerTaskRuntime`. If this is to avoid a circular…
- PR [#61077](https://github.com/apache/airflow/pull/61077#discussion_r2895879084) — `airflow-core/tests/unit/cli/commands/test_dag_command.py` — The imports at lines 1077-1079 are inside the test method body rather than at the…

</details>

Precedent: [#68118](https://github.com/apache/airflow/pull/68118#discussion_r3367146276), [#66161](https://github.com/apache/airflow/pull/66161#discussion_r3176620527), [#64563](https://github.com/apache/airflow/pull/64563#discussion_r3025276601), [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669149), [#62696](https://github.com/apache/airflow/pull/62696#discussion_r2973215185), [#61077](https://github.com/apache/airflow/pull/61077#discussion_r2895879084)

### `airflow-r423` — In `execute_complete`, branch explicitly on `event["status"]` and handle every status the paired trigger can emit — success, error, timeout and cancelled — before reading any payload field; never collapse all non-success statuses into one failure branch.

- **Trigger** — `execute_complete` reads payload fields without a prior status check, or returns on `status == "success"` and falls through to a single failure/cancel handler while the paired Trigger can emit timeout or cancelled statuses.
- **Why** — A trigger and the operator method that resumes from it are one contract written in the same PR. If the operator does not decode each status the trigger can emit, a cancellation or a timeout is reported to the user as the wrong error, or a payload field is read off an event that never carried one.
- **Scope** — `providers/`
- **Support** — 4 distinct PRs, 4 distinct reviewers

<details><summary>Evidence</summary>

- PR [#68479](https://github.com/apache/airflow/pull/68479#discussion_r3410679318) — `providers/google/src/airflow/providers/google/cloud/operators/vertex_ai/agent_engine.py` — You are collapsing all non-success states into one Error. I think you should explicitly branch…
- PR [#64770](https://github.com/apache/airflow/pull/64770#discussion_r3096872099) — `providers/amazon/src/airflow/providers/amazon/aws/operators/emr.py` — Also we look for the state success above, but attempt to cancel on every other…
- PR [#64274](https://github.com/apache/airflow/pull/64274#discussion_r3283416317) — `providers/amazon/src/airflow/providers/amazon/aws/operators/neptune_analytics.py` — The base trigger returns an event with status error. event["status"] is never read. If the…
- PR [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3133251259) — `providers/airbyte/src/airflow/providers/airbyte/operators/airbyte.py` — `execute_complete` still has no branch for `event["status"] == "cancelled"`. The trigger yields this status when…

</details>

Precedent: [#68479](https://github.com/apache/airflow/pull/68479#discussion_r3410679318), [#64770](https://github.com/apache/airflow/pull/64770#discussion_r3096872099), [#64274](https://github.com/apache/airflow/pull/64274#discussion_r3283416317), [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3133251259)

### `airflow-r428` — Test for presence with an explicit `is not None` (Python) or `!== undefined && !== null` (TypeScript) rather than truthiness wherever `0`, `False` or an empty string is a legitimate value.

- **Trigger** — `if value:` / `if not value:` in Python or `if (value)` / `Boolean(value)` in TypeScript used as a presence check on a field — `bundle_version`, `dag.fileloc`, an active `map_index = 0` filter, an XCom value — whose valid domain includes falsy values.
- **Why** — Airflow's domain is full of legitimately falsy values — map index 0, an empty bundle version, a `False` XCom — so a truthiness check quietly drops real data instead of testing whether the value was supplied.
- **Scope** — `airflow-core/src/airflow/` `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/operators/`
- **Support** — 4 distinct PRs, 4 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67226](https://github.com/apache/airflow/pull/67226#discussion_r3283917687) — `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/operators/pod.py` — If the value evaluates to `False` would not persist. Can you change to explicit NULL…
- PR [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3486308679) — `airflow-core/src/airflow/models/dag_version.py` — Let's set this line to `if bundle_version is not None` to guard against `bundle_version=""` selecting…
- PR [#60127](https://github.com/apache/airflow/pull/60127#discussion_r2661971525) — `airflow-core/src/airflow/dag_processing/dagbag.py` — The comment on line 379 states 'Only set fileloc if not already set by importer…
- PR [#54210](https://github.com/apache/airflow/pull/54210#discussion_r2266280970) — `airflow-core/src/airflow/ui/src/pages/Events/filterUtils.ts` — Take a look at `const getFilterCount` in DagsFilter. You can't do `Boolean(something)` because this will…

</details>

Precedent: [#67226](https://github.com/apache/airflow/pull/67226#discussion_r3283917687), [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3486308679), [#60127](https://github.com/apache/airflow/pull/60127#discussion_r2661971525), [#54210](https://github.com/apache/airflow/pull/54210#discussion_r2266280970)

### `airflow-r424` — Instance attributes belong to `__init__`: initialise every resource handle and state flag there, and never first-assign or overwrite them in `execute()`, `run()`, `submit()` or `get_conn()` — those methods resolve values into local variables and reset released resources to `None` after cleanup.

- **Trigger** — diff assigns `self.<resource>` or a state flag for the first time inside `async def run()` / `submit()` / `execute()`, or `get_conn()` assigns to `self.<param>` from `connection.extra_dejson` or a `getattr(..., default)` fallback chain.
- **Why** — Triggers, hooks and operators are serialised, resumed and re-entered, so an attribute that only exists after a particular method has run raises `AttributeError` on the other paths and makes the object's state depend on call order.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#65991](https://github.com/apache/airflow/pull/65991#discussion_r3237175340) — `providers/apache/spark/src/airflow/providers/apache/spark/hooks/spark_submit.py` — Why set it to false here? Shouldn't it be false due to the constructor? In…
- PR [#64612](https://github.com/apache/airflow/pull/64612#discussion_r3025696227) — `providers/apache/kafka/src/airflow/providers/apache/kafka/triggers/await_message.py` — `self._consumer` is introduced dynamically in `run()`. For clarity/type safety and to make cleanup idempotent, initialize…
- PR [#62790](https://github.com/apache/airflow/pull/62790#discussion_r2963359574) — `providers/ibm/mq/src/airflow/providers/ibm/mq/hooks/mq.py` — `self.open_options` is mutated on the instance inside `get_conn()`. Since `get_conn()` can be called multiple times,…

</details>

Precedent: [#65991](https://github.com/apache/airflow/pull/65991#discussion_r3237175340), [#64612](https://github.com/apache/airflow/pull/64612#discussion_r3025696227), [#62790](https://github.com/apache/airflow/pull/62790#discussion_r2963359574)

### `airflow-r425` — Operator, sensor and trigger error paths — including the failure and timeout branches of `execute_complete` — must raise Airflow exception types (`AirflowException`, `AirflowFailException`, `AirflowTaskTimeout`), never `RuntimeError` or another builtin.

- **Trigger** — diff adds `raise RuntimeError(...)` (or another builtin) on a trigger-event failure/timeout branch, or replaces an existing `raise AirflowException(` with `raise RuntimeError(` in an operator, sensor or trigger.
- **Why** — Airflow's exception hierarchy is what the task runner and every caller catch on; swapping in a builtin silently changes retry and failure handling for code that was catching the Airflow type.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#64119](https://github.com/apache/airflow/pull/64119#discussion_r3025331522) — `providers/airbyte/src/airflow/providers/airbyte/operators/airbyte.py` — Raising a bare `RuntimeError` here is inconsistent with the rest of this operator (which raises…
- PR [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3066494712) — `providers/airbyte/src/airflow/providers/airbyte/operators/airbyte.py` — Raising `RuntimeError` from an operator callback is inconsistent with typical Airflow operator semantics and makes…
- PR [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3025331365) — `providers/airbyte/src/airflow/providers/airbyte/operators/airbyte.py` — In Airflow operators, raising `RuntimeError` makes it harder to classify failures consistently (and conflicts with…
- PR [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3066494627) — `providers/airbyte/src/airflow/providers/airbyte/operators/airbyte.py` — The `timeout` handling block is duplicated (lines 147–158 and 160–168). The second block is unreachable…
- PR [#56936](https://github.com/apache/airflow/pull/56936#discussion_r2449631897) — `providers/amazon/src/airflow/providers/amazon/aws/operators/ssm.py` — Was there any other code that was catching the previous AriflowException that now needs to…

</details>

Precedent: [#64119](https://github.com/apache/airflow/pull/64119#discussion_r3025331522), [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3066494712), [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3025331365), [#64051](https://github.com/apache/airflow/pull/64051#discussion_r3066494627), [#56936](https://github.com/apache/airflow/pull/56936#discussion_r2449631897)

### `airflow-r426` — Post-submit commands and other cleanup that must run once a job finishes belong in a `try/finally` that covers the whole method including its early-exit guards, so they execute on success, failure and kill alike.

- **Trigger** — A `_run_post_submit_commands()` / sidecar-cleanup call sits outside a `finally`, or a `raise` appears before the `try/finally` that wraps it, in `SparkSubmitHook.submit()` or a K8s/YARN poll method.
- **Why** — These hooks exist to tear down sidecars and driver-side state; if the job raises or is killed the cleanup is exactly what still has to happen, so placing it on the success path only leaks the resources it was written to reclaim.
- **Scope** — `providers/apache/spark/src/airflow/providers/apache/spark/hooks/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67715](https://github.com/apache/airflow/pull/67715#discussion_r3344205081) — `providers/apache/spark/src/airflow/providers/apache/spark/hooks/spark_submit.py` — `_delete_driver_pod()` (hooks/spark_submit.py:974) already deletes this same pod with `body=V1DeleteOptions(), pretty=True` and its own logging/except. This…
- PR [#67118](https://github.com/apache/airflow/pull/67118#discussion_r3270205715) — `providers/apache/spark/src/airflow/providers/apache/spark/hooks/spark_submit.py` — `finally: self._run_post_submit_commands()` now runs immediately after the spark-submit subprocess exits -- which in cluster mode…
- PR [#64391](https://github.com/apache/airflow/pull/64391#discussion_r3025334221) — `providers/apache/spark/src/airflow/providers/apache/spark/hooks/spark_submit.py` — `submit()` calls `_run_post_submit_commands()` only on the success path. Any `AirflowException` raised for non-zero return codes…

</details>

Precedent: [#67715](https://github.com/apache/airflow/pull/67715#discussion_r3344205081), [#67118](https://github.com/apache/airflow/pull/67118#discussion_r3270205715), [#64391](https://github.com/apache/airflow/pull/64391#discussion_r3025334221)

## api-design

### `airflow-r418` — Keep FastAPI route modules to route handlers only: Pydantic request/response models belong in the package's datamodels module, authorization and business helpers in its services module, query/filter construction in the corresponding Query* filter class's to_orm, and callback or domain-object definitions in the module that owns the domain model.

- **Trigger** — A Pydantic BaseModel, an authorization dependency, a callback-definition object (e.g. _ImportPathCallbackDef), or resolution/query-building logic (e.g. resolve_task_group_pattern_to_task_ids) is defined or constructed inline inside a routes/*.py handler in the core API or a provider package.
- **Why** — The Core API's datamodels/services/filter-parameter layering is what makes routes reviewable and reusable, and provider APIs are expected to mirror it; logic inlined into a handler is unreachable for other callers and untestable on its own.
- **Scope** — `airflow-core/src/airflow/api_fastapi/core_api/routes/public/` `providers/`
- **Support** — 4 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#62343](https://github.com/apache/airflow/pull/62343#discussion_r2839712645) — `airflow-core/src/airflow/api_fastapi/core_api/routes/public/connections.py` — How above moving `_ImportPathCallbackDef` to `models.test_connection` module and add a factory method for constructing `ExecutorCallback`?
- PR [#57199](https://github.com/apache/airflow/pull/57199#discussion_r2462737163) — `providers/fab/src/airflow/providers/fab/auth_manager/api_fastapi/routes/roles.py` — It would be better to move the `requires_fab_custom_view` to service module as well. Since Airflow…
- PR [#55670](https://github.com/apache/airflow/pull/55670#discussion_r2426513087) — `airflow-core/src/airflow/api_fastapi/core_api/routes/public/task_instances.py` — Also this piece of code should probably leave in `QueryTITaskDisplayNamePatternSearch` implementation. (Don't use the factory,…
- PR [#55301](https://github.com/apache/airflow/pull/55301#discussion_r2325987777) — `providers/edge3/src/airflow/providers/edge3/worker_api/routes/ui.py` — For consistency, can you move this class to providers/edge3/src/airflow/providers/edge3/worker_api/datamodels_ui.py please?

</details>

Precedent: [#62343](https://github.com/apache/airflow/pull/62343#discussion_r2839712645), [#57199](https://github.com/apache/airflow/pull/57199#discussion_r2462737163), [#55670](https://github.com/apache/airflow/pull/55670#discussion_r2426513087), [#55301](https://github.com/apache/airflow/pull/55301#discussion_r2325987777)

### `airflow-r417` — A FastAPI route decorator must declare every status code its handler can produce: each status raised via HTTPException belongs in the responses= mapping, and the decorator's status_code must agree with the success codes the handler actually returns.

- **Trigger** — raise HTTPException(status.HTTP_4xx_...) in a handler body whose decorator does not list that status in responses=, or a route declaring status_code=HTTP_204_NO_CONTENT whose handler also returns a different 2xx code.
- **Why** — The decorator is what generates the OpenAPI spec and the generated UI client, so an undeclared status code is invisible to every consumer of the API.
- **Scope** — `airflow-core/src/airflow/api_fastapi/` `providers/edge3/src/airflow/providers/edge3/worker_api/routes/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#64556](https://github.com/apache/airflow/pull/64556#discussion_r3025326748) — `providers/edge3/src/airflow/providers/edge3/worker_api/routes/jobs.py` — `fetch()` now raises an HTTP 404 when the worker is unknown, but the route’s documented…
- PR [#63994](https://github.com/apache/airflow/pull/63994#discussion_r3040828096) — `airflow-core/src/airflow/api_fastapi/core_api/routes/public/pools.py` — bulk_pools can now raise an HTTP 400 when multi_team is disabled and any entity includes…
- PR [#63355](https://github.com/apache/airflow/pull/63355#discussion_r3066474121) — `airflow-core/src/airflow/api_fastapi/execution_api/routes/task_instances.py` — The route declares a default `204 No Content` success status, but the handler now also…

</details>

Precedent: [#64556](https://github.com/apache/airflow/pull/64556#discussion_r3025326748), [#63994](https://github.com/apache/airflow/pull/63994#discussion_r3040828096), [#63355](https://github.com/apache/airflow/pull/63355#discussion_r3066474121)

### `airflow-r419` — Keep the public surface of provider operators, hooks and extractors backward compatible: a changed return value, changed traversal, or new constructor keyword must be opt-in via a new parameter defaulting to the legacy behaviour, and existing public signatures (e.g. `BaseExtractor.__init__(self, operator)`) must keep working.

- **Trigger** — A diff that changes an existing operator's `execute()` return shape, alters what an existing hook method traverses or returns, or passes a new required keyword to a subclass constructor unconditionally
- **Why** — These classes are third-party extension points and DAG-facing API; silently changing their contract breaks user DAGs and out-of-tree subclasses at upgrade time with no deprecation path.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#66992](https://github.com/apache/airflow/pull/66992#discussion_r3322901303) — `providers/openlineage/src/airflow/providers/openlineage/extractors/manager.py` — source_code_enabled is passed as a new keyword to every extractor constructor in _get_extractor(). Custom extractors…
- PR [#64465](https://github.com/apache/airflow/pull/64465#discussion_r3025335272) — `providers/sftp/src/airflow/providers/sftp/hooks/sftp.py` — `list_directory()` now recursively walks subdirectories and returns full paths. This is a breaking behavior change…
- PR [#61284](https://github.com/apache/airflow/pull/61284#discussion_r2787581438) — `providers/google/src/airflow/providers/google/cloud/transfers/calendar_to_gcs.py` — I went over the PR again and noticed that changing the returned value from `dest_file_name`…

</details>

Precedent: [#66992](https://github.com/apache/airflow/pull/66992#discussion_r3322901303), [#64465](https://github.com/apache/airflow/pull/64465#discussion_r3025335272), [#61284](https://github.com/apache/airflow/pull/61284#discussion_r2787581438)

## testing

### `airflow-r441` — Mocks standing in for a real Airflow, provider or SDK type must be specced - MagicMock(spec=...), spec_set= or create_autospec, including nested attributes - so signature drift against the real class fails the test; MagicMock(autospec=True) is a no-op keyword and specs nothing.

- **Trigger** — A bare Mock()/MagicMock() (or MagicMock(autospec=True)) substituted for a known type - the Task SDK execution API Client, RunContext, ToolsetTool, a credentials object, a SerializedDAG cache entry, an AWS hook or its async connection, a SQLAlchemy session, an ORM instance, a DAG or an operator method - and then given attributes.
- **Why** — An unspecced mock accepts any attribute or signature, so the test keeps passing after the real class changes; specced mocks are what makes these tests catch drift instead of hiding it.
- **Scope** — `airflow-core/tests/unit/models/` `providers/` `task-sdk/tests/task_sdk/`
- **Support** — 9 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#68974](https://github.com/apache/airflow/pull/68974#discussion_r3473214532) — `providers/databricks/tests/unit/databricks/operators/test_databricks.py` — `MagicMock(autospec=True)` here does not actually apply autospeccing ("autospec" is a `mock.patch` feature, not a `MagicMock`…
- PR [#67635](https://github.com/apache/airflow/pull/67635#discussion_r3316173929) — `task-sdk/tests/task_sdk/coordinators/test_subprocess.py` — `mock_client` is created as a bare `MagicMock()` without `spec`/`autospec`, which can hide real API mismatches…
- PR [#64770](https://github.com/apache/airflow/pull/64770#discussion_r3067080837) — `providers/amazon/tests/unit/amazon/aws/triggers/test_emr.py` — This new test also relies on unspecced `MagicMock` instances for the hook/client/context manager. Using autospecced…
- PR [#64568](https://github.com/apache/airflow/pull/64568#discussion_r3066480500) — `task-sdk/tests/task_sdk/execution_time/test_supervisor.py` — `fake_client = MagicMock()` is an unspecced mock; consider using a `spec`/`spec_set` (or `autospec`) for the…
- PR [#64563](https://github.com/apache/airflow/pull/64563#discussion_r3025276615) — `task-sdk/tests/task_sdk/definitions/test_dag.py` — This test replaces `DAG.add_result` with `mock.MagicMock()` without a `spec`/`autospec`. Using an autospecced mock (e.g., `mock.create_autospec(DAG.add_result,…
- PR [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669079) — `providers/common/ai/tests/unit/common/ai/toolsets/test_datafusion.py` — These tests frequently pass `MagicMock()` for `ctx` and `tool` without a spec. Using a spec…
- PR [#62737](https://github.com/apache/airflow/pull/62737#discussion_r2874870299) — `providers/fab/tests/unit/fab/auth_manager/security_manager/test_override.py` — The new tests use several unspecced `Mock()` instances (e.g., `role`, `permission`, `mock_session`). Using `spec`/`autospec` (especially…
- PR [#60804](https://github.com/apache/airflow/pull/60804#discussion_r3067262376) — `airflow-core/tests/unit/models/test_dagbag.py` — This TTL expiry test uses `MagicMock()` without a `spec`, which can hide interface mistakes. Prefer…
- PR [#53801](https://github.com/apache/airflow/pull/53801#discussion_r3176107143) — `providers/hashicorp/tests/unit/hashicorp/hooks/test_vault.py` — Please give this new credential double a `spec`/`autospec`. A bare `MagicMock` fabricates arbitrary attributes, so…

</details>

Precedent: [#68974](https://github.com/apache/airflow/pull/68974#discussion_r3473214532), [#67635](https://github.com/apache/airflow/pull/67635#discussion_r3316173929), [#64770](https://github.com/apache/airflow/pull/64770#discussion_r3067080837), [#64568](https://github.com/apache/airflow/pull/64568#discussion_r3066480500), [#64563](https://github.com/apache/airflow/pull/64563#discussion_r3025276615), [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669079), [#62737](https://github.com/apache/airflow/pull/62737#discussion_r2874870299), [#60804](https://github.com/apache/airflow/pull/60804#discussion_r3067262376) (+1 more)

### `airflow-r439` — E2e tests and page objects must fail when the feature is broken: no if-guards around the assertions and no try/catch or .catch(() => false) around visibility/state checks - use web-first assertions such as expect(el).toBeVisible()/toBeHidden() and let failures propagate.

- **Trigger** — A tests/e2e/specs/*.ts diff adds an if (count > 0) { ... } guard or similar short-circuit around the assertions, or a Playwright page-object method wraps isVisible()/isEnabled() in try/catch returning false.
- **Why** — A conditional or swallowed check turns the spec into a test that passes whether or not the feature works, which is worse than no coverage because it looks like coverage.
- **Scope** — `airflow-core/src/airflow/ui/tests/e2e/`
- **Support** — 4 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#64189](https://github.com/apache/airflow/pull/64189#discussion_r3025333560) — `airflow-core/src/airflow/ui/tests/e2e/pages/DagCalendarTab.ts` — `waitForCalendarReady()` removed the loading overlay handling entirely. Since the overlay element is conditionally rendered, you…
- PR [#60738](https://github.com/apache/airflow/pull/60738#discussion_r2793925426) — `airflow-core/src/airflow/ui/tests/e2e/pages/ConnectionsPage.ts` — This will silently return in case of an actual issue, we should not even use…
- PR [#59943](https://github.com/apache/airflow/pull/59943#discussion_r2664402173) — `airflow-core/src/airflow/ui/tests/e2e/specs/dag-tasks.spec.ts` — Test passes whether filtering works or not. This is a no-op test. Also you are…
- PR [#59791](https://github.com/apache/airflow/pull/59791#discussion_r2649672306) — `airflow-core/src/airflow/ui/tests/e2e/pages/BackfillPage.ts` — ColumnVisible() and isFilterAvailable() catch errors and return false. This makes debugging difficult 1. Test failures…

</details>

Precedent: [#64189](https://github.com/apache/airflow/pull/64189#discussion_r3025333560), [#60738](https://github.com/apache/airflow/pull/60738#discussion_r2793925426), [#59943](https://github.com/apache/airflow/pull/59943#discussion_r2664402173), [#59791](https://github.com/apache/airflow/pull/59791#discussion_r2649672306)

### `airflow-r438` — Do not use pytest's caplog fixture to assert on log output; assert on observable behaviour or return values, or capture the logger directly with a mock.

- **Trigger** — caplog appears as a fixture argument, or caplog.text/caplog.records is asserted on, in a test under providers/**/tests/, kubernetes-tests/ or the core test suites.
- **Why** — Log text is not the contract under test; caplog assertions break on unrelated logging changes and depend on handler and propagation setup that differs between the unit, provider and integration suites.
- **Scope** — `kubernetes-tests/tests/kubernetes_tests/` `providers/cncf/kubernetes/tests/unit/cncf/kubernetes/operators/` `shared/logging/tests/logging/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#65232](https://github.com/apache/airflow/pull/65232#discussion_r3081754322) — `providers/cncf/kubernetes/tests/unit/cncf/kubernetes/operators/test_pod.py` — Since some time be banned caplog for testing - in many cases this generated negative…
- PR [#63878](https://github.com/apache/airflow/pull/63878#discussion_r3215299268) — `shared/logging/tests/logging/test_structlog.py` — [`CLAUDE.md`](https://github.com/apache/airflow/blob/main/CLAUDE.md) is explicit on this: *"Do not use `caplog` in tests, prefer checking logic and…
- PR [#53598](https://github.com/apache/airflow/pull/53598#discussion_r2234597434) — `kubernetes-tests/tests/kubernetes_tests/test_kubernetes_pod_operator.py` — Sorry, I miss the `caplog` usage in last review. Since `caplog` introduce some flakiness in…

</details>

Precedent: [#65232](https://github.com/apache/airflow/pull/65232#discussion_r3081754322), [#63878](https://github.com/apache/airflow/pull/63878#discussion_r3215299268), [#53598](https://github.com/apache/airflow/pull/53598#discussion_r2234597434)

### `airflow-r440` — In Playwright e2e tests, wait on an explicit UI condition - a key element becoming visible before a navigation helper returns, expect.poll() for post-click assertions - never read state immediately after an action and never page.waitForLoadState('networkidle').

- **Trigger** — A goto/navigateTo* helper is added with no subsequent waitFor/toBeVisible, page content is compared immediately after a navigation click without expect.poll, or waitForLoadState('networkidle') is called.
- **Why** — The UI keeps fetching after navigation, so an immediate read or a networkidle wait is a race that flakes in CI; waiting on the element the test actually depends on is both deterministic and self-documenting.
- **Scope** — `airflow-core/src/airflow/ui/tests/e2e/pages/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#60738](https://github.com/apache/airflow/pull/60738#discussion_r2735507029) — `airflow-core/src/airflow/ui/tests/e2e/pages/ConnectionsPage.ts` — Would it be possible to handle this without relying on networkidle? In Playwright, using networkidle…
- PR [#60449](https://github.com/apache/airflow/pull/60449#discussion_r2727235691) — `airflow-core/src/airflow/ui/tests/e2e/pages/RequiredActionsPage.ts` — We can use below ``` public async verifyPagination(limit: number): Promise<void> { await this.navigateToRequiredActionsPage(limit); await expect(this.paginationNextButton).toBeVisible();…
- PR [#59943](https://github.com/apache/airflow/pull/59943#discussion_r2664463948) — `airflow-core/src/airflow/ui/tests/e2e/pages/DagsPage.ts` — We do not need default here. We should also wait task to load ```suggestion public…

</details>

Precedent: [#60738](https://github.com/apache/airflow/pull/60738#discussion_r2735507029), [#60449](https://github.com/apache/airflow/pull/60449#discussion_r2727235691), [#59943](https://github.com/apache/airflow/pull/59943#discussion_r2664463948)

## naming

### `airflow-r012` — Reuse Airflow's established name for a concept instead of inventing a synonym: `run_after` for the DAG run scheduling timestamp, `wait_for_completion` for the wait-for-finish flag, and an `a`-prefixed method name (`aget_connection`) for the async variant of an existing method.

- **Trigger** — A new or renamed parameter/method uses `logical_date` or `date` for scheduling time, `wait_for_termination` for a completion flag, or an `async_`-prefixed name where a sync counterpart already exists.
- **Why** — Users move between providers constantly; a synonym for a parameter that is already named consistently across the AWS and core operators forces them to re-learn the same flag per package and shows up in every DAG they write.
- **Scope** — `providers/` `task-sdk/src/airflow/sdk/bases/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#60369](https://github.com/apache/airflow/pull/60369#discussion_r2760020633) — `providers/microsoft/azure/src/airflow/providers/microsoft/azure/operators/powerbi.py` — Here you are using `wait_for_termination`, I would rather use `wait_for_completion` instead for consistency purposes. I…
- PR [#60369](https://github.com/apache/airflow/pull/60369#discussion_r2759608445) — `providers/microsoft/azure/src/airflow/providers/microsoft/azure/operators/powerbi.py` — We usually use `wait_for_completion` in the AWS provider package. Can you please use it as…
- PR [#55110](https://github.com/apache/airflow/pull/55110#discussion_r2317575671) — `providers/google/src/airflow/providers/google/cloud/hooks/bigquery.py` — if we want to replace it with `run_after` in the future, let's make it `run_after`…
- PR [#53831](https://github.com/apache/airflow/pull/53831#discussion_r2249148386) — `task-sdk/src/airflow/sdk/bases/hook.py` — I wonder if this should be called `aget_connection` instead. I think this might be the…

</details>

Precedent: [#60369](https://github.com/apache/airflow/pull/60369#discussion_r2760020633), [#60369](https://github.com/apache/airflow/pull/60369#discussion_r2759608445), [#55110](https://github.com/apache/airflow/pull/55110#discussion_r2317575671), [#53831](https://github.com/apache/airflow/pull/53831#discussion_r2249148386)

## performance

### `airflow-r432` — Fetch exactly the columns the consuming code reads: enumerate columns instead of select(SomeModel) in grid/UI and other hot-path queries, restrict with_row_locks selects to the key actually used, and do not add a column to load_only() that no caller consumes.

- **Trigger** — A grid/UI or hot-path query uses select(SomeModel) instead of listing columns, a with_row_locks(select(Model)) retrieves the full entity when only .id is consumed, or a column is added to a load_only(...) call that no downstream code path reads.
- **Why** — These queries run per page load or per scheduler pass over wide tables, so every extra column is bytes off the wire and rows the ORM has to hydrate for nothing; the column list is expected to match what the code actually reads.
- **Scope** — `airflow-core/src/airflow/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#66488](https://github.com/apache/airflow/pull/66488#discussion_r3212988421) — `airflow-core/src/airflow/dag_processing/collection.py` — If I check the downstream references to `_get_latest_runs_stmt` and `_get_latest_runs_stmt_partitioned` correct. They don't access `run_after`…
- PR [#59183](https://github.com/apache/airflow/pull/59183#discussion_r2602787179) — `airflow-core/src/airflow/assets/manager.py` — I think it would be a bit more efficient if we only retrieve id of…
- PR [#53216](https://github.com/apache/airflow/pull/53216#discussion_r2248281167) — `airflow-core/src/airflow/api_fastapi/core_api/routes/ui/grid.py` — Keep the explicit naming of fields that we want please. Grid endpoint are very subject…

</details>

Precedent: [#66488](https://github.com/apache/airflow/pull/66488#discussion_r3212988421), [#59183](https://github.com/apache/airflow/pull/59183#discussion_r2602787179), [#53216](https://github.com/apache/airflow/pull/53216#discussion_r2248281167)

## providers

### `airflow-r433` — A provider must not unconditionally import, call or attribute-access an airflow-core symbol that does not exist in its minimum supported core version: gate it behind an AIRFLOW_V_X_Y_PLUS check (or `getattr(obj, "attr", default)`) and keep the older fallback path.

- **Trigger** — Provider code imports, calls or reads an airflow-core symbol, method or attribute introduced after that provider's minimum supported Airflow version with no version guard or fallback, or a diff deletes the Airflow 2 branch from a provider that still supports Airflow 2.
- **Why** — Providers are released independently of core and are installed against a range of Airflow versions, so any core API newer than the declared floor has to be optional at runtime — otherwise the provider fails at import for every user on an older core.
- **Scope** — `providers/`
- **Support** — 5 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#69005](https://github.com/apache/airflow/pull/69005#discussion_r3484117644) — `providers/edge3/src/airflow/providers/edge3/executors/edge_executor.py` — Looks like Edge has support for 3.0+; self.team_name was added in 3.1 so this could…
- PR [#62984](https://github.com/apache/airflow/pull/62984#discussion_r3119521170) — `providers/amazon/src/airflow/providers/amazon/aws/executors/batch/batch_executor.py` — Both. If you name the parameter `workload_items` then you get rid of the name shadowing…
- PR [#60675](https://github.com/apache/airflow/pull/60675#discussion_r2724353852) — `providers/celery/src/airflow/providers/celery/cli/celery_command.py` — @o-nikolas, this is failing backward compatibility. In Airflow 3.1.3, ExecutorConf exists but lacks critical methods…
- PR [#53821](https://github.com/apache/airflow/pull/53821#discussion_r2271903582) — `providers/elasticsearch/src/airflow/providers/elasticsearch/log/es_task_handler.py` — We might still need to test ES provider against Airflow 2, no really sure will…
- PR [#53356](https://github.com/apache/airflow/pull/53356#discussion_r2553195034) — `providers/microsoft/azure/src/airflow/providers/microsoft/azure/triggers/message_bus.py` — Adding compact import _should_ fix the CI. ```suggestion if AIRFLOW_V_3_0_PLUS: from airflow.triggers.base import BaseEventTrigger, TriggerEvent…

</details>

Precedent: [#69005](https://github.com/apache/airflow/pull/69005#discussion_r3484117644), [#62984](https://github.com/apache/airflow/pull/62984#discussion_r3119521170), [#60675](https://github.com/apache/airflow/pull/60675#discussion_r2724353852), [#53821](https://github.com/apache/airflow/pull/53821#discussion_r2271903582), [#53356](https://github.com/apache/airflow/pull/53356#discussion_r2553195034)

### `airflow-r434` — Express cross-version Airflow compatibility through the shared compat layer — the `AIRFLOW_V_X_Y_PLUS` sentinels in `version_compat` and the helpers in `providers/common/compat` — instead of inline `packaging.version.parse` comparisons or per-provider copies of the same check.

- **Trigger** — Provider code compares `packaging.version.parse(airflow_version)` against a literal version string, or repeats an inline `if AIRFLOW_V_3_X_PLUS` shim that already exists in (or belongs in) `providers/common/compat`.
- **Why** — Version gates are scattered across dozens of providers; when they live in one compat module they can be audited and retired in a single change, whereas hand-rolled comparisons drift and are missed when a minimum version is finally raised.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#61153](https://github.com/apache/airflow/pull/61153#discussion_r2858312360) — `providers/celery/src/airflow/providers/celery/executors/celery_executor.py` — Instead of many `if v3.2` checks, can we consider adding to compat/sdk.py: https://github.com/apache/airflow/blob/main/providers/common/compat/src/airflow/providers/common/compat/sdk.py?
- PR [#56911](https://github.com/apache/airflow/pull/56911#discussion_r2453608665) — `providers/discord/src/airflow/providers/discord/hooks/discord_webhook.py` — Yea, makes sense. I also just noticed this: https://github.com/apache/airflow/issues/57018 So I was thinking we add…
- PR [#54043](https://github.com/apache/airflow/pull/54043#discussion_r2249218988) — `providers/fab/src/airflow/providers/fab/auth_manager/fab_auth_manager.py` — ```suggestion and AIRFLOW_V_3_1_PLUS ``` from airflow.providers.fab.version_compat import AIRFLOW_V_3_1_PLUS

</details>

Precedent: [#61153](https://github.com/apache/airflow/pull/61153#discussion_r2858312360), [#56911](https://github.com/apache/airflow/pull/56911#discussion_r2453608665), [#54043](https://github.com/apache/airflow/pull/54043#discussion_r2249218988)

### `airflow-r435` — Import anything a provider does not require unconditionally — a package behind an optional extra, or another provider's package — inside `try`/`except ImportError`, and either raise `AirflowOptionalProviderFeatureException` naming the extra to install or degrade the feature; never import it unconditionally at module top level.

- **Trigger** — A provider module imports a package declared only as an optional extra, or a symbol from another `airflow.providers.*` package, at module top level with no `try`/`except ImportError` guard.
- **Why** — A top-level import of something optional turns a missing extra into an import failure for the whole provider; guarding it keeps the rest of the provider usable and turns the error into an actionable message naming what to install.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#69234](https://github.com/apache/airflow/pull/69234#discussion_r3549548031) — `providers/google/src/airflow/providers/google/cloud/openlineage/mixins.py` — As mentioned above, this will not work with older OL provider (api was added recently),…
- PR [#64754](https://github.com/apache/airflow/pull/64754#discussion_r3066502813) — `providers/akeyless/src/airflow/providers/akeyless/hooks/akeyless.py` — `akeyless_cloud_id` is an optional dependency, but importing it directly will raise a bare `ImportError` when…
- PR [#62790](https://github.com/apache/airflow/pull/62790#discussion_r2984868963) — `providers/ibm/mq/src/airflow/providers/ibm/mq/queues/mq.py` — `BaseMessageQueueProvider` is imported unconditionally. Other message-queue providers guard this import and raise `AirflowOptionalProviderFeatureException` when `common.messaging`…

</details>

Precedent: [#69234](https://github.com/apache/airflow/pull/69234#discussion_r3549548031), [#64754](https://github.com/apache/airflow/pull/64754#discussion_r3066502813), [#62790](https://github.com/apache/airflow/pull/62790#discussion_r2984868963)

### `airflow-r436` — In provider code, raise the most appropriate built-in Python exception (ValueError, TypeError, RuntimeError) for argument validation, internal invariant violations and third-party service failures, rather than AirflowException.

- **Trigger** — A new `raise AirflowException(...)` inside a provider hook, operator or trigger for parameter validation, an internal/programming error, or an error originating in an external service.
- **Why** — AirflowException is Airflow's own signalling channel. Using it for ordinary programming errors or third-party failures makes provider errors indistinguishable from Airflow control flow and hides the real cause from users; the built-in exception types already say what went wrong.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#62240](https://github.com/apache/airflow/pull/62240#discussion_r2843460423) — `providers/amazon/src/airflow/providers/amazon/aws/hooks/sagemaker_unified_studio_notebook.py` — We're trying to avoid the overuse of `AirflowException` there is nothing related to Airflow failing…
- PR [#60963](https://github.com/apache/airflow/pull/60963#discussion_r2725622949) — `providers/imap/src/airflow/providers/imap/hooks/imap.py` — Following a recent decision (see [dev list thread](https://lists.apache.org/thread/5rv4tz0oc27bgr4khx0on0jz8fpxvh55)), the directive is not to use `AirflowException`,…
- PR [#55068](https://github.com/apache/airflow/pull/55068#discussion_r2497942742) — `providers/google/src/airflow/providers/google/cloud/triggers/dataproc.py` — ```suggestion raise RuntimeError( ``` not sure whehter we can duplicate these parts by moving them…
- PR [#55068](https://github.com/apache/airflow/pull/55068#discussion_r2497913513) — `providers/google/src/airflow/providers/google/cloud/triggers/bigquery.py` — Let's not use AirflowException ```suggestion raise RuRuntimeErrorn(f"TaskInstance not set on {self.__class__.__name__}!") ```

</details>

Precedent: [#62240](https://github.com/apache/airflow/pull/62240#discussion_r2843460423), [#60963](https://github.com/apache/airflow/pull/60963#discussion_r2725622949), [#55068](https://github.com/apache/airflow/pull/55068#discussion_r2497942742), [#55068](https://github.com/apache/airflow/pull/55068#discussion_r2497913513)

### `airflow-r437` — Public provider API must stay backward compatible: renaming an executor attribute or method requires a deprecated property/forwarding wrapper under the old name, and removing an operator parameter requires deprecating it and mapping its values onto the replacement rather than dropping it.

- **Trigger** — diff renames a public attribute or method on a `BaseExecutor` subclass with no shim, or removes a parameter (e.g. `wait_policy`) from an operator and hard-codes one of its former values.
- **Why** — Users subclass executors and pass these parameters from their own DAGs; a silent rename or removal breaks them at runtime with no migration path.
- **Scope** — `providers/amazon/src/airflow/providers/amazon/aws/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#63657](https://github.com/apache/airflow/pull/63657#discussion_r3113972841) — `providers/amazon/src/airflow/providers/amazon/aws/executors/ecs/ecs_executor.py` — Why no shims? Pretty sure we need them for back-compat, no? Just something like ```python…
- PR [#63035](https://github.com/apache/airflow/pull/63035#discussion_r3133852800) — `providers/amazon/src/airflow/providers/amazon/aws/executors/aws_lambda/lambda_executor.py` — Can you add property shim for `pending_tasks` and `running_tasks` as well? They'll look something like…
- PR [#56158](https://github.com/apache/airflow/pull/56158#discussion_r2384296825) — `providers/amazon/src/airflow/providers/amazon/aws/operators/emr.py` — The code hardcodes `WaitPolicy.WAIT_FOR_COMPLETION`, removing support for `WaitPolicy.WAIT_FOR_STEPS_COMPLETION` that was previously available through the `wait_policy`…

</details>

Precedent: [#63657](https://github.com/apache/airflow/pull/63657#discussion_r3113972841), [#63035](https://github.com/apache/airflow/pull/63035#discussion_r3133852800), [#56158](https://github.com/apache/airflow/pull/56158#discussion_r2384296825)

## docs

### `airflow-r430` — In user-facing prose - documentation, newsfragments, release notes, changelog entries, config.yml descriptions and UI strings - spell Airflow's core nouns the Airflow 3 way (Dag, Dags, Dag run, Dag files, Dag bundles, Dag Processor, API Server); never all-caps DAG/DAGs, "DAG processor" or "webserver", and reserve all-caps DAG for code identifiers and quoted strings.

- **Trigger** — A docs page, newsfragment, RELEASE_NOTES.rst bullet, changelog entry, config.yml description or translated UI string adds prose containing "DAG"/"DAGs" outside backticks or a code identifier, or uses "webserver"/"DAG processor".
- **Why** — Airflow 3 deliberately re-spelled these concepts; the all-caps forms leak pre-3.0 vocabulary into text users read, while the code identifiers keep their old casing, so reviewers correct the prose on sight.
- **Scope** — `.github/skills/airflow-translations/locales/` `./` `airflow-core/`
- **Support** — 6 distinct PRs, 4 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67994](https://github.com/apache/airflow/pull/67994#discussion_r3383967813) — `airflow-core/newsfragments/67994.doc.rst` — I don't think you need a newsfragment for a docs update, that's quite overkill. But…
- PR [#64322](https://github.com/apache/airflow/pull/64322#discussion_r3014691143) — `airflow-core/newsfragments/64322.bugfix.rst` — ```suggestion Fix premature asset-triggered DagRuns when ``AssetDagRunQueue`` had rows but ``SerializedDagModel`` was not yet available;…
- PR [#62083](https://github.com/apache/airflow/pull/62083#discussion_r2862611606) — `.github/skills/airflow-translations/locales/pt.md` — Section 1 says to keep "TaskInstance" and "DagRun" in English, but the established UI translations…
- PR [#61160](https://github.com/apache/airflow/pull/61160#discussion_r2745044731) — `RELEASE_NOTES.rst` — ```suggestion - Fix asset scheduling for stale Dags (#59337) (#60022) (#61106) - Fix unnecessary Dag…
- PR [#59430](https://github.com/apache/airflow/pull/59430#discussion_r2660900575) — `airflow-core/src/airflow/config_templates/config.yml` — ```suggestion Controls the behavior of Dag stability checker performed before Dag parsing in the Dag…
- PR [#53727](https://github.com/apache/airflow/pull/53727#discussion_r2266271491) — `airflow-core/docs/core-concepts/dags.rst` — ```suggestion Deadline Alerts allow you to set time thresholds for your Dag runs and automatically…
- PR [#53727](https://github.com/apache/airflow/pull/53727#discussion_r2243570766) — `airflow-core/docs/core-concepts/dags.rst` — Unless you have good reason to keep it capitalized? ```suggestion Here's a simple example using…

</details>

Precedent: [#67994](https://github.com/apache/airflow/pull/67994#discussion_r3383967813), [#64322](https://github.com/apache/airflow/pull/64322#discussion_r3014691143), [#62083](https://github.com/apache/airflow/pull/62083#discussion_r2862611606), [#61160](https://github.com/apache/airflow/pull/61160#discussion_r2745044731), [#59430](https://github.com/apache/airflow/pull/59430#discussion_r2660900575), [#53727](https://github.com/apache/airflow/pull/53727#discussion_r2266271491), [#53727](https://github.com/apache/airflow/pull/53727#discussion_r2243570766)

### `airflow-r429` — A parameter's documented semantics must match what the code actually does with it: whether the value overrides, is appended to or merged with an underlying default; what the real fallback is when it is unset; and how much the code actually validates. Fix whichever side is wrong - reword the docstring, or make the implementation pass the value conditionally so the documented fallback really applies

- **Trigger** — A `:param:` docstring, RST page or OpenAPI query-parameter description states override/append/merge semantics, a fallback ("if None, the connection's project id is used"), or a validation scope that the implementation does not actually provide - e.g. the kwarg is passed unconditionally so the spec-file default can never apply, or `build_ordering()` supports a single field while the description says comma-separated
- **Why** — Reviewers repeatedly catch hook/operator docstrings that describe plausible-sounding behaviour instead of the behaviour the code implements; users configure against the docs and get silently different results.
- **Scope** — `providers/`
- **Support** — 4 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67788](https://github.com/apache/airflow/pull/67788#discussion_r3329421418) — `providers/common/ai/src/airflow/providers/common/ai/hooks/pydantic_ai.py` — `instructions` doesn't override the spec file -- pydantic-ai merges them. `from_spec` does `merged = normalize_instructions(spec.instructions);…
- PR [#67788](https://github.com/apache/airflow/pull/67788#discussion_r3329411745) — `providers/common/ai/src/airflow/providers/common/ai/hooks/pydantic_ai.py` — The documentation and example DAG state that "the model declared in the spec file is…
- PR [#63418](https://github.com/apache/airflow/pull/63418#discussion_r2923138501) — `providers/fab/src/airflow/providers/fab/auth_manager/api_fastapi/routes/roles.py` — The `order_by` description says fields can be comma-separated, but `build_ordering()` only supports a single field…
- PR [#62793](https://github.com/apache/airflow/pull/62793#discussion_r2880993764) — `providers/common/ai/src/airflow/providers/common/ai/operators/llm_schema_compare.py` — Design question: since `system_prompt` defaults to `DEFAULT_SYSTEM_PROMPT` (type equivalences + severity definitions), passing `system_prompt="focus on…
- PR [#56324](https://github.com/apache/airflow/pull/56324#discussion_r2662090249) — `providers/google/src/airflow/providers/google/common/hooks/base_google.py` — The docstring says "If None, the project ID from the GCP connection is used." However,…
- PR [#56324](https://github.com/apache/airflow/pull/56324#discussion_r2724153278) — `providers/google/src/airflow/providers/google/common/hooks/base_google.py` — ```suggestion """Validate the quota project ID format ``` It doesn't validate existence (not sure that…

</details>

Precedent: [#67788](https://github.com/apache/airflow/pull/67788#discussion_r3329421418), [#67788](https://github.com/apache/airflow/pull/67788#discussion_r3329411745), [#63418](https://github.com/apache/airflow/pull/63418#discussion_r2923138501), [#62793](https://github.com/apache/airflow/pull/62793#discussion_r2880993764), [#56324](https://github.com/apache/airflow/pull/56324#discussion_r2662090249), [#56324](https://github.com/apache/airflow/pull/56324#discussion_r2724153278)

### `airflow-r431` — Provider changelog.rst entries must read as sentence-case, user-facing prose: strip conventional-commit prefixes such as fix: or feat(...), do not open with a lowercase word, name no internal tooling such as Dependabot, and state the concrete change.

- **Trigger** — A line added to providers/*/docs/changelog.rst starts with a lowercase word or a fix:/feat: prefix, or mentions dependabot instead of describing the user-visible change.
- **Why** — The changelog is published documentation, not a commit log; raw commit titles and tooling names read as repo internals to the provider's users.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#68642](https://github.com/apache/airflow/pull/68642#discussion_r3426446809) — `providers/apache/livy/docs/changelog.rst` — This is not informative for users. Users don't know nor care about dependedbot. Lets rephrase…
- PR [#67920](https://github.com/apache/airflow/pull/67920#discussion_r3344459225) — `providers/amazon/docs/changelog.rst` — Can you "beautify"? ```suggestion * ``Fix EksPodOperator 401 with cross-account AssumeRole via aws_conn_id (#65335)`` ```
- PR [#64864](https://github.com/apache/airflow/pull/64864#discussion_r3047726662) — `providers/apache/spark/docs/changelog.rst` — Is this now a feature and provider needs a feature increment + pushing this up…

</details>

Precedent: [#68642](https://github.com/apache/airflow/pull/68642#discussion_r3426446809), [#67920](https://github.com/apache/airflow/pull/67920#discussion_r3344459225), [#64864](https://github.com/apache/airflow/pull/64864#discussion_r3047726662)

## commit-hygiene

### `airflow-r420` — Keep a PR's diff scoped to what its title and description claim: regenerate uv.lock against fresh main so it carries only the dependency changes this PR actually makes, and split an independent schema-fix migration or a second unrelated feature into its own PR or call it out in the description with its own rationale.

- **Trigger** — The diff contains uv.lock changes no source change in the PR accounts for (extras added or dependencies dropped by a rebase), an independent schema-fix migration alongside a feature migration, or a second unrelated feature.
- **Why** — Reviewers read the description as the contract for the diff; unexplained lockfile churn and piggy-backed migrations or features cannot be reviewed or reverted independently of the feature the PR is named for.
- **Scope** — `./` `airflow-core/src/airflow/`
- **Support** — 4 distinct PRs, 4 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67235](https://github.com/apache/airflow/pull/67235#discussion_r3277765811) — `uv.lock` — Unrelated change: this PR removes `langchain-openai` from the langchain extra (also in the deleted package…
- PR [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3116493328) — `uv.lock` — 362 lines of churn here looks unrelated to this feature. Please revert or split into…
- PR [#60804](https://github.com/apache/airflow/pull/60804#discussion_r3066474591) — `airflow-core/src/airflow/cli/commands/api_server_command.py` — This PR introduces API server worker recycling (`worker_max_requests` + Uvicorn `limit_max_requests`) in addition to the…
- PR [#55954](https://github.com/apache/airflow/pull/55954#discussion_r2380281165) — `airflow-core/src/airflow/migrations/versions/0088_3_2_0_add_length_dag_bundle_team_bundle_name.py` — I mean: isn't this a problem today, and so this should be pulled out in…

</details>

Precedent: [#67235](https://github.com/apache/airflow/pull/67235#discussion_r3277765811), [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3116493328), [#60804](https://github.com/apache/airflow/pull/60804#discussion_r3066474591), [#55954](https://github.com/apache/airflow/pull/55954#discussion_r2380281165)

### `airflow-r421` — Never hand-edit generated files; change the source of truth and regenerate in the same commit - `get_provider_info.py` comes from `provider.yaml` via `prek run update-providers-build-files`, and the task-SDK `datamodels/_generated.py` comes from the Execution API OpenAPI schema

- **Trigger** — A diff edits `providers/**/get_provider_info.py` or `task-sdk/src/airflow/sdk/api/datamodels/_generated.py` by hand, or edits a `provider.yaml` without the matching regenerated `get_provider_info.py`
- **Why** — Hand edits to generated files are overwritten by the next regeneration and break the pre-commit consistency checks.
- **Scope** — `providers/` `task-sdk/src/airflow/sdk/api/datamodels/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#63733](https://github.com/apache/airflow/pull/63733#discussion_r2941535964) — `task-sdk/src/airflow/sdk/api/datamodels/_generated.py` — `task-sdk/.../_generated.py` is generated by datamodel-codegen (per the header). Please confirm this change was produced by…
- PR [#62816](https://github.com/apache/airflow/pull/62816#discussion_r2892283042) — `providers/common/ai/src/airflow/providers/common/ai/get_provider_info.py` — This file is auto-generated from `provider.yaml` — manual edits here will be overwritten by `prek…
- PR [#62790](https://github.com/apache/airflow/pull/62790#discussion_r3066482686) — `providers/ibm/mq/provider.yaml` — The placeholder JSON includes `cls.default_open_options`, which is not valid JSON and will be copied by…

</details>

Precedent: [#63733](https://github.com/apache/airflow/pull/63733#discussion_r2941535964), [#62816](https://github.com/apache/airflow/pull/62816#discussion_r2892283042), [#62790](https://github.com/apache/airflow/pull/62790#discussion_r3066482686)

### `airflow-r422` — Pick the newsfragment from the change's actual user-visible impact: none at all for a documentation-only or purely internal change, and bugfix.rst rather than significant.rst for an internal fix that changes no observable behaviour.

- **Trigger** — A PR whose diff touches only docs also adds a file under newsfragments/, or a significant.rst fragment is added for an internal race-condition fix or scheduler-internal improvement with no API or behaviour change.
- **Why** — Newsfragments become the release notes users read; a fragment for a change nobody outside the repo can observe, or a significant fragment for an internal fix, inflates the upgrade reading users must do.
- **Scope** — `airflow-core/newsfragments/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67994](https://github.com/apache/airflow/pull/67994#discussion_r3383967813) — `airflow-core/newsfragments/67994.doc.rst` — I don't think you need a newsfragment for a docs update, that's quite overkill. But…
- PR [#65239](https://github.com/apache/airflow/pull/65239#discussion_r3088683803) — `airflow-core/newsfragments/65239.bugfix.rst` — I think we do not need a newsfragment for this fix. Newsfragments are for important…
- PR [#62501](https://github.com/apache/airflow/pull/62501#discussion_r3512131105) — `airflow-core/newsfragments/62501.significant.rst` — This is not user-facing but more like internal improvement. I feel we don't need a…

</details>

Precedent: [#67994](https://github.com/apache/airflow/pull/67994#discussion_r3383967813), [#65239](https://github.com/apache/airflow/pull/65239#discussion_r3088683803), [#62501](https://github.com/apache/airflow/pull/62501#discussion_r3512131105)
