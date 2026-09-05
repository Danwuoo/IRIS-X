# Phase 5 Model Execution Qualification Handoff

- **Status:** result / durable handoff
- **Date:** 2026-09-05 Asia/Taipei
- **Phase:** Phase 5 — provisional architecture development
- **Batch:** Batch 4 only
- **Required and actual starting `main`:** `0d738fec43bafc72b5f6ca0f1ca39a6426b0b751`
- **Definition/code freeze:** `b7cb5db1334ba20ec9d19c43af2ffb31a2edce93`
- **Run-evidence commit:** `d85320d57007677be747924426270feb79cc92e2`
- **Validated implementation head:** `d85320d57007677be747924426270feb79cc92e2`
- **Architecture authority:** provisional; not a general model runtime, provider layer, or production architecture

The handoff commit cannot contain its own SHA, and the separate retirement
commit does not exist until after this file is committed. Their full SHAs, the
final local/remote SHA, clean-tree state, ahead/behind state, and push result are
therefore reported in the owner-facing final response.

## Outcome

Phase 5 Batch 4 completed with provider-execution failure. One frozen Codex CLI
qualification attempt was made from a clean definition/code commit. Codex
rejected the command during local configuration loading because the frozen
zero-retry overrides attempted to configure the reserved built-in provider ID
`openai`. The CLI emitted no provider event and no model result. The one-call
ceiling was consumed and no retry was made.

The existing IRIS-X boundaries failed closed: identity and exact program bytes
bound successfully; task state remained unchanged; the adapter failure carried
truthful resource accounting into the terminal ledger; deterministic
verification recorded that no result existed to verify; canonical adjudication
recorded failure/reject/not eligible; and all raw artifacts were preserved.

The strongest allowed conclusion is:

> **Phase 5 Batch 4 complete with provider-execution failure — the frozen model-backed qualification path preserved fail-closed execution, evidence, and terminal accounting boundaries, but successful model-backed execution was not established.**

## Repository and commits

1. `f654d25d7bd406459ee897c8f4a2020a130991e4` — `docs: activate Phase 5 model-execution qualification plan`
2. `0fc48769ecc73af18a1bc5e6f6f85fd5d48e57dc` — `experiments: freeze model-execution qualification definition`
3. `e63cf5db26a34114df801dd8a83d4fe819b35e97` — `experiments: implement model-execution qualification adapter`
4. `b7cb5db1334ba20ec9d19c43af2ffb31a2edce93` — `tests: qualify model-execution preflight`
5. `d85320d57007677be747924426270feb79cc92e2` — `experiments: record model-execution qualification run`
6. Handoff commit — reported after creation.
7. Separate plan-retirement commit — reported after creation.

No commit was amended, rebased, squashed, force-pushed, or otherwise rewritten.

## Provider and configuration identity

| Field | Frozen/observed value |
| --- | --- |
| Provider baseline ID | `irisx-openai-codex-dual-model-v0` |
| Provider baseline SHA-256 | `a1a85c7464fbc090c2bf2e1682bee9a22957146e50abf11ab5c41f1544046d74` |
| Provider | `openai` |
| Execution surface | `codex-cli` |
| Resolved path | `C:\Users\wurre\AppData\Roaming\npm\codex.cmd` |
| Codex CLI version | `codex-cli 0.147.0` |
| Runtime catalog check | `2026-09-05T10:22:54.634405+00:00` |
| Catalog observation | `gpt-5.6-luna` listed with medium reasoning support |
| Model role / ID | `cheaper` / `gpt-5.6-luna` |
| Reasoning effort | `medium` |
| Authentication | `chatgpt`; CLI reported `Logged in using ChatGPT` |
| Billing | `chatgpt-subscription` |
| API-key fallback | prohibited; API-key variables removed from the child; not used |
| Provider snapshot | no distinct date-versioned snapshot in the accepted baseline |
| Provider cost | `Unknown` |

The parent process did contain an `OPENAI_API_KEY`, which made sanitization
material rather than theoretical. The child environment removed all declared
API-key variables before both the final auth preflight and the live attempt.
The connected ChatGPT authentication remained available without changing
account, authentication, or billing configuration.

### Tool, sandbox, and retry envelope

- isolated temporary working directory with no repository or hidden oracle;
- `--ignore-user-config`, `--ignore-rules`, `--ephemeral`;
- read-only sandbox and approval policy `never`;
- shell, web search, apps, browser use, computer use, image generation,
  `view_image`, skills, goals, and multi-agent facilities disabled;
- structured-output schema frozen at
  `definition/output-schema.json`;
- prompt explicitly prohibited every tool and external action;
- any observed tool event would have invalidated the result;
- configured HTTP request retries `0` and stream reconnect retries `0`;
- manual retries, routes, escalations, and recovery actions fixed at `0`.

The failure shows that Codex CLI 0.147.0 did not accept the frozen built-in
provider retry override syntax. This is a provider-execution failure, not
permission to change the frozen command or make a second attempt.

## Exact call ledger

