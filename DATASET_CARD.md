---
license: cc-by-4.0
task_categories:
  - text-classification
  - tabular-classification
tags:
  - security
  - post-quantum
  - cryptography
  - benchmark
  - protocol-verification
pretty_name: "PQC-MFB: Post-Quantum Migration Failure Benchmark"
size_categories:
  - n<1K
configs:
  - config_name: default
    data_files: src/pqc_mfb/data/pqc_mfb.jsonl
---

# Dataset Card — PQC-MFB

## Summary

322 executed cases describing how post-quantum migrations of authenticated key-exchange
protocols fail. Each case pairs an unrepaired ("naive") design with a failure family and
the protocol invariant that breaks. 312 of the 322 are failures; the remaining 10 pass
even unrepaired and serve as regression controls.

- **Cases:** 322 (312 failures, 10 controls)
- **Failure families:** 39
- **Unrepaired designs:** 10
- **Format:** JSON Lines, one case per line
- **Licence:** CC-BY-4.0 (data) / Apache-2.0 (code)

## Fields

| Field | Type | Description |
|---|---|---|
| `case_id` | string | `<design>::<family>`, unique |
| `design` | string | which unrepaired design was executed |
| `family` | string | failure family (one of 39) |
| `invariant` | string | the protocol invariant under test |
| `is_failure` | bool | whether the unrepaired design fails this case |
| `naive_detail` | string | what the unrepaired design actually did |
| `naive_held` | bool | whether the invariant held unrepaired |
| `prior_art_analogue` | string | a published failure of similar shape, where one exists |

### Deliberately withheld

`repair_mechanism`, `repaired_detail` and `repaired_held` are **removed** from the public
release. Together they form the failure-to-mechanism incidence matrix, which is the input
to a minimum-cover computation over the repair set and belongs to the closed core.

Scoring does not need them: the benchmark asks whether your implementation holds the
invariant, not which mechanism you used. The projection step is
`src/pqc_mfb/build_dataset.py`, and a test asserts the withheld fields never appear in
the published file.

## How it was produced

Cases were executed against a modeled protocol state machine — not captured from network
traffic or from shipping products. For each (design, family) pair the harness runs the
adversary for that family against the unrepaired design and records whether the named
invariant held.

The public file is derived from the internal manifest by a single reproducible
projection; regenerate it with:

```bash
python -m pqc_mfb.build_dataset <internal_manifest.json> src/pqc_mfb/data/pqc_mfb.jsonl
```

## Intended use

- Scoring a post-quantum AKE implementation for migration-failure coverage.
- Teaching: a concrete catalogue of what breaks when key material outgrows a frame.
- Research on protocol state-machine failure taxonomies.

## Out of scope

- **Not a vulnerability disclosure.** No case is an assertion about a named product.
- **Not a security certification.** A perfect score means 312 modeled cases handled.
- **Not byte-exact CVE reproduction.** `prior_art_analogue` names a failure of similar
  *shape*. It is a pointer for the reader, not a claim of equivalence.
- **Not a fuzzing corpus.** There are no packet captures or binary inputs here.

## Limitations and biases

- Cases derive from **one** modeled state machine, so they inherit its modelling choices.
  A failure mode that model cannot express is not represented.
- Coverage across families is uneven — some families have one case, others many. Overall
  coverage therefore weights families unequally, which is why the scorer also reports
  per-family results and names zero-coverage families explicitly.
- The 10 unrepaired designs are constructed baselines, not third-party implementations.
- Wireless-derived. Families transfer to other transports, but the designs are wireless.

## Citation

```bibtex
@misc{pqcmfb2026,
  title  = {PQC-MFB: A Post-Quantum Migration Failure Benchmark},
  author = {{PQC Migration Safety Lab}},
  year   = {2026},
  note   = {322 cases, 39 failure families, 10 unrepaired designs}
}
```

## Contact

Issues and submissions via the repository. For the closed core, open a GitHub Discussion or an issue.
