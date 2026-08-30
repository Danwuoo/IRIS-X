# H-V1b Interpretation: `hv1b-20260830-local-01`

- **Status:** reviewed valid result
- **Support status:** `Supported — task-local`
- **Code revision executed:** `6ced50ddd38b9251af507519f515030fcb42905a`
- **Frozen challenge SHA-256:** `c5e2aa38d07d05aca1d25dc244780a0cb868d74f67ce1c34f662ae54a3e26672`
- **Raw records:** `raw/terminal-records.jsonl`
- **Derived aggregate:** `results.json`

## Directly Observed Result

The run completed 576/576 valid paired-arm terminal records: 12 tasks, eight
frozen evidence variants, two arms, and three repetitions. Every producer
output was semantically equal to its fixture oracle, every system claim was
`success`, and all 576 independently adjudicated actual outcomes were
`success`. The semantic verifier accepted every record in both arms.

| Arm | Actual success | Verified-success eligible | Unverified success | False verified acceptance | False rejection of complete evidence |
| --- | ---: | ---: | ---: | ---: | ---: |
| `semantic-only-v0` | 288 | 288 | 0 | 252 | 0 |
| `evidence-bound-v0` | 288 | 36 | 252 | 0 | 0 |

The complete-correct cases were all eligible in both arms. Treatment accepted all 36
complete-correct records as `sufficient`. It denied verified-success eligibility
to all 252 predefined invalid/insufficient records: all 36 missing-entry records
were `insufficient`, and the remaining 216 records were `invalid_binding`.
Those 252 actual successes remained `unverified_success`; none was relabeled as
task failure.

The treatment recomputed path existence, fixture containment, SHA-256, byte
size, declared-input identity, role, and duplicate consistency from the actual
files. Its interface received only `fixture`, `required_inputs`, and
`supplied_evidence`; no case ID, variant ID, challenge metadata, expected
validity, actual outcome, or semantic decision entered the interface. A targeted
temporary-fixture test changed bytes under an unchanged evidence envelope and
observed the decision change from `sufficient` to `invalid_binding`, directly
checking that the implementation used real bytes rather than case lookup.

All paired fixed fields were identical across arms and all arm/case decisions
agreed across three repetitions. These observations satisfy every predeclared
H-V1b support condition.

## Cost and Preservation Observation

Treatment evidence verification recorded 230.65 ms wall and 187.5 ms process
CPU across 288 records. Supplied evidence occupied 60,318 canonical payload
bytes per arm. Decision artifacts occupied 50,112 bytes for semantic-only and
55,650 bytes for treatment. Terminal records excluding self-size fields totaled
560,817 and 653,222 bytes respectively; the combined raw terminal artifact was
1,306,208 bytes.

These same-host timings are descriptive only. Development, maintenance,
electricity, hardware, fixture-authoring, and external failure-impact costs
remain `Unknown`; model/token/API cost was not applicable and no paid use
occurred.

The registered VANTA source snapshot assertion passed, the registry hash stayed
unchanged, and `sources/` plus `references/papers/` remained clean.

## Evidence Boundary

This is finite-sample, task-local support that the tested local path/hash
contract discriminates the frozen evidence-integrity challenges while
preserving outcome/evidence separation. It does not establish causal provenance
beyond registered local bytes, universal evidence sufficiency, trustworthy
model citations, real-world lineage, held-out behavior, parent H-V1, or an
architecture requirement.
