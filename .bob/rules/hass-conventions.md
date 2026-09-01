# home-assistant/core — mined review conventions

Generated 2026-08-31T21:52:51.081279+00:00 by `distill/critic.py` from 375 candidate rules that map subagents extracted from merged-PR review comments.

**Support** is the number of distinct PRs in a rule's merged evidence. A pattern is promoted to a rule at support >= 3; everything below that stays a candidate, in the companion candidates file.

Review comments are never reproduced here. Each evidence line carries a permalink and an excerpt of at most 15 words.

| | |
|---|---|
| rules promoted | 27 |
| candidates (support below threshold) | 232 |
| incidents (one-off fixes, not conventions) | 10 |
| contested pairs | 0 |

To disagree with a rule, delete its section and commit. This file is the rulebook, not a cache.

## correctness

### `hass-r011` — Missing or None device data must be handled explicitly and surface as unknown: guard coordinator.data, list indexing and device lookups before dereferencing them, and return None rather than crashing, raising UpdateFailed, or collapsing the absent value into the false/off branch.

- **Trigger** — A native_value/is_on/available property or an EntityDescription value_fn dereferences self.coordinator.data, indexes a library result or looks a device up by id with no None or membership guard; or a state expression such as `result.get(key) == "0"`, `bool(data.get(key, False))` or `"a" if flag else "b"` turns a possible None into a boolean.
- **Why** — Devices drop fields and go offline; reviewers want the entity to report unknown so users can see the data is missing, rather than a traceback in the log or a confidently wrong `off`.
- **Scope** — `homeassistant/components/`
- **Support** — 7 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#172813](https://github.com/home-assistant/core/pull/172813#discussion_r3339590630) — `homeassistant/components/helty/sensor.py` — `self.coordinator.data` can be `None` (e.g., before the first successful refresh or after update failures). Calling…
- PR [#172234](https://github.com/home-assistant/core/pull/172234#discussion_r3304021741) — `homeassistant/components/vistapool/binary_sensor.py` — `_coerce_to_bool()` can return `None`, but this branch treats `None` as falsy and will create the…
- PR [#170114](https://github.com/home-assistant/core/pull/170114#discussion_r3306568281) — `homeassistant/components/hr_energy_qube/select.py` — `self.coordinator.data` can be `None` before the first successful refresh (DataUpdateCoordinator starts with `data=None` and `last_update_success=True`…
- PR [#167956](https://github.com/home-assistant/core/pull/167956#discussion_r3089515106) — `homeassistant/components/sonos/switch.py` — Treat a missing `IncludeLinkedZones` key the same way as `poll_state()` does (unknown/unavailable) instead of implicitly…
- PR [#167905](https://github.com/home-assistant/core/pull/167905#discussion_r3066571400) — `homeassistant/components/fritz/sensor.py` — Handle empty CPU temperature lists during updates by also catching IndexError in `_retrieve_cpu_temperature_state` and returning…
- PR [#161882](https://github.com/home-assistant/core/pull/161882#discussion_r2971420467) — `homeassistant/components/nina/sensor.py` — `native_value` always calls `_get_warning_data()`. For slots where there is no active warning (or the warning…
- PR [#155786](https://github.com/home-assistant/core/pull/155786#discussion_r2690877665) — `homeassistant/components/nintendo_parental_controls/sensor.py` — The entity_picture property calls `get_player` every time it's accessed without any error handling. If the…

</details>

Precedent: [#172813](https://github.com/home-assistant/core/pull/172813#discussion_r3339590630), [#172234](https://github.com/home-assistant/core/pull/172234#discussion_r3304021741), [#170114](https://github.com/home-assistant/core/pull/170114#discussion_r3306568281), [#167956](https://github.com/home-assistant/core/pull/167956#discussion_r3089515106), [#167905](https://github.com/home-assistant/core/pull/167905#discussion_r3066571400), [#161882](https://github.com/home-assistant/core/pull/161882#discussion_r2971420467), [#155786](https://github.com/home-assistant/core/pull/155786#discussion_r2690877665)

### `hass-r005` — Anything derived from device or coordinator data must be recomputed on every update path rather than frozen at construction: populate attributes and capability mappings from one shared method called from both __init__ and the update callback, assign on all sibling branches of a conditional, and clear a cached value when the new payload no longer contains it, before writing state.

- **Trigger** — An entity __init__ assigns a subset of the _attr_* values its update callback assigns or caches a dict built from device status/capabilities; a state-derivation method sets an attribute in one branch and leaves it untouched in the elif/else; or an update callback calls async_write_ha_state on an early-return branch without resetting the value or availability.
- **Why** — A value computed once in __init__ or on only one branch goes stale the moment the device changes, and users see an attribute that never updates.
- **Scope** — `homeassistant/components/`
- **Support** — 5 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#176444](https://github.com/home-assistant/core/pull/176444#discussion_r3576876247) — `homeassistant/components/netatmo/sensor.py` — Clear the cached value and restore local availability when this measurement is absent. This is…
- PR [#167308](https://github.com/home-assistant/core/pull/167308#discussion_r3033378833) — `homeassistant/components/luci/device_tracker.py` — Update the entity name when the coordinator data changes (e.g., when the hostname changes) so…
- PR [#166573](https://github.com/home-assistant/core/pull/166573#discussion_r2993168739) — `homeassistant/components/device_tracker/legacy.py` — Clear `_in_zones` when the device state is derived from `location_name` or when no GPS fix…
- PR [#164536](https://github.com/home-assistant/core/pull/164536#discussion_r2919218664) — `homeassistant/components/casper_glow/light.py` — Would it make sense to extract setting the `_attr_*` into a separate method you call…
- PR [#160034](https://github.com/home-assistant/core/pull/160034#discussion_r2834073329) — `homeassistant/components/smartthings/media_player.py` — `async_select_source` relies on `_source_to_smartthings_id` populated during `__init__` (or when `source_list` is accessed). If supported sources…

</details>

Precedent: [#176444](https://github.com/home-assistant/core/pull/176444#discussion_r3576876247), [#167308](https://github.com/home-assistant/core/pull/167308#discussion_r3033378833), [#166573](https://github.com/home-assistant/core/pull/166573#discussion_r2993168739), [#164536](https://github.com/home-assistant/core/pull/164536#discussion_r2919218664), [#160034](https://github.com/home-assistant/core/pull/160034#discussion_r2834073329)

### `hass-r006` — Anything interpolated into a user-facing error message or into translation_placeholders must be a deterministic, informative string: never a raw container repr such as str(set) or str(dict), never the repr of a bare wrapper exception instead of the underlying library error or its __cause__, and never an exception whose str() is empty - fall back to the exception type name.

- **Trigger** — A raise builds translation_placeholders from str() of a set/list/dict, formats an exception that was itself raised bare with `raise CustomError from err`, or interpolates an exception such as TimeoutError that stringifies to an empty value.
- **Why** — These strings are the only thing the user sees when setup fails; a Python repr, a blank message, or a wrapper with no detail leaves them with nothing to act on and makes bug reports useless.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#168268](https://github.com/home-assistant/core/pull/168268#discussion_r3097436602) — `homeassistant/components/iaqualink/__init__.py` — Ensure the ConfigEntryNotReady message includes a non-empty error detail (e.g., fall back to the exception…
- PR [#164417](https://github.com/home-assistant/core/pull/164417#discussion_r2867329708) — `homeassistant/components/proxmoxve/coordinator.py` — `ProxmoxServerError` is raised without a message (only `from err`), but `_async_setup` formats the user-facing error…
- PR [#163760](https://github.com/home-assistant/core/pull/163760#discussion_r2836939543) — `homeassistant/components/roborock/vacuum.py` — The `{map_flags}` placeholder is built from `str(unique_map_flags)` which produces a set representation with non-deterministic ordering…

</details>

Precedent: [#168268](https://github.com/home-assistant/core/pull/168268#discussion_r3097436602), [#164417](https://github.com/home-assistant/core/pull/164417#discussion_r2867329708), [#163760](https://github.com/home-assistant/core/pull/163760#discussion_r2836939543)

### `hass-r007` — Compose _attr_unique_id and DeviceInfo identifiers from every identifier that can vary - the parent node, hub or device id alongside the config entry id and the description key, plus a per-entity suffix - whenever the resource or entity is only unique inside its parent.

- **Trigger** — A unique_id or identifiers f-string is built from only the config entry id/unique id plus a description key or resource name for a resource enumerated per device, node or hub; or a comprehension creates several entities of the same class from one device object with the unique_id derived only from the device id.
- **Why** — Registry collisions silently drop entities, so reviewers check that every component of the identity that can repeat ends up in the id.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#168290](https://github.com/home-assistant/core/pull/168290#discussion_r3089017192) — `homeassistant/components/duco/sensor.py` — Include the BOX node_id in DucoBoxSensorEntity unique_id to prevent duplicate unique IDs if the API…
- PR [#166952](https://github.com/home-assistant/core/pull/166952#discussion_r3021523993) — `homeassistant/components/tuya/fan.py` — Include a quirk-specific suffix (e.g., the quirk entity key) in the entity’s unique_id when building…
- PR [#166409](https://github.com/home-assistant/core/pull/166409#discussion_r2988646408) — `homeassistant/components/proxmoxve/entity.py` — Include the node identifier in the storage DeviceInfo identifiers and entity unique_id to avoid collisions…

</details>

Precedent: [#168290](https://github.com/home-assistant/core/pull/168290#discussion_r3089017192), [#166952](https://github.com/home-assistant/core/pull/166952#discussion_r3021523993), [#166409](https://github.com/home-assistant/core/pull/166409#discussion_r2988646408)

### `hass-r008` — Config flow steps, including discovery steps, must catch the same set of library exceptions the integration handles during entry setup - connection, timeout and authentication errors, TimeoutError included - and map each onto a specific errors key or abort reason such as cannot_connect, invalid_auth or not_found, rather than letting them escape or collapsing them into unknown.

- **Trigger** — A config-flow step awaits a library call with no except clause, catches only the library's own error base class while the coordinator also catches TimeoutError, or maps every failure to reason unknown.
- **Why** — The config flow is the only place the user can fix the problem, so it has to tell them which problem it is; an uncaught or unknown-mapped error just shows an unrecoverable dialog.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#169597](https://github.com/home-assistant/core/pull/169597#discussion_r3173272992) — `homeassistant/components/indevolt/config_flow.py` — Catch indevolt_api TimeOutException (and unexpected response/key errors) during DHCP discovery and input validation so the…
- PR [#165992](https://github.com/home-assistant/core/pull/165992#discussion_r2976997228) — `homeassistant/components/bsblan/config_flow.py` — `_get_bsblan_info()` wraps circuit discovery in `except BSBLANError`, but it also calls `await bsblan.initialize()` which can…
- PR [#160953](https://github.com/home-assistant/core/pull/160953#discussion_r3336753916) — `homeassistant/components/incomfort/config_flow.py` — Handle HTTP-level failures from `client.heaters()` explicitly so the config flow shows the correct error reason…

</details>

Precedent: [#169597](https://github.com/home-assistant/core/pull/169597#discussion_r3173272992), [#165992](https://github.com/home-assistant/core/pull/165992#discussion_r2976997228), [#160953](https://github.com/home-assistant/core/pull/160953#discussion_r3336753916)

### `hass-r009` — Handle each failure class on its own branch: only an authentication failure (401) may start a reauth flow, and it must raise its own message saying reauthentication is required; an authorization failure (403) must raise ConfigEntryError because new credentials cannot fix it; and connection, timeout and server-side failures must be reported the way the sibling setup path reports them.

- **Trigger** — An except clause groups an authentication error together with connection/transport errors into one HomeAssistantError, or a config-flow/coordinator branch converts a broad API exception or any 4xx into a specific abort/error key or calls async_start_reauth without inspecting the status code.
- **Why** — Reauth prompts the user for credentials, so pointing it at a network outage or a permissions problem sends them down a path that cannot possibly succeed.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#169682](https://github.com/home-assistant/core/pull/169682#discussion_r3178134638) — `homeassistant/components/proxmoxve/config_flow.py` — Translate only 4xx node-list failures to `no_nodes_found`. This branch still turns every `client.nodes.get()` `ResourceException` into…
- PR [#164615](https://github.com/home-assistant/core/pull/164615#discussion_r2873450354) — `homeassistant/components/anthropic/entity.py` — Authentication errors now return the same generic message as connection errors ("Sorry, I had a…
- PR [#164417](https://github.com/home-assistant/core/pull/164417#discussion_r2867329718) — `homeassistant/components/proxmoxve/coordinator.py` — The permission fetch path triggers `async_start_reauth` for any 4xx `ResourceException`. A 403 (insufficient privileges) is…

</details>

Precedent: [#169682](https://github.com/home-assistant/core/pull/169682#discussion_r3178134638), [#164615](https://github.com/home-assistant/core/pull/164615#discussion_r2873450354), [#164417](https://github.com/home-assistant/core/pull/164417#discussion_r2867329718)

### `hass-r010` — Media source identifier parsing and service helpers must validate their inputs and preconditions before use and raise a proper Home Assistant error - Unresolvable/BrowseError, ServiceValidationError or HomeAssistantError - so a malformed identifier, an unloaded config entry, or an uncastable user value never surfaces as a raw UnboundLocalError, AttributeError, ValueError or TypeError.

- **Trigger** — A from_identifier/async_resolve_media splits an identifier and assigns fields without checking the parts exist; code reads entry.runtime_data after async_get_entry without checking the entry is loaded; or an entity service passes a user-provided value straight into int()/float()/an enum lookup or a library call with no try/except.
- **Why** — These paths are all reachable from user input, and a raw Python exception gives the user a traceback instead of a message telling them what they typed wrong.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#168494](https://github.com/home-assistant/core/pull/168494#discussion_r3106902453) — `homeassistant/components/shelly/media_player.py` — Validate `media_id` before casting to `int` for local audio playback and raise a user-facing error…
- PR [#167028](https://github.com/home-assistant/core/pull/167028#discussion_r3020235710) — `homeassistant/components/octoprint/__init__.py` — Check that the config entry is loaded (and has runtime_data) before returning its client in…
- PR [#162001](https://github.com/home-assistant/core/pull/162001#discussion_r2848004476) — `homeassistant/components/icloud/media_source.py` — The `from_identifier` method will raise `UnboundLocalError` if the identifier string is empty or contains no…

</details>

Precedent: [#168494](https://github.com/home-assistant/core/pull/168494#discussion_r3106902453), [#167028](https://github.com/home-assistant/core/pull/167028#discussion_r3020235710), [#162001](https://github.com/home-assistant/core/pull/162001#discussion_r2848004476)

## api-design

### `hass-r002` — A value that already has a name must be imported, not restated: use the integration's and core's own constants and helpers (DOMAIN, CONF_*, STATE_*, identifier helpers) wherever a literal would otherwise be written, in tests as well as in code, and define a value used by more than one module once - in the integration's const.py for code, in the shared test module for tests.

- **Trigger** — A raw literal such as the domain name, `unavailable`, or a config/option key appears in a module, test or conftest where the integration or homeassistant.const already defines a constant; an identifier is recomputed inline where the integration has a helper; or a constant, command map or tuning literal (delay, timeout, threshold, TEST_*) is added to a second module while the same value is already named elsewhere in that integration.
- **Why** — Duplicated literals drift apart silently, so reviewers ask for a single definition that a rename or a retune cannot leave half the code and tests behind on.
- **Scope** — `homeassistant/components/` `tests/components/`
- **Support** — 8 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#174276](https://github.com/home-assistant/core/pull/174276#discussion_r3487432969) — `homeassistant/components/yardian/button.py` — Avoid hardcoding the refresh delay. `switch.py` already uses the `SWITCH_REFRESH_DELAY` constant from `const.py` (value `2`)…
- PR [#173454](https://github.com/home-assistant/core/pull/173454#discussion_r3389632389) — `tests/components/todo/conftest.py` — `TEST_TIMEZONE` is also defined in `tests/components/todo/test_init.py`, which risks the two copies drifting over time. Consider…
- PR [#172464](https://github.com/home-assistant/core/pull/172464#discussion_r3318894587) — `tests/components/energieleser/conftest.py` — The integration code uses `CONF_DEVICE_ID` from `homeassistant.const` (see `config_flow.py` and `coordinator.py`), while the test fixtures…
- PR [#171761](https://github.com/home-assistant/core/pull/171761#discussion_r3283425697) — `homeassistant/components/system_bridge/__init__.py` — `POWER_COMMAND_MAP` (and related service constants like `CONF_KEY`/`CONF_TEXT`) now exist both here and in `services.py`. This…
- PR [#168603](https://github.com/home-assistant/core/pull/168603#discussion_r3109654673) — `tests/components/go2rtc/test_init.py` — Derive the expected stream identifier in this test via get_camera_identifier(camera) to keep the assertions aligned…
- PR [#168154](https://github.com/home-assistant/core/pull/168154#discussion_r3078053807) — `tests/components/fluss/test_init.py` — Use the `STATE_UNAVAILABLE` constant here (as in the other Fluss tests) instead of the raw…
- PR [#168064](https://github.com/home-assistant/core/pull/168064#discussion_r3105853652) — `tests/components/onedrive/test_services.py` — Use the integration constant for the option key (instead of the raw string) so the…
- PR [#164020](https://github.com/home-assistant/core/pull/164020#discussion_r2851849675) — `tests/components/counter/test_init.py` — The configuration dictionary key should also use the DOMAIN constant instead of the hardcoded string…

</details>

Precedent: [#174276](https://github.com/home-assistant/core/pull/174276#discussion_r3487432969), [#173454](https://github.com/home-assistant/core/pull/173454#discussion_r3389632389), [#172464](https://github.com/home-assistant/core/pull/172464#discussion_r3318894587), [#171761](https://github.com/home-assistant/core/pull/171761#discussion_r3283425697), [#168603](https://github.com/home-assistant/core/pull/168603#discussion_r3109654673), [#168154](https://github.com/home-assistant/core/pull/168154#discussion_r3078053807), [#168064](https://github.com/home-assistant/core/pull/168064#discussion_r3105853652), [#164020](https://github.com/home-assistant/core/pull/164020#discussion_r2851849675)

### `hass-r001` — A sensor's state_class must match the nature of its value: declare one, consistent with the integration's sibling descriptions of the same device_class, for genuinely numeric readings; do not put a numeric state class on a value that can also be a non-numeric enum state, and do not use SensorStateClass.MEASUREMENT for uptime or duration-since-boot sensors.

- **Trigger** — A SensorEntityDescription sets device_class and unit but omits state_class while neighbouring descriptions set one; assigns MEASUREMENT/TOTAL* to a key whose strings.json also defines enum state values; or combines SensorDeviceClass.DURATION or an uptime translation_key with MEASUREMENT.
- **Why** — state_class is what enrolls a sensor in long-term statistics; missing it loses the history, and a wrong one records statistics for values that are not measurements at all.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#176069](https://github.com/home-assistant/core/pull/176069#discussion_r3550195388) — `homeassistant/components/imou/sensor.py` — `storage_used` is declared with `SensorStateClass.MEASUREMENT` (and a `%` unit) unconditionally, but `strings.json` defines enum states…
- PR [#166409](https://github.com/home-assistant/core/pull/166409#discussion_r2988513355) — `homeassistant/components/proxmoxve/sensor.py` — Add a `state_class` (consistent with the other data-size capacity sensors in this integration) for the…
- PR [#166275](https://github.com/home-assistant/core/pull/166275#discussion_r2975837553) — `homeassistant/components/proxmoxve/sensor.py` — Use an uptime-appropriate `state_class` (or omit it) for the new duration uptime sensor to match…

</details>

Precedent: [#176069](https://github.com/home-assistant/core/pull/176069#discussion_r3550195388), [#166409](https://github.com/home-assistant/core/pull/166409#discussion_r2988513355), [#166275](https://github.com/home-assistant/core/pull/166275#discussion_r2975837553)

### `hass-r003` — Declare entity attributes through the _attr_* attributes or an EntityDescription only: not as a @property returning a constant, not as a bare un-prefixed class attribute, and never duplicated into a legacy private attribute alongside its _attr_ counterpart.

- **Trigger** — An entity class body contains `translation_key = ...` without the _attr_ prefix and outside an EntityDescription, defines a supported_features property returning a constant flag combination, or assigns both self._attr_name and self._name to the same value.
- **Why** — The _attr_ family is the mechanism the base Entity actually reads; anything else either has no effect at all or duplicates state that then drifts apart.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#169169](https://github.com/home-assistant/core/pull/169169#discussion_r3148119965) — `homeassistant/components/gree/climate.py` — Use `_attr_translation_key = "climate"` (or an entity description) instead of `translation_key = "climate"`, because the…
- PR [#163937](https://github.com/home-assistant/core/pull/163937#discussion_r2846338127) — `homeassistant/components/myneomitis/climate.py` — The supported_features property should not be defined as a method decorated with @property. According to…
- PR [#161028](https://github.com/home-assistant/core/pull/161028#discussion_r2696104072) — `homeassistant/components/vera/sensor.py` — Same issue as with the Power sensor - setting both `_attr_name` and `_name` is redundant.…

</details>

Precedent: [#169169](https://github.com/home-assistant/core/pull/169169#discussion_r3148119965), [#163937](https://github.com/home-assistant/core/pull/163937#discussion_r2846338127), [#161028](https://github.com/home-assistant/core/pull/161028#discussion_r2696104072)

## testing

### `hass-r024` — Every fixture, fixture file, module-level TEST_* constant, test-signature parameter and parametrization added must be consumed by a test in the same PR, or removed - including a parametrize over a fixture name that the test signature does not take.

- **Trigger** — A diff adds a conftest fixture, a file under tests/components/*/fixtures/, a helper such as init_*_integration, or a test-signature parameter that no test in the diff references; leaves one behind after the test that used it changed; or applies @pytest.mark.parametrize over a fixture name to a test whose signature omits that name.
- **Why** — Scaffolding nothing reads is dead weight the next contributor has to reason about, and a parametrization the signature ignores runs the same test twice while looking like coverage.
- **Scope** — `tests/components/`
- **Support** — 8 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#176439](https://github.com/home-assistant/core/pull/176439#discussion_r3573072207) — `tests/components/plugwise/fixtures/anna_v4/data.json` — Remove this unused fixture from the dependency-only PR. No test or fixture loader references `anna_v4`,…
- PR [#172500](https://github.com/home-assistant/core/pull/172500#discussion_r3320669225) — `tests/components/mqtt/test_init.py` — Add the missing `mqtt_config_entry_data` parameter to this test function (it’s being parametrized above), otherwise pytest…
- PR [#172500](https://github.com/home-assistant/core/pull/172500#discussion_r3324226090) — `tests/components/mqtt/test_init.py` — Add `mqtt_config_entry_data` to the test function parameters so the parametrization is applied and pytest can…
- PR [#168559](https://github.com/home-assistant/core/pull/168559#discussion_r3107307821) — `tests/components/unifi/test_services.py` — Add the missing `clients_all_payload` parameter (or remove the parametrization) so this test actually receives the…
- PR [#167470](https://github.com/home-assistant/core/pull/167470#discussion_r3037266907) — `tests/components/roborock/test_vacuum.py` — Update this test’s docstring and signature to reflect that it asserts ServiceNotSupported (and remove the…
- PR [#166609](https://github.com/home-assistant/core/pull/166609#discussion_r2995742815) — `tests/components/sfr_box/conftest.py` — Remove or start using the new fixtures (ensure_token/voip_get_info); they are currently defined but not referenced…
- PR [#165260](https://github.com/home-assistant/core/pull/165260#discussion_r2923414464) — `tests/components/flic_button/conftest.py` — The conftest contains ~350 lines of fixture code (`mock_coordinator`, `mock_twist_coordinator`, `mock_twist_flic_client`, `mock_duo_coordinator`, `mock_duo_flic_client`, `init_integration`, `init_twist_integration`,…
- PR [#164621](https://github.com/home-assistant/core/pull/164621#discussion_r2874132426) — `tests/components/template/test_lock.py` — `TEST_OBJECT_ID` is now unused (only defined, never referenced). Consider removing it to avoid dead code,…
- PR [#160409](https://github.com/home-assistant/core/pull/160409#discussion_r2891005324) — `tests/components/qube_heatpump/conftest.py` — The `mock_config_entry` fixture defined in `conftest.py` is not used by any test in the test…

</details>

Precedent: [#176439](https://github.com/home-assistant/core/pull/176439#discussion_r3573072207), [#172500](https://github.com/home-assistant/core/pull/172500#discussion_r3320669225), [#172500](https://github.com/home-assistant/core/pull/172500#discussion_r3324226090), [#168559](https://github.com/home-assistant/core/pull/168559#discussion_r3107307821), [#167470](https://github.com/home-assistant/core/pull/167470#discussion_r3037266907), [#166609](https://github.com/home-assistant/core/pull/166609#discussion_r2995742815), [#165260](https://github.com/home-assistant/core/pull/165260#discussion_r2923414464), [#164621](https://github.com/home-assistant/core/pull/164621#discussion_r2874132426) (+1 more)

### `hass-r018` — A branch the diff adds must be tested in every outcome it can take, not only the one that motivated the change: the rejection as well as the acceptance, the success path as well as the failure path, the suppressed case as well as the reported one, and each distinct error or translation variant the new code can produce.

- **Trigger** — A diff adds a conditional - an auth guard such as @require_admin on a view, a legacy vs non-legacy platform-loading branch, a device-quirk `available` override, a config-flow fallback path, a new hassfest validation, a caller-is-a-built-in-integration check, or a repair issue that selects among translation keys - while the accompanying tests exercise only one side of it.
- **Why** — The untested side is exactly the behaviour the change introduces, so reviewers here treat a half-covered branch as an untested change.
- **Scope** — `homeassistant/components/` `script/hassfest/` `tests/components/`
- **Support** — 7 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#171819](https://github.com/home-assistant/core/pull/171819#discussion_r3296477220) — `tests/components/device_tracker/test_entity.py` — Add test coverage for the branch that suppresses the warning for built-in integrations (module starting…
- PR [#171507](https://github.com/home-assistant/core/pull/171507#discussion_r3274180609) — `homeassistant/components/device_tracker/__init__.py` — Add coverage for the non-legacy discovery path that routes to EntityComponent.async_setup_platform so regressions (like missing…
- PR [#170118](https://github.com/home-assistant/core/pull/170118#discussion_r3208816650) — `homeassistant/components/overkiz/entity.py` — Add a regression test covering the new local-API availability fallback (device.available=False but core:StatusState=available) and asserting…
- PR [#169205](https://github.com/home-assistant/core/pull/169205#discussion_r3143799133) — `homeassistant/components/cloud/http_api.py` — Add a regression test asserting non-admin users cannot download `/api/cloud/support_package` (should return 401/unauthorized), since existing…
- PR [#167844](https://github.com/home-assistant/core/pull/167844#discussion_r3060785206) — `tests/components/anthropic/test_config_flow.py` — Add a test that covers the success path where the selected model is not in…
- PR [#166333](https://github.com/home-assistant/core/pull/166333#discussion_r2981426032) — `script/hassfest/conditions.py` — Add hassfest tests that cover valid and invalid `context` usage (unknown context key, missing selector,…
- PR [#159601](https://github.com/home-assistant/core/pull/159601#discussion_r3202983454) — `tests/components/lg_thinq/test_repairs.py` — Add a test case that covers the “entity used in automations/scripts” branch so the issue…

</details>

Precedent: [#171819](https://github.com/home-assistant/core/pull/171819#discussion_r3296477220), [#171507](https://github.com/home-assistant/core/pull/171507#discussion_r3274180609), [#170118](https://github.com/home-assistant/core/pull/170118#discussion_r3208816650), [#169205](https://github.com/home-assistant/core/pull/169205#discussion_r3143799133), [#167844](https://github.com/home-assistant/core/pull/167844#discussion_r3060785206), [#166333](https://github.com/home-assistant/core/pull/166333#discussion_r2981426032), [#159601](https://github.com/home-assistant/core/pull/159601#discussion_r3202983454)

### `hass-r019` — A new entity platform module, or a new entity description added to an existing descriptions tuple, must come with tests whose fixture data actually creates the entity and exercises each value its mapping declares, plus regenerated and committed snapshot files; any hard-coded expected-entity list must follow the order the descriptions are iterated during setup.

- **Trigger** — A diff adds homeassistant/components/<domain>/<platform>.py or appends an EntityDescription (including a state_mapping/options dict) without a matching added or extended tests/components/<domain>/test_<platform>.py, updated fixtures, or regenerated snapshot.
- **Why** — An untested description is indistinguishable from a typo, and the snapshot is what proves the entity, its unit and its state actually materialise for the fixture device.
- **Scope** — `homeassistant/components/` `tests/components/ecovacs/`
- **Support** — 5 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#174521](https://github.com/home-assistant/core/pull/174521#discussion_r3459219241) — `tests/components/ecovacs/test_button.py` — The reset-lifespan buttons are created in `SUPPORTED_LIFESPANS` order (button.py iterates `LIFESPAN_ENTITY_DESCRIPTIONS`), so `cleaning_solution` must come…
- PR [#172936](https://github.com/home-assistant/core/pull/172936#discussion_r3356426066) — `homeassistant/components/aqvify/sensor.py` — The sensor platform (`sensor.py`) introduces entity setup logic and a `native_value` property, but there is…
- PR [#170729](https://github.com/home-assistant/core/pull/170729#discussion_r3244249469) — `homeassistant/components/indevolt/sensor.py` — The fixture sets register `6107` to `1000` (mapped to `"standby"`), but the test at `test_realtime_sensor_energy_mode_availability`…
- PR [#169910](https://github.com/home-assistant/core/pull/169910#discussion_r3195496596) — `homeassistant/components/blebox/binary_sensor.py` — Add tests that cover creation and state reporting for the new "open" window binary sensor.…
- PR [#165886](https://github.com/home-assistant/core/pull/165886#discussion_r2951518772) — `homeassistant/components/roborock/sensor.py` — This new Q7 battery sensor isn’t covered by the existing snapshot tests because the Q7…

</details>

Precedent: [#174521](https://github.com/home-assistant/core/pull/174521#discussion_r3459219241), [#172936](https://github.com/home-assistant/core/pull/172936#discussion_r3356426066), [#170729](https://github.com/home-assistant/core/pull/170729#discussion_r3244249469), [#169910](https://github.com/home-assistant/core/pull/169910#discussion_r3195496596), [#165886](https://github.com/home-assistant/core/pull/165886#discussion_r2951518772)

### `hass-r021` — A test double must match the real callable it replaces: patch coroutine functions with new_callable=AsyncMock and synchronous ones with MagicMock, never spec a whole library object as AsyncMock when it also exposes synchronous listener or registration methods, and give replacement functions *args and **kwargs so they accept the arguments the integration passes.

- **Trigger** — patch("<library>.<Class>.<async_method>", return_value=...) without new_callable=AsyncMock; a patch, AsyncMock(spec=...) or fixture annotation whose sync-vs-async kind does not match the awaited-ness of the target in the integration code; or a zero-argument stub substituted for a library method the integration calls with arguments.
- **Why** — A mismatched double either hands back a non-awaitable MagicMock or throws on the real call signature, so the test passes or fails for a reason unrelated to the code under test.
- **Scope** — `tests/components/`
- **Support** — 5 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#170932](https://github.com/home-assistant/core/pull/170932#discussion_r3254928439) — `tests/components/homee/test_switch.py` — This builder is defined at the bottom of the test module and is called from…
- PR [#170892](https://github.com/home-assistant/core/pull/170892#discussion_r3293950970) — `tests/components/syncthing/test_init.py` — The mocked `events.listen` has a zero-argument signature. If the integration calls `events.listen(...)` with positional/keyword arguments…
- PR [#167695](https://github.com/home-assistant/core/pull/167695#discussion_r3053771744) — `tests/components/dsmr/test_config_flow.py` — Patch `usb.async_scan_serial_ports` with an `AsyncMock` (or `new_callable=AsyncMock`) since it is awaited in the config flow.
- PR [#167018](https://github.com/home-assistant/core/pull/167018#discussion_r3019135202) — `tests/components/tessie/conftest.py` — Use `new_callable=AsyncMock` when patching async methods. Since `Tessie.list_vehicles()` is an async method that will be…
- PR [#165305](https://github.com/home-assistant/core/pull/165305#discussion_r2916204073) — `tests/components/generic/test_config_flow.py` — `mock_create_stream` patches a synchronous `create_stream` call. The patched object is a `MagicMock`/`Mock`, so `AsyncMock` is…

</details>

Precedent: [#170932](https://github.com/home-assistant/core/pull/170932#discussion_r3254928439), [#170892](https://github.com/home-assistant/core/pull/170892#discussion_r3293950970), [#167695](https://github.com/home-assistant/core/pull/167695#discussion_r3053771744), [#167018](https://github.com/home-assistant/core/pull/167018#discussion_r3019135202), [#165305](https://github.com/home-assistant/core/pull/165305#discussion_r2916204073)

### `hass-r022` — A test's name and docstring must describe exactly the platform, service, failure and outcome its body actually exercises: patch the dependency so the named path really happens - a failing side_effect for a failure test rather than a benign empty result - and when a copied or parametrized test disagrees with its body, fix whichever of the two is wrong before merge.

- **Trigger** — A module or test docstring names a different platform, service or exception than the file/body asserts, including a docstring copied from a neighbouring test or one describing only a subset of the parametrize list; or a test named for a startup/discovery failure patches the helper to return an empty result and asserts a generic abort reason.
- **Why** — Reviewers read the name and docstring to know what is covered, so a test whose body does something else leaves the named path uncovered and nobody notices.
- **Scope** — `tests/components/`
- **Support** — 5 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#169251](https://github.com/home-assistant/core/pull/169251#discussion_r3249257609) — `tests/components/izone/test_config_flow.py` — The docstring (and test name) say the user flow aborts because the discovery service cannot…
- PR [#167470](https://github.com/home-assistant/core/pull/167470#discussion_r3037266907) — `tests/components/roborock/test_vacuum.py` — Update this test’s docstring and signature to reflect that it asserts ServiceNotSupported (and remove the…
- PR [#165924](https://github.com/home-assistant/core/pull/165924#discussion_r2957570643) — `tests/components/risco/test_init.py` — This test asserts that CLOCK timeouts do not trigger a reload (and the docstring states…
- PR [#164545](https://github.com/home-assistant/core/pull/164545#discussion_r2936867126) — `tests/components/counter/test_trigger.py` — The test docstring says the trigger fires when a counter changes to a specific state,…
- PR [#163306](https://github.com/home-assistant/core/pull/163306#discussion_r2829296458) — `tests/components/cambridge_audio/test_number.py` — The test file docstring incorrectly says "Tests for the Cambridge Audio select platform" when this…

</details>

Precedent: [#169251](https://github.com/home-assistant/core/pull/169251#discussion_r3249257609), [#167470](https://github.com/home-assistant/core/pull/167470#discussion_r3037266907), [#165924](https://github.com/home-assistant/core/pull/165924#discussion_r2957570643), [#164545](https://github.com/home-assistant/core/pull/164545#discussion_r2936867126), [#163306](https://github.com/home-assistant/core/pull/163306#discussion_r2829296458)

### `hass-r026` — Test fixtures and mocked client returns must reproduce what the real library or device produces: typed objects where the library returns typed objects, the upstream key casing and payload shape rather than the integration's post-processed form, and device metadata consistent with the datapoints the fixture declares.

- **Trigger** — A conftest or fixture file supplying plain dicts/MagicMocks where the library returns typed objects, already-normalised keys (snake_case where the API sends camelCase), or a device fixture whose product name and category do not match its datapoint set.
- **Why** — Mocks more forgiving than the real library hide attribute-versus-item and shape errors until users hit them; these fixtures are the only description of the upstream contract this repo has.
- **Scope** — `homeassistant/components/sunricher_dali/` `tests/components/`
- **Support** — 4 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#172393](https://github.com/home-assistant/core/pull/172393#discussion_r3357315431) — `tests/components/environment_canada/fixtures/current_conditions_data.json` — This key is `expiry_time` (snake_case), but the first warning entry on line 10 uses `expiryTime`…
- PR [#171412](https://github.com/home-assistant/core/pull/171412#discussion_r3270557571) — `tests/components/tuya/fixtures/tzc1_5vlawhjm.json` — The fixture metadata (`name` / `product_name` = “INTELAR IR288”) appears inconsistent with the exposed datapoints…
- PR [#168074](https://github.com/home-assistant/core/pull/168074#discussion_r3070742281) — `homeassistant/components/sunricher_dali/diagnostics.py` — `scene.devices` members are described as `SceneDeviceType` (with fields like `gw_sn_obj` and `property`), which strongly suggests…
- PR [#164074](https://github.com/home-assistant/core/pull/164074#discussion_r2871784978) — `tests/components/fritz/conftest.py` — `call_action` currently drops any non-dict `action_data` by returning `{}`. The test fixture data includes actions…

</details>

Precedent: [#172393](https://github.com/home-assistant/core/pull/172393#discussion_r3357315431), [#171412](https://github.com/home-assistant/core/pull/171412#discussion_r3270557571), [#168074](https://github.com/home-assistant/core/pull/168074#discussion_r3070742281), [#164074](https://github.com/home-assistant/core/pull/164074#discussion_r2871784978)

### `hass-r027` — When code newly depends on optional or loosely typed payload fields, add a test with a reduced payload - fields omitted, null, or carrying an unexpected value - asserting that setup does not raise, that only the always-available entities are created, that the value helpers return None instead of raising, and that absent data reads as unknown rather than as false or zero.

- **Trigger** — A platform's async_setup_entry gains `if <key> in data` guards around entity creation, new value_fn helpers introduce `return None` paths, a property returns bool | None, or payload data is fed into a SensorDeviceClass/SensorStateClass lookup, while the fixtures contain only fully populated, well-formed payloads.
- **Why** — Real devices omit fields and firmware versions differ; the fully populated fixture is the case that already works, so the degraded payload is the one worth a test.
- **Scope** — `homeassistant/components/` `tests/components/arwn/`
- **Support** — 4 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#176360](https://github.com/home-assistant/core/pull/176360#discussion_r3567074399) — `homeassistant/components/proxmoxve/sensor.py` — Add a regression test using the reduced PVEVMUser node payload. The current test changes cover…
- PR [#172264](https://github.com/home-assistant/core/pull/172264#discussion_r3304282855) — `tests/components/arwn/test_sensor.py` — The new enum conversions in `sensor.py` can fail when `state_class`/`device_class` are missing or invalid. Add…
- PR [#172234](https://github.com/home-assistant/core/pull/172234#discussion_r3303897984) — `homeassistant/components/vistapool/binary_sensor.py` — The dosing-tank sensor behavior needs a test case for the scenario where tank values are…
- PR [#170480](https://github.com/home-assistant/core/pull/170480#discussion_r3252992287) — `homeassistant/components/prusalink/sensor.py` — New behavior relies on job helpers returning `None` (yielding an `unknown` state) instead of making…

</details>

Precedent: [#176360](https://github.com/home-assistant/core/pull/176360#discussion_r3567074399), [#172264](https://github.com/home-assistant/core/pull/172264#discussion_r3304282855), [#172234](https://github.com/home-assistant/core/pull/172234#discussion_r3303897984), [#170480](https://github.com/home-assistant/core/pull/170480#discussion_r3252992287)

### `hass-r020` — A parametrized test must span the whole input space the implementation accepts, including its edge and negative values: every supported entity domain plus an unsupported one proving it does not match, and the combined-flags and zero/empty value alongside the individual enum members.

- **Trigger** — A new or edited parametrization lists only individual enum members where the code interprets bitwise capability flags, or only one supported domain (e.g. only `person`) for a trigger or condition that also handles others, with no unsupported-entity or empty-value case.
- **Why** — Interpretation bugs live in the combined and empty cases, and a matcher with no negative case cannot show that it stops matching everything else.
- **Scope** — `tests/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#171789](https://github.com/home-assistant/core/pull/171789#discussion_r3284488267) — `tests/components/esphome/test_infrared.py` — Add/restore test coverage for `InfraredCapability.TRANSMITTER | InfraredCapability.RECEIVER` and `InfraredCapability(0)`; the updated platform logic changes how…
- PR [#171751](https://github.com/home-assistant/core/pull/171751#discussion_r3282905197) — `tests/components/zone/test_trigger.py` — Add coverage for `device_tracker` targets in the new `zone.entered`/`zone.left` trigger tests. The trigger implementation explicitly…
- PR [#166595](https://github.com/home-assistant/core/pull/166595#discussion_r2995455756) — `tests/components/illuminance/test_condition.py` — Add a negative test to confirm illuminance.is_value does not accept/does not pass when targeting only…

</details>

Precedent: [#171789](https://github.com/home-assistant/core/pull/171789#discussion_r3284488267), [#171751](https://github.com/home-assistant/core/pull/171751#discussion_r3282905197), [#166595](https://github.com/home-assistant/core/pull/166595#discussion_r2995455756)

### `hass-r023` — Commit only .ambr snapshots produced by running pytest --snapshot-update against the current code: never hand-write, hand-append or hand-edit snapshot blocks or their parametrization ids, and regenerate rather than leaving stale duplicate entries for one unique_id.

- **Trigger** — A diff to tests/components/*/snapshots/*.ambr deviates from generator output - a manually written EntityRegistryEntrySnapshot block, a duplicated `# ---` divider, a bracketed id that does not match the parametrize source values, or two entries sharing a unique_id under different entity_ids.
- **Why** — A hand-edited snapshot asserts what the author believed rather than what the code produces, which is the one thing the snapshot exists to catch.
- **Scope** — `tests/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#175300](https://github.com/home-assistant/core/pull/175300#discussion_r3508683656) — `tests/components/vesync/snapshots/test_sensor.ambr` — Duplicate `# ---` divider here. Syrupy generates a single divider between snapshot blocks (see the…
- PR [#175300](https://github.com/home-assistant/core/pull/175300#discussion_r3508683628) — `tests/components/vesync/snapshots/test_switch.ambr` — Duplicate `# ---` divider here. Syrupy generates a single divider between snapshot blocks (see the…
- PR [#166298](https://github.com/home-assistant/core/pull/166298#discussion_r2990388935) — `tests/components/matter/snapshots/test_sensor.ambr` — Regenerate/prune this snapshot: it contains multiple snapshots with the same Matter unique_id but different entity_ids…
- PR [#164358](https://github.com/home-assistant/core/pull/164358#discussion_r2865571700) — `tests/components/renault/snapshots/test_sensor.ambr` — These new snapshots are stored under `test_sensors[megane_e-tech]`, but the tests are parametrized by `vehicle_type` values…

</details>

Precedent: [#175300](https://github.com/home-assistant/core/pull/175300#discussion_r3508683656), [#175300](https://github.com/home-assistant/core/pull/175300#discussion_r3508683628), [#166298](https://github.com/home-assistant/core/pull/166298#discussion_r2990388935), [#164358](https://github.com/home-assistant/core/pull/164358#discussion_r2865571700)

### `hass-r025` — Migration tests must start from a realistic pre-migration state and cover every variant the migration can encounter: seed the entity registry with the entities an existing install would already have and assert they are re-associated with the new device or subentry, and exercise each stored value shape and each unique_id format the integration has produced, without one format's pattern matching another's ids.

- **Trigger** — A diff modifies async_migrate_entry, an import step, or normalization of stored config entry data while its tests add no case for the newly handled input variants, derive old-format unique_ids by string slicing or suffix matching, skip entries where a component such as the channel is None, or assert only that subentries and devices were created without registering the old entities beforehand.
- **Why** — A migration runs once per install and cannot be re-run, so an untested variant leaves those users with orphaned entities and no way back.
- **Scope** — `homeassistant/components/proxmoxve/` `tests/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#176742](https://github.com/home-assistant/core/pull/176742#discussion_r3606990242) — `homeassistant/components/proxmoxve/__init__.py` — Add migration coverage that asserts uppercase realms remain unchanged. Please cover both a realm already…
- PR [#175048](https://github.com/home-assistant/core/pull/175048#discussion_r3500143932) — `tests/components/steam_online/test_init.py` — Consider seeding a pre-existing friend sensor entity in this migration test to cover the riskiest…
- PR [#166580](https://github.com/home-assistant/core/pull/166580#discussion_r2994011803) — `tests/components/homematicip_cloud/test_init.py` — Strengthen the round-trip migration test so it actually exercises multi-channel entities (`config.channel is None`) and…

</details>

Precedent: [#176742](https://github.com/home-assistant/core/pull/176742#discussion_r3606990242), [#175048](https://github.com/home-assistant/core/pull/175048#discussion_r3500143932), [#166580](https://github.com/home-assistant/core/pull/166580#discussion_r2994011803)

## naming

### `hass-r016` — Entity names must come from strings.json: give every new entity an _attr_translation_key (or a description translation_key) with a matching entry under `entity`, and do not also set a literal name on that description.

- **Trigger** — A new entity or EntityDescription sets _attr_device_class or a literal name with no translation_key, declares both translation_key= and name=, or a snapshot shows original_name/object_id_base as None with an entity_id equal to the bare device or container slug.
- **Why** — A name written in code cannot be translated and collapses the entity_id onto the device name; reviewers expect the translation key to be the single source of the displayed name.
- **Scope** — `homeassistant/components/` `tests/components/portainer/snapshots/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#167163](https://github.com/home-assistant/core/pull/167163#discussion_r3027481405) — `tests/components/portainer/snapshots/test_button.ambr` — Ensure the recreate button gets a distinct translated name (and thus a distinct entity_id suffix)…
- PR [#166801](https://github.com/home-assistant/core/pull/166801#discussion_r3006372591) — `homeassistant/components/casper_glow/sensor.py` — Add an `_attr_translation_key` (and update `strings.json`) for this new battery sensor so it uses the…
- PR [#163079](https://github.com/home-assistant/core/pull/163079#discussion_r2810056307) — `homeassistant/components/renault/number.py` — The `name` field should be removed from entity descriptions when using `translation_key`. The translation system…

</details>

Precedent: [#167163](https://github.com/home-assistant/core/pull/167163#discussion_r3027481405), [#166801](https://github.com/home-assistant/core/pull/166801#discussion_r3006372591), [#163079](https://github.com/home-assistant/core/pull/163079#discussion_r2810056307)

## performance

### `hass-r017` — A coordinator must not await one API call per device inside a for loop in _async_update_data; use the library's batch endpoint, or asyncio.gather(..., return_exceptions=True) so per-item failures are isolated and previous values are kept for the items that errored.

- **Trigger** — _async_update_data awaits a client call inside a `for` loop over devices, circuits, zones or endpoints and assembles the results.
- **Why** — Sequential per-device polling multiplies request volume and refresh latency by the device count, and lets the first failing device abort the entire update for every other entity.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#172936](https://github.com/home-assistant/core/pull/172936#discussion_r3361617212) — `homeassistant/components/aqvify/coordinator.py` — This loop makes one API call per device on every update cycle (N+1 pattern: 1…
- PR [#165992](https://github.com/home-assistant/core/pull/165992#discussion_r2958948201) — `homeassistant/components/bsblan/coordinator.py` — Fast coordinator fetches `state()` for each circuit sequentially. With multiple circuits this increases update duration…
- PR [#165855](https://github.com/home-assistant/core/pull/165855#discussion_r3197250898) — `homeassistant/components/portainer/coordinator.py` — Handle per-endpoint DF failures so one slow/failing endpoint does not fail the entire disk-space refresh…

</details>

Precedent: [#172936](https://github.com/home-assistant/core/pull/172936#discussion_r3361617212), [#165992](https://github.com/home-assistant/core/pull/165992#discussion_r2958948201), [#165855](https://github.com/home-assistant/core/pull/165855#discussion_r3197250898)

## docs

### `hass-r012` — Every status in quality_scale.yaml must match what the integration actually implements: never mark a rule `done` without the code that satisfies it, never leave `todo` on a rule that is already implemented, and mark rules the integration structurally cannot satisfy as `exempt` with a comment whose justification agrees with manifest.json.

- **Trigger** — A quality_scale.yaml diff sets or keeps a status that the integration's source contradicts - `done` with no implementation, `todo` alongside the implementation, or an `exempt` comment (e.g. about not polling) that conflicts with the manifest iot_class.
- **Why** — The quality scale is the promise the integration makes to users and to the reviewer checklist; a status that does not describe the code makes the whole scale untrustworthy.
- **Scope** — `homeassistant/components/`
- **Support** — 5 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#173666](https://github.com/home-assistant/core/pull/173666#discussion_r3593597596) — `homeassistant/components/dyson_infrared/quality_scale.yaml` — Mark the devices rule as incomplete until the fan supplies `DeviceInfo`, or implement the missing…
- PR [#171402](https://github.com/home-assistant/core/pull/171402#discussion_r3284008139) — `homeassistant/components/ovhcloud_ai_endpoints/quality_scale.yaml` — This states the integration 'does not poll', but the integration metadata sets `iot_class` to `cloud_polling`.…
- PR [#170491](https://github.com/home-assistant/core/pull/170491#discussion_r3234553388) — `homeassistant/components/cert_expiry/quality_scale.yaml` — Mark `reauthentication-flow` as `exempt` (with a short comment) since the config flow only collects host/port…
- PR [#169709](https://github.com/home-assistant/core/pull/169709#discussion_r3185501553) — `homeassistant/components/airnow/quality_scale.yaml` — Mark `config-entry-unloading` as `done` (not `todo`) since the integration implements `async_unload_entry` (see `homeassistant/components/airnow/__init__.py`), so config…
- PR [#167738](https://github.com/home-assistant/core/pull/167738#discussion_r3068209198) — `homeassistant/components/iaqualink/quality_scale.yaml` — Update the quality scale rule status to match current functionality by marking `reauthentication-flow` as `todo`…

</details>

Precedent: [#173666](https://github.com/home-assistant/core/pull/173666#discussion_r3593597596), [#171402](https://github.com/home-assistant/core/pull/171402#discussion_r3284008139), [#170491](https://github.com/home-assistant/core/pull/170491#discussion_r3234553388), [#169709](https://github.com/home-assistant/core/pull/169709#discussion_r3185501553), [#167738](https://github.com/home-assistant/core/pull/167738#discussion_r3068209198)

### `hass-r014` — strings.json and the code must correspond in both directions and in the same PR: every translation key, error key, entity name, enum state and options value the code can reference must have an entry, and no entry may be added that nothing references or removed while code still uses it.

- **Trigger** — A diff adds exception, error or entity translation keys that no code references, adds a raise path nothing can reach, adds new device-class/enum state constants or options values without the corresponding strings.json keys, or deletes a `name` under a key that code still sets as translation_key.
- **Why** — The frontend falls back to the raw key when an entry is missing, and a stale entry hides which messages are actually reachable, so reviewers check both directions on every strings.json change.
- **Scope** — `homeassistant/components/` `tests/components/proxmoxve/snapshots/`
- **Support** — 5 distinct PRs, 3 distinct reviewers

<details><summary>Evidence</summary>

- PR [#176347](https://github.com/home-assistant/core/pull/176347#discussion_r3686082575) — `homeassistant/components/music_assistant/services.py` — Add an explicit schema-version guard before validating the username. Nothing in the integration raises the…
- PR [#175448](https://github.com/home-assistant/core/pull/175448#discussion_r3518006606) — `homeassistant/components/mikrotik/strings.json` — These two translation keys are unused. The code only references `invalid_auth`, `cannot_connect`, and `mikrotik_api_error`; `cannot_login`…
- PR [#173463](https://github.com/home-assistant/core/pull/173463#discussion_r3453677246) — `homeassistant/components/renault/strings.json` — @audrenfr-rgb I now fixed the CI. But there were no translations added for the states…
- PR [#167565](https://github.com/home-assistant/core/pull/167565#discussion_r3043080242) — `homeassistant/components/victron_gx/strings.json` — Add back an entity `name` translation for `multi_mppt_mpptnumber_state` so this enum sensor is not created…
- PR [#165890](https://github.com/home-assistant/core/pull/165890#discussion_r2970171438) — `tests/components/proxmoxve/snapshots/test_button.ambr` — Making good progress here, @Stathogon! :) A Core member with write permission can update the…

</details>

Precedent: [#176347](https://github.com/home-assistant/core/pull/176347#discussion_r3686082575), [#175448](https://github.com/home-assistant/core/pull/175448#discussion_r3518006606), [#173463](https://github.com/home-assistant/core/pull/173463#discussion_r3453677246), [#167565](https://github.com/home-assistant/core/pull/167565#discussion_r3043080242), [#165890](https://github.com/home-assistant/core/pull/165890#discussion_r2970171438)

### `hass-r015` — User-facing text in strings.json must follow Home Assistant string style: sentence case with only the brand or product name capitalised and spelled the same way as the neighbouring entries, `for example` spelled out instead of e.g., no slash-joined noun pairs, and literal example values wrapped in backticks rather than quotes.

- **Trigger** — An added or changed strings.json value uses title case or capitalises a common noun mid-sentence while neighbouring entries are sentence case, spells the brand differently from existing entries in the same file, contains a slash-joined noun pair or e.g., or quotes an example value.
- **Why** — Every integration's strings feed the same UI and the same translation pipeline, so reviewers hold new entries to the style the surrounding entries already use rather than letting each integration drift.
- **Scope** — `homeassistant/components/`
- **Support** — 4 distinct PRs, 2 distinct reviewers

<details><summary>Evidence</summary>

- PR [#171995](https://github.com/home-assistant/core/pull/171995#discussion_r3293447413) — `homeassistant/components/homee/strings.json` — Brand capitalization is inconsistent between messages (`Homee` vs `homee`). Since this PR adds new user-facing…
- PR [#164412](https://github.com/home-assistant/core/pull/164412#discussion_r2962451383) — `homeassistant/components/earn_e_p1/strings.json` — In case that "meter" should be translated and not kept as part of the product…
- PR [#162836](https://github.com/home-assistant/core/pull/162836#discussion_r2814409228) — `homeassistant/components/aws_s3/strings.json` — The `prefix` description uses "Folder/Prefix" and quotes around the example. To align with Home Assistant…
- PR [#161808](https://github.com/home-assistant/core/pull/161808#discussion_r2824281292) — `homeassistant/components/switchbot/strings.json` — The new button name uses title case ("Sync Date and Time"), but the other button…

</details>

Precedent: [#171995](https://github.com/home-assistant/core/pull/171995#discussion_r3293447413), [#164412](https://github.com/home-assistant/core/pull/164412#discussion_r2962451383), [#162836](https://github.com/home-assistant/core/pull/162836#discussion_r2814409228), [#161808](https://github.com/home-assistant/core/pull/161808#discussion_r2824281292)

### `hass-r013` — Reference existing translation text with the exact [%key:...%] reference syntax - including the shared [%key:common::config_flow::data::*%] entries for standard fields such as host, port, username, password and ssl - instead of repeating a label, data_description, or exception message that is already defined elsewhere; the reference path must contain no stray whitespace.

- **Trigger** — A strings.json diff adds a value textually identical to one already present under another step or section of the same file, or gives a plain literal label for a field that already exists under common::config_flow::data.
- **Why** — Duplicated strings are translated separately and then drift apart; the reference syntax keeps one source of truth and saves translator effort.
- **Scope** — `homeassistant/components/`
- **Support** — 3 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#170491](https://github.com/home-assistant/core/pull/170491#discussion_r3271846987) — `homeassistant/components/cert_expiry/strings.json` — The `data_description` text for `host`/`port` is duplicated in two steps. Consider reducing duplication by referencing…
- PR [#168064](https://github.com/home-assistant/core/pull/168064#discussion_r3165372790) — `homeassistant/components/onedrive/strings.json` — Fix the translation key reference for the `connection_error` exception message by removing the stray space…
- PR [#167308](https://github.com/home-assistant/core/pull/167308#discussion_r3033378847) — `homeassistant/components/luci/strings.json` — Use the shared common translation key for the SSL field label (as most integrations do)…

</details>

Precedent: [#170491](https://github.com/home-assistant/core/pull/170491#discussion_r3271846987), [#168064](https://github.com/home-assistant/core/pull/168064#discussion_r3165372790), [#167308](https://github.com/home-assistant/core/pull/167308#discussion_r3033378847)

## commit-hygiene

### `hass-r004` — The pull request description must match what the diff actually does: it must not claim a removal, payload or quality-scale rule the code does not carry out, must not close an issue the change does not implement, and must cover every entity or behaviour the diff adds beyond the stated feature.

- **Trigger** — A PR body announces removing a key, adding data, or satisfying a quality-scale rule that the diff does not do; carries issue-closing keywords on a change that only bumps a requirement; or the diff adds entity descriptions or platform entities the title and body never mention.
- **Why** — The description is what reviewers and the release notes rely on; when it diverges from the diff, both the review and the changelog describe a change that was never made.
- **Scope** — `homeassistant/components/`
- **Support** — 4 distinct PRs, 1 distinct reviewer

<details><summary>Evidence</summary>

- PR [#177369](https://github.com/home-assistant/core/pull/177369#discussion_r3656426805) — `homeassistant/components/hunterdouglas_powerview/manifest.json` — Remove the `fixes #165651 fixes #176743` closure references from the PR description. This version bump…
- PR [#169862](https://github.com/home-assistant/core/pull/169862#discussion_r3205685458) — `homeassistant/components/ptdevices/binary_sensor.py` — Update the PR description (or remove the extra change) because this adds an `external_power` binary…
- PR [#165923](https://github.com/home-assistant/core/pull/165923#discussion_r2956438853) — `homeassistant/components/growatt_server/diagnostics.py` — The PR description says diagnostics should include total coordinator data and per-device coordinator data, but…
- PR [#164413](https://github.com/home-assistant/core/pull/164413#discussion_r2881685536) — `homeassistant/components/hassio/coordinator.py` — The PR description notes that the `addons` field will be removed from Supervisor info in…

</details>

Precedent: [#177369](https://github.com/home-assistant/core/pull/177369#discussion_r3656426805), [#169862](https://github.com/home-assistant/core/pull/169862#discussion_r3205685458), [#165923](https://github.com/home-assistant/core/pull/165923#discussion_r2956438853), [#164413](https://github.com/home-assistant/core/pull/164413#discussion_r2881685536)
