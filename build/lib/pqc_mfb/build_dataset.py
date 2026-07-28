"""Derive the public PQC-MFB dataset from the internal benchmark manifest.

This is the reproducible provenance step: it takes the lab's internal manifest and
emits the public JSONL, dropping the fields that belong to the closed core.

WHAT IS DROPPED, AND WHY
------------------------
Two fields are removed from every case:

  repair_mechanism  -- which mechanism closes this failure
  repaired_detail   -- what the repaired run does instead

Together those form the failure-to-mechanism incidence matrix, which is the *input*
to the minimum-cover computation. Publishing the benchmark is publishing the disease:
here is a failure, here is what a naive design does, here is the published analogue.
Publishing the incidence matrix would be publishing the shape of the cure.

Everything a scorer needs is retained. You can evaluate any implementation against
every case without knowing which mechanism the reference used.

Usage:
    python -m pqc_mfb.build_dataset <internal_manifest.json> src/pqc_mfb/data/pqc_mfb.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Fields removed from every published case.
WITHHELD_FIELDS = ("repair_mechanism", "repaired_detail", "repaired_held")

# Fields published, in order.
PUBLIC_FIELDS = (
    "case_id",
    "design",
    "family",
    "invariant",
    "is_failure",
    "naive_detail",
    "naive_held",
    "prior_art_analogue",
)


def to_public_case(case: dict) -> dict:
    """Project one internal case onto the published schema."""
    out = {k: case.get(k) for k in PUBLIC_FIELDS if k in case}
    for field in WITHHELD_FIELDS:
        assert field not in out, f"{field} must not reach the public dataset"
    return out


def build(manifest_path: Path, out_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    cases = manifest["cases"]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for case in cases:
            fh.write(json.dumps(to_public_case(case), sort_keys=True) + "\n")

    families = sorted({c["family"] for c in cases})
    designs = sorted({c["design"] for c in cases})
    failures = sum(1 for c in cases if c.get("is_failure"))

    meta = {
        "name": "PQC-MFB",
        "long_name": "Post-Quantum Migration Failure Benchmark",
        "schema_version": 1,
        "n_cases": len(cases),
        "n_failures": failures,
        "n_families": len(families),
        "n_designs": len(designs),
        "families": families,
        "designs": designs,
        "public_fields": list(PUBLIC_FIELDS),
        "withheld_fields": list(WITHHELD_FIELDS),
    }
    (out_path.parent / "pqc_mfb_meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n"
    )
    return meta


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print(__doc__)
        return 2
    meta = build(Path(args[0]), Path(args[1]))
    print(f"wrote {meta['n_cases']} cases "
          f"({meta['n_failures']} failures, {meta['n_families']} families, "
          f"{meta['n_designs']} designs)")
    print(f"withheld fields: {', '.join(meta['withheld_fields'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
