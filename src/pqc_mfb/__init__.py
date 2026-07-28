"""PQC-MFB: the Post-Quantum Migration Failure Benchmark.

Public API
----------
Everything in ``__all__`` is a supported entry point and will not change shape
without a major version bump. Anything else -- names beginning with ``_``, and the
submodules themselves -- is internal.

    from pqc_mfb import load_cases, families, score_submission

    cases = load_cases()                       # list[Case], cached per file
    tax   = families(cases)                    # list[Family], cached per corpus
    score = score_submission(sub, cases)       # Score, with .verdict
"""

from .report import junit_report, sarif_report
from .score import (
    Case,
    Family,
    Score,
    families,
    load_cases,
    naive_baseline,
    perfect_submission,
    score_submission,
    to_dataframe,
)

__version__ = "0.2.0"
__all__ = [
    "Case",
    "Family",
    "Score",
    "__version__",
    "families",
    "junit_report",
    "load_cases",
    "naive_baseline",
    "perfect_submission",
    "sarif_report",
    "score_submission",
    "to_dataframe",
]
