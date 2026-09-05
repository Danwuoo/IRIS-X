# Phase 5 Batch 4 — Model Execution Qualification Run 03 Handoff

- **Status:** Complete — accepted frozen qualification
- **Date:** 2026-09-05 Asia/Taipei
- **Repository:** Danwuoo/IRIS-X
- **Required original Batch 4 baseline:** `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751`
- **Run-03 starting SHA:** `43d2d2936ad41cfb3ea21e8d6a7db7aae995df6a`
- **Run-03 plan activation:** `a625bde59e85f6cf995a7843c4eb0aee1e09ec9e`
- **Definition/code freeze:** `47d9173fa929119377fdf01034c399792bdde8ba`
- **Immutable run-evidence commit:** `ccfa44fc255357ba42c8f4ebbd22deda475055e6`
- **Run ID:** `qualification-20260905-03`
- **Acceptance:** `accept`
- **Joint interpretation:** `verified_success`

## Outcome

The one frozen run-03 provider attempt completed successfully. The model returned
the schema-valid result `{"selected_id":"alpha"}`. The fixture-local,
deterministic verifier independently matched `alpha` to the sole qualifying
record in the frozen task input. Canonical adjudication therefore recorded:

| Terminal field | Value |
| --- | --- |
| `terminal_execution_status` | `completed` |
| `actual_outcome` | `success` |
| `producer_claim` | `success` |
| `empirical_evidence_status` | `sufficient` |
| `acceptance_decision` | `accept` |
| `verified_success_eligibility` | `true` |
| `joint_interpretation` | `verified_success` |

This qualifies exactly the frozen run-03 configuration and bounded task. It
does not establish general model capability, routing policy, recovery behavior,
production readiness, or any excluded hypothesis.

## Lifecycle and launch record

The qualification definition, identity, preflight observation, adapter code,
and zero-call tests were committed and pushed before execution at freeze SHA
`47d9173fa929119377fdf01034c399792bdde8ba`.

The frozen runner was launched once as a hidden background process:

- PID at launch: `14256`;
- launch observation: `2026-09-05T14:05:49.3451651Z`;
- immediate process state: created and not exited;
- runner start: `2026-09-05T14:05:52.158776+00:00`;
- runner end: `2026-09-05T14:05:55.648076+00:00`;
- provider process return code: `0`;
- measured wall time: `3,489,073,800 ns`;
- external launcher stdout:
  `C:\Users\wurre\AppData\Local\Temp\irisx-qualification-20260905-03-47d9173\runner.stdout.log`;
- external launcher stderr:
  `C:\Users\wurre\AppData\Local\Temp\irisx-qualification-20260905-03-47d9173\runner.stderr.log`.

The launch task stopped monitoring after the immediate confirmation, as
instructed. Collection occurred only after a later owner request. At collection,
the process was absent/exited, launcher stderr was empty, and launcher stdout
contained the accepted terminal summary.

## Frozen provider and configuration identity

| Field | Frozen/observed value |
| --- | --- |
| Provider | `openai` |
| Provider config slot | `irisx_openai_no_retry` |
| Execution surface | `codex-cli` |
| Resolved executable | `C:\Users\wurre\AppData\Roaming\npm\codex.cmd` |
| CLI version | `codex-cli 0.147.0` |
| Codex source tag | `rust-v0.147.0` |
| Codex source commit | `be6e8eac029b183056b7e4402879f15d2c85f61b` |
| Model | `gpt-5.6-luna` |
| Accepted role | `cheaper` |
| Reasoning effort | `medium` |
| Wire API | `responses` |
| Authentication | `chatgpt` |
| Billing | `chatgpt-subscription` |
| API-key fallback | not used; API-key variables removed from child environment |
| HTTP request retries | `0` |
| Stream reconnect retries | `0` |
| WebSockets | disabled |
| Sandbox | read-only isolated temporary workspace |
| Model tools | disabled |

The accepted provider/model baseline and bundled Codex catalog both passed
zero-call validation. Catalog observation occurred at
`2026-09-05T14:05:52.153345+00:00`; the frozen catalog SHA-256 is
`d743f4bd8e92951ce1c9d3d126b7dc086c3d34279a92f92badf902b8bbcdc921`.
The accepted baseline SHA-256 is
`a1a85c7464fbc090c2bf2e1682bee9a22957146e50abf11ab5c41f1544046d74`.

