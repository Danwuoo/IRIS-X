# D1a Custodian Execution Remediation and Relaunch Handoff

- Terminal state: `remediation_in_progress`
- Status: **fourth exact-path repair frozen; admission A4 pending**
- Starting SHA: `586142b3652b68f60b09f43b0d8bf766a8b99da5`
- Branch / starting authority: `main` and `origin/main` both matched the
  starting SHA; the worktree was clean.
- Task/Oracle freeze SHA:
  `2c8fe1cc4a34484e25f3f87907ec26d78bbc9c22`.
- Task/Oracle bundle: `d1a-task-oracle-2026-09-15-v1`.
- Task/Oracle manifest SHA-256:
  `62fa935d7f02843cab2615dda8b9455d79c8bbcc9f6307841a9ddb95e1977564`.

## Failure evidence reviewed

- `docs/d1a-custodian-turn-b-collection-failure-report.md`.
- `docs/d1a-parallel-custodian-launch-handoff.md`.
- `docs/d1a-parallel-custodian-relaunch-handoff.md`.
- `docs/plans/TEMP_D1A_CUSTODIAN_RELAUNCH_CORRECTION.md`.
- Complete stdout JSONL and stderr logs for B1, C1, B2, and C2 under the two
  retained external-run roots recorded in the failure report.
- Exact original and corrected `Start-Process` launch commands recovered from
  their coordinator rollout records.
- The local Codex CLI installation, version, help, diagnostic output,
  environment, user config signals, and model-visible permission preflight.

## Root-cause findings

| Question | Finding | Evidence class |
|---|---|---|
| Requested sandbox | `workspace-write` in all launch records. | Directly observed |
| Effective model-visible sandbox | The deterministic preflight advertised a managed workspace-write profile, but every B1/C1/B2/C2 patch was enforced as read-only. | Directly observed |
| Requested approval policy | `never`. | Directly observed |
| Effective approval behavior | Sandbox escalation was unavailable and rejected writes were returned to the child. | Directly observed |
| Requested command/rule behavior | B1/C1 and B2/C2 used `--ignore-rules`; B2/C2 also moved the sandbox and approval flags to the global invocation position. | Directly observed |
| Effective command/rule behavior | SHA-256, Python, OpenSSL, `certutil`, direct .NET hashing, and some read commands were declined as `blocked by policy`. | Directly observed |
| Argument propagation path | PowerShell `Start-Process -ArgumentList` invoked the npm `codex.cmd` shim for CLI 0.147.0; process creation and CLI parsing succeeded. | Directly observed |
| Environment propagation path | Corrected launches replaced only API-key variables. `Start-Process -Environment` otherwise inherited the surrounding Codex Desktop control environment. | Directly observed for launch construction; inherited variable values at the historical child process are Unknown |
| Config precedence | `--ignore-user-config` removed the user config layer; explicit model, provider, effort, service tier, sandbox, approval, and rules flags were accepted. The later tool enforcement nevertheless diverged from the model-visible profile. | Directly observed |
| Host/runtime constraints | The failed path nested CLI 0.147.0 inside a newer Codex Desktop runtime and retained its surrounding `CODEX_*` control environment. Which individual inherited marker or 0.147.0 subsystem produced the enforcement divergence cannot be discriminated from retained evidence. | Inferred path defect; specific causal component Unknown |
| Working directory/write root | Each child read its disclosure from the intended external workspace, and the preflight named that workspace as writable; the tool router still rejected `output/` patches. | Directly observed |

The highest supported diagnosis is an **effective nested child launch-path
enforcement defect after CLI configuration parsing**. The retained evidence
does not justify attributing it to Terra or choosing one undocumented internal
override as the unique cause. The admission canary below directly falsified the
narrow hypothesis that pinning the newer desktop CLI and removing inherited
Codex control variables would by itself restore allowed hashing.

Model-free remediation probing subsequently established that the same pinned
CLI can place a command under the Windows restricted-token `:workspace`
profile: a file was created and hashed inside the exact workspace while a
sibling-path write was denied and no sibling file appeared. This supports a
second narrow repair: remove the defective inner policy layer with
`--dangerously-bypass-approvals-and-sandbox`, while enforcing the write root in
an outer OS sandbox created by the same pinned executable. Admission A2 will
test the complete nested model-visible path before either real launch.

## Narrow execution-substrate repair attempted

- Pin the exact desktop-bundled Codex executable at version
  `0.154.0-alpha.6.2` and SHA-256
  `081e4de4be8e38fac6ed4d95e3b1a0b9f6d31c090ddc36e1696b349fe406f575`
  instead of resolving the stale npm 0.147.0 shim through `PATH`.
- Remove the surrounding session's `CODEX_*` app/session/permission control
  variables from the child process environment while preserving only
  `CODEX_HOME` for the existing ChatGPT authentication record.
- Continue to clear API-key fallback variables.
- Keep explicit `workspace-write`, `approval_policy="never"`,
  `--ignore-user-config`, and `--ignore-rules` settings.
