"""Tests for the command line interface.

`pqc-mfb info` and `pqc-mfb score` are the README quickstart, so their exit
codes and headline numbers are a public contract. Driven as a subprocess
because a CI pipeline consumes exactly the exit code and the stdout text.
"""

from __future__ import annotations

import json
import subprocess
import sys


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pqc_mfb.cli", *args],
        capture_output=True, text=True, timeout=60,
    )


def test_info_reports_the_documented_totals():
    r = run("info")
    assert r.returncode == 0
    for expected in ("322", "312", "39", "10"):
        assert expected in r.stdout


def test_naive_baseline_scores_zero():
    """The floor has to actually be the floor.

    If the unrepaired baseline ever scored above zero the benchmark would be
    measuring something other than what it claims.
    """
    r = run("score", "--baseline", "naive")
    assert "0/312" in r.stdout
    assert "regressions   0" in r.stdout


def test_zero_coverage_families_is_38_not_39():
    """One family is control-only, so it can never be zero-covered.

    `fragment_truncate` is held even by the unrepaired baseline, so it
    contributes controls rather than failures. Printing 38 next to an
    advertised 39 families looks like an off-by-one; it is not, and the
    README says why.
    """
    r = run("score", "--baseline", "naive")
    assert "zero-coverage families (38)" in r.stdout
    assert "fragment_truncate" not in r.stdout


def test_json_output_is_parseable():
    r = run("--json", "score", "--baseline", "naive")
    payload = json.loads(r.stdout)
    assert payload["n_failures"] == 312
    assert payload["n_closed"] == 0


def test_unknown_subcommand_is_a_usage_error():
    r = run("definitely-not-a-command")
    assert r.returncode != 0