The capture shape follows Codex non-interactive mode: `codex exec --json`
emits JSONL events, `--output-schema` constrains the final result, and
`--output-last-message` writes the final response. Primary reference:
[OpenAI Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode).

## Frozen qualification identity

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `definition/qualification-run-03-contract.json` | 4,872 | `2cae29982a5482298e2ee87fed64f824743a4cd1e43955906d8e2e932f2defb4` |
| `definition/run-03-execution-identity.json` | 3,889 | `a33d6d113731bdb5a055afb93ac7cb5495f24304e633f1d9bfd5a21474383312` |
| `definition/run-03-preflight-observation.json` | 1,560 | `9dd5b5e28652d1fa9e6c7cd45bb4e3c8b1e88023b0c85e03ed60ae21ff563a14` |
| `definition/output-schema.json` | 229 | `d977a731158927cb0b15b67b250cd52e01c54b12a0e8a1a001e95bd2f94fee8b` |
| `inputs/model-program.txt` | 418 | `0803fdc4fc92cae03e1c736e372a8a60bd4039f2cdab996420664e7b36368e36` |
| `inputs/task-input.json` | 314 | `05ebad722aadac9355907534581ca01e331df412541ae7260a58a0a9d25e88a1` |

Additional identities:

- configuration ID:
  `openai-codex-luna-medium-readonly-zero-retry-run-03-v0`;
- contract ID: `contract-model-record-selection-alpha-run-03-v0`;
- task ID: `model-record-selection-alpha-v0`;
- program ID: `program-model-record-selection-json-v0`;
- exact prompt SHA-256:
  `b3d7aa200d23c6791fbe453bd83e5b8b91700abae58b8bc67794150320a8a52b`.

## Exact call ledger

Run 03 consumed its single frozen allowance:

| Count | Value |
| --- | ---: |
| Provider attempts | 1 |
| Model calls | 1 |
| Manual retries | 0 |
| Automatic HTTP retries | 0 |
| Stream reconnect retries | 0 |
| Routes | 0 |
| Fallbacks | 0 |
| Escalations | 0 |
| Recovery actions | 0 |
| Tool attempts/calls | 0 |

The provider event stream contains exactly four events:
`thread.started`, `turn.started`, one agent-message `item.completed`, and
`turn.completed`. It contains no retry, route, fallback, or tool event.

The complete owner-authorized Batch 4 lineage contains three logical launches:
the preserved run-01 attempt, preserved run-02 corrective attempt, and this
run-03 formal attempt. Run 01 and run 02 produced no provider event or model
result because Codex rejected local configuration before a result; their
records conservatively retain `model_calls: 1` once each launch crossed its
committed attempt boundary. They were not retried or overwritten. Run 03 is the
only lineage run with observed provider events, output, and token usage.

## Raw evidence and hashes

Immutable run directory:
`experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-03/`

Git tree: `3a9059216ce8134c91438b9a37e97140cacbfce3`.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `attempt-start.json` | 3,003 | `564db52edc7725ef0475c607e95b1360f3cb5d9ec37af5a93ca8c60592f544ea` |
| `provider-events.jsonl` | 366 | `3e5f776f4bd2edd3032117344df34fd004a999ee51cf12d4c902539700875f2e` |
| `provider-stderr.txt` | 158 | `48ad01762d10be6ff52d60109a6b606e34b0f17f01dea59eb1b6b8fe46f8d533` |
| `raw-output.txt` | 23 | `f2ee0c4319dec8fa7d42b15f5c859c73306a19e768ae49cb5c9ebd20c1af6e6e` |
| `resource-record.json` | 718 | `ae604197a2fedb4b872987cc3b154ddddc34e3089a0ddf38268274abfd6f84d8` |
| `run-manifest.json` | 9,460 | `7d96542eb57c7b8d1f02b5f98c96e581fc4b813cb11a7a79c71eaccfe5a73c85` |
| `terminal-record.json` | 3,614 | `59a790459b752b06a06d9be285a77964ff3b93a47ec8cbeefa87f3ab6b8af6f2` |
| `interpretation.json` | 2,857 | `fc2a853405039fb878f577086747e602034c3a440eb00d882b1072c39a82dc06` |

