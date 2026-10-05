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

# PQC-MFB — Post-Quantum Migration Failure Benchmark

[![license](https://img.shields.io/badge/code-Apache--2.0-blue.svg)](LICENSE)
[![data](https://img.shields.io/badge/data-CC--BY--4.0-blue.svg)](DATASET_CARD.md)
[![cases](https://img.shields.io/badge/cases-322-brightgreen.svg)](src/pqc_mfb/data/pqc_mfb.jsonl)
[![families](https://img.shields.io/badge/failure%20families-39-brightgreen.svg)](#the-39-families)
[![ci](https://github.com/nickharris808/pqc-mfb/actions/workflows/ci.yml/badge.svg)](https://github.com/nickharris808/pqc-mfb/actions/workflows/ci.yml)

**Will your post-quantum migration break? Here are 322 ways it has already broken.**

322 cases across 39 failure families and 10 unrepaired designs. Score your implementation
in one command. The naive baseline closes **0 of 312**. Post your number.

**📖 Full documentation, tutorial and conceptual guide: <https://nickharris808.github.io/pqc-toolkit/>**

---

## Why this exists

Everyone migrating to post-quantum cryptography is writing the same handful of bugs, and
most of them are not cryptographic — they are state-machine bugs that the size change
*reintroduces*. A downgrade that isn't bound into the key. A key that reinstalls on
retransmission. A fragment sequence that reassembles across two sessions. A roam that
silently extends an ephemeral's lifetime forever.

These have published analogues — KRACK, Dragonblood, FragAttacks — and the post-quantum
size regime reopens them on the ordinary path rather than in exotic configurations.

There was no shared way to ask "does my implementation handle these?" This is one.

## Install

```bash
pip install git+https://github.com/nickharris808/pqc-mfb
```

Zero runtime dependencies. Not on PyPI yet, so `pip install pqc-mfb` does not
work today — the command above does.

## 30-second quickstart

```bash
pqc-mfb info                          # what's in the benchmark
pqc-mfb score --baseline naive        # the floor: 0/312
pqc-mfb score my_results.json -v      # your implementation
```

## Worked example — actual output

```
$ pqc-mfb info
PQC-MFB — Post-Quantum Migration Failure Benchmark
  cases      322
  failures   312   (cases where the naive baseline breaks)
  families   39
  designs    10

family                                 cases
----------------------------------------------
  algorithm_substitution                 10
  ap_flood                               10
...

$ pqc-mfb score --baseline naive
submission: naive baseline
  coverage      0/312  (0.0%)
  regressions   0
  unanswered    0

  zero-coverage families (38):
    - algorithm_substitution
    - ap_flood
...

  result: PASS
  reason: all 312 failure cases answered, no regressions
```

38, not 39: `fragment_truncate` is the one family the unrepaired baseline already
holds, so it contributes controls rather than failures and cannot be *zero*-covered.

A submission is a JSON object mapping case IDs to whether **your** implementation held
the invariant:

```json
{
  "naive_hybrid_akm::algorithm_substitution": true,
  "naive_pqc_sae::offline_dictionary": false
}
```

## Scoring

**Coverage** = closed / 312, over the cases where the unrepaired baseline fails.

**Regressions are a hard fail.** Ten cases pass even unrepaired. If you fail one of
those you have broken something that already worked, and you do not pass regardless of
coverage. A submission can score 100% coverage and still `FAIL`.

**Silence is not credit, and it is not a pass.** A case you omit is *unanswered*, and
any unanswered case makes the verdict `INCOMPLETE`. There are three verdicts:

| Verdict | Meaning | Exit |
|---|---|--:|
| `PASS` | every failure case answered, nothing regressed | 0 |
| `FAIL` | at least one regression — a hard fail whatever the coverage | 1 |
| `INCOMPLETE` | at least one case unanswered, so no pass is claimed | 3 |

`INCOMPLETE` exists because the earlier two-verdict scheme was wrong: `passed` was
defined as "no regressions", so an empty submission `{}` scored **PASS** at 0%
coverage with 312 unanswered cases. Answering nothing is now `INCOMPLETE`, and the
scorer also names any submitted case id that matches no case in the benchmark rather
than silently ignoring it.

**Zero-families are reported by name.** Overall coverage hides shape. Closing 90% while
missing every roaming case is a different result from closing 90% evenly, and the
scorer says which you did.

| Reference | Coverage | Regressions | Unanswered | Verdict |
|---|--:|--:|--:|---|
| Naive baseline (floor) | 0/312 — 0.0% | 0 | 0 | PASS |
| Reference ceiling | 312/312 — 100.0% | 0 | 0 | PASS |
| Empty submission `{}` | 0/312 — 0.0% | 0 | 312 | INCOMPLETE |

The naive baseline passes at 0% coverage because `PASS` is the **regression gate**,
not the score — it answers every case honestly and breaks nothing. Coverage is the
number you report; use `--min-coverage` in
[`pqc-guard-action`](https://github.com/nickharris808/pqc-guard-action) to gate on it.

Both are computed, not asserted: `baselines/` is regenerated by the test suite and a
test fails if the committed numbers drift.

## The 39 families

Downgrade and negotiation — `algorithm_substitution`, `capability_spoof`,
`forced_fallback`, `suite_rollback`, `mtu_downgrade`, `fec_downgrade`,
`policy_substitution`, `eap_method_downgrade`, `eap_pqc_strip`, `combiner_downgrade`,
`recovery_downgrade`, `sig_profile_substitution`.

Installation and replay — `krack_retransmission`, `resumption_replay`,
`stale_credential_replay`, `puzzle_replay`, `roam_ticket_replay`, `group_key_injection`.

Fragmentation — `fragment_splice`, `fragment_swap`, `compression_bomb`.

Resource exhaustion — `ap_flood`, `flood_starvation`.

Roaming and multi-link — `ft_roam_fs_erosion`, `roam_key_reuse`, `mlo_key_crosslink`,
`mlo_misbind`.

Password and identity — `offline_dictionary`, `online_guess`, `sae_role_confusion`,
`kem_impersonation_no_confirm`.

Cryptographic hygiene — `skipped_reencryption_check`, `single_family_break`,
`owe_quantum_recoverable`, `beacon_forgery`, `beacon_batch_replay`,
`cross_protocol_confusion`, `length_fingerprint`.

## Use it as a library

```python
from pqc_mfb import load_cases, score_submission

cases = load_cases()
sub = {c.case_id: my_impl_holds(c.invariant, c.design) for c in cases}
sc = score_submission(sub, cases)

print(sc.coverage, sc.zero_families, sc.verdict)
```

## What is in the data, and what is not

Each case carries the failure and its context: `case_id`, `design`, `family`,
`invariant`, `is_failure`, `naive_detail`, `naive_held`, `prior_art_analogue`.

**Deliberately withheld:** `repair_mechanism` and `repaired_detail`. Those form the
failure-to-mechanism incidence matrix, which is the input to a minimum-cover computation
and belongs to the closed core. You do not need them to score an implementation — the
benchmark asks whether you hold the invariant, not how. See
[`DATASET_CARD.md`](DATASET_CARD.md) and `src/pqc_mfb/build_dataset.py`, which is the
reproducible projection step and asserts the withheld fields never reach the public file.

## Scope

Cases are executed against a **modeled** state machine, not captured from shipping
products. `prior_art_analogue` names a published failure of similar *shape*; it does not
assert the case reproduces that CVE byte-for-byte, and this is **not** a vulnerability
disclosure against any vendor. A perfect score means you handled 312 modeled cases — a
useful signal, not a security certification.

## Tests

```bash
pip install -e ".[dev]" && pytest       # 117 passed
```

## Where this comes from

Extracted from a research lab on post-quantum authentication for constrained and
wireless devices. Companion tools: [`pqc-sizes`](https://github.com/nickharris808/pqc-sizes) (why fragmentation is
now mandatory), [`pqc-dos-embedded`](https://github.com/nickharris808/pqc-dos-embedded) (one failure family on real
hardware), [`farkas-check`](https://github.com/nickharris808/farkas-check) (on-device bound verification).

**The benchmark tells you which families you fail. It does not tell you how to close
them.** That is what the closed core does. Patent claims have been drafted for relevant subject matter; filing status available on request. For commercial use of the full envelope, open a
[GitHub Discussion](https://github.com/nickharris808) or an issue on this repository.

## CLI reference

| Command | What it does | Exit |
|---|---|---|
| `pqc-mfb info` | Case, failure, family and design counts | 0 |
| `pqc-mfb cases [--family F] [--design D] [--failures-only]` | List cases | 0 |
| `pqc-mfb explain FAMILY` | What breaks in one family, and what each naive design did | 0 / 2 |
| `pqc-mfb submit [-o FILE] [--fill baseline\|true\|false]` | Write a complete submission template | 0 |
| `pqc-mfb diff BEFORE AFTER` | What this release closed, and what it broke | 0 / **1** |
| `pqc-mfb score FILE` | Score a submission | 0 / **1** / **3** |
| `pqc-mfb score FILE --format sarif\|junit` | Score, as a CI-native report | 0 / **1** / **3** |
| `pqc-mfb score --baseline naive\|perfect` | Score a built-in reference | 0 |

`--json` is global: `pqc-mfb --json score results.json`.

**Start here:** `pqc-mfb submit -o results.json` writes all 322 case ids seeded
from the unrepaired baseline, so it scores cleanly before you edit it. Flip a
case to `true` when your implementation holds that invariant.

### Tracking a release

Coverage alone cannot tell you whether a release helped: two runs at 78% can
differ in every case. `diff` answers the question directly.

```
$ pqc-mfb diff examples/baseline.json examples/after-a-sprint.json
examples/baseline.json -> examples/after-a-sprint.json
  coverage      0/312 -> 5/312  (+5)
  verdict       PASS -> FAIL

  newly closed (5):
    + naive_hybrid_akm::algorithm_substitution   [algorithm_substitution]
    ...

  NEW CONTROL REGRESSIONS (1) -- cases the unrepaired baseline already held:
    ! naive_hybrid_akm::fragment_truncate   [fragment_truncate]
```

It exits **1** if anything regressed, so it gates a release as-is. Cases you
answered before and omitted now are reported as *newly unanswered* rather than
silently vanishing.

### CI-native reports

`--format sarif` puts zero-coverage families in the GitHub Security tab;
`--format junit` puts per-family results in any CI's test pane. Both are emitted
from the same `Score` the text output uses, so they cannot disagree with it.

Neither format can natively express "I could not tell", so an `INCOMPLETE`
submission is reported as a **failure** in both — never as a pass.

```bash
pqc-mfb score results.json --format sarif -o pqc-mfb.sarif
pqc-mfb score results.json --format junit -o pqc-mfb.xml
```

## Troubleshooting

**`INCOMPLETE` (exit 3).** You left cases unanswered. Silence is not credit, so
no pass is claimed. `pqc-mfb submit` writes every id for you.

**`FAIL` with high coverage.** You regressed a control — a case the unrepaired
baseline already handled. That is a hard fail regardless of coverage, and the
scorer names the count. Regressions outrank incompleteness.

**`WARNING: N submitted id(s) match no case`.** Your submission targets a
different benchmark version, or an id is mistyped. Regenerate with
`pqc-mfb submit`. Unknown ids are ignored in scoring, so without this warning a
typo would look identical to an honest zero.

**The naive baseline scores `PASS`.** Intended. `PASS` is the regression gate,
not the score: the baseline answers every case honestly and breaks nothing. Its
coverage is 0%. Gate on coverage with `--min-coverage` in
[`pqc-guard-action`](https://github.com/nickharris808/pqc-guard-action).

**`zero-coverage families (38)` but you advertise 39.** One family
(`fragment_truncate`) is held even unrepaired, so it contributes controls rather
than failures and can never be zero-covered.

## Honest scope

**What this proves.** That your implementation held, or did not hold, each named
invariant across 322 cases executed against a modelled protocol state machine.

**What it does NOT prove.**

- **Not a security certification.** 312/312 means you handled 312 *modelled*
  cases. It is a signal, not an assurance.
- **Not a vulnerability disclosure.** `prior_art_analogue` names a published
  failure of similar *shape*. It is not a claim that the case reproduces that
  CVE, and it asserts nothing about any vendor's product.
- **Not exhaustive.** The 39 families are what this effort modelled. A failure
  mode the model cannot express is absent, and absence here means nothing.
- **Not derived from traffic.** No packet captures, no shipping firmware. The 10
  unrepaired designs are constructed baselines.
- **Not a repair.** The benchmark tells you which families you fail, never how to
  close them.

**Verdicts.** `PASS` (0) · `FAIL` (1, a regression) · `INCOMPLETE` (3, something
unanswered). `PASS` is the regression gate, not the score — the unrepaired
baseline passes at 0% coverage. Coverage is the number you report.

---

## The PQC migration toolkit

Eleven free tools for teams moving authenticated key exchange to post-quantum. They **find and measure**; they do not repair.

| Tool | What it does | Where |
|---|---|---|
| [pqc-sizes](https://github.com/nickharris808/pqc-sizes) | Sizes, fragment counts, and the two-sided reassembly window | source |
| [pqc-sizes-js](https://github.com/nickharris808/pqc-sizes-js) | The same arithmetic for Node and the browser | source |
| [pqc-guard-action](https://github.com/nickharris808/pqc-guard-action) | Fail the build when the window is empty | GitHub Action |
| [pqc-dos-embedded](https://github.com/nickharris808/pqc-dos-embedded) | 169 lines of C: the failure on a real 64 KB device | source |
| [farkas-check](https://github.com/nickharris808/farkas-check) | Re-verify the bound on-device, no SMT solver | source |
| [pqc-bounds-lean](https://github.com/nickharris808/pqc-bounds-lean) | The same bound in Lean 4 — 0 `sorry`, 0 imports | source |
| [pqc-dos-gate-rtl](https://github.com/nickharris808/pqc-dos-gate-rtl) | The gate in synthesizable RTL, 5 Yosys proofs | source |
| [pqc-migration-mcp](https://github.com/nickharris808/pqc-migration-mcp) | Six MCP tools for AI agents | source |
| **pqc-mfb** ← you are here | 322 cases · 39 failure families · scorer | source |
| [pqc-mfb (data)](https://huggingface.co/datasets/nickh007/pqc-mfb) | The benchmark as a dataset | HF |
| [pqc-formal-corpus](https://huggingface.co/datasets/nickh007/pqc-formal-corpus) | 122 named formal results, 6 provers | HF |
| [pqc-explorer](https://huggingface.co/spaces/nickh007/pqc-explorer) | Try it in your browser, no install | HF Space |

**New here?** The [end-to-end tutorial](https://github.com/nickharris808/pqc-sizes/blob/main/TUTORIAL.md) walks one realistic migration through all of them in about ten minutes: sizes -> window -> CI gate -> benchmark.

**In a hurry?** [`pqc-sizes`](https://github.com/nickharris808/pqc-sizes) tells you in five seconds whether your credential fragments and whether a safe cap exists. [`pqc-explorer`](https://huggingface.co/spaces/nickh007/pqc-explorer) does the same in a browser, with no install.

### The closed core

Closing the 39 failure families — downgrade binding, retransmission-safe installation, fragmentation transcripts, roaming forward secrecy, multi-link key separation, admission control, group-key binding — is a separate proprietary codebase. Patent claims have been drafted for relevant subject matter; filing status available on request.

That split is measured, not asserted: under a replicate noise control only **4 of 32** repair mechanisms are externally distinguishable, so publishing these detectors does not disclose the repairs.

For commercial licensing, open a [GitHub Discussion](https://github.com/nickharris808/pqc-sizes/discussions) or an issue on any of these repos.

## License

Code Apache-2.0 ([LICENSE](LICENSE)). Data CC-BY-4.0 ([LICENSE-DATA](LICENSE-DATA), terms in [DATASET_CARD.md](DATASET_CARD.md)).
See [CONTRIBUTING.md](CONTRIBUTING.md).
