# Phase 5 Model Execution Qualification Repair Handoff

- **Status:** result / durable corrective handoff
- **Date:** 2026-09-05 Asia/Taipei
- **Phase and batch:** Phase 5 Batch 4 corrective continuation only
- **Required original baseline:** `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751`
- **Required and actual repair starting SHA:** `000cc1c3c9affbbf84c434803389bfd427e12dee`
- **Repair plan activation:** `f01e854a30f7e1b259ced181d79acf4be6ae8bf0`
- **Repair definition/code freeze:** `2fe2a3183ee631fe57929b41e354211295a23ce3`
- **Repair run-evidence commit:** `39f7d2c2344bfd701e30e165d5f30bf913aa07e7`
- **Architecture authority:** provisional; not a general provider layer or production runtime

The handoff commit cannot contain its own SHA, and the separate plan-retirement
commit does not exist until after this file is committed. Their full SHAs and
the final push/ahead-behind result are reported in the owner-facing final
response.

## Outcome

The owner-authorized Batch 4 repair lifecycle is complete, but successful
model-backed execution qualification remains **not established**.

Exactly one additional frozen Codex CLI invocation was made with no retry.
Codex CLI 0.147.0 rejected the command during local strict configuration
loading because `tools.view_image` is not a recognized configuration field.
No provider event or model result was observed. The repair call ceiling was
consumed, the raw failure was preserved, and no changed command was submitted.

The existing IRIS-X boundaries again failed closed: exact identity and program
bytes bound successfully; task state remained unchanged; the attempted model
use was recorded as one logical model call rather than zero; deterministic
verification recorded that there was no result to verify; and canonical
adjudication recorded failure/reject/not eligible.

The strongest allowed conclusion is:

> **The Batch 4 corrective attempt preserved fail-closed identity, evidence,
> deterministic verification, adjudication, terminal, and resource-accounting
> boundaries, but it did not qualify a successful model-backed execution path.
> No further attempt is authorized in this batch.**

This work did not start Batch 5.

## Repair commits

1. `f01e854a30f7e1b259ced181d79acf4be6ae8bf0` — `docs: activate Phase 5 model-execution repair plan`
2. `2fe2a3183ee631fe57929b41e354211295a23ce3` — `experiments: freeze model-execution qualification repair`
3. `39f7d2c2344bfd701e30e165d5f30bf913aa07e7` — `experiments: preserve model-execution repair attempt`
4. Handoff commit — reported after creation.
5. Separate repair-plan retirement commit — reported after creation.

No commit was amended, rebased, squashed, force-pushed, or otherwise rewritten.

## Frozen repair identity

| Field | Value |
| --- | --- |
| Task ID | `model-record-selection-alpha-v0` |
| Contract ID | `contract-model-record-selection-alpha-repair-v0` |
| Contract SHA-256 | `261f80ec9e8e24df7c183c20c48524ac96122356b5a7b0f1463d60cab5c8e5f0` |
| Program ID | `program-model-record-selection-json-v0` |
| Program SHA-256 | `0803fdc4fc92cae03e1c736e372a8a60bd4039f2cdab996420664e7b36368e36` |
| Task-input SHA-256 | `05ebad722aadac9355907534581ca01e331df412541ae7260a58a0a9d25e88a1` |
| Output-schema SHA-256 | `d977a731158927cb0b15b67b250cd52e01c54b12a0e8a1a001e95bd2f94fee8b` |
| Tool-free model-catalog SHA-256 | `d743f4bd8e92951ce1c9d3d126b7dc086c3d34279a92f92badf902b8bbcdc921` |
| Frozen preflight-observation SHA-256 | `aa7a6405bacb9ef7b53362441a18bc50e99b1ad52c45b4b563152a4d74fae049` |
| Execution/run ID | `qualification-20260905-02` |
| Configuration ID | `openai-codex-luna-medium-readonly-zero-retry-repair-v0` |
| Prompt SHA-256 | `b3d7aa200d23c6791fbe453bd83e5b8b91700abae58b8bc67794150320a8a52b` |
| Deterministic oracle | `{"selected_id":"alpha"}` |

## Provider and execution configuration

| Field | Frozen/observed value |
| --- | --- |
| Accepted provider baseline | `irisx-openai-codex-dual-model-v0` |
| Provider baseline SHA-256 | `a1a85c7464fbc090c2bf2e1682bee9a22957146e50abf11ab5c41f1544046d74` |
| Upstream provider identity | `openai` |
| Codex provider config slot | `irisx_openai_no_retry` |
| Codex provider display name | `OpenAI` |
| Explicit provider base URL | none |
| Endpoint resolution | compiled ChatGPT-auth default, `https://chatgpt.com/backend-api/codex` |
| Execution surface | `codex-cli` |
| Resolved executable | `C:\Users\wurre\AppData\Roaming\npm\codex.cmd` |
| Codex CLI version | `codex-cli 0.147.0` |
| Codex source observation | tag `rust-v0.147.0`, commit `be6e8eac029b183056b7e4402879f15d2c85f61b` |
| Model role / ID | `cheaper` / `gpt-5.6-luna` |
| Reasoning effort | `medium` |
| Authentication | `chatgpt`; `Logged in using ChatGPT` |
| Billing | `chatgpt-subscription` |
| API-key fallback | prohibited; all declared key/base-URL variables removed from the child |
| Provider snapshot | no separate date-versioned snapshot in the accepted baseline |
| Provider cost | `Unknown` |

