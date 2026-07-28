"""SARIF and JUnit emitters.

A report format exists to be consumed by a machine that will act on it. A
malformed SARIF file is not a loud error -- GitHub ignores it and the build goes
green, having verified nothing. So these tests check structure against the spec's
required shape, not merely that a string came back.

The property that matters most: an INCOMPLETE submission must appear as a failure
in every format. Neither SARIF nor JUnit can natively express "I could not tell",
and mapping that onto "passed" would hand a green check to a submission that
showed no work.
"""

from __future__ import annotations

import json
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from pqc_mfb import junit_report, load_cases, sarif_report
from pqc_mfb.report import write_report
from pqc_mfb.score import perfect_submission, score_submission

EXIT_PASS, EXIT_FAIL, EXIT_INCOMPLETE = 0, 1, 3


@pytest.fixture(scope="module")
def cases():
    return load_cases()


@pytest.fixture()
def incomplete(cases):
    return score_submission({}, cases)


@pytest.fixture()
def clean(cases):
    return score_submission(perfect_submission(cases), cases)


def run(*args):
    return subprocess.run([sys.executable, "-m", "pqc_mfb.cli", *args],
                          capture_output=True, text=True, timeout=60)


# ------------------------------------------------------------------------- SARIF

def test_sarif_has_the_required_top_level_shape(incomplete):
    log = sarif_report(incomplete)
    assert log["version"] == "2.1.0"
    assert "$schema" in log
    assert isinstance(log["runs"], list) and len(log["runs"]) == 1
    driver = log["runs"][0]["tool"]["driver"]
    assert driver["name"] == "pqc-mfb"
    assert "informationUri" in driver


def test_every_result_references_a_declared_rule(incomplete):
    """A result whose ruleId is not in the driver's rule list is invalid SARIF."""
    run_ = sarif_report(incomplete)["runs"][0]
    declared = {r["id"] for r in run_["tool"]["driver"]["rules"]}
    used = {r["ruleId"] for r in run_["results"]}
    assert used <= declared, f"undeclared rules: {used - declared}"


def test_every_result_has_a_message_level_and_location(incomplete):
    for result in sarif_report(incomplete)["runs"][0]["results"]:
        assert result["message"]["text"]
        assert result["level"] in {"error", "warning", "note", "none"}
        loc = result["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"]


def test_incomplete_is_reported_as_an_error_not_a_pass(incomplete):
    results = sarif_report(incomplete)["runs"][0]["results"]
    verdicts = [r for r in results if r["ruleId"] == "pqc-mfb/verdict"]
    assert verdicts, "an INCOMPLETE submission produced no verdict result"
    assert verdicts[0]["level"] == "error"
    assert "INCOMPLETE" in verdicts[0]["message"]["text"]


def test_a_clean_submission_emits_no_results(clean):
    assert sarif_report(clean)["runs"][0]["results"] == []


def test_zero_coverage_families_each_get_a_result(incomplete):
    results = sarif_report(incomplete)["runs"][0]["results"]
    zero = [r for r in results if "zero-coverage" in r["ruleId"]]
    assert len(zero) == len(incomplete.zero_families) == 38


def test_unknown_ids_surface_in_sarif(cases):
    score = score_submission({"ghost::case": True}, cases)
    text = json.dumps(sarif_report(score))
    assert "ghost::case" in text


def test_sarif_is_json_serialisable(incomplete):
    json.loads(json.dumps(sarif_report(incomplete)))


# ------------------------------------------------------------------------- JUnit

def test_junit_parses_as_xml(incomplete):
    root = ET.fromstring(junit_report(incomplete).split("?>", 1)[1])
    assert root.tag == "testsuite"
    assert root.get("name") == "pqc-mfb"


def test_junit_counts_match_its_own_cases(incomplete):
    root = ET.fromstring(junit_report(incomplete).split("?>", 1)[1])
    declared = int(root.get("tests"))
    family_cases = [c for c in root.findall("testcase")
                    if c.get("classname", "").endswith("families")]
    assert declared == len(family_cases)


def test_junit_marks_incomplete_as_a_failure(incomplete):
    root = ET.fromstring(junit_report(incomplete).split("?>", 1)[1])
    verdict = next(c for c in root.findall("testcase") if c.get("name") == "verdict")
    failure = verdict.find("failure")
    assert failure is not None, "INCOMPLETE was not reported as a failure"
    assert "INCOMPLETE" in failure.get("message")


def test_junit_verdict_passes_for_a_clean_submission(clean):
    root = ET.fromstring(junit_report(clean).split("?>", 1)[1])
    verdict = next(c for c in root.findall("testcase") if c.get("name") == "verdict")
    assert verdict.find("failure") is None


def test_junit_exposes_properties(incomplete):
    root = ET.fromstring(junit_report(incomplete).split("?>", 1)[1])
    props = {p.get("name"): p.get("value") for p in root.find("properties")}
    assert props["verdict"] == "INCOMPLETE"
    assert props["unanswered"] == "312"


# --------------------------------------------------------------------- CLI wiring

@pytest.mark.parametrize("fmt", ["sarif", "junit"])
def test_cli_emits_the_format_and_keeps_the_exit_code(tmp_path, fmt):
    sub = tmp_path / "s.json"
    sub.write_text("{}")
    out = tmp_path / f"r.{fmt}"
    r = run("score", str(sub), "--format", fmt, "-o", str(out))
    assert r.returncode == EXIT_INCOMPLETE, "the format must not mask the verdict"
    assert out.exists() and out.read_text().strip()


def test_cli_writes_sarif_to_stdout_when_no_output(tmp_path):
    sub = tmp_path / "s.json"
    sub.write_text("{}")
    r = run("score", str(sub), "--format", "sarif")
    assert json.loads(r.stdout)["version"] == "2.1.0"


def test_sarif_points_at_the_submission_file(tmp_path):
    sub = tmp_path / "mysub.json"
    sub.write_text("{}")
    r = run("score", str(sub), "--format", "sarif")
    uri = json.loads(r.stdout)["runs"][0]["results"][0]["locations"][0] \
        ["physicalLocation"]["artifactLocation"]["uri"]
    assert "mysub.json" in uri


def test_unknown_format_is_rejected(incomplete):
    with pytest.raises(ValueError, match="unknown report format"):
        write_report(incomplete, "yaml")


# ------------------------------------------------------- validation against the spec

def test_declared_schema_url_resolves():
    """The $schema we emit must actually exist.

    The widely-copied raw.githubusercontent.com/oasis-tcs/.../Schemata/ URL is a
    404; shipping it would mean every report pointed at nothing.
    """
    urllib = pytest.importorskip("urllib.request")
    from pqc_mfb.report import SARIF_SCHEMA
    try:
        with urllib.urlopen(SARIF_SCHEMA, timeout=20) as response:
            assert response.status == 200
            assert len(response.read()) > 10_000
    except OSError as exc:
        pytest.skip(f"network unavailable: {exc}")


@pytest.mark.parametrize("which", ["incomplete", "clean"])
def test_sarif_validates_against_the_official_schema(request, which):
    """Structural tests are not enough: GitHub silently ignores invalid SARIF."""
    jsonschema = pytest.importorskip("jsonschema")
    import urllib.request

    from pqc_mfb.report import SARIF_SCHEMA
    try:
        with urllib.request.urlopen(SARIF_SCHEMA, timeout=20) as response:
            schema = json.loads(response.read())
    except OSError as exc:
        pytest.skip(f"network unavailable: {exc}")
    jsonschema.validate(sarif_report(request.getfixturevalue(which)), schema)
