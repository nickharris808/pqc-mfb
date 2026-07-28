"""Machine-readable reports: SARIF for code scanning, JUnit for CI test panes.

Both formats are emitted from a scored submission, so neither can disagree with
what `pqc-mfb score` prints -- they read the same `Score`.

A note on honesty in these formats. SARIF and JUnit both encode "problem" and
"no problem", and neither has a native way to say "I could not tell". An
INCOMPLETE submission is therefore reported as a *failure* in both, never as a
pass, with the reason in the message. Mapping "did not answer" onto "passed"
would hand a green check to a submission that showed no work -- the exact defect
this benchmark already had once.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .score import Score

SARIF_VERSION = "2.1.0"
#: The OASIS canonical schema URL. The widely-copied
#: raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/... address is a
#: 404 -- that repository moved -- so emitting it would have shipped a $schema
#: pointer that does not resolve. A test fetches this URL and validates against it.
SARIF_SCHEMA = ("https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/"
                "schemas/sarif-schema-2.1.0.json")

#: SARIF levels. "note" is never used for a real finding: a family you close zero
#: of is an error or nothing, not advice.
_LEVEL = {"FAIL": "error", "INCOMPLETE": "error", "PASS": "none"}


def sarif_report(score: Score, submission_path: str = "pqc-mfb-submission.json") -> dict:
    """A SARIF 2.1.0 log for GitHub code scanning.

    One rule per zero-coverage family plus one for the overall verdict, each
    anchored to the submission file so the Security tab has somewhere to point.
    """
    rules: list[dict] = []
    results: list[dict] = []

    def location() -> list[dict]:
        return [{"physicalLocation": {
            "artifactLocation": {"uri": submission_path},
            "region": {"startLine": 1},
        }}]

    rules.append({
        "id": "pqc-mfb/verdict",
        "name": "BenchmarkVerdict",
        "shortDescription": {"text": "PQC-MFB submission verdict"},
        "fullDescription": {"text": (
            "PASS requires every failure case answered and no regressions. "
            "INCOMPLETE means cases were left unanswered; it is not a pass.")},
        "defaultConfiguration": {"level": "error"},
    })
    if score.verdict != "PASS":
        results.append({
            "ruleId": "pqc-mfb/verdict",
            "level": _LEVEL[score.verdict],
            "message": {"text": f"{score.verdict}: {score.verdict_reason} "
                                f"(coverage {score.n_closed}/{score.n_failures})"},
            "locations": location(),
        })

    for family in score.zero_families:
        rule_id = f"pqc-mfb/zero-coverage/{family}"
        rules.append({
            "id": rule_id,
            "name": f"ZeroCoverage{family.title().replace('_', '')}",
            "shortDescription": {"text": f"No cases closed in {family}"},
            "fullDescription": {"text": (
                f"The submission closed zero of the failure cases in the "
                f"{family} family. Overall coverage hides shape: closing 90% "
                f"while missing a family entirely is a different result from "
                f"closing 90% evenly.")},
            "defaultConfiguration": {"level": "error"},
        })
        results.append({
            "ruleId": rule_id,
            "level": "error",
            "message": {"text": f"zero coverage in failure family '{family}'"},
            "locations": location(),
        })

    for unknown in score.unknown_ids[:50]:
        results.append({
            "ruleId": "pqc-mfb/verdict",
            "level": "error",
            "message": {"text": f"submitted case id '{unknown}' matches no case in "
                                f"this benchmark and was ignored"},
            "locations": location(),
        })

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [{
            "tool": {"driver": {
                "name": "pqc-mfb",
                "informationUri": "https://github.com/nickharris808/pqc-mfb",
                "rules": rules,
            }},
            "results": results,
        }],
    }


def junit_report(score: Score, suite_name: str = "pqc-mfb") -> str:
    """A JUnit XML report: one test case per failure family.

    CI systems render this natively, so a benchmark run appears alongside the
    project's own tests rather than buried in log output.
    """
    n_fail = sum(1 for f in score.by_family.values() if f["closed"] < f["total"])
    suite = ET.Element("testsuite", {
        "name": suite_name,
        "tests": str(len(score.by_family)),
        "failures": str(n_fail),
        "errors": "0",
        "skipped": "0",
    })

    for family, stats in sorted(score.by_family.items()):
        case = ET.SubElement(suite, "testcase", {
            "classname": f"{suite_name}.families",
            "name": family,
        })
        if stats["closed"] < stats["total"]:
            ET.SubElement(case, "failure", {
                "message": f"closed {stats['closed']}/{stats['total']} "
                           f"({stats['pct']}%)",
                "type": "coverage",
            }).text = (f"The submission closed {stats['closed']} of {stats['total']} "
                       f"failure cases in '{family}'.")

    verdict = ET.SubElement(suite, "testcase", {
        "classname": suite_name,
        "name": "verdict",
    })
    if score.verdict != "PASS":
        ET.SubElement(verdict, "failure", {
            "message": f"{score.verdict}: {score.verdict_reason}",
            "type": score.verdict,
        }).text = (f"verdict={score.verdict}  coverage={score.n_closed}/"
                   f"{score.n_failures}  regressions={score.n_regressions}  "
                   f"unanswered={score.n_unanswered}")

    props = ET.SubElement(suite, "properties")
    for key, value in [("verdict", score.verdict),
                       ("coverage_pct", f"{100 * score.coverage:.2f}"),
                       ("regressions", str(score.n_regressions)),
                       ("unanswered", str(score.n_unanswered)),
                       ("unknown_ids", str(len(score.unknown_ids)))]:
        ET.SubElement(props, "property", {"name": key, "value": value})

    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            + ET.tostring(suite, encoding="unicode"))


def write_report(score: Score, fmt: str, path: str | None = None,
                 submission_path: str = "pqc-mfb-submission.json") -> str:
    """Render a scored submission in `fmt`. Returns the text."""
    if fmt == "sarif":
        text = json.dumps(sarif_report(score, submission_path), indent=2)
    elif fmt == "junit":
        text = junit_report(score)
    else:
        raise ValueError(f"unknown report format {fmt!r}; use 'sarif' or 'junit'")
    if path:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    return text
