# D1a Parallel Custodian Corrected Relaunch Handoff

## Terminal state

`custodians_relaunched_stop`

This is a corrected TURN-A launch-only record. It contains no corrected child
result, output interpretation, or completion claim.

## Authority and frozen inputs

- Owner correction authorization: 2026-09-15, continue with
  `gpt-5.6-terra` / `high` after correcting the execution environment.
- Relaunch-scope freeze SHA:
  `93afec07d5bcb316096d447c04ebc1e2c8f1e824`.
- Frozen Task/Oracle SHA:
  `2c8fe1cc4a34484e25f3f87907ec26d78bbc9c22`.
- Task/Oracle bundle ID: `d1a-task-oracle-2026-09-15-v1`.
- Task/Oracle manifest SHA-256:
  `62fa935d7f02843cab2615dda8b9455d79c8bbcc9f6307841a9ddb95e1977564`.
- Authority disclosure ID:
  `d1a-authority-policy-disclosure-20260915-v1`.
- Authority disclosure manifest SHA-256:
  `35a6459c40751528cac210da5340db8d049176ec9eff0dc9101a8c759c9be030`.
- Semantic-verifier disclosure ID:
  `d1a-semantic-verifier-disclosure-20260915-v1`.
- Semantic-verifier disclosure manifest SHA-256:
  `af48f165a6b43eccbc58c9de6163f69f0f8001ea9532ba983339e4927f7de571`.
- All seven allowed files in each copied disclosure matched their frozen
  SHA-256 digests before launch.
- Each fresh child workspace contained exactly its eight disclosure/input
  files plus its frozen prompt; both output directories were empty.

## Corrected deterministic admission

- Provider: `openai`.
- Execution surface: `codex-cli 0.147.0` at
  `C:\Users\wurre\AppData\Roaming\npm\codex.cmd`.
- Model / effort: exact `gpt-5.6-terra` / `high`.
- Authentication: `Logged in using ChatGPT`.
- Sandbox: explicit global `workspace-write` rooted separately at each fresh
  external workspace.
- Approval policy: explicit global `never`.
- Exec-policy correction: `--ignore-rules`.
- User configuration ignored; model, provider, effort, service tier, sandbox,
  approval policy, and disabled features were explicit.
- API-key fallback environment variables were cleared for both launches.
- Sessions are ephemeral; multi-agent, app, browser, computer-use, plugin,
  remote-plugin, skill-search, tool-suggestion, hook, and image-generation
  features were disabled.
- A deterministic model-visible permission preflight showed a managed
  restricted profile with write access to the Authority workspace.
- Prelaunch stdin redirection was initially refused because the two prompt
  files had been marked read-only. No process or model call was created. The
  prompt attributes were corrected before the two launches below; prompt
  content and digests did not change.

## Corrected Child B — Authority-policy custodian

- Authoring-session ID: `d1a-authority-terra-high-20260915-b2`.
- Model / effort: `gpt-5.6-terra` / `high`.
- Prompt SHA-256:
  `2a2617fbd6d9dfca78cb9cde09b7263c92a170011bd001d074bde756b9535212`.
- Workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\authority-custodian`.
- Expected bundle:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\authority-custodian\output\authority-policy.bundle.json`.
- Stdout:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\authority-b2.stdout.jsonl`.
- Stderr:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\authority-b2.stderr.log`.
- Launch timestamp: `2026-09-15T09:24:18.7237837+08:00`.
- PID: `20476`.
- Sole immediate confirmation timestamp:
  `2026-09-15T09:24:18.7620430+08:00`.
- Immediate state: `process_created_running_at_immediate_confirmation`.

## Corrected Child C — Semantic-verifier custodian

- Authoring-session ID: `d1a-semantic-verifier-terra-high-20260915-c2`.
- Model / effort: `gpt-5.6-terra` / `high`.
- Prompt SHA-256:
  `d24ba1c9b73e840703ddb4f8e20f731188263ee63e7048614ff5b7fb98cb4e0d`.
- Workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\semantic-verifier-custodian`.
- Expected bundle:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\semantic-verifier-custodian\output\semantic-verifier.bundle.json`.
- Stdout:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\semantic-c2.stdout.jsonl`.
- Stderr:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c-relaunch-b2c2\logs\semantic-c2.stderr.log`.
- Launch timestamp: `2026-09-15T09:24:18.7671060+08:00`.
- PID: `30552`.
- Sole immediate confirmation timestamp:
  `2026-09-15T09:24:18.7776202+08:00`.
- Immediate state: `process_created_running_at_immediate_confirmation`.

## Accounting and stop boundary

```text
historical failed child model calls: 2
owner-authorized corrected child model calls: 2
cumulative repository-initiated child model calls: 4
corrected-launch retries after process creation: 0
fallbacks: 0
routes: 0
escalations: 0
model judges: 0
child subagents or follow-on sessions: 0
D1b producer calls: 0
```

After the one immediate confirmation for each corrected child, neither process,
log, output directory, expected bundle, nor terminal message was checked. No
corrected child output was monitored, collected, validated, inferred, or
interpreted.

## Required next action

The owner must issue a later explicit TURN-B collection request before any
corrected process status, log, handoff, bundle, validation, or substantive
result is inspected.