The official Codex configuration reference documents custom
`model_providers.<id>` definitions, `requires_openai_auth`,
`request_max_retries`, and `stream_max_retries`:
<https://learn.chatgpt.com/docs/config-file/config-reference>.

The custom slot retained OpenAI provider semantics while avoiding the reserved
built-in `openai` configuration ID that caused the original attempt to fail.
The frozen slot required ChatGPT authentication, fixed HTTP request retries and
stream reconnect retries at zero, disabled WebSocket transport, and supplied
no API-key, bearer-token, authentication-command, or base-URL fallback.

The isolated model catalog retained only the accepted `gpt-5.6-luna` alias and
medium reasoning level. It declared shell disabled, no patch tool, no search
support, no experimental tools, no parallel tool calls, and direct tool-free
mode. The live command also disabled shell, patch, JavaScript REPL, web/tool
search, apps, plugins, browsers, computer use, image generation, skills, goals,
multi-agent facilities, WebSockets, and remote compaction.

Preflight made zero model calls and confirmed the custom provider, Luna/medium,
ChatGPT authentication, subscription billing, compiled endpoint resolution,
zero configured retries, and disabled WebSocket support. Codex `debug` and
`doctor` do not exercise the `exec --strict-config` validation path, so they did
not expose the unsupported `tools.view_image` field before the frozen live
attempt. This is the observed repair falsifier; it is not authorization to
change the command and retry.

## Exact call ledger

### Repair attempt

| Resource/event | Observed value |
| --- | ---: |
| Live repair qualification attempts | 1 |
| Logical model invocation attempts recorded | 1 |
| Codex process return code | 1 |
| Provider events emitted | 0 |
| Model results emitted | 0 |
| Automatic retries / stream reconnects | 0 |
| Manual retries | 0 |
| Routes | 0 |
| Escalations | 0 |
| Recovery/fallback actions | 0 |
| Tool calls/events | 0 |
| Paid API calls | 0 |
| Transport/network request count | `Unknown` |
| Input/cached/cache-write/output/reasoning tokens | `Unknown` |
| Provider cost USD | `Unknown` |
| Adapter wall time | 135,004,400 ns |

`model_calls: 1` is the adapter-controlled logical invocation attempt. It does
not claim that an HTTP request or model computation occurred. Because Codex
does not expose a transport count for this failure, that field remains
`Unknown`, not a fabricated zero.

### Batch 4 lineage

| Attempt | Run | Result | Logical calls | Retries |
| --- | --- | --- | ---: | ---: |
| Original | `qualification-20260905-01` | reserved built-in provider config rejection | 1 | 0 |
| Owner-authorized repair | `qualification-20260905-02` | strict config rejection of `tools.view_image` | 1 | 0 |
| **Total** | — | no model result established | **2** | **0** |

There was no third attempt, retry, reroute, fallback, escalation, recovery,
comparison, or alternate model.

## Deterministic verification and terminal semantics

No model answer existed to parse. Core failure handling produced a
deterministic `VerificationResult` with `semantic_valid: false`, reason
`executor_failure:ExecutorAdapterError`, evidence status `not_assessed`, and
reason `no_result_to_verify`. No model judge was used.

Canonical terminal semantics are:

```text
actual_outcome: failure
producer_claim: null
empirical_evidence_status: not_assessed
acceptance_decision: reject
verified_success_eligibility: false
joint_interpretation: correctly_recognized_failure
terminal_execution_status: failed
```

Read-only state remained unchanged:

```text
state_before_sha256: a5e53e0f8bdc6def70a3eec03a8d361d61c18b45ba312f5fb9adcee1a0fd4a62
state_after_sha256:  a5e53e0f8bdc6def70a3eec03a8d361d61c18b45ba312f5fb9adcee1a0fd4a62
changed_paths: []
mutation primitive calls: 0
```

## Repair run artifacts and hashes

