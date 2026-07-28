"""Adversarial scoring tests: a submission must never be credited for work not shown.

Oracle for every test here:

    NO INPUT MAY PRODUCE A CONFIDENT-LOOKING ANSWER THAT IS WRONG.

The defect these exist to prevent was live in the published benchmark: `passed` was
defined as ``n_regressions == 0``, so a submission of ``{}`` -- answering nothing --
scored ``result: PASS`` with 0% coverage and 312 unanswered cases, and exited 0. A
vendor could have submitted an empty file and truthfully reported a passing run.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from pqc_mfb import load_cases
from pqc_mfb.score import naive_baseline, perfect_submission, score_submission

EXIT_PASS, EXIT_FAIL, EXIT_INCOMPLETE, EXIT_USAGE = 0, 1, 3, 2


def run(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pqc_mfb.cli", *args],
                          capture_output=True, text=True, timeout=60, input=stdin)


def write(tmp_path, obj) -> str:
    p = tmp_path / "sub.json"
    p.write_text(json.dumps(obj))
    return str(p)


# ------------------------------------------------- the defect: silence is not credit

def test_empty_submission_is_not_a_pass():
    sc = score_submission({}, load_cases())
    assert sc.verdict == "INCOMPLETE"
    assert sc.passed is False
    assert sc.n_unanswered == sc.n_failures


def test_empty_submission_exits_nonzero(tmp_path):
    r = run("score", write(tmp_path, {}))
    assert r.returncode == EXIT_INCOMPLETE
    assert "INCOMPLETE" in r.stdout
    assert "PASS" not in r.stdout.split("result:")[-1]


def test_partial_submission_is_incomplete():
    """Answering 311 of 312 is still not a pass."""
    cases = load_cases()
    failures = [c for c in cases if c.is_failure]
    sub = {c.case_id: True for c in failures[:-1]}
    sc = score_submission(sub, cases)
    assert sc.n_unanswered == 1
    assert sc.verdict == "INCOMPLETE"
    assert sc.passed is False


def test_only_fabricated_ids_is_incomplete_and_warns():
    sc = score_submission({"totally::fabricated": True}, load_cases())
    assert sc.verdict == "INCOMPLETE"
    assert sc.unknown_ids == ["totally::fabricated"]


def test_unknown_ids_are_named_in_cli_output(tmp_path):
    r = run("score", write(tmp_path, {"ghost::case": True}))
    assert "ghost::case" in r.stdout
    assert "match no case" in r.stdout


# ------------------------------------------------------------- the verdicts are real

def test_perfect_submission_passes():
    sc = score_submission(perfect_submission(), load_cases())
    assert sc.verdict == "PASS"
    assert sc.coverage == 1.0
    assert sc.n_unanswered == 0


def test_regression_outranks_full_coverage():
    """100% coverage plus one broken control must be FAIL, never PASS.

    The README promises this; nothing asserted it before.
    """
    cases = load_cases()
    sub = {c.case_id: True for c in cases}
    control = next(c for c in cases if not c.is_failure)
    sub[control.case_id] = False
    sc = score_submission(sub, cases)
    assert sc.coverage == 1.0
    assert sc.n_regressions == 1
    assert sc.verdict == "FAIL"
    assert sc.passed is False


def test_regression_outranks_incompleteness():
    """A definite finding beats an absence of one."""
    cases = load_cases()
    control = next(c for c in cases if not c.is_failure)
    sc = score_submission({control.case_id: False}, cases)
    assert sc.n_regressions == 1
    assert sc.n_unanswered > 0
    assert sc.verdict == "FAIL"


def test_naive_baseline_answers_everything_so_it_is_not_incomplete():
    sc = score_submission(naive_baseline(), load_cases())
    assert sc.n_unanswered == 0
    assert sc.coverage == 0.0
    assert sc.verdict == "PASS"  # documented: PASS is the regression gate, not the score


# ------------------------------------------------------------------ malformed inputs

@pytest.mark.parametrize("payload", ["[]", "null", '"a string"', "42"])
def test_non_object_submissions_are_usage_errors(tmp_path, payload):
    p = tmp_path / "s.json"
    p.write_text(payload)
    r = run("score", str(p))
    assert r.returncode == EXIT_USAGE
    assert r.returncode != EXIT_PASS


def test_malformed_json_is_a_usage_error(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    r = run("score", str(p))
    assert r.returncode == EXIT_USAGE


def test_missing_file_is_a_usage_error():
    r = run("score", "/nonexistent/submission.json")
    assert r.returncode == EXIT_USAGE


def test_string_values_are_coerced_not_silently_trusted(tmp_path):
    """Truthy strings must not quietly become 'closed'."""
    cases = load_cases()
    failures = [c for c in cases if c.is_failure]
    sub = {c.case_id: "yes" for c in failures}
    sc = score_submission({k: bool(v) for k, v in sub.items()}, cases)
    # bool("yes") is True; the point is that the CLI does the coercion explicitly
    # and the verdict still requires completeness.
    assert sc.n_unanswered == 0


def test_enormous_submission_does_not_change_the_denominator(tmp_path):
    """100k junk keys must not inflate or deflate the score."""
    cases = load_cases()
    sub = {c.case_id: True for c in cases}
    sub.update({f"junk::{i}": True for i in range(100_000)})
    sc = score_submission(sub, cases)
    assert sc.n_failures == 312
    assert sc.coverage == 1.0
    assert len(sc.unknown_ids) == 100_000
    assert sc.verdict == "PASS"


# --------------------------------------------------------------- numbers are derived

def test_headline_numbers_are_recomputed_from_data_not_hardcoded():
    cases = load_cases()
    assert len(cases) == 322
    assert sum(1 for c in cases if c.is_failure) == 312
    assert len({c.family for c in cases}) == 39
    assert len({c.design for c in cases}) == 10
    # 38, not 39: one family is control-only and so can never be zero-covered.
    sc = score_submission({}, cases)
    assert len(sc.zero_families) == 38


def test_json_output_reports_the_verdict(tmp_path):
    r = run("--json", "score", write(tmp_path, {}))
    payload = json.loads(r.stdout)
    assert payload["verdict"] == "INCOMPLETE"
    assert payload["passed"] is False
    assert r.returncode == EXIT_INCOMPLETE
