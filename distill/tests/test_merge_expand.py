"""Tests for the merge-expand contract.

The claim this file defends: **rule loss is structurally impossible at the merge stage.**

critic-MERGE emits only the groups that merge; every cluster it does not mention becomes a
singleton here, in code. That inversion exists because asking an agent to restate all ~450
clusters produced an output it ran out of budget partway through — and a truncated
restatement drops rules silently while looking like a successful run.

So the property under test is: whatever the agent emits, every input cluster and every
candidate key survives into the output.
"""

from __future__ import annotations

import json

from distill.critic import main as critic_main


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def chunk_file(tmp_path, letter, clusters):
    p = tmp_path / f"clusters_{letter}.json"
    write(p, {"clusters": clusters})
    return str(p)


def cl(rule, members, kind="convention", category="correctness"):
    return {"rule": rule, "category": category, "trigger": "t", "rationale": "r",
            "kind": kind, "members": members}


def run_expand(tmp_path, chunks, merged):
    mp = tmp_path / "merged.json"
    write(mp, merged)
    out = tmp_path / "clusters_merged.json"
    rc = critic_main(["merge-expand", "--clusters", *chunks,
                      "--merged", str(mp), "--out", str(out)])
    return rc, json.loads(out.read_text(encoding="utf-8"))


class TestNothingIsLost:
    def test_empty_merge_keeps_every_cluster_as_a_singleton(self, tmp_path):
        a = chunk_file(tmp_path, "A", [cl("one", ["t1/b1#0"]), cl("two", ["t1/b1#1"])])
        rc, got = run_expand(tmp_path, [a], {"merges": []})
        assert rc == 0
        assert got["n_clusters_out"] == 2
        assert got["n_singletons"] == 2
        assert got["n_candidates_covered"] == 2

    def test_merged_and_unmerged_clusters_both_survive(self, tmp_path):
        a = chunk_file(tmp_path, "A", [cl("same", ["t1/b1#0"]), cl("other", ["t1/b1#1"])])
        b = chunk_file(tmp_path, "B", [cl("same thing", ["t1/b2#0"])])
        rc, got = run_expand(tmp_path, [a, b], {"merges": [
            {"rule": "merged", "category": "correctness", "trigger": "t",
             "rationale": "r", "kind": "convention", "cluster_ids": ["A:0", "B:0"]}]})
        assert rc == 0
        # one merge group + one untouched singleton
        assert got["n_clusters_out"] == 2
        assert got["n_singletons"] == 1
        assert got["n_candidates_covered"] == 3
        merged = [c for c in got["clusters"] if c["rule"] == "merged"][0]
        assert merged["members"] == ["t1/b1#0", "t1/b2#0"]

    def test_every_candidate_key_survives_any_merge(self, tmp_path):
        a = chunk_file(tmp_path, "A", [cl(f"r{i}", [f"t1/b1#{i}"]) for i in range(5)])
        rc, got = run_expand(tmp_path, [a], {"merges": [
            {"rule": "m", "category": "correctness", "trigger": "t", "rationale": "r",
             "kind": "convention", "cluster_ids": ["A:0", "A:3"]}]})
        keys = sorted(k for c in got["clusters"] for k in c["members"])
        assert keys == [f"t1/b1#{i}" for i in range(5)]
        assert rc == 0


class TestIncidentsCannotInflateSupport:
    def test_a_group_containing_an_incident_is_an_incident(self, tmp_path):
        # This is the load-bearing guard: a one-off defect merged into a real rule
        # would contribute its PR to that rule's support count.
        a = chunk_file(tmp_path, "A", [
            cl("real convention", ["t1/b1#0"]),
            cl("one-off fix", ["t1/b1#1"], kind="incident"),
        ])
        _, got = run_expand(tmp_path, [a], {"merges": [
            {"rule": "merged", "category": "correctness", "trigger": "t",
             "rationale": "r", "kind": "convention", "cluster_ids": ["A:0", "A:1"]}]})
        assert got["clusters"][0]["kind"] == "incident"

    def test_demote_marks_a_singleton_as_an_incident(self, tmp_path):
        a = chunk_file(tmp_path, "A", [cl("use meaningful names", ["t1/b1#0"])])
        _, got = run_expand(tmp_path, [a], {"merges": [], "demote": ["A:0"]})
        assert got["clusters"][0]["kind"] == "incident"
        assert got["n_candidates_covered"] == 1   # kept, only barred from promotion


class TestMalformedMergeIsLoud:
    def test_reusing_a_cluster_id_is_an_error(self, tmp_path):
        a = chunk_file(tmp_path, "A", [cl("one", ["t1/b1#0"]), cl("two", ["t1/b1#1"])])
        rc, got = run_expand(tmp_path, [a], {"merges": [
            {"rule": "x", "cluster_ids": ["A:0"]},
            {"rule": "y", "cluster_ids": ["A:0", "A:1"]},
        ]})
        assert rc == 1
        assert got["duplicate_cluster_ids"] == ["A:0"]

    def test_unknown_cluster_id_is_an_error(self, tmp_path):
        a = chunk_file(tmp_path, "A", [cl("one", ["t1/b1#0"])])
        rc, got = run_expand(tmp_path, [a], {"merges": [
            {"rule": "x", "cluster_ids": ["A:0", "Z:99"]}]})
        assert rc == 1
        assert got["unknown_cluster_ids"] == ["Z:99"]
