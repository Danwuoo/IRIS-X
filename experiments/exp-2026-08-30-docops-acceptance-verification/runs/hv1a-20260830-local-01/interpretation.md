# H-V1a Interpretation: `hv1a-20260830-local-01`

- **Status:** reviewed valid result
- **Support status:** `Supported — task-local`
- **Code revision executed:** `5b69a0a8f8f8d843ae7e564ed349abd6bd6c5596`
- **Frozen challenge SHA-256:** `398342dee4aee9651e6c2350f8abdde34cff57cc2ae0e19f0110a33f7321d859`
- **Raw records:** `raw/terminal-records.jsonl`
- **Derived aggregate:** `results.json`

## Directly Observed Result

The run completed 360/360 valid paired-arm terminal records: 12 tasks, five
frozen output variants, two acceptance arms, and three repetitions. All 180
records per arm used complete identical input path/hash evidence and claimed
success. The treatment did not change producer output or actual-outcome
adjudication.

| Arm | True accept | True reject | False accept | False reject | Accepted claimed success | Rejected claimed success |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `claim-only-v0` | 72 | 0 | 108 | 0 | 180 | 0 |
| `independent-verify-v0` | 72 | 108 | 0 | 0 | 72 | 108 |

The control's false accepts were all 36 omission, 36 fabrication, and 36
corruption records. The treatment rejected all 108 of those records. Thus the
false-accept count fell from 108/180 total decisions (and 108/108 actual-invalid
cases) to 0/180 total decisions (0/108 actual-invalid cases).

The treatment accepted all 36 canonical-valid and all 36
semantic-equivalent-valid records. No valid semantic variant became a false
reject. Across paired arms the actual outcomes and every frozen comparison
field were identical; the 180 unique case/repetition outcomes were 72 success,
81 partial, and 27 failure. All arm/case decisions repeated identically across
the three repetitions.

The verifier had zero error/invalid records. Its function received only the
fixture path object, expected-relative path, and exact producer-output JSON
text. Targeted tests confirmed that the signature excludes actual outcome and
challenge metadata and that the verifier does not call the actual-outcome
adjudicator.

These observations satisfy every predeclared H-V1a support condition.

## Cost and Preservation Observation

The treatment recorded 101.2129 ms verification wall time and 140.625 ms
process CPU time across 180 records. Producer-output bytes were fixed at 25,887
per arm. Decision-artifact bytes were 23,220 for claim-only and 23,364 for
treatment; terminal-record bytes excluding their self-size fields were 358,936
and 359,343 respectively. The combined raw terminal artifact was 772,639 bytes.

These short single-host timings are descriptive. Verifier overhead in other
task families or environments is `Not established`. Development, maintenance,
electricity, hardware, fixture-authoring, and external failure-impact costs
remain `Unknown`; model/token/API cost was not applicable and no paid use
occurred.

The registered VANTA source tree assertion passed, the registry hash remained
unchanged, and `sources/` plus `references/papers/` remained clean.

## Evidence Boundary

The observed 0/108 treatment false accepts and 0/72 false rejects are an exact
finite-sample result for deterministic oracle comparison on constructed
development challenges. They do not establish perfect verifier reliability, a
universal verifier, model judging reliability, held-out generalization,
production evidence sufficiency, or an architectural invariant.

`H-V1b — evidence/provenance binding: deferred / not evaluated in this batch`

The supported narrow constraint is: for these fixed oracle-backed Document Ops
outputs, acceptance of claimed success should be gated by an independently
computed semantic verification decision rather than the claim alone.
