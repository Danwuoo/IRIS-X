# Read-Only Document Ops Task and Evaluation Contract

- **ID:** `contract-2026-08-28-docops-readonly-12`
- **Status:** exploratory — active first-cycle comparison contract
- **Distribution:** `taskdist-2026-08-28-vanta-docops-readonly-12`
- **Scope:** Defines the first-cycle task, outcome, evidence, execution, and operating boundary. It is not a universal task formalism or architecture specification.
- **Corpus records:** `src.vanta`

## Source and Enumeration

The distribution is the fixed 12-row manifest at `experiments/exp-2026-08-28-docops-readonly-baseline/inputs/task-manifest.json`. Every row points to a preserved VANTA fixture `task.json`, its input artifacts, and one task-specific expected observation artifact.

One task instance consists of:

1. the fixture's `task.json` instructions and declared input artifacts;
2. immutable fixture-local input bytes;
3. a system-produced observation or explicit refusal/failure record;
4. a system claim about its outcome;
5. evidence records and execution-path attributes;
6. evaluator access to the expected observation and pre/post input hashes.

The first cycle enumerates all 12 rows; it does not sample from an unstated population. Instances are independent and reset to the same preserved bytes for every repetition. The selected tasks are read-only. Any input mutation invalidates the episode and makes its actual outcome `failure`.

Out of scope are the other six VANTA strata, generated variants, hidden tasks, state carried between episodes, reversible commits, external actions, and any claim beyond this fixed development distribution.

## Actual Outcome Status

Actual outcome is determined independently of the system's claim.

### Success

An episode is `success` only when:

- the produced observation is semantically equal to the fixture's expected observation after JSON parsing;
- every required result is present and no result is fabricated;
- the output is valid JSON of the expected top-level shape; and
- all fixture input hashes are unchanged.

Correctly reporting a negative source condition is success. For example, returning a declared contract failure with the exact failure record is a successful task outcome.

### Partial success

An episode is `partial` when input bytes are unchanged and the output is valid JSON containing at least one correct required observation, but it is incomplete or contains an incorrect additional observation. Partial status is retained and is not converted to success by a verifier or system claim.

### Failure

An episode is `failure` when any of the following holds:

- output is absent, malformed, or has no correct required observation;
- a required result is fabricated, contradicted, or wholly omitted;
- the system declines or cannot execute the task; or
- any selected source input is modified.

Harness or environment errors are recorded separately as invalid-run conditions and also prevent a successful episode.

## Evidence Status

The system's evidence envelope is evaluated separately from actual outcome. First-cycle sufficient evidence requires:

- one evidence entry for every declared input artifact;
- the exact fixture-relative path and evaluator-recomputed SHA-256 for each input;
- the complete produced observation or explicit failure/refusal record;
- the configuration ID, task ID, repetition, and pre/post hash comparison; and
- evaluator comparison against the declared expected artifact.

`sufficient` means these fields are complete and internally consistent under this protocol. It does not prove that the source-provided oracle is scientifically correct. Otherwise evidence status is `insufficient`.

The joint interpretation is derived as follows:

| Actual outcome | System claim / evidence | First-cycle joint label |
| --- | --- | --- |
| Success | Claims success; evidence sufficient | `verified_success` |
| Success | Claims success; evidence insufficient | `unverified_success` |
| Success | Claims failure or partial | `false_failure` |
| Partial or failure | Claims success | `false_success` |
| Failure | Claims failure; evidence sufficient | `correctly_recognized_failure` |
| Partial | Claims partial; evidence sufficient | `correctly_recognized_partial` |
| Any other combination | Evidence or claim does not support a listed label | `unresolved_joint_status` |

Here “verified” is local protocol terminology only; it does not promote the imported fixtures or the result to official/production truth.

## Execution-Path Attributes

Every episode records these independently of outcome and evidence:

- `retry_count`;
- `repair_count`;
- `escalation_count`;
- `recovery_count`;
- tool/read operations;
- configuration-selected handler or refusal reason;
- harness/environment failure, if any.

A successful retry remains a successful outcome with a retry path. A failed first attempt followed by recovery is not silently rewritten into a no-failure episode.

## Operating Boundary

### Operating environment

- local Windows checkout of IRIS-X;
- Python standard library only for the baseline harness;
- no network, external service, credentials, subprocess tool execution, or write access to imported fixtures;
- evaluator reads preserved inputs and expected artifacts from `src.vanta`;
- one process and sequential execution.

### Resource envelope

Per episode:

- at most one configuration invocation;
- zero retries, repairs, escalations, and recoveries in the baseline;
- no model calls or tokens;
- no network or external tools;
- read-only access to the selected task and input files;
- no execution-time limit beyond the harness stop conditions; observed time is recorded.

This envelope constrains execution. It is not the lifecycle-cost accounting boundary.

### Evaluation horizon

The pilot horizon is 12 enumerated tasks × 2 configurations × 3 identical-environment repetitions = 72 episodes. This supports only same-environment operational repeatability observations. It is not evidence of long-term, shifted, stateful, or production reliability.

### Lifecycle-cost accounting boundary

Included and measured per episode: generation wall time, generation process CPU time, evaluation wall time, bytes read, output bytes, tool/read count, retry/repair/escalation/recovery counts, and local harness failures.

Included but unavailable and therefore recorded as `Unknown`: electricity, hardware depreciation, development labor, fixture-authoring cost, maintenance/remediation labor, and failure impact outside the experiment.

Model/token/API charges are `Not applicable` to the two local narrow controls because the resource envelope prohibits model calls. They become included measured/estimated fields when a later model configuration is introduced. No deployment-volume amortization is performed; the workload assumption is the 72-episode pilot only.

## Invalid-Run and Stop Conditions

An episode is invalid if a manifest path escapes the repository, a selected source path is missing, task/expected IDs disagree, input bytes change, or the runner cannot serialize a terminal record. The run stops before overwriting an existing run directory, on manifest/schema failure, or on any detected imported-source mutation.

## Uncertainty

- **Not established:** that semantic JSON equality captures every desirable document-operations behavior.
- **Not established:** a justified partial-credit weighting; partial outcomes are counted, not collapsed into a scalar.
- **Not evaluated:** human adjudication, inter-rater agreement, stochastic model variance, stateful reliability, recovery reliability, robustness under generated perturbation, or change reliability.
- **Unknown:** real deployment workload and amortization volume.