- Use one checked-in launcher for the model-backed canary and both final child
  launches. The only mode difference is that admission waits for collection;
  TURN-A returns after one immediate process-state observation.

The exact frozen configuration is
`experiments/d1a-warrant-discrimination-v0/execution-remediation-2026-09-15-v1/launch-configuration.json`.

## Second exact-path repair frozen for admission A2

- Outer command: pinned Codex `sandbox -P :workspace -C <workspace>`.
- Outer enforcement: Windows restricted token; exact isolated workspace is the
  only write root; managed requirements are not included.
- Inner command: the same pinned Codex `exec` with
  `--dangerously-bypass-approvals-and-sandbox`, `--ignore-user-config`, and
  `--ignore-rules`.
- Inner working directory: the same exact isolated workspace.
- Rationale: the bypass removes the model-visible command-policy layer that
  directly rejected A1 before execution; the outer restricted token retains a
  host-enforced filesystem boundary.
- Model-free boundary result: inside create/hash passed; outside sibling write
  was denied; outside file remained absent.
- Admission A2 identity:
  `d1a-execution-canary-terra-high-20260915-a2`.
- Admission A2 workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-execution-admission-canary-20260915-a2`.
- Admission A2 status: pending after this repair freeze is committed.

Admission A2 then exited before model inference or a model-visible tool call.
The outer restricted token correctly made the real user `CODEX_HOME` read-only,
but inner Codex startup attempted to create its arg0 aliases and open
`state_5.sqlite` there. Startup failed with access denied and read-only database
errors, stdout remained empty, and no canary output was created. This is direct
evidence of a runtime-state/write-root mismatch, not a Terra capability result.

The third repair assigns each child an isolated `.codex-home` under its exact
workspace. Before launch, the launcher copies only the existing `auth.json`
into that directory. Authentication remains available while arg0, state
database, authentication refresh, and other runtime writes remain inside the same
outer `:workspace` boundary. No credential is placed in `output/` or the
repository. Admission A3 will be the next short model-backed check.

- Admission A2 prompt SHA-256:
  `79dce8b2df1d8abe797de20550f03dd7bdf3bc9e3d7cd8142e4375f000d28af7`.
- Admission A2 launch timestamp: `2026-09-15T21:52:31.0396112+08:00`.
- Admission A2 PID: `14604`.
- Admission A2 completion timestamp: `2026-09-15T21:52:33.2548414+08:00`.
- Admission A2 exit code: `1`.
- Admission A2 stdout SHA-256:
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- Admission A2 stderr SHA-256:
  `15a2ac95ca6100de0a0d055855c1d39903e0bb405ca5e447d36a5b569b0e4f71`.
- Admission A2 backend/model-visible call evidence: none; stdout was empty and
  initialization failed before the in-process app-server client was created.
- Admission A3 identity:
  `d1a-execution-canary-terra-high-20260915-a3`.
- Admission A3 workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-execution-admission-canary-20260915-a3`.

Admission A3 passed runtime initialization and created a Codex thread, directly
confirming the isolated `CODEX_HOME` repair. The outer built-in `:workspace`
profile then denied all WebSocket and HTTPS service connections. No model
response or model-visible tool call occurred. The coordinator interrupted the
single canary after approximately 120 seconds to avoid an unbounded failed
session; no output artifact was created.

- Admission A3 prompt SHA-256:
  `8ec9138b5bff6e7c12c8356d99b0b2917b385ef0fa6f42a76329667cb38b576d`.
- Admission A3 CLI thread ID:
  `01a0a55b-aab9-7090-b906-e5a2ed6763db`.
- Admission A3 stdout SHA-256:
  `e574363d5656d672c4f43ab2d50be58362e754a7583ad8661298ae1367a63fc8`.
- Admission A3 stderr SHA-256:
  `ea6dc41c9d9c189e518538c31b643600496a7fd2170f01560dbcbfdbbd5b8bfa`.
- Admission A3 terminal disposition: coordinator-interrupted network-blocked
  admission; no model response and no scientific evidence.

Model-free A4 preflight defined `d1a_external` as `extends = ":workspace"`
with `network.enabled = true`. Under that profile, in-workspace create/hash
succeeded, an outside sibling write was denied, and a TCP connection to
`chatgpt.com:443` succeeded. Windows restricted-token processes could not use
the system certificate store, so the final configuration supplies Codex's
documented `CODEX_CA_CERTIFICATE` and `SSL_CERT_FILE` variables with a pinned
local certifi bundle. A sandboxed HTTPS probe completed TLS and received an
HTTP response. Admission A4 will qualify the full model-visible path.

- CA bundle SHA-256:
  `bbc7e9c01d7551bb8a159b5dedd989b8ee3ce105aff522b68eb1b01bf854cab0`.
- Admission A4 identity:
  `d1a-execution-canary-terra-high-20260915-a4`.
