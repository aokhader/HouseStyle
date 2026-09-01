"""Tests for the eval's matcher and judge cache.

Recall and precision are computed from this assignment, so an off-by-one in the line
window or a double-counted comment moves the headline numbers silently.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.judge import Judge, VerdictCache, pair_key, parse_verdict
from eval.run_eval import candidate_pairs, match_pr


class StubJudge:
    """Judge stand-in driven by a verdict table, so matching is tested alone."""

    def __init__(self, table: dict[tuple[str, str], str] | None = None,
                 default: str = "NO_MATCH") -> None:
        self.table = table or {}
        self.default = default
        self.calls = 0

    def verdict(self, finding, comment):
        self.calls += 1
        key = (finding.get("message", ""), comment.get("body", ""))
        v = self.table.get(key, self.default)
        return None if v is None else {"verdict": v, "why": ""}


def F(path, line, msg, **kw):
    return {"path": path, "line": line, "message": msg, **kw}


def C(path, line, body):
    return {"path": path, "line": line, "body": body}


class TestCandidatePairs:
    def test_pairs_only_within_the_line_window(self):
        findings = [F("a.py", 10, "f")]
        truth = [C("a.py", 15, "t1"), C("a.py", 16, "t2")]
        got = list(candidate_pairs(findings, truth, window=5))
        assert len(got) == 1          # 15 is inside, 16 is outside

    def test_different_files_never_pair(self):
        got = list(candidate_pairs([F("a.py", 10, "f")], [C("b.py", 10, "t")], 5))
        assert got == []

    def test_missing_line_numbers_are_skipped_not_crashed(self):
        got = list(candidate_pairs([F("a.py", None, "f")], [C("a.py", 10, "t")], 5))
        assert got == []


class TestMatchPr:
    def test_a_comment_is_matched_at_most_once(self):
        # Two findings on the same defect must not both claim the one comment,
        # which would inflate precision.
        findings = [F("a.py", 10, "f1"), F("a.py", 11, "f2")]
        truth = [C("a.py", 10, "t1")]
        judge = StubJudge({("f1", "t1"): "MATCH", ("f2", "t1"): "MATCH"})
        pairs, _ = match_pr(findings, truth, judge, window=5, lenient=False)
        assert len(pairs) == 1

    def test_a_finding_is_matched_at_most_once(self):
        findings = [F("a.py", 10, "f1")]
        truth = [C("a.py", 10, "t1"), C("a.py", 12, "t2")]
        judge = StubJudge({("f1", "t1"): "MATCH", ("f1", "t2"): "MATCH"})
        pairs, _ = match_pr(findings, truth, judge, window=5, lenient=False)
        assert len(pairs) == 1

    def test_match_wins_over_partial_for_the_same_comment(self):
        findings = [F("a.py", 10, "weak"), F("a.py", 10, "strong")]
        truth = [C("a.py", 10, "t1")]
        judge = StubJudge({("weak", "t1"): "PARTIAL", ("strong", "t1"): "MATCH"})
        pairs, _ = match_pr(findings, truth, judge, window=5, lenient=True)
        assert len(pairs) == 1
        assert pairs[0]["finding"]["message"] == "strong"

    def test_partial_is_not_a_match_in_strict_mode(self):
        judge = StubJudge({("f1", "t1"): "PARTIAL"})
        pairs, _ = match_pr([F("a.py", 10, "f1")], [C("a.py", 10, "t1")],
                            judge, window=5, lenient=False)
        assert pairs == []

    def test_partial_counts_in_lenient_mode(self):
        judge = StubJudge({("f1", "t1"): "PARTIAL"})
        pairs, _ = match_pr([F("a.py", 10, "f1")], [C("a.py", 10, "t1")],
                            judge, window=5, lenient=True)
        assert len(pairs) == 1

    def test_unjudged_pairs_are_reported_not_guessed(self):
        judge = StubJudge(default=None)
        pairs, unresolved = match_pr([F("a.py", 10, "f1")], [C("a.py", 10, "t1")],
                                     judge, window=5, lenient=False)
        assert pairs == []
        assert unresolved == 1

    def test_no_findings_yields_no_matches_and_no_judge_calls(self):
        judge = StubJudge()
        pairs, unresolved = match_pr([], [C("a.py", 10, "t1")], judge, 5, False)
        assert pairs == [] and unresolved == 0 and judge.calls == 0


class TestJudgeCache:
    def test_key_is_stable_and_order_sensitive(self):
        a = pair_key("finding text", "comment text", "a.py")
        assert a == pair_key("finding text", "comment text", "a.py")
        assert a != pair_key("comment text", "finding text", "a.py")

    def test_key_ignores_surrounding_whitespace(self):
        assert pair_key(" f ", "c", "a.py") == pair_key("f", "c", "a.py")

    def test_key_separates_identical_text_in_different_files(self):
        assert pair_key("f", "c", "a.py") != pair_key("f", "c", "b.py")

    def test_cached_verdict_is_not_re_judged(self, tmp_path):
        judge = Judge(backend="cache", cache_dir=tmp_path)
        key = pair_key("f", "c", "a.py")
        judge.cache.put(key, {"verdict": "MATCH", "why": "same issue", "judge": "test"})
        got = judge.verdict(F("a.py", 1, "f"), C("a.py", 1, "c"))
        assert got["verdict"] == "MATCH"
        assert judge.stats["cache_hit"] == 1
        assert judge.stats["queued"] == 0

    def test_uncached_pair_is_queued_never_invented(self, tmp_path):
        judge = Judge(backend="cache", cache_dir=tmp_path)
        assert judge.verdict(F("a.py", 1, "f"), C("a.py", 1, "c")) is None
        assert judge.stats["queued"] == 1

    def test_cache_survives_a_new_instance(self, tmp_path):
        VerdictCache(tmp_path).put(pair_key("f", "c", "a.py"),
                                   {"verdict": "PARTIAL", "why": "", "judge": "t"})
        judge = Judge(backend="cache", cache_dir=tmp_path)
        assert judge.verdict(F("a.py", 1, "f"), C("a.py", 1, "c"))["verdict"] == "PARTIAL"


class TestParseVerdict:
    def test_reads_the_expected_format(self):
        got = parse_verdict("VERDICT: MATCH\nWHY: both ask for the same fix")
        assert got["verdict"] == "MATCH"
        assert got["why"] == "both ask for the same fix"

    def test_tolerates_lowercase_and_padding(self):
        assert parse_verdict("  verdict:  partial .\nwhy: related")["verdict"] == "PARTIAL"

    def test_unparseable_output_is_not_a_match(self):
        # Failing closed matters: a garbled judge reply must never inflate recall.
        assert parse_verdict("I think they are basically the same")["verdict"] == "NO_MATCH"

    def test_empty_output_is_not_a_match(self):
        assert parse_verdict("")["verdict"] == "NO_MATCH"


class TestCorruptFindingsAreLoud:
    """A findings file that cannot be trusted must stop the run, not score as zero.

    During this project a reviewer subagent wrote a plain-text scratch rendering over a
    path in the eval tree. Silently treating an unreadable file as "no findings" makes
    that indistinguishable from a genuinely clean diff, and quietly lowers recall.
    """

    def _prep(self, tmp_path, monkeypatch, text):
        import eval.run_eval as re_mod
        d = tmp_path / "A_baseline"
        d.mkdir(parents=True)
        (d / "pr_42.json").write_text(text, encoding="utf-8")
        monkeypatch.setattr(re_mod, "FINDINGS_DIR", tmp_path)
        return re_mod

    def test_unparseable_file_raises(self, tmp_path, monkeypatch):
        import pytest as _pytest
        m = self._prep(tmp_path, monkeypatch, "PR 999: some plain text\n====\n")
        with _pytest.raises(m.CorruptFindings):
            m.load_findings("A_baseline", 42)

    def test_wrong_pr_number_raises(self, tmp_path, monkeypatch):
        import pytest as _pytest
        m = self._prep(tmp_path, monkeypatch, '{"pr": 999, "findings": []}')
        with _pytest.raises(m.CorruptFindings):
            m.load_findings("A_baseline", 42)

    def test_missing_findings_key_raises(self, tmp_path, monkeypatch):
        import pytest as _pytest
        m = self._prep(tmp_path, monkeypatch, '{"pr": 42}')
        with _pytest.raises(m.CorruptFindings):
            m.load_findings("A_baseline", 42)

    def test_absent_file_is_legitimately_empty(self, tmp_path, monkeypatch):
        m = self._prep(tmp_path, monkeypatch, '{"pr": 42, "findings": []}')
        assert m.load_findings("A_baseline", 7) == []

    def test_valid_file_loads(self, tmp_path, monkeypatch):
        m = self._prep(tmp_path, monkeypatch,
                       '{"pr": 42, "findings": [{"path": "a.py", "line": 1}]}')
        assert len(m.load_findings("A_baseline", 42)) == 1
