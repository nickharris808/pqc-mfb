"""Cache correctness and the stable public API.

The cache is the highest-risk change in this release. A cache keyed carelessly is
the classic way correct code starts returning confident wrong answers: the scorer
would report numbers for a corpus that no longer exists on disk, and nothing about
the output would look unusual. These tests exist to make that impossible.
"""

from __future__ import annotations

import dataclasses
import json
import time

import pytest

import pqc_mfb
from pqc_mfb import Case, Family, families, load_cases
from pqc_mfb.score import score_submission


def write_corpus(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def row(case_id, family="fam_a", is_failure=True):
    return {"case_id": case_id, "design": "d1", "family": family,
            "invariant": "inv", "is_failure": is_failure,
            "naive_detail": "", "naive_held": not is_failure,
            "prior_art_analogue": ""}


# --------------------------------------------------------------- cache correctness

def test_cache_does_not_leak_between_files(tmp_path):
    """The bug this prevents: load a fixture, then the default, and get the fixture."""
    fixture = write_corpus(tmp_path / "a.jsonl", [row("x::1")])
    assert len(load_cases(fixture)) == 1
    assert len(load_cases()) == 322, "the default corpus was shadowed by a fixture"


def test_regenerating_a_file_invalidates_the_cache(tmp_path):
    """A rebuilt dataset must not be served stale.

    `build_dataset` rewrites the corpus in place. If the cache keyed on path
    alone, every consumer in that process would keep scoring against the old data.
    """
    path = write_corpus(tmp_path / "c.jsonl", [row("x::1"), row("x::2")])
    assert len(load_cases(path)) == 2

    time.sleep(0.01)  # ensure a distinguishable mtime on coarse-grained filesystems
    write_corpus(path, [row("y::1")])
    assert len(load_cases(path)) == 1, "stale corpus served after regeneration"


def test_mutating_the_result_cannot_corrupt_the_cache():
    first = load_cases()
    first.append("not a case")
    first.clear()
    assert len(load_cases()) == 322


def test_repeat_loads_return_equal_data():
    a, b = load_cases(), load_cases()
    assert a == b
    assert a is not b, "callers must not share one mutable list"


def test_str_and_path_are_both_accepted(tmp_path):
    path = write_corpus(tmp_path / "s.jsonl", [row("x::1")])
    assert load_cases(str(path)) == load_cases(path)


def test_missing_file_still_raises_a_useful_error(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        load_cases(tmp_path / "nope.jsonl")
    assert "build_dataset" in str(exc.value)


# ------------------------------------------------------------------- families() API

def test_families_matches_the_corpus():
    fams = families()
    assert len(fams) == 39
    assert all(isinstance(f, Family) for f in fams)
    assert sum(f.n_cases for f in fams) == 322
    assert sum(f.n_failures for f in fams) == 312


def test_families_is_sorted_and_stable():
    names = [f.name for f in families()]
    assert names == sorted(names)
    assert names == [f.name for f in families()]


def test_exactly_one_family_is_control_only():
    """This is why the scorer reports 38 zero-coverage families, not 39."""
    control_only = [f.name for f in families() if f.is_control_only]
    assert control_only == ["fragment_truncate"]


def test_families_accepts_an_explicit_corpus(tmp_path):
    path = write_corpus(tmp_path / "t.jsonl",
                        [row("a::1", "fam_a"), row("b::1", "fam_b", is_failure=False)])
    fams = families(load_cases(path))
    assert [f.name for f in fams] == ["fam_a", "fam_b"]
    assert fams[1].is_control_only is True


def test_families_agrees_with_the_scorer():
    """Two independent derivations of the same fact must not diverge."""
    cases = load_cases()
    from_scorer = {f for f in score_submission({}, cases).by_family}
    from_api = {f.name for f in families(cases) if not f.is_control_only}
    assert from_scorer == from_api


# --------------------------------------------------------------------- public API

def test_public_api_is_declared():
    for name in ("Case", "Family", "Score", "families", "load_cases",
                 "score_submission", "sarif_report", "junit_report"):
        assert name in pqc_mfb.__all__
        assert hasattr(pqc_mfb, name)


def test_everything_exported_is_importable():
    for name in pqc_mfb.__all__:
        assert getattr(pqc_mfb, name, None) is not None


def test_case_is_immutable():
    case = load_cases()[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        case.family = "mutated"  # type: ignore[misc]
    assert isinstance(case, Case)
