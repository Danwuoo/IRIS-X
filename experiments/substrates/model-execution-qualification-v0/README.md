# Model Execution Qualification v0

- **Status:** frozen Batch 4 evidence, completed Batch 5 admission hardening, and active Batch 6 task-family qualification
- **Scope:** one admitted provider profile reused across exactly three new bounded read-only task families
- **Provider/configuration:** OpenAI through Codex CLI, `gpt-5.6-luna`, medium reasoning
- **Current Batch 6 ceiling:** maximum three model calls; one independently authorized call per task; zero retries
- **Verifier:** deterministic fixture-local JSON/oracle comparison; no model judge
- **Architecture status:** provisional; not a general provider layer or production runtime

This substrate qualifies one simple record-selection task through the existing
IRIS-X identity, contract-bound evidence, independent-verification, canonical
adjudication, terminal-record, and resource-accounting boundaries. Provider-
specific code stays in `scripts/run_qualification.py`; `irisx.core` contains no
OpenAI, Codex, or Luna type.

The immutable original attempt is `runs/qualification-20260905-01/`. It failed
closed during config loading because Codex CLI 0.147.0 rejects overriding the
reserved built-in provider ID `openai`. The corrective run is separately
frozen as `qualification-20260905-02`; it uses the custom Codex configuration
slot `irisx_openai_no_retry` while retaining `openai` as the upstream provider
identity. The slot requires OpenAI authentication, has no API-key/base-URL
fallback, fixes HTTP and SSE retry counts at zero, and disables WebSockets.
The frozen repair model catalog retains the accepted Luna alias and medium
reasoning level while declaring no shell, patch, search, or experimental tool.
Both live attempts remain immutable failures. The subsequent tool-only repair
does not alter either run: it replaces the unsupported `tools.view_image`
override with the 0.147.0-supported `--disable view_image` feature flag.

Owner-authorized formal run `qualification-20260905-03` has its own contract,
identity, and preflight observation. It preserved two prior logical attempts,
permitted one new invocation with zero retries, and was launched only from its
clean committed definition/code freeze. Its result was not inferred from
launch; collection and adjudication occurred in a separate later lifecycle
step.

Run 03 subsequently completed as the only accepted model-backed configuration
in this lineage. Batch 5 does not reopen or replay that run live. The frozen
profile at `admission/codex-cli-0.147.0-run-03-profile.json` and the static
checker at `scripts/check_admission.py` bind the exact historical command,
definition, provider baseline, catalog, and environment policy. Provider-
specific admission remains local to this substrate and authorizes no future
model execution.

## Batch 6 task family

The owner-authorized Batch 6 surface is under `task-family/`. Task A performs
ordered threshold filtering, Task B performs grouped integer aggregation, and
Task C performs top-N ranking with an explicit ID-ascending tie-break. Each has
its own immutable contract, input, program, output schema, deterministic
oracle, verifier identity, execution identity, evidence paths, and run
directory. `scripts/model_adapter.py` is the single provider-specific adapter
shared by the three tasks; shared adapter reuse grants no cross-task authority.

Before any live task, all task-family executable artifacts and offline negative
fixtures/tests are committed under one definition/code freeze SHA. The runner
requires a separately committed current admission snapshot, a clean launch
HEAD, and byte-identical frozen executable paths. It enforces Task A/B/C order,
one immutable evidence commit between tasks, and no retry, route, fallback,
escalation, recovery, tool use, or state mutation.

The 27 offline synthetic outputs cover correct, malformed, schema-valid wrong,
missing, extra, wrong-order or wrong-aggregate, producer-claimed-success
failure, and Task C tie-break-violation cases. They use the real deterministic
verifiers and canonical core adjudication without a model call.

## Frozen task

The prompt combines exact bytes from `inputs/model-program.txt` with canonical
JSON derived from `inputs/task-input.json`. The required answer is exactly the
semantic object:

```json
{"selected_id":"alpha"}
```

The output schema constrains shape. The verifier independently parses the final
text, compares it with the frozen oracle, verifies contract/program evidence
against the bound `ExecutionContext`, and requires the in-memory state identity
to remain unchanged.

## Execution envelope

The adapter runs Codex in an isolated temporary directory with:

- `--ignore-user-config`, `--ignore-rules`, `--ephemeral`;
- `--sandbox read-only` and `approval_policy="never"`;
- shell, web search, apps, and multi-agent facilities disabled;
- patch, plugin, tool-search, and WebSocket transport facilities disabled;
- HTTP-request and stream-reconnect retry counts fixed at zero;
- an output schema and a prompt that forbids every tool;
- API-key environment variables removed from the child process; and
- JSONL auditing that invalidates any observed tool attempt.

Before auth/catalog diagnostics, preflight now loads the exact live config
overrides through `codex app-server --strict-config --listen off` in an
isolated temporary `CODEX_HOME`. Codex 0.147.0 reaches a frozen no-transport
sentinel only after strict parsing succeeds. This exercises the same strict
config loader without starting a model turn or transport.

Codex CLI's provider transport count is not exposed, so the terminal resource
ledger records `network_calls` as `Unknown`. The one adapter-controlled logical
model invocation is recorded as `model_calls: 1`; token usage is preserved only
when the CLI event stream exposes it, and provider cost remains `Unknown`.

## Zero-call validation

From the repository root:

```powershell
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --replay-run-01
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --replay-run-02
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --replay-run-03
python experiments\substrates\model-execution-qualification-v0\scripts\check_admission.py --current
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --check-strict-config
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --preflight
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --validate-run --run-id qualification-20260905-01
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --validate-run --run-id qualification-20260905-02
```

None of those commands may execute `codex exec` or start a model turn.

Run 01 and Run 02 intentionally return a nonzero admission exit status because
they are rejected. Run 03 and a compatible current environment return zero.
Current-environment records under `admission/results/` are authored static
preflight artifacts, not model-run evidence; no Batch 5 run directory exists.

## Preserved Batch 4 live-invocation procedure

The following describes the already-consumed Batch 4 procedure and is retained
only to preserve the substrate history:

```powershell
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --live --definition-commit <full-definition-commit> --code-commit <full-clean-head>
```

The qualification command refuses an existing run directory, a dirty tree, non-full or
unresolvable commit identities, mismatched frozen artifacts, unavailable Luna
catalog entry, non-ChatGPT auth, or any API-key fallback requirement. It makes
at most one `codex exec` subprocess invocation and has no retry branch.

After that attempt, tests inspect the immutable run artifacts; they never invoke
the provider again.

Batch 5 authorizes no use of `--live`, no new run directory, and no model call,
even when the static admission result is `admitted`.