All paths are under
`experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-02/`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `attempt-start.json` | 3,014 | `67f3e085deed532a4e50965503f633b0467dd739467ae7ece2ac7aa8cc55a2bd` |
| `provider-events.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider-stderr.txt` | 98 | `74cb00300ed4a4c23ba979d30d34218cd356e4bfb55b81f10a3dc832d52c56c7` |
| `raw-output.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `terminal-record.json` | 2,803 | `c94fa8373814853e6de56f60599bfc936c242802539f8856a4e1612847831b0e` |
| `resource-record.json` | 753 | `734470c0fd615f60dc24d939666ac591b3cb75e3b58603b5198f929802e0d996` |
| `run-manifest.json` | 9,218 | `cd14c407e2e13d89da2b6f09daec92e5697c1c98152eec79114224c736a3249c` |
| `interpretation.json` | 2,771 | `4fc5855d66bc31be56636fdb2fb3761244a4c2bcaf56474ca7f7796fc5c0802b` |

The run validator re-hashed all seven manifest-controlled artifacts and checked
terminal/resource agreement, one recorded logical model call, zero excluded
mechanisms, `Unknown` network count, and unchanged task state.

## Original run preservation

The original run remains under
`experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-01/`.
Its Git tree stayed exactly
`1fd6b4779ea936e8e1f6026433143a9106317ffa` from repair start through the
run-evidence commit. Its validator still passes.

| Artifact | SHA-256 |
| --- | --- |
| `attempt-start.json` | `633dca513fa1d8ada2cc862b2123913f3c8c4df519056b607db0ab8d85b61de5` |
| `provider-events.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider-stderr.txt` | `4cf1ac52b2ecccadc6d5d889db31c8a4437cfb3fe107f20ef93f17fe86cb27f0` |
| `raw-output.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `terminal-record.json` | `d7e09cbe9a2fbdf497fa72aaa4af16db6c6bc46cc9f7aa1c8a4c745d1fd7a696` |
| `resource-record.json` | `7cb63e3fb888d672e5b59911b55ca4485ff7f0c30f02da07a96b801236a00d4b` |
| `run-manifest.json` | `767d3eccb7bc9a2f3f983f7a031ce775d0426e2a416a0398f9669a60eabfa4d6` |
| `interpretation.json` | `ba8522f38fa9dbaeb65f6bd0aa59832708eb9d0b939022585ad821deb8007b65` |

## Validation

Post-run zero-call focused validation:

- core: 28/28 PASS;
- deterministic mutation path: 13/13 PASS;
- deterministic read-only integration path: 9/9 PASS;
- model-execution qualification: 18/18 PASS;
- focused total: **68/68 PASS**.

Post-run full test inventory:

- total: **139**;
- passed: **138**;
- failures: **1**, the same known Phase 4 retired-plan hash mismatch;
- errors: **0**;
- skipped: **0**;
- new failures/errors: **0**.

The sole historical failure remains
`HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes` for
`docs/plans/TEMP_PHASE_4_FINAL_MODEL_SPECIALIZATION_AND_CLOSURE.md`: observed
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`,
expected
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
It was not modified or suppressed.

Additional zero-call checks passed:

- repository validation: 13 sources and 7 paper artifacts, hashes checked;
- accepted provider/model baseline: 1 provider, 1 strong, 1 cheaper;
- local bundled catalog: Luna/medium present under Codex CLI 0.147.0;
- original and repair immutable-run validators;
- JSON, Python compilation, frozen hash, and Git diff checks.

## Preservation proof

From repair starting SHA `000cc1c3c9affbbf84c434803389bfd427e12dee`
through run-evidence SHA `39f7d2c2344bfd701e30e165d5f30bf913aa07e7`:

| Preserved tree | Before and after Git tree |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` |
| original Batch 4 run | `1fd6b4779ea936e8e1f6026433143a9106317ffa` |

Prior durable handoff blobs remain:

- Batch 1 core interfaces: `972036e40751e200a98573695a76db4b93e95715`;
- Batch 2 contract-bound evidence: `6dd15c653c0d5c4cad8440eadee9b33bb93c8230`;
- Batch 3 terminal semantic integrity: `792868a831a84fc2c6348ce4e79dd971846f7009`;
- original Batch 4 handoff: `748901d24753a36f085ecf1f9e5cc17f1181a64a`.

The four deterministic Phase 5 inputs remain byte-identical:

- mutation contract: `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2`;
- mutation program: `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242`;
- read-only contract: `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a`;
- read-only program: `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181`.

Tracked run material changed from 17 directories / 831 files to 18
directories / 839 files. The only new run directory is
`qualification-20260905-02`, containing exactly the eight artifacts listed
above. No `irisx/core` file changed during the repair.

## Explicit excluded-mechanism status

| Mechanism | Status |
| --- | --- |
| Second repair call / retry / recovery | not performed; repair ceiling consumed |
| Model comparison / alternate model | not implemented or evaluated |
| Routing / cascade / fallback / escalation | not implemented, invoked, or evaluated |
| Persistence / workflow engine or search / optimizer | not implemented or evaluated |
| Fine-tuning / training / architecture search | not implemented or evaluated |
| Multi-agent work | not used |
| Non-deterministic verifier / model judge | not used |
| External action / production server, UI, or API | not implemented or exercised |
| Provider-specific type in `irisx.core` | none introduced |
| H-G1 / H-W1 / H-C1 / H-R1 | not evaluated |
| Batch 5 | not started |

Any future correction requires a new owner-authorized scope and a newly frozen
execution definition. It must not reinterpret either preserved Batch 4 attempt
as a successful model-backed qualification.