| Resource/event | Observed value |
| --- | ---: |
| Live qualification attempts | 1 |
| Logical model invocation attempts recorded | 1 |
| Codex process return code | 1 |
| Provider events emitted | 0 |
| Model result emitted | 0 |
| Automatic retries | 0 |
| Manual retries | 0 |
| Routes | 0 |
| Escalations | 0 |
| Recovery actions | 0 |
| Tool calls/events | 0 |
| Paid API calls | 0 |
| Transport/network request count | `Unknown` |
| Input tokens | `Unknown` |
| Cached input tokens | `Unknown` |
| Cache-write input tokens | `Unknown` |
| Output tokens | `Unknown` |
| Reasoning tokens | `Unknown` |
| Provider cost USD | `Unknown` |
| Adapter wall time | 151,339,400 ns |

`model_calls: 1` is the adapter-controlled logical invocation attempt. It is
not a claim that an HTTP transport request or model computation occurred. The
empty provider event stream and configuration error establish only that no
provider event or model result was observed; the transport count remains
`Unknown` rather than a fabricated zero.

## Frozen qualification identity

| Field | Value |
| --- | --- |
| Task ID | `model-record-selection-alpha-v0` |
| Contract ID | `contract-model-record-selection-alpha-v0` |
| Contract SHA-256 | `77598da50097ef10f0ff42da1b119ee73d67d21a286a26e6381ae09254364070` |
| Program ID | `program-model-record-selection-json-v0` |
| Program SHA-256 | `0803fdc4fc92cae03e1c736e372a8a60bd4039f2cdab996420664e7b36368e36` |
| Execution ID / run ID | `qualification-20260905-01` |
| Configuration ID | `openai-codex-luna-medium-readonly-v0` |
| Prompt SHA-256 | `b3d7aa200d23c6791fbe453bd83e5b8b91700abae58b8bc67794150320a8a52b` |
| Deterministic oracle | `{"selected_id":"alpha"}` |

Identity binding completed before the adapter attempt. Because the adapter
failed before returning a `RawResult`, the fixture-local semantic verifier did
not parse a model answer. Core failure handling produced a deterministic
`VerificationResult` with `semantic_valid: false`, reason
`executor_failure:ExecutorAdapterError`, evidence `not_assessed`, and reason
`no_result_to_verify`.

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

Task state remained read-only:

```text
state_before_sha256: a5e53e0f8bdc6def70a3eec03a8d361d61c18b45ba312f5fb9adcee1a0fd4a62
state_after_sha256:  a5e53e0f8bdc6def70a3eec03a8d361d61c18b45ba312f5fb9adcee1a0fd4a62
changed_paths: []
mutation primitive calls: 0
```

## Run artifacts and hashes

