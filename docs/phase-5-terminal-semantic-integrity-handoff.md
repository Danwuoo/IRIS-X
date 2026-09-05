# Phase 5 Terminal Semantic Integrity Handoff

- **Status:** result / durable handoff
- **Date:** 2026-09-05 Asia/Taipei
- **Phase:** Phase 5 — provisional architecture development
- **Batch:** Batch 3 only
- **Required baseline:** `954b95d0126ac057789d1eee5584ec7bef391614`
- **Actual starting `main`:** `954b95d0126ac057789d1eee5584ec7bef391614`
- **Starting `origin/main`:** `954b95d0126ac057789d1eee5584ec7bef391614`
- **Validated implementation head:** `fd3b179ec7515f435f941b18055077f1ad8a6c81`
- **Architecture authority:** provisional; not general adjudication, a final architecture, or a production runtime

The handoff commit cannot contain its own SHA, and the separate retirement commit
does not exist until after this handoff is committed. Their full SHAs, the final
local and remote `main`, ahead/behind state, clean-tree result, and normal push
result are therefore recorded in the owner-facing final report.

## Outcome

Phase 5 Batch 3 centralizes the currently supported deterministic terminal
semantics into one pure core operation and makes direct `TerminalRecord`
construction compare all adjudicated fields against that canonical result. Both
existing execution paths retain their prior behavior and terminal schema version
1. No third path or excluded mechanism was added.

The strongest supported conclusion is:

> **Phase 5 Batch 3 complete — terminal outcome, evidence, acceptance, verified-success eligibility, and joint interpretation are canonically derived and consistency-checked across the existing provisional deterministic execution paths.**

This does not establish general adjudication, universal verifier correctness,
probabilistic reliability, production reliability, or final architecture
correctness. Phase 5 remains open.

## Commit sequence before handoff and retirement

1. `45828999ff39e7617a21e308ef6c5f4cda40027f` — `docs: activate Phase 5 terminal-integrity plan`
2. `0e7ec248480ac6598b56c53e161b4abe100d2361` — `docs: align Phase 5 terminal-integrity authority`
3. `587e3a12767caa31bcdfc5b6436687ba78fa7c47` — `core: centralize terminal adjudication`
4. `fd3b179ec7515f435f941b18055077f1ad8a6c81` — `core: enforce terminal semantic consistency`
5. Handoff commit — reported after creation because this file cannot contain its own commit SHA.
6. Separate plan-retirement commit — reported after creation.

No commit was amended, rebased, squashed, force-pushed, or otherwise rewritten.

## Changed files

The completed batch changes only:

- `AGENTS.md`
- `docs/plans/TEMP_PHASE_5_TERMINAL_SEMANTIC_INTEGRITY.md`
- `docs/phase-5-terminal-semantic-integrity-handoff.md`
- `irisx/core/__init__.py`
- `irisx/core/records.py`
- `irisx/core/execution.py`
- `irisx/core/tests/test_adjudication.py`
- `experiments/substrates/minimal-reliable-execution-v0/tests/test_slice.py`
- `experiments/substrates/core-execution-integration-v0/tests/test_integration.py`

No fixture input, CLI script, substrate README, imported source, research record,
pre-existing run, retired plan, or prior handoff changed.

## Previous ambiguity

`execute()` previously computed actual outcome, acceptance, eligibility, and
joint interpretation locally, while `TerminalRecord` could be constructed
directly with contradictory combinations. Its prior validation checked evidence
status equality and one derived eligibility expression, but did not establish
one source of truth for all terminal semantic fields.

## Canonical adjudication boundary

`irisx.core.records` now exposes:

```python
@dataclass(frozen=True)
class AdjudicationResult:
    actual_outcome: str
    acceptance_decision: str
    verified_success_eligibility: bool
    joint_interpretation: str


def adjudicate(
    verification: VerificationResult,
    *,
    terminal_execution_status: str,
) -> AdjudicationResult:
    ...
```

