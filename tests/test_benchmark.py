"""Tests for the PQC-MFB dataset and scorer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pqc_mfb import load_cases, naive_baseline, perfect_submission, score_submission
from pqc_mfb.build_dataset import PUBLIC_FIELDS, WITHHELD_FIELDS, to_public_case

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "src" / "pqc_mfb" / "data" / "pqc_mfb.jsonl"


@pytest.fixture(scope="module")
def cases():
    return load_cases()


# ------------------------------------------------------------- dataset

def test_dataset_shape(cases):
    assert len(cases) == 322
    assert sum(1 for c in cases if c.is_failure) == 312
    assert len({c.family for c in cases}) == 39
    assert len({c.design for c in cases}) == 10


def test_case_ids_are_unique(cases):
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))


def test_every_case_has_a_family_design_and_invariant(cases):
    for c in cases:
        assert c.family and c.design and c.invariant
        assert "::" in c.case_id


def test_failure_cases_carry_a_naive_detail(cases):
    """A failure with no description is not usable by a third party."""
    for c in cases:
        if c.is_failure:
            assert c.naive_detail, f"{c.case_id} has no naive_detail"


# --------------------------------------------------------------- moat

def test_withheld_fields_are_absent_from_the_published_file():
    """The incidence matrix (failure -> mechanism) stays closed."""
    raw = DATA.read_text()
    for field in WITHHELD_FIELDS:
        assert field not in raw, f"{field} leaked into the public dataset"


def test_projection_drops_withheld_fields():
    internal = {
        "case_id": "x::y", "design": "x", "family": "y", "invariant": "i",
        "is_failure": True, "naive_detail": "d", "naive_held": False,
        "prior_art_analogue": "a",
        "repair_mechanism": "AB", "repaired_detail": "secret", "repaired_held": True,
    }
    pub = to_public_case(internal)
    for field in WITHHELD_FIELDS:
        assert field not in pub
    for field in ("case_id", "design", "family", "invariant", "is_failure"):
        assert field in pub


def test_public_and_withheld_field_sets_are_disjoint():
    assert not (set(PUBLIC_FIELDS) & set(WITHHELD_FIELDS))


# -------------------------------------------------------------- scoring

def test_naive_baseline_is_the_floor(cases):
    sc = score_submission(naive_baseline(cases), cases)
    assert sc.n_closed == 0
    assert sc.coverage == 0.0
    assert sc.n_regressions == 0          # the baseline cannot regress against itself
    assert sc.passed


def test_perfect_submission_is_the_ceiling(cases):
    sc = score_submission(perfect_submission(cases), cases)
    assert sc.n_closed == sc.n_failures == 312
    assert sc.coverage == 1.0
    assert sc.zero_families == []
    assert sc.passed


def test_missing_case_counts_as_unanswered_not_credit(cases):
    partial = {c.case_id: True for c in cases if c.is_failure}
    dropped = next(iter(partial))
    del partial[dropped]
    sc = score_submission(partial, cases)
    assert sc.n_unanswered == 1
    assert sc.n_closed == 311


def test_empty_submission_scores_zero_and_is_all_unanswered(cases):
    sc = score_submission({}, cases)
    assert sc.n_closed == 0
    assert sc.n_unanswered == sc.n_failures


def test_regression_on_a_passing_case_is_a_hard_fail(cases):
    """Breaking something the baseline already got right fails, whatever the score."""
    sub = perfect_submission(cases)
    ok_case = next(c for c in cases if not c.is_failure)
    sub[ok_case.case_id] = False
    sc = score_submission(sub, cases)
    assert sc.n_regressions == 1
    assert sc.coverage == 1.0             # perfect coverage ...
    assert not sc.passed                  # ... and still does not pass


def test_partial_submission_reports_zero_families(cases):
    """Close one family only; every other family must be reported as zero."""
    target = cases[0].family
    sub = {c.case_id: (c.family == target) for c in cases if c.is_failure}
    sc = score_submission(sub, cases)
    assert target not in sc.zero_families
    assert len(sc.zero_families) >= 30
    assert sc.by_family[target]["pct"] == 100.0


def test_per_family_totals_sum_to_overall(cases):
    sub = perfect_submission(cases)
    sc = score_submission(sub, cases)
    assert sum(v["total"] for v in sc.by_family.values()) == sc.n_failures
    assert sum(v["closed"] for v in sc.by_family.values()) == sc.n_closed


def test_per_design_totals_sum_to_overall(cases):
    sc = score_submission(perfect_submission(cases), cases)
    assert sum(v["total"] for v in sc.by_design.values()) == sc.n_failures


# ------------------------------------------------------------ baselines

def test_committed_baselines_match_a_fresh_computation(cases):
    """The published baseline files must be reproducible, not hand-written."""
    fresh_naive = score_submission(naive_baseline(cases), cases).to_dict()
    stored = json.loads((ROOT / "baselines" / "naive_baseline.json").read_text())
    assert stored["n_closed"] == fresh_naive["n_closed"] == 0
    assert stored["coverage_pct"] == fresh_naive["coverage_pct"]

    fresh_perfect = score_submission(perfect_submission(cases), cases).to_dict()
    ceiling = json.loads((ROOT / "baselines" / "reference_ceiling.json").read_text())
    assert ceiling["coverage_pct"] == fresh_perfect["coverage_pct"] == 100.0


def test_scoring_a_stored_submission_file_works(cases):
    sub = json.loads((ROOT / "baselines" / "naive_submission.json").read_text())
    sc = score_submission({k: bool(v) for k, v in sub.items()}, cases)
    assert sc.n_closed == 0
    assert sc.n_unanswered == 0           # the file answers every case


# ------------------------------------------------------- packaging

def test_dataset_lives_inside_the_package():
    """Regression: the data file must ship INSIDE the installed package.

    It previously lived at <repo>/data/, which works under `pip install -e .`
    (the src layout points back at the checkout) but is absent from a real
    wheel -- so `pip install pqc-mfb` from an index crashed on first use.
    Resolving from the package directory is what makes the wheel self-contained.
    """
    import pqc_mfb.score as score_mod

    pkg_dir = Path(score_mod.__file__).resolve().parent
    assert score_mod.DATA.parent == pkg_dir / "data"
    assert score_mod.DATA.exists()


def test_package_data_is_declared_for_the_wheel():
    """pyproject must tell setuptools to include the data, or the wheel is empty.

    Asserts the required globs are present rather than matching the declaration
    byte-for-byte: adding an unrelated entry such as ``py.typed`` must not fail a
    test whose subject is the data files.
    """
    text = (ROOT / "pyproject.toml").read_text()
    assert "[tool.setuptools.package-data]" in text
    declaration = next(ln for ln in text.splitlines() if ln.startswith("pqc_mfb = ["))
    for glob in ('"data/*.jsonl"', '"data/*.json"'):
        assert glob in declaration, f"{glob} missing from package-data"


def test_py_typed_marker_ships():
    """PEP 561: without this file, type checkers ignore the package's annotations."""
    text = (ROOT / "pyproject.toml").read_text()
    declaration = next(ln for ln in text.splitlines() if ln.startswith("pqc_mfb = ["))
    assert '"py.typed"' in declaration
    assert (ROOT / "src" / "pqc_mfb" / "py.typed").exists()


def test_load_cases_works_without_a_cwd_dependency(tmp_path, monkeypatch):
    """Running from an unrelated directory must still find the dataset."""
    monkeypatch.chdir(tmp_path)
    assert len(load_cases()) == 322
