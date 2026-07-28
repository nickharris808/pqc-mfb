"""Load PQC-MFB and score a submission against it.

A submission says, for each case, whether YOUR implementation held the invariant.
The scorer reports coverage overall, per family and per design, and -- the part that
matters -- which families you close ZERO of.

Scoring rule
------------
For each case where the naive baseline fails (`is_failure`), your implementation
either HELD the invariant (closed it) or did not. Score = closed / failures.

Cases the naive baseline already passes are NOT counted toward your score. They are
reported separately as a regression check: if you fail one of those, you have broken
something that worked before, and that is a hard failure regardless of your score.

Verdicts
--------
``PASS``        every failure case answered, nothing regressed.
``FAIL``        at least one regression -- a hard fail whatever the coverage.
``INCOMPLETE``  at least one case left unanswered, so no pass can be claimed.

The third verdict exists because the second one was wrong. Until it was added, a
submission of ``{}`` -- answering nothing at all -- scored ``PASS`` with 0% coverage
and 312 unanswered cases, because ``passed`` only consulted the regression count. A
vendor could have submitted an empty file and truthfully reported a passing PQC-MFB
run. Silence is not credit, so silence is now INCOMPLETE.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data" / "pqc_mfb.jsonl"


@dataclass(frozen=True)
class Case:
    case_id: str
    design: str
    family: str
    invariant: str
    is_failure: bool
    naive_detail: str = ""
    naive_held: bool = False
    prior_art_analogue: str = ""


def load_cases(path: Path | None = None) -> list[Case]:
    src = path or DATA
    if not src.exists():
        raise FileNotFoundError(
            f"dataset not found at {src}. Build it with "
            f"`python -m pqc_mfb.build_dataset <manifest.json> "
            f"src/pqc_mfb/data/pqc_mfb.jsonl`."
        )
    cases: list[Case] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        cases.append(Case(**{k: raw.get(k, Case.__dataclass_fields__[k].default)
                             for k in Case.__dataclass_fields__}))
    return cases


@dataclass
class Score:
    n_cases: int
    n_failures: int
    n_closed: int
    n_regressions: int
    n_unanswered: int
    by_family: dict = field(default_factory=dict)
    by_design: dict = field(default_factory=dict)
    zero_families: list = field(default_factory=list)
    unknown_ids: list = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return self.n_closed / self.n_failures if self.n_failures else 0.0

    @property
    def verdict(self) -> str:
        """PASS, FAIL or INCOMPLETE -- never a pass for work not shown.

        A regression outranks incompleteness: breaking something that already
        worked is a definite finding, whereas an unanswered case is an absence of
        one.
        """
        if self.n_regressions:
            return "FAIL"
        if self.n_unanswered:
            return "INCOMPLETE"
        return "PASS"

    @property
    def passed(self) -> bool:
        """True only for an outright PASS.

        Deliberately NOT ``n_regressions == 0``: that let an empty submission pass.
        """
        return self.verdict == "PASS"

    @property
    def verdict_reason(self) -> str:
        if self.n_regressions:
            return (f"{self.n_regressions} regression"
                    f"{'s' if self.n_regressions != 1 else ''}: a case the unrepaired "
                    f"baseline already held is now broken")
        if self.n_unanswered:
            return (f"{self.n_unanswered} of {self.n_failures} failure cases "
                    f"unanswered -- silence is not credit, so no pass is claimed")
        return f"all {self.n_failures} failure cases answered, no regressions"

    def to_dict(self) -> dict:
        return {
            "n_cases": self.n_cases,
            "n_failures": self.n_failures,
            "n_closed": self.n_closed,
            "n_regressions": self.n_regressions,
            "n_unanswered": self.n_unanswered,
            "coverage": round(self.coverage, 4),
            "coverage_pct": round(100 * self.coverage, 2),
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "passed": self.passed,
            "zero_families": self.zero_families,
            "unknown_ids": self.unknown_ids,
            "by_family": self.by_family,
            "by_design": self.by_design,
        }


def score_submission(submission: dict[str, bool], cases: list[Case] | None = None) -> Score:
    """Score {case_id: held} against the benchmark.

    A case_id absent from the submission counts as NOT closed and is reported as
    unanswered -- silence is not credit.
    """
    cases = cases if cases is not None else load_cases()

    fam_tot: dict[str, int] = defaultdict(int)
    fam_closed: dict[str, int] = defaultdict(int)
    des_tot: dict[str, int] = defaultdict(int)
    des_closed: dict[str, int] = defaultdict(int)

    n_failures = n_closed = n_regressions = n_unanswered = 0

    for case in cases:
        held = submission.get(case.case_id)
        if case.is_failure:
            n_failures += 1
            fam_tot[case.family] += 1
            des_tot[case.design] += 1
            if held is None:
                n_unanswered += 1
            elif held:
                n_closed += 1
                fam_closed[case.family] += 1
                des_closed[case.design] += 1
        else:
            # Baseline already passes. Failing here is a regression.
            if held is False:
                n_regressions += 1

    by_family = {
        f: {"total": fam_tot[f], "closed": fam_closed[f],
            "pct": round(100 * fam_closed[f] / fam_tot[f], 1)}
        for f in sorted(fam_tot)
    }
    by_design = {
        d: {"total": des_tot[d], "closed": des_closed[d],
            "pct": round(100 * des_closed[d] / des_tot[d], 1)}
        for d in sorted(des_tot)
    }
    zero = [f for f in sorted(fam_tot) if fam_closed[f] == 0]

    # Keys that match no case in the benchmark. A submission built against a stale
    # copy, or with a typo'd id, otherwise looks identical to one that answered
    # nothing -- both score 0 in silence. Name them instead.
    known = {c.case_id for c in cases}
    unknown = sorted(k for k in submission if k not in known)

    return Score(
        n_cases=len(cases), n_failures=n_failures, n_closed=n_closed,
        n_regressions=n_regressions, n_unanswered=n_unanswered,
        by_family=by_family, by_design=by_design, zero_families=zero,
        unknown_ids=unknown,
    )


def naive_baseline(cases: list[Case] | None = None) -> dict[str, bool]:
    """The floor: an unrepaired design. Holds exactly what the baseline holds."""
    cases = cases if cases is not None else load_cases()
    return {c.case_id: bool(c.naive_held) for c in cases}


def perfect_submission(cases: list[Case] | None = None) -> dict[str, bool]:
    """The ceiling: closes every failure and regresses nothing."""
    cases = cases if cases is not None else load_cases()
    return {c.case_id: True for c in cases}