The authoritative inputs are only the independent `VerificationResult` and the
terminal execution status. Producer claim, provider/model identity, evidence
payload rows, observations, telemetry, and `ResourceLedger` are not parameters
and cannot affect the returned semantics.

The bounded mapping is:

| Verifier semantics | Evidence | Terminal execution | Outcome | Acceptance | Eligible | Joint interpretation |
| --- | --- | --- | --- | --- | --- | --- |
| valid | sufficient | completed | success | accept | true | verified_success |
| valid | insufficient | completed | success | reject | false | unverified_success |
| valid | invalid_binding | completed | success | reject | false | unverified_success |
| invalid | any current status | any allowed status | failure | reject | false | correctly_recognized_failure |

A semantically valid result with a non-completed terminal execution status is
not eligible or accepted and is represented as unverified success. Current
`execute()` paths do not produce this combination, but the rule prevents terminal
completion from being ignored during direct construction.

Every `execute()` return branch now calls `adjudicate()`. The previous standalone
joint-interpretation mapper and inline outcome/acceptance/eligibility mapping
were removed. The dependency direction remains:

```text
experiments/substrates/* -> irisx.core
```

The core still imports nothing from `experiments/`, `sources/`, or `references/`.

## TerminalRecord consistency rules

After vocabulary and SHA checks, `TerminalRecord.__post_init__()` now:

1. requires terminal evidence status to equal verifier evidence status;
2. recomputes the canonical `AdjudicationResult`;
3. requires exact equality for actual outcome;
4. requires exact equality for acceptance decision;
5. requires exact equality for verified-success eligibility;
6. requires exact equality for joint interpretation; and
7. retains the existing fail-closed retry and recovery checks.

This rejects semantic-valid/failure, semantic-invalid/success, false acceptance,
false eligibility, non-canonical joint interpretation, and crossed terminal
evidence states. Producer claims remain recordable as claims but cannot make a
contradictory terminal state constructible.

The serialized terminal layout is unchanged: `schema_version` remains `1`, no
field was renamed, and no top-level field was added or removed.

## Behavioral proof

The focused core tests establish:

- valid semantics plus sufficient evidence and completed execution yields verified success;
- insufficient or invalid evidence preserves actual success while rejecting acceptance and eligibility;
- semantic failure remains failure even when the producer claims success;
- semantic failure cannot become verified success;
- direct contradictions in outcome, acceptance, eligibility, joint interpretation, or evidence status raise `ValueError`;
- changing producer claim, observation contents, artifact/executor resource counts, or wall-time telemetry leaves all four adjudication outputs identical; and
- serialization retains schema version 1 and the exact prior top-level key set.

The mutation CLI retains:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
ordered observations: 6
executor calls: 1
mutation primitive calls: 1
changed_paths: [scratch/result]
```

The read-only CLI retains:

```text
actual_outcome: success
producer_claim: success
empirical_evidence_status: sufficient
acceptance_decision: accept
verified_success_eligibility: true
joint_interpretation: verified_success
terminal_execution_status: completed
policy_decision: not_required
ordered observations: 6
executor calls: 1
mutation primitive calls: 0
changed_paths: []
state_before_sha256 == state_after_sha256
```

## Validation before handoff

Executed from repository root:

```powershell
python tools\repository_check.py
python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m py_compile irisx\__init__.py irisx\core\__init__.py irisx\core\records.py irisx\core\interfaces.py irisx\core\execution.py
python experiments\substrates\minimal-reliable-execution-v0\scripts\run_slice.py
python experiments\substrates\core-execution-integration-v0\scripts\run_lookup.py
git diff --check
git diff --cached --check
```

Results:

- repository validation: PASS, 13 registered sources and 7 paper artifacts with hashes checked;
- core tests: 28/28 PASS;
- mutation-path tests: 13/13 PASS;
- read-only-path tests: 9/9 PASS;
- focused total: 50/50 PASS;
- required Python compilation: PASS;
- mutation CLI: PASS with schema version 1 and the preserved semantics above;
- read-only CLI: PASS with schema version 1 and the preserved semantics above;
- whitespace checks: PASS.

The established full experiment/substrate sweep covered 15 test directories and
ran 93 tests: 92 passed, one failed, and zero errored. This is identical to the
Batch 3 baseline sweep.

The sole failure remains the historical Phase 4 debt:

`experiments/exp-2026-09-01-luna-structured-program-specialization/tests/test_contract.py::HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`

It observes SHA-256
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`
for `docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`,
while the preserved frozen pre-retirement assertion expects
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
The assertion, expected hash, retired plan, test classification, and skip state
were not edited. There are zero new failures and zero errors.

