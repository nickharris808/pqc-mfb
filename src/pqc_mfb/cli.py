"""pqc-mfb command line: inspect the benchmark and score a submission."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from .score import load_cases, naive_baseline, perfect_submission, score_submission

#: Exit codes. INCOMPLETE is deliberately distinct from FAIL: a CI gate should be able
#: to tell "you broke something" apart from "you did not show your work", and neither
#: may be mistaken for success.
EXIT_FOR_VERDICT = {"PASS": 0, "FAIL": 1, "INCOMPLETE": 3}


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


def cmd_submit(args) -> int:
    """Emit a complete submission template, every case id pre-filled.

    Hand-writing 322 case ids is the biggest barrier to a first score, and a
    mistyped id is invisible -- it scores as unanswered rather than erroring.

    The default fill is the unrepaired baseline, NOT all-false. Filling every
    case false marks the 10 control cases as broken, so the scaffold would score
    FAIL with 10 regressions before its owner had changed anything -- a scaffold
    that starts red teaches nothing. Seeding from the baseline starts at the
    documented floor: 0% coverage, 0 regressions, PASS.
    """
    cases = load_cases(args.data)
    if args.fill == "baseline":
        template = {c.case_id: bool(c.naive_held) for c in cases}
        note = ("seeded from the unrepaired baseline: 0% coverage, no regressions. "
                "Flip a case to true when your implementation holds that invariant.")
    elif args.fill == "true":
        template = {c.case_id: True for c in cases}
        note = "every case true -- this is the reference ceiling, not a result."
    else:
        template = {c.case_id: False for c in cases}
        note = ("every case false -- note this marks the 10 control cases as broken, "
                "so it scores FAIL with 10 regressions.")

    body = json.dumps(template, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(body + "\n", encoding="utf-8")
        print(f"wrote {len(template)} case ids to {args.output}")
        print(f"  {note}")
        print(f"  then: pqc-mfb score {args.output}")
    else:
        print(body)
    return 0


def cmd_explain(args) -> int:
    """Describe one failure family: what breaks, where, and what the naive design did."""
    cases = load_cases(args.data)
    known = sorted({c.family for c in cases})
    if args.family not in known:
        near = [f for f in known if args.family in f or f.startswith(args.family[:4])]
        print(f"unknown family {args.family!r}", file=sys.stderr)
        if near:
            print(f"  did you mean: {', '.join(near[:5])}", file=sys.stderr)
        else:
            print(f"  see `pqc-mfb info` for all {len(known)} families", file=sys.stderr)
        return 2

    hits = [c for c in cases if c.family == args.family]
    if args.json:
        print(json.dumps({
            "family": args.family,
            "n_cases": len(hits),
            "n_failures": sum(1 for c in hits if c.is_failure),
            "invariants": sorted({c.invariant for c in hits}),
            "designs": sorted({c.design for c in hits}),
            "prior_art_analogue": next(
                (c.prior_art_analogue for c in hits if c.prior_art_analogue), None),
            "cases": [c.__dict__ for c in hits],
        }, indent=2))
        return 0

    failures = sum(1 for c in hits if c.is_failure)
    print(f"{args.family}")
    print(f"  cases        {len(hits)}  ({failures} where the unrepaired baseline fails)")
    print(f"  invariants   {', '.join(sorted({c.invariant for c in hits}))}")
    print(f"  designs      {len({c.design for c in hits})}")
    analogue = next((c.prior_art_analogue for c in hits if c.prior_art_analogue), None)
    if analogue:
        print(f"  analogue     {analogue}  (similar in shape; not a reproduction)")
    print("\n  what the unrepaired designs did:")
    for c in hits:
        if c.naive_detail:
            print(f"    [{'FAIL' if c.is_failure else 'ok  '}] {c.design}: {c.naive_detail}")
    print("\n  The repair for this family is not part of this benchmark. See the "
          "README\n  section \"What is in the data, and what is not\".")
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

    if getattr(args, "format", None) in ("sarif", "junit"):
        from .report import write_report
        text = write_report(sc, args.format, args.output,
                            submission_path=args.submission or "pqc-mfb-submission.json")
        if args.output:
            print(f"wrote {args.format} report to {args.output}")
        else:
            print(text)
        return EXIT_FOR_VERDICT[sc.verdict]

    if args.json:
        print(json.dumps(sc.to_dict(), indent=2))
        return EXIT_FOR_VERDICT[sc.verdict]

    print(f"submission: {label}")
    print(f"  coverage      {sc.n_closed}/{sc.n_failures}  ({100*sc.coverage:.1f}%)")
    print(f"  regressions   {sc.n_regressions}" +
          ("   <-- HARD FAIL" if sc.n_regressions else ""))
    print(f"  unanswered    {sc.n_unanswered}" +
          ("   <-- no pass can be claimed" if sc.n_unanswered else ""))
    if sc.unknown_ids:
        shown = ", ".join(sc.unknown_ids[:3])
        more = f" (+{len(sc.unknown_ids) - 3} more)" if len(sc.unknown_ids) > 3 else ""
        print(f"\n  WARNING: {len(sc.unknown_ids)} submitted id(s) match no case in "
              f"this benchmark and were ignored:\n    {shown}{more}")
        print("  Check you built the submission against this version "
              "(`pqc-mfb info`).")
    if sc.zero_families:
        print(f"\n  zero-coverage families ({len(sc.zero_families)}):")
        for f in sc.zero_families:
            print(f"    - {f}")
    if args.verbose:
        print(f"\n  {'family':<38} closed")
        print("  " + "-" * 50)
        for fam, st in sc.by_family.items():
            print(f"  {fam:<38} {st['closed']:>3}/{st['total']:<3} ({st['pct']:>5.1f}%)")
    print(f"\n  result: {sc.verdict}")
    print(f"  reason: {sc.verdict_reason}")
    return EXIT_FOR_VERDICT[sc.verdict]


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

    t = sub.add_parser("submit", help="write a submission template with every case id")
    t.add_argument("-o", "--output", help="file to write (default: stdout)")
    t.add_argument("--fill", choices=["baseline", "true", "false"], default="baseline",
                   help="starting values (default: baseline -- 0%% coverage, "
                        "0 regressions)")
    t.set_defaults(func=cmd_submit)

    e = sub.add_parser("explain", help="describe one failure family")
    e.add_argument("family")
    e.set_defaults(func=cmd_explain)

    s = sub.add_parser("score", help="score a submission")
    s.add_argument("submission", nargs="?", help="JSON file of {case_id: bool}")
    s.add_argument("--baseline", choices=["naive", "perfect"],
                   help="score a built-in reference instead of a file")
    s.add_argument("-v", "--verbose", action="store_true")
    s.add_argument("--format", choices=["text", "sarif", "junit"], default="text",
                   help="sarif for GitHub code scanning, junit for CI test panes")
    s.add_argument("-o", "--output", help="write the report to a file")
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
