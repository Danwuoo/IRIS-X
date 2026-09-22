# ARC-AGI-2 prompt pilot

This is the current status page for trial `arc-agi-2-prompt-pilot`, authorized
by Decision 0016. It is separate from closed Trial 001 and completed Trial 002.

## Goal

Measure whether instruction-only GEPA proposals can later improve a fixed
Qwen3.5-4B selected-output exact-match baseline without changing the solver,
parser, demonstrations, decoding, or data isolation. The current task covers
only baseline run `prompt-pilot-baseline-001`.

## Current state

- Status: `package-ready`; the exact staged bytes passed offline technical
  preflight, but no new external execution evidence is claimed until the exact
  submitted run supplies it.
- Split: 256 optimization-train, 128 selection-dev, 128 locked-holdout from
  pinned official public training; only the first 384 groups run now.
- Runtime: private Kaggle `NvidiaL4` x4, Internet disabled, USD 0 paid cost.
- Solver: `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Baseline: greedy pass@1, thinking disabled, 512 tokens, one generation per
  test-index-0 job, no retry or warm-up.
- Run identity digest:
  `861110e3df3d8f691cd73fe69ef9d08063821593e0bb89f5f398241d445ef74e`.
- Split digest:
  `6176d88ce9a66dcc45584aa09c110898c0f782b1f97e42e1f268c3ef1f25bd2b`.
- Truth-free outbound SHA-256:
  `22cd2d9449b8aaa0646d1baf1e5ba8ecb71c54b1a73fc761be5e8751c62eed24`.
- Exact runtime wheel SHA-256:
  `2afbe550c0d63947f3e1062193d9d10df9563ddd48c69fba14a6385248342f9b`.
- The retained Trial 002 result verifier regression reaccepted result digest
  `91b21a5fdae10d5adda5dc59e22626a92d1935f15e06ca5a35cf2eeac0b53097`.

## Stop boundary

After four identity-bound `model_ready` events on distinct L4 GPU UUIDs and
initial scheduler dispatch are retained, stop development and external
monitoring. Do not wait for completion, retrieve or score results, invoke Codex
reflection, or launch another candidate under Decision 0016.