`provider-stderr.txt` contains one non-fatal Codex warning that PowerShell shell
snapshotting is unsupported. No shell tool was exposed, the provider exited
zero, no changed path was observed, and this warning did not affect the result.

## Resource accounting

| Resource | Observed value |
| --- | ---: |
| Input tokens | 4,141 |
| Cached input tokens | 0 |
| Cache-write input tokens | 0 |
| Output tokens | 16 |
| Reasoning tokens | 0 |
| Wall time | 3,489,073,800 ns |
| Tool calls | 0 |
| Paid API calls | 0 |
| Transport request count | `Unknown` |
| Network calls | `Unknown` |
| Provider cost USD | `Unknown` |

The run used ChatGPT subscription authentication. No run-attributable
subscription price basis was available, so cost remains `Unknown`. Transport
and network counts remain `Unknown` because Codex CLI did not expose them; no
count was fabricated. The observed invocation is truthfully recorded as one
model call.

## Deterministic verification and read-only proof

The verifier used only the frozen task fixture and exact contract/program
bindings. It did not call a model or external service. It found
`deterministic_record_selection_match` with `complete_correct_binding`.

The isolated task-state digest was unchanged:

```text
before: a5e53e0f8bdc6def70a3eec03a8d361d61c18b45ba312f5fb9adcee1a0fd4a62
after:  a5e53e0f8bdc6def70a3eec03a8d361d61c18b45ba312f5fb9adcee1a0fd4a62
changed_paths: []
```

No OpenAI-, Codex-, or Luna-specific type was added to `irisx.core`.

## Validation

All post-run validation made zero model calls.

- run-03 immutable validator: PASS for all 7 manifest-governed execution
  artifacts; the directory also contains the separately hashed authored
  interpretation;
- run-01 and run-02 immutable validators: PASS;
- exact accepted provider/model baseline plus Codex 0.147.0 bundled catalog:
  PASS;
- repository validation: PASS, 13 sources and 7 paper artifacts;
- Python compilation: PASS;
- core tests: 28/28 PASS;
- deterministic mutation-path tests: 13/13 PASS;
- deterministic read-only integration tests: 9/9 PASS;
- model-execution qualification tests: 20/20 PASS;
- focused total: 70/70 PASS;
- full inventory: 141 total, 140 passed, 1 known historical failure,
  0 errors, 0 skips, and 0 new failures.

The sole full-inventory failure remains the preserved Phase 4 assertion
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`. The retired
plan's actual SHA-256 is
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`,
while the historical assertion expects
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
It was neither modified nor suppressed.

## Preservation proof

From run-03 starting SHA `43d2d2936ad41cfb3ea21e8d6a7db7aae995df6a`
through evidence SHA `ccfa44fc255357ba42c8f4ebbd22deda475055e6`:

| Preserved tree | Before and after Git tree |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` |
| `qualification-20260905-01` | `1fd6b4779ea936e8e1f6026433143a9106317ffa` |
| `qualification-20260905-02` | `f84fd3563386703303206ed66dc0712652a372e4` |

The four frozen deterministic Phase 5 inputs also remain byte-identical:

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `minimal-reliable-execution-v0/inputs/task-contract.json` | 1,283 | `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2` |
| `minimal-reliable-execution-v0/inputs/specialization-program.txt` | 257 | `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242` |
| `core-execution-integration-v0/inputs/task-contract.json` | 1,228 | `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a` |
| `core-execution-integration-v0/inputs/lookup-program.txt` | 278 | `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181` |

No prior run artifact, evidence record, retired plan, handoff, source, paper,
research record, or frozen deterministic Phase 5 input was changed.

## Explicit excluded-mechanism status

No second run-03 model call, retry, model comparison, routing, cascade,
fallback, escalation, recovery, persistence framework, workflow engine/search,
optimizer, fine-tuning, training, multi-agent work, architecture search, model
judge, non-deterministic verifier, external action, production server/UI/API,
or H-G1/H-W1/H-C1/H-R1 evaluation occurred. Batch 5 was not started.

## Closure

Phase 5 Batch 4 is complete for the single frozen run-03 configuration. Retire
`docs/plans/TEMP_PHASE_5_MODEL_EXECUTION_QUALIFICATION_RUN_03.md` in a separate
commit, push `main` normally, confirm ahead/behind `0/0`, and stop.
