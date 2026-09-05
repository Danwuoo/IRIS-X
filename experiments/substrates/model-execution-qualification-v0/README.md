# Model Execution Qualification v0

- **Status:** frozen qualification substrate for Phase 5 Batch 4
- **Scope:** exactly one model-backed read-only `ExecutorAdapter` path
- **Provider/configuration:** OpenAI through Codex CLI, `gpt-5.6-luna`, medium reasoning
- **Run ceiling:** one provider invocation, zero retries, routes, escalations, or recovery actions
- **Verifier:** deterministic fixture-local JSON/oracle comparison; no model judge
- **Architecture status:** provisional; not a general provider layer or production runtime

This substrate qualifies one simple record-selection task through the existing
IRIS-X identity, contract-bound evidence, independent-verification, canonical
adjudication, terminal-record, and resource-accounting boundaries. Provider-
specific code stays in `scripts/run_qualification.py`; `irisx.core` contains no
OpenAI, Codex, or Luna type.

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
- HTTP-request and stream-reconnect retry counts fixed at zero;
- an output schema and a prompt that forbids every tool;
- API-key environment variables removed from the child process; and
- JSONL auditing that invalidates any observed tool attempt.

Codex CLI's provider transport count is not exposed, so the terminal resource
ledger records `network_calls` as `Unknown`. The one adapter-controlled logical
model invocation is recorded as `model_calls: 1`; token usage is preserved only
when the CLI event stream exposes it, and provider cost remains `Unknown`.

## Zero-call validation

From the repository root:

```powershell
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog
python -m unittest discover -s experiments\substrates\model-execution-qualification-v0\tests -v
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --preflight
```

None of those commands may execute `codex exec`.

## Single live invocation

Only after the definition/code freeze is committed and the tree is clean:

```powershell
python experiments\substrates\model-execution-qualification-v0\scripts\run_qualification.py --live --definition-commit <full-definition-commit> --code-commit <full-clean-head>
```

The command refuses an existing run directory, a dirty tree, non-full or
unresolvable commit identities, mismatched frozen artifacts, unavailable Luna
catalog entry, non-ChatGPT auth, or any API-key fallback requirement. It makes
at most one `codex exec` subprocess invocation and has no retry branch.

After that attempt, tests inspect the immutable run artifacts; they never invoke
the provider again.