All paths are under
`experiments/substrates/model-execution-qualification-v0/runs/qualification-20260905-01/`.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `attempt-start.json` | 1,823 | `633dca513fa1d8ada2cc862b2123913f3c8c4df519056b607db0ab8d85b61de5` |
| `provider-events.jsonl` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `provider-stderr.txt` | 217 | `4cf1ac52b2ecccadc6d5d889db31c8a4437cfb3fe107f20ef93f17fe86cb27f0` |
| `raw-output.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `terminal-record.json` | 2,771 | `d7e09cbe9a2fbdf497fa72aaa4af16db6c6bc46cc9f7aa1c8a4c745d1fd7a696` |
| `resource-record.json` | 661 | `7cb63e3fb888d672e5b59911b55ca4485ff7f0c30f02da07a96b801236a00d4b` |
| `run-manifest.json` | 6,547 | `767d3eccb7bc9a2f3f983f7a031ce775d0426e2a416a0398f9669a60eabfa4d6` |
| `interpretation.json` | 2,609 | `ba8522f38fa9dbaeb65f6bd0aa59832708eb9d0b939022585ad821deb8007b65` |

The run validator re-hashed every artifact listed by the immutable manifest and
checked terminal/resource consistency, one recorded model invocation attempt,
zero excluded-mechanism counts, `Unknown` network count, and unchanged state.

## Minimal core change

`AdapterResourceReport` is a provider-neutral frozen record carried by
`RawResult`. `execute()` copies only directly observed fields into the existing
`ResourceLedger`. `ExecutorAdapterError` carries that same report when an
adapter fails after consuming an invocation attempt. `network_calls` can now be
`Unknown`; existing deterministic adapters retain their prior default zeroes.

No provider/model identity, parser, command, authentication type, billing type,
token record, general telemetry framework, provider SDK, or model-specific
class entered `irisx.core`. Provider-specific code remains wholly inside the
new substrate.

## Validation

The final zero-call focused validation executed:

```powershell
python tools\repository_check.py
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog
python -m unittest discover -s irisx\core\tests -v
python -m unittest discover -s experiments\substrates\minimal-reliable-execution-v0\tests -v
python -m unittest discover -s experiments\substrates\core-execution-integration-v0\tests -v
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --validate-run
```

Results:

- repository validation: PASS, 13 registered sources and 7 paper artifacts;
- provider baseline: PASS;
- bundled catalog: PASS with Codex CLI 0.147.0 and Luna/medium;
- core tests: 28/28 PASS;
- mutation-path tests: 13/13 PASS;
- prior read-only-path tests: 9/9 PASS;
- model-qualification tests: 15/15 PASS;
- focused total: 65/65 PASS;
- run-artifact, terminal-record, and resource-record validation: PASS;
- Python compilation: PASS;
- both prior deterministic CLIs: PASS with unchanged semantics;
- whitespace checks: PASS for the post-run working diff.

The established full experiment/substrate sweep covered 16 test directories
and ran 108 tests: 107 passed, one failed, zero errored, and zero skipped.

The sole failure is the unchanged historical Phase 4 debt:

`experiments/exp-2026-09-01-luna-structured-program-specialization/tests/test_contract.py::HPIaContractTests.test_frozen_artifact_hashes_match_exact_bytes`

It still observes SHA-256
`4f3e47a6fa8af63dee6d4397d995a917a216ce70791416909e76a5448697246b`
for the retired Phase 4 plan while the preserved historical assertion expects
`9e2ac0aabcae9a89ed92d9145ec787f4d6ee1920b5344be703498c6435aaf76c`.
The plan, assertion, expected hash, skip state, and classification were not
modified or suppressed. There are zero new failures and zero errors.

## Preservation proof

Protected trees are identical at the required baseline and validated head:

| Material | Baseline/current Git tree |
| --- | --- |
| `sources/` | `10e28d83184c789fc468ca1edc3bebf42ba40b46` |
| `references/papers/` | `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` |
| `research/` | `0d89db5ef0d4712e6068bd499c11a852570633da` |

`git diff --name-only 0d738fec43bafc72b5f6ca0f1ca39a6426b0b751 HEAD -- sources references/papers research`
returned zero paths.

The baseline contained 16 pre-existing run directories and 823 tracked run
files. Their paths and contents are unchanged. The only run-path differences
are the eight files in the one newly authorized Batch 4 run directory.

All 11 pre-existing plans are unchanged. The only plan-path difference is the
new Batch 4 controlling plan, which is retired separately after this handoff.
Prior handoff blobs remain exact:

| Handoff | Baseline/current blob |
| --- | --- |
| Phase 5 Batch 1 | `972036e40751e200a98573695a76db4b93e95715` |
| Phase 5 Batch 2 | `6dd15c653c0d5c4cad8440eadee9b33bb93c8230` |
| Phase 5 Batch 3 | `792868a831a84fc2c6348ce4e79dd971846f7009` |

All four deterministic Phase 5 inputs remain byte-identical:

| Input | Bytes | SHA-256 | Baseline/current blob |
| --- | ---: | --- | --- |
| `minimal-reliable-execution-v0/inputs/task-contract.json` | 1,283 | `d99571c5ed28b79ef5bb9880a078b02545f7e1d51df811934a95e385785266f2` | `c5503e122d00dff5120d0ce554a785f97757d7d0` |
| `minimal-reliable-execution-v0/inputs/specialization-program.txt` | 257 | `30b56206f628174443bd2f7ae27e29530ac60c09ecf6d31b29c553ba5f99f242` | `1e4e57205743514ea2319898221d369bfdf844c0` |
| `core-execution-integration-v0/inputs/task-contract.json` | 1,228 | `359775eba550d889768228886e29acc1778cbb4e242c6bf317887b3e0985e77a` | `c2c4e08849bd4e3842878e7c2ec5d13476b31336` |
| `core-execution-integration-v0/inputs/lookup-program.txt` | 278 | `8962a8a2478d1664ff4f69b7abc47ef158738b505fb05b59277908004dbae181` | `a8ff6ec77279fa8b5526e282549a324e3a31e994` |

## Research and exclusion boundary

- H-G1: `Not evaluated`.
- H-W1: `Not evaluated`.
- H-C1: `Not evaluated`.
- H-R1: `Not evaluated`.

No second model call, model comparison, routing, cascade, fallback,
escalation, retry, recovery, persistence, crash/restart mechanism, workflow
engine/search, optimizer, fine-tuning, training, multi-agent work, architecture
search, non-deterministic verifier, model judge, external action, production
server/UI/API, lifecycle-cost optimization, provider SDK, or final architecture
was implemented or evaluated. API-key fallback did not occur.

## Remaining uncertainty and stop boundary

Successful model-backed execution was not established. Model correctness,
reliability, equivalence, portability, cost advantage, production readiness,
and final architecture correctness remain `Not established` or `Not evaluated`.
Whether Codex CLI can expose a zero-retry built-in OpenAI path without a custom
provider definition remains unresolved by this consumed qualification attempt.

After this handoff is committed, the controlling plan must be retired in a
separate commit, final deterministic validation must retain only the same
historical failure, and `main` must be pushed normally. Then stop. This handoff
does not authorize Batch 5.
