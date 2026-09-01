"""Tests for the arithmetic half of the critic.

These are the steps where a silent error would be invisible in the output: a scope that
is too deep makes a rule that never fires, a scope that is too shallow makes one that
fires on everything, and an excerpt one word too long is a privacy-rule violation shipped
into a committed artifact.
"""

from __future__ import annotations

from distill.critic import (
    clip_excerpt,
    find_contested,
    generalise_scope,
    assign_ids,
    rule_key,
)


class TestGeneraliseScope:
    def test_single_file_becomes_its_directory(self):
        # Amendment 1: a scope pointing at one file almost never fires.
        got = generalise_scope(["airflow-core/src/airflow/api/routes/dags.py"])
        assert got == ["airflow-core/src/airflow/api/routes/"]

    def test_siblings_share_their_common_directory(self):
        got = generalise_scope([
            "airflow-core/src/airflow/api/routes/dags.py",
            "airflow-core/src/airflow/api/routes/task_instances.py",
        ])
        assert got == ["airflow-core/src/airflow/api/routes/"]

    def test_cousins_generalise_to_the_shallowest_covering_prefix(self):
        got = generalise_scope([
            "airflow-core/src/airflow/api/routes/dags.py",
            "airflow-core/src/airflow/api/serializers/dag.py",
        ])
        assert got == ["airflow-core/src/airflow/api/"]

    def test_distinct_top_levels_stay_separate(self):
        # One useless "/" scope would match the entire repository.
        got = generalise_scope([
            "airflow-core/src/airflow/models/dag.py",
            "providers/amazon/src/airflow/providers/amazon/hooks/s3.py",
        ])
        assert got == ["airflow-core/src/airflow/models/",
                       "providers/amazon/src/airflow/providers/amazon/hooks/"]

    def test_root_file_is_not_widened_to_everything(self):
        assert generalise_scope(["pyproject.toml"]) == ["./"]

    def test_widens_to_top_level_only_when_evidence_spans_it(self):
        got = generalise_scope([
            "airflow-core/src/airflow/models/dag.py",
            "airflow-core/docs/index.rst",
        ])
        assert got == ["airflow-core/"]


class TestClipExcerpt:
    def test_respects_the_fifteen_word_ceiling(self):
        body = " ".join(f"w{i}" for i in range(40))
        out = clip_excerpt(body)
        assert len(out.rstrip("…").split()) == 15

    def test_short_body_is_not_marked_truncated(self):
        assert clip_excerpt("three short words") == "three short words"

    def test_empty_body_is_safe(self):
        assert clip_excerpt("") == ""


class TestStableIds:
    def test_id_survives_a_rerun(self):
        rules = [{"rule": "Do the thing", "category": "testing"}]
        id_map: dict[str, str] = {}
        assign_ids(rules, "airflow", id_map)
        first = rules[0]["id"]

        # A later tranche adds rules; the existing one keeps its id.
        more = [{"rule": "Another thing", "category": "async"},
                {"rule": "Do the thing", "category": "testing"}]
        assign_ids(more, "airflow", id_map)
        assert more[1]["id"] == first
        assert more[0]["id"] != first

    def test_ids_do_not_collide_after_reload(self):
        id_map = {"do the thing": "airflow-r007"}
        rules = [{"rule": "New rule", "category": "docs"}]
        assign_ids(rules, "airflow", id_map)
        assert rules[0]["id"] == "airflow-r008"

    def test_rule_key_ignores_punctuation_and_case(self):
        assert rule_key("Use `flush()`, not commit!") == rule_key("use flush not commit")


class TestContested:
    def test_flags_overlapping_triggers_in_the_same_scope(self):
        rules = [
            {"id": "a", "category": "api-design", "scope_paths": ["core/api/"],
             "rule": "Pagination cursor must be null on the final page",
             "trigger": "endpoint returns next_cursor computed from the last row"},
            {"id": "b", "category": "api-design", "scope_paths": ["core/api/"],
             "rule": "Pagination cursor must always be present on the final page",
             "trigger": "endpoint returns next_cursor computed from the last row"},
        ]
        assert len(find_contested(rules)) == 1

    def test_does_not_flag_across_unrelated_scopes(self):
        rules = [
            {"id": "a", "category": "api-design", "scope_paths": ["core/api/"],
             "rule": "Pagination cursor must be null on the final page",
             "trigger": "endpoint returns next_cursor computed from the last row"},
            {"id": "b", "category": "api-design", "scope_paths": ["providers/aws/"],
             "rule": "Pagination cursor must be null on the final page",
             "trigger": "endpoint returns next_cursor computed from the last row"},
        ]
        assert find_contested(rules) == []

    def test_does_not_flag_different_categories(self):
        rules = [
            {"id": "a", "category": "api-design", "scope_paths": ["core/"],
             "rule": "same words entirely", "trigger": "same trigger entirely"},
            {"id": "b", "category": "testing", "scope_paths": ["core/"],
             "rule": "same words entirely", "trigger": "same trigger entirely"},
        ]
        assert find_contested(rules) == []


class TestRepoName:
    def test_reads_the_true_name_from_the_manifest(self):
        # Never reconstruct by replacing the first hyphen: that turns
        # "home-assistant-core" into "home/assistant-core".
        from distill.critic import repo_name
        assert repo_name("home-assistant-core") == "home-assistant/core"
        assert repo_name("apache-airflow") == "apache/airflow"

    def test_already_qualified_name_passes_through(self):
        from distill.critic import repo_name
        assert repo_name("owner/repo") == "owner/repo"

    def test_unknown_slug_does_not_crash(self):
        from distill.critic import repo_name
        assert repo_name("no-such-repo-here") == "no-such-repo-here"
