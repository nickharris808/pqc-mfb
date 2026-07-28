"""pqc-mfb command line: inspect the benchmark and score a submission."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .score import load_cases, naive_baseline, perfect_submission, score_submission


def cmd_info(args) -> int:
    cases = load_cases(args.data)
    fams = Counter(c.family for c in cases)
    designs = Counter(c.design for c in cases)
    failures = sum(1 for c in cases if c.is_failure)
    if args.json:
        print(json.dumps({"n_cases": len(cases), "n_failures": failures,
                          "n_families": len(fams), "n_designs": len(designs),
                          "families": sorted(fams), "designs": sorted(designs)}, indent=2))
        return 0
    print("PQC-MFB — Post-Quantum Migration Failure Benchmark")
    print(f"  cases      {len(cases)}")
    print(f"  failures   {failures}   (cases where the naive baseline breaks)")
    print(f"  families   {len(fams)}")
    print(f"  designs    {len(designs)}")
    print(f"\n{'family':<38} cases")
    print("-" * 46)
    for fam, n in sorted(fams.items()):
        print(f"  {fam:<36} {n:>4}")
    return 0


def cmd_cases(args) -> int:
    cases = load_cases(args.data)
    if args.family:
        cases = [c for c in cases if c.family == args.family]
    if args.design:
        cases = [c for c in cases if c.design == args.design]
    if args.failures_only:
        cases = [c for c in cases if c.is_failure]
    if args.json:
        print(json.dumps([c.__dict__ for c in cases], indent=2))
        return 0
    for c in cases:
        flag = "FAIL" if c.is_failure else "ok  "
        print(f"[{flag}] {c.case_id}")
        if c.naive_detail:
            print(f"         {c.naive_detail}")
        if c.prior_art_analogue:
            print(f"         analogue: {c.prior_art_analogue}")
    print(f"\n{len(cases)} case(s)")
    return 0


def cmd_score(args) -> int:
    cases = load_cases(args.data)
    if args.baseline == "naive":
        submission = naive_baseline(cases)
        label = "naive baseline"
    elif args.baseline == "perfect":
        submission = perfect_submission(cases)
        label = "perfect (reference ceiling)"
    else:
        try:
            raw = json.loads(Path(args.submission).read_text())
        except Exception as exc:
            print(f"could not read submission: {exc}", file=sys.stderr)
            return 2
        if not isinstance(raw, dict):
            print("submission must be a JSON object of {case_id: bool}", file=sys.stderr)
            return 2
        submission = {k: bool(v) for k, v in raw.items()}
        label = args.submission

    sc = score_submission(submission, cases)
    if args.json:
        print(json.dumps(sc.to_dict(), indent=2))
        return 0 if sc.passed else 1

    print(f"submission: {label}")
    print(f"  coverage      {sc.n_closed}/{sc.n_failures}  ({100*sc.coverage:.1f}%)")
    print(f"  regressions   {sc.n_regressions}" +
          ("   <-- HARD FAIL" if sc.n_regressions else ""))
    print(f"  unanswered    {sc.n_unanswered}")
    if sc.zero_families:
        print(f"\n  families closed 0 of ({len(sc.zero_families)}):")
        for f in sc.zero_families:
            print(f"    - {f}")
    if args.verbose:
        print(f"\n  {'family':<38} closed")
        print("  " + "-" * 50)
        for fam, st in sc.by_family.items():
            print(f"  {fam:<38} {st['closed']:>3}/{st['total']:<3} ({st['pct']:>5.1f}%)")
    print(f"\n  result: {'PASS' if sc.passed else 'FAIL (regressions present)'}")
    return 0 if sc.passed else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pqc-mfb",
        description="Post-Quantum Migration Failure Benchmark: inspect and score.")
    p.add_argument("--json", action="store_true")
    p.add_argument("--data", type=Path, default=None, help="path to pqc_mfb.jsonl")
    sub = p.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("info", help="dataset summary")
    i.set_defaults(func=cmd_info)

    c = sub.add_parser("cases", help="list cases")
    c.add_argument("--family")
    c.add_argument("--design")
    c.add_argument("--failures-only", action="store_true")
    c.set_defaults(func=cmd_cases)

    s = sub.add_parser("score", help="score a submission")
    s.add_argument("submission", nargs="?", help="JSON file of {case_id: bool}")
    s.add_argument("--baseline", choices=["naive", "perfect"],
                   help="score a built-in reference instead of a file")
    s.add_argument("-v", "--verbose", action="store_true")
    s.set_defaults(func=cmd_score)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "score" and not args.submission and not args.baseline:
        print("give a submission file, or --baseline naive|perfect", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
