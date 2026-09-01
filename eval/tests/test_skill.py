"""Tests for the Skill's diff parsing, scope filter and precedent suppression.

The eval reuses these same functions, so a bug here would move the headline numbers
without ever showing up as an error.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SKILL_PATH = Path(".bob/skills/house-style/scripts/house_style.py")


def _load_skill():
    spec = importlib.util.spec_from_file_location("house_style", SKILL_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hs = _load_skill()


DIFF = """diff --git a/airflow-core/src/airflow/api/routes/dags.py b/airflow-core/src/airflow/api/routes/dags.py
index 1111111..2222222 100644
--- a/airflow-core/src/airflow/api/routes/dags.py
+++ b/airflow-core/src/airflow/api/routes/dags.py
@@ -10,6 +10,9 @@ def list_dags(limit: int):
     session = get_session()
     query = select(DagModel).limit(limit)
     rows = session.scalars(query).all()
+    next_cursor = rows[-1].id if rows else None
+    return {"dags": rows, "next_cursor": next_cursor}
+
     return rows
diff --git a/providers/amazon/src/airflow/providers/amazon/hooks/s3.py b/providers/amazon/src/airflow/providers/amazon/hooks/s3.py
index 3333333..4444444 100644
--- a/providers/amazon/src/airflow/providers/amazon/hooks/s3.py
+++ b/providers/amazon/src/airflow/providers/amazon/hooks/s3.py
@@ -40,3 +40,4 @@ class S3Hook:
     def get_conn(self):
         return self.conn