- Admission A4 workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-execution-admission-canary-20260915-a4`.

## Semantic C2 contract review

Verdict: `no_material_contract_defect`

The public action contract declares the supplied ledger to be the complete
initial state, defines the complete transition, and requires exact structural
equality for both the result and the complete post-state. Untouched fields and
entries are preserved by applying the declared transition to the complete
state; JSON object key order and insignificant JSON whitespace do not affect
structural equality. The frozen, conforming task instances therefore admit an
independent verifier without new hidden information or changed task truth.

Task/Oracle v1 changed by this review: **no**.

## Exact-path admission result

- Canary identity: `d1a-execution-canary-terra-high-20260915-a1`.
- Model / effort: `gpt-5.6-terra` / `high`.
- Prompt SHA-256:
  `55283b494219e4dde47767abc94129dd448055425cfec035b79ea2182efc6641`.
- Workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-execution-admission-canary-20260915-a1`.
- Executable / version:
  `C:\Users\wurre\AppData\Local\OpenAI\Codex\bin\bffc5354119c8421\codex.exe`
  / `codex-cli 0.154.0-alpha.6.2`.
- Executable SHA-256:
  `081e4de4be8e38fac6ed4d95e3b1a0b9f6d31c090ddc36e1696b349fe406f575`.
- Sandbox / approval / rules: `workspace-write` / `never` /
  `--ignore-rules`.
- User config: ignored; ChatGPT auth retained through `CODEX_HOME`; API-key
  fallback and surrounding Codex app/session/permission environment variables
  removed as enumerated in the frozen launch configuration.
- Launch timestamp: `2026-09-15T21:16:26.4917662+08:00`.
- PID: `8224`.
- Completion timestamp: `2026-09-15T21:16:43.9418779+08:00`.
- CLI thread ID: `01a0a536-31f9-7701-be08-8b51f21b2447`.
- Launcher process exit code: `0`; this was not accepted as capability success.
- Model terminal state: `execution_capability_blocked`.
- Direct failure: the first model-visible command, combining a read of
  `input/admission-sentinel.txt` with PowerShell `Get-FileHash`, was rejected
  before execution as `blocked by policy`.
- Required output `output/terminal-capability-record.json`: absent.
- Required `output/capability.txt`: absent.
- Admission result: **failed**. Read/hash, create/read/hash, update/hash, and
  outside-root enforcement could not all be demonstrated.
- Canary stdout SHA-256:
  `9092552966b922cb6bbf2e85063d20922044cdf069b741d82433fff591ce0eaf`.
- Canary stderr SHA-256:
  `6542306ba98d84dc944e0838f5bf2b191e151d3c8aef23c4c350be6319c67860`.
- Canary last-message SHA-256:
  `9c37a36636fb6057c19c3f6d0380364e24a405a9a355446ec95775aaca37ef15`.
- Token usage: 27,963 input; 13,056 cached input; 349 output; 178 reasoning
  output.
- Canary retries: `0`; the canary was not rerun.

## Fresh custodian launch disposition

Exact-path admission did not pass, so neither fresh custodian was launched.
The frozen but unused identities and paths are retained for provenance only:

- Authority authoring-session ID:
  `d1a-authority-terra-high-20260915-b3`.
- Authority workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-remediation-b3c3\authority-custodian`.
- Authority prompt SHA-256:
  `46a10212d7290e2d4b60b913290fd0dbd1a799211a9a42affb8bbd98f68d9464`.
- Authority model / effort: `gpt-5.6-terra` / `high`.
- Authority PID / immediate state / launch timestamp: not applicable; not
  launched.
- Semantic-verifier authoring-session ID:
  `d1a-semantic-verifier-terra-high-20260915-c3`.
- Semantic-verifier workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-remediation-b3c3\semantic-verifier-custodian`.
- Semantic-verifier prompt SHA-256:
  `d77550a90dbd9c12c34db5f3bceb2eafc1f6c0b7079143cc32f67ada9fa9f590`.
- Semantic-verifier model / effort: `gpt-5.6-terra` / `high`.
- Semantic-verifier PID / immediate state / launch timestamp: not applicable;
  not launched.

## Accounting and stop boundary

```text
prior failed custodian model calls: 4
new admission-canary model calls: 1
new Authority custodian calls: 0
new Semantic-verifier custodian calls: 0
new repository-initiated model calls: 1
cumulative custodian/remediation calls: 5
retries: 0
fallbacks: 0
routes: 0
escalations: 0
model judges: 0
subagents: 0
D1b producer calls: 0
```

No fresh custodian process or substantive child output exists to monitor or
collect. No Task/Oracle asset changed. D1a empirical qualification remains
`Not established`; F1-B/C/D/E and wider novelty remain unchanged or not
established; D1b and Phase 7 remain unauthorized.

Next action requires a new owner-authorized execution-path remediation scope.
TURN-B custodian collection is not applicable because no fresh custodian was
launched.
