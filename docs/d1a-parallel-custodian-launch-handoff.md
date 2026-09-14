# D1a Parallel Custodian Launch Handoff

## Terminal state

`custodians_launched_stop`

This is a TURN-A launch-only record. It contains no child result, output
interpretation, or completion claim.

## Repository and frozen Task/Oracle

- Starting SHA: `9a7e9824bb0dbc28ef212626a7da6016a6f7c071`.
- Task/Oracle freeze SHA: `2c8fe1cc4a34484e25f3f87907ec26d78bbc9c22`.
- Task/Oracle bundle ID: `d1a-task-oracle-2026-09-15-v1`.
- Task/Oracle manifest SHA-256:
  `62fa935d7f02843cab2615dda8b9455d79c8bbcc9f6307841a9ddb95e1977564`.
- Frozen validation state: `independence_supported`; schema, provenance,
  information boundary, asset digests, manifest seal, focused outcome checks,
  full D1a deterministic tests, and repository validation passed before launch.
- No Task/Oracle contract, instance, outcome rule, post-state rule, or truth
  label was changed after the freeze commit.

## Frozen disclosures

- Authority disclosure ID:
  `d1a-authority-policy-disclosure-20260915-v1`.
- Authority disclosure manifest SHA-256:
  `35a6459c40751528cac210da5340db8d049176ec9eff0dc9101a8c759c9be030`.
- Semantic-verifier disclosure ID:
  `d1a-semantic-verifier-disclosure-20260915-v1`.
- Semantic-verifier disclosure manifest SHA-256:
  `af48f165a6b43eccbc58c9de6163f69f0f8001ea9532ba983339e4927f7de571`.
- Disclosure isolation check: both copied workspaces contained only their nine
  allowed frozen files; no held-out or oracle path was disclosed.

## Deterministic Codex admission

- Provider: `openai`.
- Execution surface: `codex-cli 0.147.0` at
  `C:\Users\wurre\AppData\Roaming\npm\codex.cmd`.
- Model: exact alias `gpt-5.6-terra`.
- Reasoning effort: `high`.
- Authentication mode observed before launch: `Logged in using ChatGPT`.
- Billing mode: `chatgpt-subscription`; run-attributable provider cost remains
  `Unknown`.
- API-key fallback: disabled for both child process environments.
- Sandbox: `workspace-write` in each isolated external workspace.
- Approval policy: `never`.
- User configuration ignored; provider, model, effort, service tier, sandbox,
  and approval policy were explicit.
- Sessions were ephemeral. Multi-agent, browser, computer-use, app, plugin,
  remote-plugin, skill-search, tool-suggestion, and hook features were disabled.
- Same-model correlated-failure risk remains a later limitation; separate
  sessions and disclosures do not establish independence of model failure modes.

## Child B — Authority-policy custodian

- Authoring-session ID: `d1a-authority-terra-high-20260915-b1`.
- Model / effort: `gpt-5.6-terra` / `high`.
- Prompt SHA-256:
  `9e6c8e760a032277e56ed4eb834c27491911ba8540d466d1eb43358e500fa329`.
- Workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\authority-custodian`.
- Expected bundle:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\authority-custodian\output\authority-policy.bundle.json`.
- Stdout:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\authority.stdout.jsonl`.
- Stderr:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\authority.stderr.log`.
- Launch timestamp: `2026-09-15T01:18:29.2960004+08:00`.
- PID: `29144`.
- Sole immediate confirmation timestamp:
  `2026-09-15T01:18:29.3268322+08:00`.
- Immediate state: `process_created_running_at_immediate_confirmation`.
- Launch attempts: `1`; retries: `0`; fallbacks: `0`; routes: `0`.

## Child C — Semantic-verifier custodian

- Authoring-session ID: `d1a-semantic-verifier-terra-high-20260915-c1`.
- Model / effort: `gpt-5.6-terra` / `high`.
- Prompt SHA-256:
  `47867c39ee91d1f42dc52f80b95a00310a5f721acfc05a6c74756bd84e7ca1d8`.
- Workspace:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\semantic-verifier-custodian`.
- Expected bundle:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\semantic-verifier-custodian\output\semantic-verifier.bundle.json`.
- Stdout:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\semantic-verifier.stdout.jsonl`.
- Stderr:
  `C:\Users\wurre\.codex\external-runs\d1a-custodians-20260915-freeze-2c8fe1c\logs\semantic-verifier.stderr.log`.
- Launch timestamp: `2026-09-15T01:18:48.2173786+08:00`.
- PID: `29348`.
- Sole immediate confirmation timestamp:
  `2026-09-15T01:18:48.2426223+08:00`.
- Immediate state: `process_created_running_at_immediate_confirmation`.
- Launch attempts: `1`; retries: `0`; fallbacks: `0`; routes: `0`.

## Execution accounting and boundary

```text
repository-initiated child model calls: 2
Authority child calls: 1
Semantic-verifier child calls: 1
retries: 0
fallbacks: 0
routes: 0
escalations: 0
model judges: 0
child subagents or follow-on sessions: 0
D1b producer calls: 0
```

After each sole immediate confirmation, that child process, stdout, stderr,
output directory, and expected bundle were not checked again. No child output
was monitored, read, validated, collected, inferred, or interpreted in TURN A.

## Required next action

The owner must initiate a separate, explicitly authorized TURN-B collection
task before any process status, child log, terminal handoff, bundle, validation,
or substantive result may be inspected.