+        # trailing
"""


class TestParseDiff:
    def test_finds_every_changed_file(self):
        files = hs.parse_diff(DIFF)
        assert [f["path"] for f in files] == [
            "airflow-core/src/airflow/api/routes/dags.py",
            "providers/amazon/src/airflow/providers/amazon/hooks/s3.py",
        ]

    def test_added_lines_get_post_image_line_numbers(self):
        # A reviewer comments on the new file's line numbers, so that is what a
        # finding must carry for the eval's +/-5 line window to mean anything.
        f = hs.parse_diff(DIFF)[0]
        added = [ln for ln in f["hunks"][0]["lines"] if ln["kind"] == "+"]
        assert [ln["n"] for ln in added] == [13, 14, 15]
        assert added[0]["text"].strip().startswith("next_cursor =")

    def test_deleted_lines_do_not_advance_the_counter(self):
        diff = (
            "diff --git a/x.py b/x.py\n"
            "--- a/x.py\n+++ b/x.py\n"
            "@@ -1,3 +1,3 @@\n"
            " keep\n-gone\n+added\n"
        )
        lines = hs.parse_diff(diff)[0]["hunks"][0]["lines"]
        kinds = {ln["kind"]: ln["n"] for ln in lines}
        assert kinds[" "] == 1
        assert kinds["-"] == 2      # occupies no post-image line
        assert kinds["+"] == 2

    def test_empty_diff_is_not_an_error(self):
        assert hs.parse_diff("") == []

    def test_bare_patch_fragment_keeps_its_hunks(self):
        # GitHub's /pulls/{n}/files returns a per-file `patch` with no "diff --git"
        # header. Without a default path the parsed file has no path, gets filtered
        # out, and every hunk vanishes — which would silently zero the whole eval.
        fragment = "@@ -10,3 +10,4 @@ def f():\n keep\n+added\n"
        got = hs.parse_diff(fragment, default_path="a/b/c.py")
        assert len(got) == 1
        assert got[0]["path"] == "a/b/c.py"
        assert len(got[0]["hunks"]) == 1

    def test_patch_json_yields_hunks_for_every_file(self, tmp_path):
        p = tmp_path / "pr.json"
        p.write_text(
            json.dumps({"files": [
                {"path": "x/y.py", "patch": "@@ -1,2 +1,3 @@\n keep\n+added\n"},
                {"path": "x/z.py", "patch": "@@ -5,1 +5,2 @@\n ctx\n+more\n"},
            ]}),
            encoding="utf-8")
        files = hs.files_from_patch_json(str(p))
        assert [f["path"] for f in files] == ["x/y.py", "x/z.py"]
        assert [len(f["hunks"]) for f in files] == [1, 1]
        added = [ln for ln in files[0]["hunks"][0]["lines"] if ln["kind"] == "+"]
        assert added[0]["n"] == 2


class TestScopeFilter:
    def test_directory_scope_matches_files_beneath_it(self):
        assert hs.scope_matches("airflow-core/src/airflow/api/",
                                "airflow-core/src/airflow/api/routes/dags.py")

    def test_scope_does_not_match_a_sibling_prefix(self):
        # "airflow-core/" must not match "airflow-core-tests/".
        assert not hs.scope_matches("airflow-core/", "airflow-core-tests/x.py")

    def test_root_scope_matches_only_root_files(self):
        assert hs.scope_matches("./", "pyproject.toml")
        assert not hs.scope_matches("./", "airflow-core/x.py")

    def test_only_rules_touching_the_diff_are_loaded(self):
        rules = [
            {"id": "r1", "scope_paths": ["airflow-core/src/airflow/api/"]},
            {"id": "r2", "scope_paths": ["task-sdk/"]},
            {"id": "r3", "scope_paths": ["providers/amazon/"]},
        ]
        paths = [f["path"] for f in hs.parse_diff(DIFF)]
        got = hs.applicable_rules(rules, paths)
        assert [r["id"] for r in got] == ["r1", "r3"]

    def test_matched_paths_are_recorded(self):
        rules = [{"id": "r1", "scope_paths": ["airflow-core/"]}]
        got = hs.applicable_rules(rules, [f["path"] for f in hs.parse_diff(DIFF)])
        assert got[0]["_matched_paths"] == [
            "airflow-core/src/airflow/api/routes/dags.py"]


class TestRenderSuppressesUnjustifiedFindings:
    """A finding with no precedent links is a bug, so render must drop it."""

    def _book(self, tmp_path, evidence):
        book = {"rules": [{
            "id": "airflow-r001", "rule": "Do the thing", "category": "api-design",
            "trigger": "t", "rationale": "because", "scope_paths": ["airflow-core/"],
            "support_count": 4, "evidence": evidence,
        }]}
        p = tmp_path / "rules.json"
        p.write_text(json.dumps(book), encoding="utf-8")
        return p

    def _findings(self, tmp_path, rule_id):
        p = tmp_path / "findings.json"
        p.write_text(json.dumps({"findings": [
            {"rule_id": rule_id, "path": "airflow-core/x.py", "line": 12,
             "message": "do the thing here"}]}), encoding="utf-8")
        return p

    def test_finding_with_precedent_is_kept(self, tmp_path, capsys):
        rules = self._book(tmp_path, [
            {"pr": 100, "url": "u", "path": "p", "excerpt": "e"},
            {"pr": 101, "url": "u", "path": "p", "excerpt": "e"},
        ])
        rc = hs.main(["--rules", str(rules), "render",
                      "--findings", str(self._findings(tmp_path, "airflow-r001"))])
        out = capsys.readouterr().out
        assert rc == 0
        assert "[airflow-r001]" in out
        assert "PR #101, PR #100" in out
        assert "1 findings across 1 rules" in out

    def test_finding_whose_rule_has_no_evidence_is_suppressed(self, tmp_path, capsys):
        rules = self._book(tmp_path, [])
        rc = hs.main(["--rules", str(rules), "render",
                      "--findings", str(self._findings(tmp_path, "airflow-r001"))])
        out = capsys.readouterr().out
        assert rc == 1
        assert "airflow-r001" not in out
        assert "0 findings" in out

    def test_finding_citing_an_unknown_rule_is_suppressed(self, tmp_path, capsys):
        rules = self._book(tmp_path, [{"pr": 1, "url": "u", "path": "p", "excerpt": "e"}])
        rc = hs.main(["--rules", str(rules), "render",
                      "--findings", str(self._findings(tmp_path, "airflow-r999"))])
        assert rc == 1
        assert "0 findings" in capsys.readouterr().out


class TestSelectKeepsContextSmall:
    def test_select_emits_only_applicable_rules(self, tmp_path, capsys):
        book = {"rules": [
            {"id": "r1", "rule": "a", "category": "c", "trigger": "t",
             "rationale": "r", "scope_paths": ["airflow-core/"], "support_count": 9},
            {"id": "r2", "rule": "b", "category": "c", "trigger": "t",
             "rationale": "r", "scope_paths": ["helm-tests/"], "support_count": 3},
        ]}
        rules_p = tmp_path / "rules.json"
        rules_p.write_text(json.dumps(book), encoding="utf-8")
        patch_p = tmp_path / "pr.json"
        patch_p.write_text(json.dumps({"files": [
            {"path": "airflow-core/src/airflow/api/routes/dags.py",
             "patch": "@@ -1,2 +1,3 @@\n keep\n+added\n"}]}), encoding="utf-8")

        hs.main(["--rules", str(rules_p), "select", "--patch-file", str(patch_p)])
        payload = json.loads(capsys.readouterr().out)
        assert payload["rules_total"] == 2
        assert payload["rules_applicable"] == 1
        assert payload["rules"][0]["id"] == "r1"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
