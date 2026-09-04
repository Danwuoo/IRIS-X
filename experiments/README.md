# Experiments Work Area

This area contains explicit, reproducible experiment definitions and reviewed outputs.

- [configurations/provider-model-baseline-v0.json](configurations/provider-model-baseline-v0.json) is the accepted machine-readable OpenAI/Codex baseline with explicit GPT-5.6 Terra `strong` and GPT-5.6 Luna `cheaper` roles. It authorizes no model call by itself.
- [exp-2026-08-28-docops-readonly-baseline](exp-2026-08-28-docops-readonly-baseline/README.md) defines the Phase 3 fixed-distribution comparison of two local narrow controls. Its run artifacts keep definition, raw episodes, aggregates, and interpretation separate.
- [exp-2026-08-30-source-snapshot-assertion](exp-2026-08-30-source-snapshot-assertion/README.md) records the H-M1a registered-snapshot assertion challenge and reviewed run.
- [exp-2026-08-30-docops-acceptance-verification](exp-2026-08-30-docops-acceptance-verification/README.md) records the frozen H-V1a acceptance-policy challenge set and reviewed paired run.
- [exp-2026-08-30-docops-profile-instrumentation](exp-2026-08-30-docops-profile-instrumentation/README.md) records the frozen H-O1a profile contract and reviewed paired instrumentation run.
- [exp-2026-08-30-docops-evidence-binding](exp-2026-08-30-docops-evidence-binding/README.md) records the frozen H-V1b path/hash evidence challenge and reviewed paired run.
- [exp-2026-08-30-preexecution-write-interception](exp-2026-08-30-preexecution-write-interception/README.md) records the frozen H-I1a copied-workspace mutation/interception definition and reviewed paired run.
- [exp-2026-08-31-process-lifetime-stability](exp-2026-08-31-process-lifetime-stability/README.md) records the separately frozen H-OR1a fresh/long-lived process comparison.
- [exp-2026-08-31-reversible-cycle-state-stability](exp-2026-08-31-reversible-cycle-state-stability/README.md) records the separately frozen H-SR1a fresh/persistent copied-workspace cycle comparison.
- [exp-2026-08-31-targeted-recovery-valid-state](exp-2026-08-31-targeted-recovery-valid-state/README.md) records the separately frozen H-RCV1a detect-only/targeted-recovery comparison.
- [substrates/docops-robustness-v0](substrates/docops-robustness-v0/README.md) and [substrates/config-regression-v0](substrates/config-regression-v0/README.md) qualify robustness and change-reliability measurement sensitivity without claiming system performance.
- [substrates/docops-generated-heldout-v0](substrates/docops-generated-heldout-v0/README.md) qualifies four IRIS-X-authored deterministic generator families using development-visible seeds only.
- [substrates/model-specialization-v0](substrates/model-specialization-v0/README.md) qualifies provider-neutral success/failure terminal paths with deterministic fake candidates and zero model calls.
- [substrates/minimal-reliable-execution-v0](substrates/minimal-reliable-execution-v0/README.md) contains the single local deterministic post-Phase-4 vertical slice for identity, policy, execution, independent verification, adjudication, and terminal-record boundaries. It is not a production runtime or a new model experiment.
