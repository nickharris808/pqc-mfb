"""Tests for `pqc-mfb submit` and `pqc-mfb explain`.

`submit` exists because hand-writing 322 case ids was the biggest barrier to a
first score, and a mistyped id is invisible -- it scores as unanswered rather
than erroring. So the scaffold has one property that matters above all: what it
produces must score cleanly without being edited.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from pqc_mfb import load_cases

EXIT_PASS, EXIT_FAIL, EXIT_INCOMPLETE, EXIT_USAGE = 0, 1, 3, 2


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "pqc_mfb.cli", *args],
                          capture_output=True, text=True, timeout=60)


# ------------------------------------------------------------------------ submit

def test_template_covers_every_case(tmp_path):
    out = tmp_path / "s.json"
    assert run("submit", "-o", str(out)).returncode == 0
    template = json.loads(out.read_text())
    assert set(template) == {c.case_id for c in load_cases()}
    assert len(template) == 322


def test_a_fresh_scaffold_scores_without_editing(tmp_path):
    """The default fill must not start red.

    Filling every case false marks the 10 control cases as broken, so the
    scaffold would score FAIL with 10 regressions before its owner changed
    anything. The default seeds from the unrepaired baseline instead.
    """
    out = tmp_path / "s.json"
    run("submit", "-o", str(out))
    r = run("score", str(out))
    assert r.returncode == EXIT_PASS, r.stdout
    assert "0/312" in r.stdout          # the documented floor
    assert "regressions   0" in r.stdout


def test_template_is_complete_so_it_is_never_incomplete(tmp_path):
    out = tmp_path / "s.json"
    run("submit", "-o", str(out))
    r = run("score", str(out))
    assert "INCOMPLETE" not in r.stdout


def test_fill_true_is_the_ceiling(tmp_path):
    out = tmp_path / "s.json"
    run("submit", "--fill", "true", "-o", str(out))
    r = run("score", str(out))
    assert r.returncode == EXIT_PASS
    assert "312/312" in r.stdout


def test_fill_false_is_documented_as_producing_regressions(tmp_path):
    out = tmp_path / "s.json"
    r = run("submit", "--fill", "false", "-o", str(out))
    assert "regressions" in r.stdout, "the footgun must be called out"
    assert run("score", str(out)).returncode == EXIT_FAIL


def test_template_to_stdout_is_valid_json():
    r = run("submit")
    assert len(json.loads(r.stdout)) == 322


def test_template_ids_are_all_recognised(tmp_path):
    """No unknown-id warning may appear for our own scaffold."""
    out = tmp_path / "s.json"
    run("submit", "-o", str(out))
    assert "match no case" not in run("score", str(out)).stdout


# ----------------------------------------------------------------------- explain

def test_explain_reports_a_real_family():
    r = run("explain", "krack_retransmission")
    assert r.returncode == 0
    assert "no_key_reinstall" in r.stdout
    assert "KRACK" in r.stdout


def test_explain_never_reveals_a_repair():
    """Same boundary as the MCP surface: detection ships, repairs do not."""
    for family in sorted({c.family for c in load_cases()}):
        out = run("explain", family).stdout
        for banned in ("repair_mechanism", "repaired_detail", "repaired_held"):
            assert banned not in out, f"{banned} leaked via explain {family}"


def test_explain_marks_the_analogue_as_shape_not_reproduction():
    r = run("explain", "krack_retransmission")
    assert "not a reproduction" in r.stdout


def test_unknown_family_suggests_a_near_match():
    r = run("explain", "krack")
    assert r.returncode == EXIT_USAGE
    assert "krack_retransmission" in r.stderr


def test_unrecognisable_family_points_at_info():
    r = run("explain", "zzzzz")
    assert r.returncode == EXIT_USAGE
    assert "pqc-mfb info" in r.stderr


@pytest.mark.parametrize("family", ["fragment_truncate", "ap_flood", "mlo_misbind"])
def test_explain_json_is_parseable(family):
    r = run("--json", "explain", family)
    payload = json.loads(r.stdout)
    assert payload["family"] == family
    assert payload["n_cases"] >= 1
