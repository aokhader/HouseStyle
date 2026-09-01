# apache/airflow — mined review conventions

Generated 2026-08-31T21:52:50.700474+00:00 by `distill/critic.py` from 499 candidate rules that map subagents extracted from merged-PR review comments.

**Support** is the number of distinct PRs in a rule's merged evidence. A pattern is promoted to a rule at support >= 3; everything below that stays a candidate, in the companion candidates file.

Review comments are never reproduced here. Each evidence line carries a permalink and an excerpt of at most 15 words.

| | |
|---|---|
| rules promoted | 14 |
| candidates (support below threshold) | 344 |
| incidents (one-off fixes, not conventions) | 58 |
| contested pairs | 0 |

To disagree with a rule, delete its section and commit. This file is the rulebook, not a cache.

## correctness

### `airflow-r009` — Put imports at module scope; an import inside a function, method, test helper or fixture body is acceptable only to break a genuine circular import or for deliberate lazy loading (worker isolation, TYPE_CHECKING), and must carry a comment naming the reason.

- **Trigger** — An import or from-import statement appears inside a function, method, test helper or fixture body with no adjacent comment explaining the circular-import or lazy-loading reason.
- **Why** — Function-body imports hide real dependency cycles and cost on every call; without the comment the next reader cannot tell whether the placement is load-bearing or accidental, so nobody ever moves it back.
- **Scope** — `airflow-core/tests/unit/` `providers/common/ai/tests/unit/common/ai/toolsets/` `task-sdk/src/airflow/sdk/`
- **Support** — 5 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#68118](https://github.com/apache/airflow/pull/68118#discussion_r3367146276) — `airflow-core/tests/unit/dag_processing/test_manager.py` — The test adds an import inside the test function body. In this repo imports are…
- PR [#64563](https://github.com/apache/airflow/pull/64563#discussion_r3025276601) — `task-sdk/src/airflow/sdk/definitions/decorators/__init__.py` — `is_decorated_task` is imported inside `result()`, but this module already imports from `airflow.sdk.bases.decorator` at the top,…
- PR [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669149) — `providers/common/ai/tests/unit/common/ai/toolsets/test_datafusion.py` — Imports inside helper functions make dependency and linting behavior harder to reason about. Since this…
- PR [#62696](https://github.com/apache/airflow/pull/62696#discussion_r2973215185) — `task-sdk/src/airflow/sdk/configuration.py` — `AirflowSDKConfigParser.__init__` now performs a local import of `ProvidersManagerTaskRuntime`. If this is to avoid a circular…
- PR [#61077](https://github.com/apache/airflow/pull/61077#discussion_r2895879084) — `airflow-core/tests/unit/cli/commands/test_dag_command.py` — The imports at lines 1077-1079 are inside the test method body rather than at the…

</details>

Precedent: [#68118](https://github.com/apache/airflow/pull/68118#discussion_r3367146276), [#64563](https://github.com/apache/airflow/pull/64563#discussion_r3025276601), [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669149), [#62696](https://github.com/apache/airflow/pull/62696#discussion_r2973215185), [#61077](https://github.com/apache/airflow/pull/61077#discussion_r2895879084)

### `airflow-r007` — Distinguish absence from a legitimate falsy value: test with `is not None` in Python and an explicit undefined/null check in TypeScript, and do not collapse None into an empty container with `param or []`, wherever 0, False, an empty string or an empty collection carry meaning.

- **Trigger** — `if bundle_version:`, `Boolean(value)` or `if (value)` is used as a presence check on a field whose valid domain includes falsy values (a map_index of 0, a falsy XCom value), or `self.param = param or []` in an operator __init__ where an explicit empty list means something downstream.
- **Why** — Airflow's domain is full of meaningful zeros and empty values - map_index 0, an XCom of False, an empty list that clears permissions - and a truthiness check silently turns each of them into `not supplied`.
- **Scope** — `airflow-core/src/airflow/` `providers/`
- **Support** — 4 distinct PRs, 4 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67226](https://github.com/apache/airflow/pull/67226#discussion_r3283917687) — `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/operators/pod.py` — If the value evaluates to `False` would not persist. Can you change to explicit NULL…
- PR [#64538](https://github.com/apache/airflow/pull/64538#discussion_r3038203070) — `providers/databricks/src/airflow/providers/databricks/operators/databricks_workflow.py` — `access_control_list` is normalized with `access_control_list or []`, which makes it impossible to distinguish an explicitly…
- PR [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3486308679) — `airflow-core/src/airflow/models/dag_version.py` — Let's set this line to `if bundle_version is not None` to guard against `bundle_version=""` selecting…
- PR [#54210](https://github.com/apache/airflow/pull/54210#discussion_r2266280970) — `airflow-core/src/airflow/ui/src/pages/Events/filterUtils.ts` — Take a look at `const getFilterCount` in DagsFilter. You can't do `Boolean(something)` because this will…

</details>

Precedent: [#67226](https://github.com/apache/airflow/pull/67226#discussion_r3283917687), [#64538](https://github.com/apache/airflow/pull/64538#discussion_r3038203070), [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3486308679), [#54210](https://github.com/apache/airflow/pull/54210#discussion_r2266280970)

### `airflow-r006` — A broad `except Exception` must not swallow or re-wrap an exception that is deliberately raised to propagate: re-raise the specific type before the generic handler, and when introducing such an exception, update every enclosing fall-through loop to let it through in the same change.

- **Trigger** — An except Exception block in dag_processing/ wraps a sentinel such as CallbackBundleUnavailable, a `raise AirflowException(...)` sits inside a try whose downstream `except Exception as e` re-wraps it, or a secrets backend is made to raise PermissionError without changing the `except Exception: continue` backend-iteration loops in execution_time/context.py and models/connection.py.
- **Why** — These handlers exist to tolerate incidental failures; when they also catch the exception a caller was meant to see, the deliberate signal disappears and the system quietly does the wrong thing - a denied secret simply falls through to the next backend.
- **Scope** — `airflow-core/src/airflow/dag_processing/` `providers/celery/src/airflow/providers/celery/executors/` `task-sdk/src/airflow/sdk/execution_time/secrets/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#66575](https://github.com/apache/airflow/pull/66575#discussion_r3262697680) — `task-sdk/src/airflow/sdk/execution_time/secrets/execution_api.py` — Raising `PermissionError` here doesn't actually close the gap because the outer dispatcher loops in `airflow/sdk/execution_time/context.py`…
- PR [#65543](https://github.com/apache/airflow/pull/65543#discussion_r3118690531) — `airflow-core/src/airflow/dag_processing/manager.py` — If a subclass override calls back into `super().initialize_callback_bundle(...)` or chains to another helper that raises…
- PR [#64767](https://github.com/apache/airflow/pull/64767#discussion_r3066476663) — `providers/celery/src/airflow/providers/celery/executors/default_celery.py` — The new explicit `AirflowException` raised for missing `SSL_KEY`/`SSL_CERT` will be caught by the broad `except…

</details>

Precedent: [#66575](https://github.com/apache/airflow/pull/66575#discussion_r3262697680), [#65543](https://github.com/apache/airflow/pull/65543#discussion_r3118690531), [#64767](https://github.com/apache/airflow/pull/64767#discussion_r3066476663)

### `airflow-r008` — Do not write an inline try/except ImportError compatibility shim where a central layer already handles the import - airflow.utils.sqlalchemy for SQLAlchemy 1.4/2.0 differences, airflow.providers.common.compat for provider redirects - or where the import cannot fail in the supported version.

- **Trigger** — A model file adds a try/except ImportError block to shim mapped_column or Mapped from sqlalchemy.orm, or a core test or provider module adds a `try: from airflow.X import Y / except ImportError:` block for a symbol the current core exports or common.compat already redirects.
- **Why** — Compat shims are load-bearing and have to be retired deliberately; scattering redundant copies through individual files hides which ones still matter and leaves dead branches nobody can safely delete.
- **Scope** — `airflow-core/` `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#64143](https://github.com/apache/airflow/pull/64143#discussion_r2992738955) — `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/template_rendering.py` — Why do we need the except for import error here? I think it was there…
- PR [#55954](https://github.com/apache/airflow/pull/55954#discussion_r2382719028) — `airflow-core/src/airflow/models/backfill.py` — I agree with Ash's comment - that was, after all, the purpose of the shim…
- PR [#54383](https://github.com/apache/airflow/pull/54383#discussion_r2299840242) — `airflow-core/tests/unit/cli/commands/test_dag_command.py` — We wont need compat here because its a core test? We could just do the…

</details>

Precedent: [#64143](https://github.com/apache/airflow/pull/64143#discussion_r2992738955), [#55954](https://github.com/apache/airflow/pull/55954#discussion_r2382719028), [#54383](https://github.com/apache/airflow/pull/54383#discussion_r2299840242)

## api-design

### `airflow-r002` — Keep the public surface of provider operators, hooks, executors and extractors backward compatible: a renamed attribute or method keeps a deprecated forwarding property, a removed parameter is deprecated with its values mapped onto the replacement, and a changed return value, changed traversal or new constructor keyword is opt-in through a parameter that defaults to the existing behaviour.

- **Trigger** — A diff renames a public attribute or method on a BaseExecutor subclass with no shim, removes an operator parameter such as wait_policy and hard-codes one of its former values, changes an existing operator's execute() return shape, alters what an existing hook method traverses or returns, or passes a new required keyword to a subclass constructor such as BaseExtractor.__init__ unconditionally.
- **Why** — Provider packages are consumed by DAGs and subclasses Airflow cannot see or update; a silent change to the public surface breaks them at runtime in someone else's deployment, with no deprecation cycle to warn them.
- **Scope** — `providers/`
- **Support** — 6 distinct PRs, 4 distinct reviewers

<details><summary>Evidence</summary>

- PR [#66992](https://github.com/apache/airflow/pull/66992#discussion_r3322901303) — `providers/openlineage/src/airflow/providers/openlineage/extractors/manager.py` — source_code_enabled is passed as a new keyword to every extractor constructor in _get_extractor(). Custom extractors…
- PR [#64465](https://github.com/apache/airflow/pull/64465#discussion_r3025335272) — `providers/sftp/src/airflow/providers/sftp/hooks/sftp.py` — `list_directory()` now recursively walks subdirectories and returns full paths. This is a breaking behavior change…
- PR [#63657](https://github.com/apache/airflow/pull/63657#discussion_r3113972841) — `providers/amazon/src/airflow/providers/amazon/aws/executors/ecs/ecs_executor.py` — Why no shims? Pretty sure we need them for back-compat, no? Just something like ```python…
- PR [#63035](https://github.com/apache/airflow/pull/63035#discussion_r3133852800) — `providers/amazon/src/airflow/providers/amazon/aws/executors/aws_lambda/lambda_executor.py` — Can you add property shim for `pending_tasks` and `running_tasks` as well? They'll look something like…
- PR [#61284](https://github.com/apache/airflow/pull/61284#discussion_r2787581438) — `providers/google/src/airflow/providers/google/cloud/transfers/calendar_to_gcs.py` — I went over the PR again and noticed that changing the returned value from `dest_file_name`…
- PR [#56158](https://github.com/apache/airflow/pull/56158#discussion_r2384296825) — `providers/amazon/src/airflow/providers/amazon/aws/operators/emr.py` — The code hardcodes `WaitPolicy.WAIT_FOR_COMPLETION`, removing support for `WaitPolicy.WAIT_FOR_STEPS_COMPLETION` that was previously available through the `wait_policy`…

</details>

Precedent: [#66992](https://github.com/apache/airflow/pull/66992#discussion_r3322901303), [#64465](https://github.com/apache/airflow/pull/64465#discussion_r3025335272), [#63657](https://github.com/apache/airflow/pull/63657#discussion_r3113972841), [#63035](https://github.com/apache/airflow/pull/63035#discussion_r3133852800), [#61284](https://github.com/apache/airflow/pull/61284#discussion_r2787581438), [#56158](https://github.com/apache/airflow/pull/56158#discussion_r2384296825)

### `airflow-r001` — Do not add or keep public surface that nothing consumes: a parameter, field or property must have a real consumer in the repository and a real effect; if it is unimplemented or no longer used, remove it from the signature and docstring, or make supplying it warn or raise.

- **Trigger** — A field is added to an execution-API datamodel with no worker-side reader, a property is added to a core base class such as CronMixin with no in-core reference site, an __init__ stores self.param that no method reads, or a parameter is dropped from a DagBag implementation body but kept in the signature or docstring.
- **Why** — Every exported name is a compatibility promise Airflow then has to keep; a parameter that is silently ignored or a field nobody reads is a promise with no behaviour behind it, and users only find the gap after depending on it.
- **Scope** — `airflow-core/src/airflow/` `providers/common/ai/src/airflow/providers/common/ai/operators/`
- **Support** — 4 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#67717](https://github.com/apache/airflow/pull/67717#discussion_r3366361035) — `airflow-core/src/airflow/timetables/_cron.py` — This public `timezone` property has no consumers in core. Per the PR description it was…
- PR [#66161](https://github.com/apache/airflow/pull/66161#discussion_r3176620534) — `airflow-core/src/airflow/dag_processing/dagbag.py` — Removing the `if include_examples:` block here makes the `include_examples` parameter a **silent no-op** on `DagBag.__init__`…
- PR [#63081](https://github.com/apache/airflow/pull/63081#discussion_r2901183999) — `providers/common/ai/src/airflow/providers/common/ai/operators/agent.py` — `self.webhook_url` is stored but nothing in the mixin, operator, or plugin ever reads or posts…
- PR [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3375946447) — `airflow-core/src/airflow/api_fastapi/execution_api/datamodels/taskinstance.py` — Is the worker actually consuming `bundle_version` from its run context? The version gating in v2026_06_30…

</details>

Precedent: [#67717](https://github.com/apache/airflow/pull/67717#discussion_r3366361035), [#66161](https://github.com/apache/airflow/pull/66161#discussion_r3176620534), [#63081](https://github.com/apache/airflow/pull/63081#discussion_r2901183999), [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3375946447)

### `airflow-r003` — Put behaviour that every concrete subclass needs in the shared base class or mixin - BaseExecutor, BaseCoordinator, BaseNotifier - rather than re-implementing it, or repeating the version guard, in each concrete implementation.

- **Trigger** — A new workload-handling method or branch is added to several concrete executor files with no base-class implementation, a new per-language coordinator re-implements socket server startup or accept helpers, or an `if AIRFLOW_V_x_y_PLUS:` guard is added inside a concrete Notifier.
- **Why** — Airflow's concrete executors, coordinators and notifiers live across providers and out-of-tree code Airflow does not control; anything the base class can do for them is a change every one of those implementations is spared.
- **Scope** — `airflow-core/src/airflow/executors/` `providers/slack/src/airflow/providers/slack/notifications/` `task-sdk/src/airflow/sdk/coordinators/java/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#65958](https://github.com/apache/airflow/pull/65958#discussion_r3293670791) — `task-sdk/src/airflow/sdk/coordinators/java/coordinator.py` — The `_start_server`, `_accept_connections`, the `stdout/stderr` socketpair setup isn't actually JVM-specific. Would it make sense to…
- PR [#62343](https://github.com/apache/airflow/pull/62343#discussion_r2970099580) — `airflow-core/src/airflow/executors/local_executor.py` — So the implementation approach in this PR means that all (=_ALL_) executors must be touched…
- PR [#55308](https://github.com/apache/airflow/pull/55308#discussion_r2331604445) — `providers/slack/src/airflow/providers/slack/notifications/slack_webhook.py` — Should we add a check in the BaseNotifier instead? Something like: ``` if context and…

</details>

Precedent: [#65958](https://github.com/apache/airflow/pull/65958#discussion_r3293670791), [#62343](https://github.com/apache/airflow/pull/62343#discussion_r2970099580), [#55308](https://github.com/apache/airflow/pull/55308#discussion_r2331604445)

## async

### `airflow-r004` — A trigger's run() must yield a distinct terminal TriggerEvent for every terminal condition it can reach: separate success and failure events rather than one collapsed success, and a timeout event carrying the timeout status and a descriptive reason rather than a bare break or return - with any cancellation side-effect in the timeout branch wrapped in its own try/except so a failed cancel cannot replace the event.

- **Trigger** — An `async def run()` yields a TriggerEvent with no separate success/failure handling or compares status against a single string instead of the provider's Enum, or a polling loop in providers/*/triggers/*.py reaches its timeout condition and breaks without yielding, or performs a cancel call in the timeout branch outside a dedicated try/except.
- **Why** — The triggerer only learns what happened from the event: a loop that exits without yielding leaves the task hanging, and a failure reported as success sends the DAG down the wrong path.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#68799](https://github.com/apache/airflow/pull/68799#discussion_r3514903842) — `providers/microsoft/azure/src/airflow/providers/microsoft/azure/triggers/ai_agents.py` — Why not yield the timeout immediately after instead of break like this: ``` if time.monotonic()…
- PR [#67524](https://github.com/apache/airflow/pull/67524#discussion_r3329167919) — `providers/amazon/src/airflow/providers/amazon/aws/triggers/dms.py` — I would use the `ENUM` for the task state instead of raw strings to be…
- PR [#63614](https://github.com/apache/airflow/pull/63614#discussion_r3144426356) — `providers/microsoft/azure/src/airflow/providers/microsoft/azure/triggers/synapse.py` — The timeout-path cancel on line 141 isn't wrapped in its own try/except, so a transient…

</details>

Precedent: [#68799](https://github.com/apache/airflow/pull/68799#discussion_r3514903842), [#67524](https://github.com/apache/airflow/pull/67524#discussion_r3329167919), [#63614](https://github.com/apache/airflow/pull/63614#discussion_r3144426356)

## testing

### `airflow-r014` — Mocks that stand in for a real interface must be specced — `MagicMock(spec=...)`, `spec_set=`, or `create_autospec` — including nested attributes; `MagicMock(autospec=True)` is a no-op keyword and does not spec anything.

- **Trigger** — A bare `MagicMock()` (or `MagicMock(autospec=True)`) substituted for a known type such as the Task SDK execution API `Client`, `RunContext`, `ToolsetTool`, or a credentials object, then given attributes the real type may not have
- **Why** — An unspecced mock fabricates any attribute, so tests keep passing when production code reads a field that no longer exists on the real object.
- **Scope** — `providers/` `task-sdk/tests/task_sdk/`
- **Support** — 5 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#68974](https://github.com/apache/airflow/pull/68974#discussion_r3473214532) — `providers/databricks/tests/unit/databricks/operators/test_databricks.py` — `MagicMock(autospec=True)` here does not actually apply autospeccing ("autospec" is a `mock.patch` feature, not a `MagicMock`…
- PR [#67635](https://github.com/apache/airflow/pull/67635#discussion_r3316173929) — `task-sdk/tests/task_sdk/coordinators/test_subprocess.py` — `mock_client` is created as a bare `MagicMock()` without `spec`/`autospec`, which can hide real API mismatches…
- PR [#64568](https://github.com/apache/airflow/pull/64568#discussion_r3066480500) — `task-sdk/tests/task_sdk/execution_time/test_supervisor.py` — `fake_client = MagicMock()` is an unspecced mock; consider using a `spec`/`spec_set` (or `autospec`) for the…
- PR [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669079) — `providers/common/ai/tests/unit/common/ai/toolsets/test_datafusion.py` — These tests frequently pass `MagicMock()` for `ctx` and `tool` without a spec. Using a spec…
- PR [#53801](https://github.com/apache/airflow/pull/53801#discussion_r3176107143) — `providers/hashicorp/tests/unit/hashicorp/hooks/test_vault.py` — Please give this new credential double a `spec`/`autospec`. A bare `MagicMock` fabricates arbitrary attributes, so…

</details>

Precedent: [#68974](https://github.com/apache/airflow/pull/68974#discussion_r3473214532), [#67635](https://github.com/apache/airflow/pull/67635#discussion_r3316173929), [#64568](https://github.com/apache/airflow/pull/64568#discussion_r3066480500), [#62850](https://github.com/apache/airflow/pull/62850#discussion_r2886669079), [#53801](https://github.com/apache/airflow/pull/53801#discussion_r3176107143)

## naming

### `airflow-r012` — Reuse Airflow's established name for a concept instead of inventing a synonym: `run_after` for the DAG run scheduling timestamp, `wait_for_completion` for the wait-for-finish flag, and an `a`-prefixed method name (`aget_connection`) for the async variant of an existing method.

- **Trigger** — A new or renamed parameter/method using `logical_date` or `date` for scheduling time, `wait_for_termination` for a completion flag, or an `async_`-prefixed name where a sync counterpart exists
- **Why** — These names appear across operators, hooks and the SDK; a synonym forces users to learn two vocabularies for the same concept and breaks the reader's ability to guess an API.
- **Scope** — `providers/` `task-sdk/src/airflow/sdk/bases/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#60369](https://github.com/apache/airflow/pull/60369#discussion_r2760020633) — `providers/microsoft/azure/src/airflow/providers/microsoft/azure/operators/powerbi.py` — Here you are using `wait_for_termination`, I would rather use `wait_for_completion` instead for consistency purposes. I…
- PR [#55110](https://github.com/apache/airflow/pull/55110#discussion_r2317575671) — `providers/google/src/airflow/providers/google/cloud/hooks/bigquery.py` — if we want to replace it with `run_after` in the future, let's make it `run_after`…
- PR [#53831](https://github.com/apache/airflow/pull/53831#discussion_r2249148386) — `task-sdk/src/airflow/sdk/bases/hook.py` — I wonder if this should be called `aget_connection` instead. I think this might be the…

</details>

Precedent: [#60369](https://github.com/apache/airflow/pull/60369#discussion_r2760020633), [#55110](https://github.com/apache/airflow/pull/55110#discussion_r2317575671), [#53831](https://github.com/apache/airflow/pull/53831#discussion_r2249148386)

## providers

### `airflow-r013` — Raise the native Python exception that fits - ValueError, TypeError, RuntimeError - for argument validation, bad user input, unexpected internal state and third-party service failures in provider code and triggers, rather than AirflowException.

- **Trigger** — A new `raise AirflowException(...)` for parameter validation inside a provider hook or operator, for an internal error condition inside a BaseTrigger.run() coroutine, or for an error that originated in an external service.
- **Why** — AirflowException means Airflow itself decided to fail; using it for everything strips the type information callers branch on and makes a vendor API error indistinguishable from a scheduler failure.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#62240](https://github.com/apache/airflow/pull/62240#discussion_r2843460423) — `providers/amazon/src/airflow/providers/amazon/aws/hooks/sagemaker_unified_studio_notebook.py` — We're trying to avoid the overuse of `AirflowException` there is nothing related to Airflow failing…
- PR [#60963](https://github.com/apache/airflow/pull/60963#discussion_r2725622949) — `providers/imap/src/airflow/providers/imap/hooks/imap.py` — Following a recent decision (see [dev list thread](https://lists.apache.org/thread/5rv4tz0oc27bgr4khx0on0jz8fpxvh55)), the directive is not to use `AirflowException`,…
- PR [#55068](https://github.com/apache/airflow/pull/55068#discussion_r2497942742) — `providers/google/src/airflow/providers/google/cloud/triggers/dataproc.py` — ```suggestion raise RuntimeError( ``` not sure whehter we can duplicate these parts by moving them…

</details>

Precedent: [#62240](https://github.com/apache/airflow/pull/62240#discussion_r2843460423), [#60963](https://github.com/apache/airflow/pull/60963#discussion_r2725622949), [#55068](https://github.com/apache/airflow/pull/55068#discussion_r2497942742)

## docs

### `airflow-r010` — Spell the Airflow concept and its Python class as `Dag`/`Dags` in prose - user-facing docs, newsfragments, release notes, config.yml descriptions, docstrings and test names - reserving all-caps `DAG` for code identifiers and quoted strings.

- **Trigger** — Prose in a newsfragment, release note, config.yml description, docstring or test name uses all-caps DAG/DAGs for the concept or the Python class, outside backticks or a code identifier.
- **Why** — Airflow 3 renamed the class to Dag and reviewers hold that spelling in prose; all-caps DAG now reads as the literal identifier, so mixing the two makes the docs look like they describe two different things.
- **Scope** — `airflow-core/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#64322](https://github.com/apache/airflow/pull/64322#discussion_r3014691143) — `airflow-core/newsfragments/64322.bugfix.rst` — ```suggestion Fix premature asset-triggered DagRuns when ``AssetDagRunQueue`` had rows but ``SerializedDagModel`` was not yet available;…
- PR [#61702](https://github.com/apache/airflow/pull/61702#discussion_r2786095205) — `airflow-core/tests/unit/models/test_dag.py` — ```suggestion """Test that a Dag with multiple deadlines stores all deadlines and persists on re-serialization."""…
- PR [#59430](https://github.com/apache/airflow/pull/59430#discussion_r2660900575) — `airflow-core/src/airflow/config_templates/config.yml` — ```suggestion Controls the behavior of Dag stability checker performed before Dag parsing in the Dag…

</details>

Precedent: [#64322](https://github.com/apache/airflow/pull/64322#discussion_r3014691143), [#61702](https://github.com/apache/airflow/pull/61702#discussion_r2786095205), [#59430](https://github.com/apache/airflow/pull/59430#discussion_r2660900575)

### `airflow-r011` — When a provider operator or hook gains a new parameter or changes its documented behaviour, update the class docstring - a `:param name:` entry describing the type, and for a Callable what each positional argument means - and the matching provider RST guide, in the same PR.

- **Trigger** — A new keyword argument on a provider operator or hook __init__ (e.g. KubernetesPodOperator) with no corresponding `:param:` entry, or a new or changed `:param ...:` list with no edit to providers/<name>/docs/operators/*.rst or providers/<name>/docs/connections/*.rst.
- **Why** — The published provider docs are generated from these two sources and are the only thing DAG authors see; a parameter documented in neither place effectively does not exist for users.
- **Scope** — `providers/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#64538](https://github.com/apache/airflow/pull/64538#discussion_r3113736037) — `providers/databricks/src/airflow/providers/databricks/operators/databricks_workflow.py` — Same as the `_CreateDatabricksWorkflowOperator` docstring: "Setting this replaces any existing job permissions" is only true…
- PR [#53801](https://github.com/apache/airflow/pull/53801#discussion_r3176107126) — `providers/hashicorp/src/airflow/providers/hashicorp/hooks/vault.py` — Updating only the hook docstring leaves the rendered Vault connection docs stale: `providers/hashicorp/docs/connections/vault.rst` still omits…
- PR [#53598](https://github.com/apache/airflow/pull/53598#discussion_r2280748143) — `providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/operators/pod.py` — The docstring of `container_name_log_prefix_enabled` and `log_formatter` is missing. https://github.com/apache/airflow/blob/16ee837a91cf9ee48c1596197b4df41bcb46ee29/providers/cncf/kubernetes/src/airflow/providers/cncf/kubernetes/operators/pod.py#L237-L238 Additionally, it would be nice to…

</details>

Precedent: [#64538](https://github.com/apache/airflow/pull/64538#discussion_r3113736037), [#53801](https://github.com/apache/airflow/pull/53801#discussion_r3176107126), [#53598](https://github.com/apache/airflow/pull/53598#discussion_r2280748143)

## commit-hygiene

### `airflow-r005` — Keep a PR scoped to the change its title and description claim: unrelated uv.lock churn must be reverted, an Alembic migration that fixes a pre-existing schema issue must go in its own PR, and a second independent feature must either be split out or added to the PR description with its own rationale and compatibility notes.

- **Trigger** — The diff contains uv.lock changes with no dependency bump in the description, an independent schema-fix migration alongside a feature migration, or a second unrelated feature (e.g. worker recycling added to a DAG-caching PR).
- **Why** — Reviewers approve what the description says; bundled unrelated changes get merged unreviewed and cannot be reverted independently when one of them regresses.
- **Scope** — `./` `airflow-core/src/airflow/`
- **Support** — 3 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3116493328) — `uv.lock` — 362 lines of churn here looks unrelated to this feature. Please revert or split into…
- PR [#60804](https://github.com/apache/airflow/pull/60804#discussion_r3066474591) — `airflow-core/src/airflow/cli/commands/api_server_command.py` — This PR introduces API server worker recycling (`worker_max_requests` + Uvicorn `limit_max_requests`) in addition to the…
- PR [#55954](https://github.com/apache/airflow/pull/55954#discussion_r2380281165) — `airflow-core/src/airflow/migrations/versions/0088_3_2_0_add_length_dag_bundle_team_bundle_name.py` — I mean: isn't this a problem today, and so this should be pulled out in…

</details>

Precedent: [#61550](https://github.com/apache/airflow/pull/61550#discussion_r3116493328), [#60804](https://github.com/apache/airflow/pull/60804#discussion_r3066474591), [#55954](https://github.com/apache/airflow/pull/55954#discussion_r2380281165)
