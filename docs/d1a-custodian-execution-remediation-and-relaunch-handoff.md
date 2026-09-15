# D1a Custodian Execution Remediation and Relaunch Handoff

- Status: **remediation definition frozen; admission pending**
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
isolation/enforcement defect after CLI configuration parsing**. The retained
evidence does not justify attributing it to Terra or choosing one undocumented
internal override as the unique cause.

## Narrow execution-substrate repair

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

## Admission and launch record

This section will be completed only from the authorized canary result and the
single immediate confirmation of each fresh child. No scientific child output
will be inspected during TURN A.

- Admission canary: pending.
- Authority child: pending.
- Semantic-verifier child: pending.
- New model calls: `0 / 3`.
- Prior failed custodian calls preserved: `4`.
- Cumulative custodian/remediation calls: `4`.
- Next action if admission passes: launch both fresh custodians and stop for an
  owner-authorized TURN-B collection.
