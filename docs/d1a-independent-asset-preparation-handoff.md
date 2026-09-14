# D1a Independent Asset Preparation Handoff

## Terminal verdict

`ready_for_independent_custodians`

The neutral D1a qualification and intake substrate is implementation-ready.
Its deterministic meta-fixtures demonstrate instrument behavior and coherent
R1-R5 win regions only. D1a remains empirically unqualified because no real
independently authored custodian bundle was created or admitted in this
coordinating session.

## Authority and repository state

- Controlling contract:
  `docs/plans/TEMP_D1A_INDEPENDENT_ASSET_PREPARATION_AND_QUALIFICATION_SUBSTRATE.md`.
- Required baseline: `b62ec56b029f0478911e9454f9a3cde7d054cd54`.
- Starting `HEAD`: `1cda0334114420fc83a9f1774a9b2048d9d1b7c2`.
- Starting `origin/main`: `1cda0334114420fc83a9f1774a9b2048d9d1b7c2`.
- Starting `origin/main...main` divergence: `0 0`.
- Starting worktree: clean.
- Baseline ancestry: verified.
- Post-baseline drift: only the owner-added controlling D1a plan. The F1
  charter, D1 specification, and XHigh handoff were unchanged from the
  controlling baseline; no unexplained scientific-authority drift existed.
- Terminal commit: the local commit containing this handoff. Its SHA is
  reported in the session final response because a commit cannot contain its
  own identity.
- Push: not performed.

The controlling plan, root/research/experiments/source instructions, F1
charter, D1 specification, XHigh handoff, durable post-synthesis state,
foundational synthesis, prior F1/D1 plan, cited Phase 4/6 direct artifacts, and
the Phase 5 execution qualification conventions were inspected before
implementation.

## Package result

`experiments/d1a-warrant-discrimination-v0/` now provides:

- frozen construct, role, provenance, perturbation, comparator, qualification,
  negative-control, interpretation, and outcome-vector contracts;
- strict Draft 2020-12 schemas for task/oracle, authority-policy,
  semantic-verifier, calibration, analysis, and custodian-attestation records;
- role-specific neutral custodian packets;
- SHA-256 seal validation, safe path resolution, declared-dependency checks,
  role-specific prohibited-information scans, and separate independence states;
- field-audited P0-P3 implementations with no fake P0 fallback;
- fail-closed assembly states, including incomplete assets, unavailable
  calibration, unsupported independence, and rejection;
- 17 synthetic meta-episodes across six meta task families, kept separate from
  future real inputs; and
- full vector reporting with policy/task-family denominators, factorized
  resources, explicit deterministic reproducibility, preserved unknowns, and no
  primary scalar.

The assembly path reaches `ready_for_d1a_qualification` only in a deterministic
test using temporary fictional bundles that satisfy every gate. No such bundle
exists in the repository, and the test is not scientific evidence.

## Independent inputs still missing

All independence-sensitive inputs remain intentionally absent:

1. at least two independently authored task/oracle families with sealed task,
   instance, outcome, and post-state rules;
2. a legitimate ex ante authority-policy bundle in which correctness and
   authorization can diverge;
3. an independently authored semantic verifier with disjoint development
   material and preserved false-accept, false-reject, disagreement, error, and
   unknown cases;
4. a disjoint exact-producer-configuration calibration bundle, or an explicit
   fair `P0_unavailable` determination; and
5. a separately frozen analysis bundle depending on the exact sealed component
   identities and created without prior held-out-result access.

No task/oracle, authority, verifier, calibration, or analysis independence is
claimed from coordinator-authored schemas, packets, code, or meta-fixtures.

## Reusable-material audit

The detailed audit is frozen in
`experiments/d1a-warrant-discrimination-v0/definition/reusable-material-audit.json`.

| Exact path | Original purpose / D1 boundary | Disposition |
|---|---|---|
| `experiments/exp-2026-08-30-source-snapshot-assertion` | H-M1a identity/digest pattern; jointly authored mismatch expectations | `reuse_pattern_only` |
| `experiments/exp-2026-08-30-docops-acceptance-verification` | H-V1a semantic interface; verifier and outcome share fixture oracle | `reuse_pattern_only` |
| `experiments/exp-2026-08-30-docops-evidence-binding` | H-V1b binding pattern; eligibility and perturbation share construction | `reuse_pattern_only` |
| `experiments/exp-2026-08-30-preexecution-write-interception` | H-I1a reversible action/post-state pattern; not independent for D1 | `reuse_pattern_only` |
| `experiments/phase-6-predicate-authority-repair-v0` | Hash-bound authority and unknown preservation; not an exogenous D1 policy | `reuse_pattern_only` |
| `experiments/substrates/model-execution-qualification-v0` | Identity/resource/terminal conventions; no independent D1 oracle or calibration | `reuse_pattern_only` |
| `experiments/configurations/provider-model-baseline-v0.json` | Provider/model identity only; no score/outcome calibration | `ineligible` |
| `sources/predecessors/eidos` | Authority concepts; external lineage is not D1 independence | `reuse_pattern_only` |
| `sources/predecessors/vanta` | Evidence/verifier/commit concepts; not held-out D1 assets | `reuse_pattern_only` |
| `sources/predecessors/spex` | Measurement/adjudication discipline; R3-compatible, not F1 evidence | `reuse_pattern_only` |

