"""`pqc-mfb diff` — what did this release close, and what did it break?

Coverage alone cannot answer that: two runs at the same percentage can differ in
every case. The property that matters is that a regression is never silent.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from pqc_mfb import load_cases

EXIT_CLEAN, EXIT_REGRESSED, EXIT_USAGE = 0, 1, 2


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pqc_mfb.cli", *args],
                          capture_output=True, text=True, timeout=60)


@pytest.fixture(scope="module")
def cases():
    return load_cases()


@pytest.fixture()
def baseline(cases, tmp_path_factory):
    path = tmp_path_factory.mktemp("d") / "v1.json"
    path.write_text(json.dumps({c.case_id: bool(c.naive_held) for c in cases}))
    return str(path)


def write(tmp_path, mapping, name="v2.json"):
    path = tmp_path / name
    path.write_text(json.dumps(mapping))
    return str(path)


def test_no_change_is_reported_as_no_change(baseline):
    r = run("diff", baseline, baseline)
    assert r.returncode == EXIT_CLEAN
    assert "no change" in r.stdout


def test_newly_closed_cases_are_listed(cases, tmp_path, baseline):
    sub = {c.case_id: bool(c.naive_held) for c in cases}
    target = next(c.case_id for c in cases if c.is_failure)
    sub[target] = True
    r = run("diff", baseline, write(tmp_path, sub))
    assert r.returncode == EXIT_CLEAN
    assert "newly closed (1)" in r.stdout
    assert target in r.stdout


def test_a_reopened_failure_case_is_flagged_and_exits_nonzero(cases, tmp_path):
    """Closing a case then reopening it must never be silent."""
    target = next(c.case_id for c in cases if c.is_failure)
    before = {c.case_id: bool(c.naive_held) for c in cases}
    before[target] = True
    after = dict(before)
    after[target] = False
    r = run("diff", write(tmp_path, before, "a.json"), write(tmp_path, after, "b.json"))
    assert r.returncode == EXIT_REGRESSED
    assert "NEWLY BROKEN" in r.stdout
    assert target in r.stdout


def test_a_broken_control_is_reported_separately(cases, tmp_path, baseline):
    """Breaking a control is worse than reopening a failure case."""
    sub = {c.case_id: bool(c.naive_held) for c in cases}
    control = next(c.case_id for c in cases if not c.is_failure)
    sub[control] = False
    r = run("diff", baseline, write(tmp_path, sub))
    assert r.returncode == EXIT_REGRESSED
    assert "NEW CONTROL REGRESSIONS" in r.stdout
    assert control in r.stdout


def test_dropping_a_previously_answered_case_is_flagged(cases, tmp_path):
    """Silently omitting a case must not look like no change."""
    before = {c.case_id: bool(c.naive_held) for c in cases}
    target = next(c.case_id for c in cases if c.is_failure)
    after = {k: v for k, v in before.items() if k != target}
    r = run("diff", write(tmp_path, before, "a.json"), write(tmp_path, after, "b.json"))
    assert "newly unanswered" in r.stdout
    assert target in r.stdout


def test_coverage_delta_is_reported(cases, tmp_path, baseline):
    sub = {c.case_id: bool(c.naive_held) for c in cases}
    for c in [x for x in cases if x.is_failure][:5]:
        sub[c.case_id] = True
    r = run("diff", baseline, write(tmp_path, sub))
    assert "(+5)" in r.stdout


def test_json_output_carries_the_lists(cases, tmp_path, baseline):
    sub = {c.case_id: bool(c.naive_held) for c in cases}
    target = next(c.case_id for c in cases if c.is_failure)
    sub[target] = True
    payload = json.loads(run("--json", "diff", baseline, write(tmp_path, sub)).stdout)
    assert payload["delta_closed"] == 1
    assert payload["newly_closed"] == [target]
    assert payload["newly_broken"] == []


def test_verdict_transition_is_shown(cases, tmp_path, baseline):
    sub = {c.case_id: bool(c.naive_held) for c in cases}
    sub[next(c.case_id for c in cases if not c.is_failure)] = False
    r = run("diff", baseline, write(tmp_path, sub))
    assert "PASS -> FAIL" in r.stdout


@pytest.mark.parametrize("body", ["[]", "not json", "null"])
def test_malformed_inputs_are_usage_errors(tmp_path, baseline, body):
    bad = tmp_path / "bad.json"
    bad.write_text(body)
    assert run("diff", baseline, str(bad)).returncode == EXIT_USAGE
    assert run("diff", str(bad), baseline).returncode == EXIT_USAGE


def test_missing_file_is_a_usage_error(baseline):
    assert run("diff", baseline, "/nonexistent.json").returncode == EXIT_USAGE