## Preservation proof

Protected Git tree identities at the required baseline and validated
implementation head are identical:

| Material | Baseline tree | Validated tree |
| --- | --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` | same |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` | same |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` | same |

All 16 pre-existing run instances and all 823 tracked files under directories
named `runs/` have identical paths and zero content diff from the required
baseline. No new run directory was created.

All 10 pre-existing plan files are unchanged; the only `docs/plans/` difference
from baseline is the new Batch 3 controlling plan. Prior durable handoffs remain
exact, including:

| Handoff | Baseline/current blob |
| --- | --- |
| Phase 5 Batch 1 | `972036e40751e200a98573695a76db4b93e95715` |
| Phase 5 Batch 2 | `6dd15c653c0d5c4cad8440eadee9b33bb93c8230` |
| Post-Phase-4 synthesis | `65cdc8eea13e308d46ee2e3bfa862f3cb9ec5bcd` |

The Phase 4 closure record remains blob
`5e292b07cef02d6a84aa88fde2035c3736b23fe1`.

All four execution inputs are byte-identical:

| Input | Bytes | SHA-256 | Baseline/current Git blob |
| --- | ---: | --- | --- |
| `minimal-reliable-execution-v0/inputs/task-contract.json` | 1,283 | `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2` | `c5503e122d00dff5120d0ce554a785f97757d7d0` |
| `minimal-reliable-execution-v0/inputs/specialization-program.txt` | 257 | `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242` | `1e4e57205743514ea2319898221d369bfdf844c0` |
| `core-execution-integration-v0/inputs/task-contract.json` | 1,228 | `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a` | `c2c4e08849bd4e3842878e7c2ec5d13476b31336` |
| `core-execution-integration-v0/inputs/lookup-program.txt` | 278 | `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181` | `a8ff6ec77279fa8b5526e282549a324e3a31e994` |

No third execution path exists.

## Research and exclusion boundary

- H-G1: `Not evaluated`.
- H-W1: `Not evaluated`.
- H-C1: `Not evaluated`.
- H-R1: `Not evaluated`.

No provider/model adapter, model call, network/API behavior, paid API, external
action, persistence, retry, recovery, routing, cascade, escalation, workflow
machinery/search, optimizer integration, fine-tuning, training, multi-agent
logic, architecture search, production infrastructure, telemetry system,
ontology redesign, additional execution path, or new run occurred.

The CLI terminal ledgers preserve zero model, network, paid API, tool, retry,
route, escalation, and recovery counts. Provider cost and wall time remain
`Unknown` and do not affect adjudication.

## Remaining uncertainty and stop boundary

The canonical operation covers only the current deterministic verifier and
terminal-status vocabulary. `partial`, `unresolved`, confidence, human
disagreement, multi-verifier consensus, probabilistic reliability, and general
reliability semantics were not redesigned or evaluated. The exact Python record
and function shapes remain provisional.

After this handoff is committed, the controlling plan must be retired in a
separate commit, final validation must pass with only the same historical
failure, and `main` must be pushed normally. Then stop. This handoff does not
authorize Phase 5 Batch 4.