No candidate was promoted to `candidate_asset`; scientific independence and
boundary fit remain `Not established` for reuse as a real D1 input.

## Validation

- `python -m unittest discover -s experiments\d1a-warrant-discrimination-v0\tests -v`:
  **PASS — 36 tests**.
- `python experiments\d1a-warrant-discrimination-v0\scripts\qualify_instrument.py`:
  **PASS — 17 episodes, six meta task families, all R1-R5 and negative-control
  checks true; `d1_empirical_qualification=false`**.
- `python experiments\d1a-warrant-discrimination-v0\scripts\assemble_d1a_bundle.py --meta-qualified`:
  **PASS — `ready_for_independent_custodian_submission`, five roles missing,
  zero fabricated assets**.
- `python tools\repository_check.py`:
  **PASS — 13 sources, seven artifacts, hashes checked**.
- `git diff --check`: **PASS**.
- Final worktree after commit: verified and reported in the session final
  response.

`research/d1-held-out-warrant-generalization-spec.md` was not changed because
implementation exposed no scientific defect requiring revision. No historical
experiment result or imported source was modified.

## Execution accounting

```text
repository provider/model calls: 0
background model launches: 0
model judges: 0
retries: 0
routes: 0
fallbacks: 0
escalations: 0
online optimization: 0
workflow search: 0
D1b producer executions: 0
follow-on model tasks: 0
```

D1b was not created, specified, frozen, launched, or authorized. Phase 7 was
not created. F1-B/C/D/E and novelty were not promoted.

## Exact changed files

```text
docs/d1a-independent-asset-preparation-handoff.md
experiments/d1a-warrant-discrimination-v0/README.md
experiments/d1a-warrant-discrimination-v0/custodian-packets/analysis-custodian.md
experiments/d1a-warrant-discrimination-v0/custodian-packets/authority-policy-custodian.md
experiments/d1a-warrant-discrimination-v0/custodian-packets/calibration-custodian.md
experiments/d1a-warrant-discrimination-v0/custodian-packets/semantic-verifier-custodian.md
experiments/d1a-warrant-discrimination-v0/custodian-packets/task-oracle-custodian.md
experiments/d1a-warrant-discrimination-v0/definition/episode.schema.json
experiments/d1a-warrant-discrimination-v0/definition/experiment-definition.json
experiments/d1a-warrant-discrimination-v0/definition/interpretation-matrix.json
experiments/d1a-warrant-discrimination-v0/definition/negative-control-contract.json
experiments/d1a-warrant-discrimination-v0/definition/perturbation-contract.json
experiments/d1a-warrant-discrimination-v0/definition/policy-contracts.json
experiments/d1a-warrant-discrimination-v0/definition/provenance-contract.json
experiments/d1a-warrant-discrimination-v0/definition/qualification-contract.json
experiments/d1a-warrant-discrimination-v0/definition/reusable-material-audit.json
experiments/d1a-warrant-discrimination-v0/definition/role-boundaries.json
experiments/d1a-warrant-discrimination-v0/meta-fixtures/README.md
experiments/d1a-warrant-discrimination-v0/meta-fixtures/calibration.json
experiments/d1a-warrant-discrimination-v0/meta-fixtures/cases.json
experiments/d1a-warrant-discrimination-v0/scripts/assemble_d1a_bundle.py
experiments/d1a-warrant-discrimination-v0/scripts/common.py
experiments/d1a-warrant-discrimination-v0/scripts/evaluate_policies.py
experiments/d1a-warrant-discrimination-v0/scripts/qualify_instrument.py
experiments/d1a-warrant-discrimination-v0/scripts/validate_information_boundaries.py
experiments/d1a-warrant-discrimination-v0/scripts/validate_submission.py
experiments/d1a-warrant-discrimination-v0/submission-schemas/analysis-bundle.schema.json
experiments/d1a-warrant-discrimination-v0/submission-schemas/authority-policy-bundle.schema.json
experiments/d1a-warrant-discrimination-v0/submission-schemas/calibration-bundle.schema.json
experiments/d1a-warrant-discrimination-v0/submission-schemas/custodian-attestation.schema.json
experiments/d1a-warrant-discrimination-v0/submission-schemas/semantic-verifier-bundle.schema.json
experiments/d1a-warrant-discrimination-v0/submission-schemas/task-oracle-bundle.schema.json
experiments/d1a-warrant-discrimination-v0/tests/support.py
experiments/d1a-warrant-discrimination-v0/tests/test_policies.py
experiments/d1a-warrant-discrimination-v0/tests/test_qualification.py
experiments/d1a-warrant-discrimination-v0/tests/test_submissions.py
```

## Smallest next owner-authorized step

Authorize only the independent task/oracle custodian to author and seal the
first real bundle under its packet and schema, without access to perturbation
assignments, future policy decisions, or held-out producer outputs. Subsequent
authority, verifier, calibration, and analysis custodians should remain
separate and follow the ordered information barriers. No model/provider call or
D1b work is warranted by this handoff.
