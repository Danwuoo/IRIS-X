# Evaluation State Semantics v1

- **ID:** `evaluation-state-semantics-v1`
- **Status:** exploratory — future-facing evaluation vocabulary
- **Scope:** Separates empirical outcome, evidence, acceptance, eligibility, and execution state for new IRIS-X records. Historical immutable run artifacts are compatibility inputs and are not rewritten.
- **Corpus records:** `src.vanta`, `src.spex`

## Controlling distinction

Future records must carry five independently sourced fields:

1. **Actual outcome** — what happened under the task contract: `success`, `partial`, `failure`, or `unresolved`.
2. **Empirical evidence status** — whether observed evidence supports adjudication: `sufficient`, `insufficient`, `invalid_binding`, `not_assessed`, or `unresolved`.
3. **Acceptance decision** — what a system or verifier decided: `accept`, `reject`, `abstain`, or `not_applicable`.
4. **Verified-success eligibility** — a protocol-derived Boolean or `not_applicable`; it is true only when the protocol's actual-outcome and evidence gates are both satisfied.
5. **Execution/state status** — what terminal execution/state transition occurred. Experiment contracts define their own closed vocabulary, such as `completed`, `rejected`, `failed`, or `invalid`.

No field may be derived merely by copying another. In particular:

> `accept` is not synonymous with `verified_success`.

An accepted failure, an accepted partial result, or an accepted success with invalid evidence binding is not eligible for verified success. Likewise, a rejected but empirically successful outcome remains an actual success and may constitute a false failure.

## Joint empirical interpretation

The joint label is derived only after the separate fields are frozen:

| Actual outcome | Evidence status | Acceptance decision | Verified-success eligible | Joint interpretation |
| --- | --- | --- | --- | --- |
| `success` | `sufficient` | `accept` or `not_applicable` | true | `verified_success` |
| `success` | `insufficient`, `invalid_binding`, or `not_assessed` | any | false | `unverified_success` |
| `success` | `sufficient` | `reject` | false | `false_failure` |
| `partial` or `failure` | any | `accept` | false | `false_success` |
| `failure` | `sufficient` | `reject` or `not_applicable` | false | `correctly_recognized_failure` |
| `partial` | `sufficient` | `reject`, `abstain`, or `not_applicable` | false | `correctly_recognized_partial` |
| any unresolved combination | any | any | false or unresolved | `unresolved` |

This table is a default future-facing interpretation. A measured experiment may tighten it, but it must freeze the derivation before observation and may not define evidence truth from acceptance.

## Eligibility rule

Unless a frozen experiment contract states a stricter rule, verified-success eligibility requires all of the following:

- actual outcome is empirically adjudicated `success`;
- empirical evidence status is `sufficient`;
- evidence is bound to the evaluated task/input/output/state identity;
- terminal execution/state status is valid under the experiment contract;
- no invalid-run condition applies; and
- acceptance is not `reject` or `abstain` when acceptance is applicable.

Eligibility is a protocol judgment, not proof that a source oracle is scientifically complete or that the result generalizes.

## Compatibility boundary

Completed Phase 3 and earlier Phase 4 runs are immutable. Some historical records use `verified_success`, `system_claim`, or verifier `decision` fields in narrower experiment-local ways. Readers must interpret those fields under their original frozen contracts. New analyses may map old values externally, but must not rewrite historical raw records or imply that historical `accept` alone established empirical verified success.

New experiment schemas in this batch use explicit fields for actual outcome, empirical evidence status, acceptance decision, verified-success eligibility, and terminal execution/state status.

## Evidence basis and uncertainty

- **Directly observed:** `research/task-contract-docops-readonly-12.md` already separates actual outcome, evidence status, and execution-path attributes.
- **Directly observed:** H-V1b raw/result records distinguish semantic acceptance from evidence binding and retain actual successes as `unverified_success` when evidence is invalid or insufficient.
- **Source-stated:** VANTA exposes verifier decisions and execution states as separate records, but its runtime vocabulary is not adopted as IRIS-X architecture authority.
- **Not established:** that this value vocabulary is sufficient for every future task family.
- **Unclear:** whether future partial-evidence states need a richer lattice.
- **Not evaluated:** human adjudication disagreement and stochastic verifier calibration.
