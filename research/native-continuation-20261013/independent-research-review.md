# Independent research and baseline review

Date: 2026-10-13 UTC. Starting commit: `2901a97a1aa934d15e468e3e6d57bd96d95791e9`.

## Decision and scope

The reviewed research documents are suitable for preserving the proposed scientific rationale, with the limitations below. This is a documentation/research review and an inherited CPU baseline receipt. It is **not** final run008 loader/integration approval, GPU admission, provider publication approval, evidence of scientific improvement, or a full-project green claim. No evaluator answer files or raw evaluator grid bodies were inspected. No historical source was edited, no provider call was made, and no commit or push was performed by this reviewer.

The initial method paragraph ambiguously placed held32 before PUBLIC. The author corrected it, and the exact reviewed text now matches the frozen order: A/B/C dev16; freeze selected arm; selected-arm PUBLIC predictions; A/B/C held32 predictions; model closure; held and original PUBLIC scoring. Decision0075 now correctly names the existing repository's public visibility and restricts publication to reviewed, sanitized project material; the earlier private-repository wording is superseded.

The new files contain aggregate research, repository-relative sources, hashes and bounded operational claims. Inspection found no credentials, private conversation excerpts, personal availability, evaluator grid bodies or absolute private execution paths. This finding covers the listed documents, not unreviewed runtime files or pre-existing repository history.

## Research findings

- The current source contract is A=SFT256, B=up to four disjoint 64-slot batches covering 32 fixed parents with eight samples each, and C=extra SFT matched to B's whole extra model-phase wall time. The older SFT64/full-256-sweep protocol review is historical and cannot approve current final bytes.
- `rl_session/plan.py`, `owned_runtime/planning.py` and `MEASURED-POLICY.json` agree on those allocations, immutable thresholds, no TTT in this comparison, fixed dev selection, reused held32 and the 120-task/167-query PUBLIC denominator.
- `reviewed/rl_math.py` supports the report's narrower description: exact binary rewards, centered groups, equal-sequence weighting, detached DDIS-style ratios and strict clipping. It does not implement every component of GRPO/PPO. Different B/C learning rates make this an intervention-package comparison.
- The stated historical aggregates match the relevant committed reports: Trial002 0/4; compact A/AT 1/3 versus B/C 0/3; modified-input native TTT 5/172 to 10/172; Stage3 official exception with null scores; uncapped top1/top2/pool oracle 1/6 with 512 updates, 24 batches/96 views and 41 distinct candidates; and the already-inspected portfolio panel's 2/6 to 5/6, retrospective 6/6. These are separate evidence chains, not comparable replications. No large historical prediction artifact was independently rescored.
- `COST-EVIDENCE.json` records 323.347121794 seconds for SFT256 and 334 public generation views totaling 7403.353845082 seconds. It explicitly limits itself to cost, timing and packing. The referenced v25 science-summary bodies are absent; this review infers no v25 accuracy.
- The sanitized transfer summary exactly matches the authenticated transfer summary for archive metadata, 17 normal plus 17 optimized tests, 283 source files and 426 candidate files, and its referenced rebuild-report SHA-256. That is CPU source reproduction, not a cuDNN or GPU result.

Important checked primary repository sources include `trials/arc-agi-2-baseline/README.md`, `trials/arc-agi-2-qwen35-nvarc/compact-abc-005-editor-diagnosis.md`, `public-eval-notebooks-001-diagnosis.md`, `stage3-official-score-001.md`, `research/arc-next-line/uncapped-result/README.md`, and `research/qwen-portfolio-20261012/{PLAN.md,panel-plan.md}`. The external method report remains a research synthesis rather than a replication: independent spot checks confirm TRM's 44.6/7.8 public results and roughly three days on four H100s, ProRL's approximately 16k H100 GPU-hours, NVARC's four eight-H100 nodes for 27 hours and disclosed public-task description exposure, and NVIDIA's split-library/runtime loader dependency guidance. Sources: [TRM original paper](https://arxiv.org/html/2510.04871v1), [ProRL original paper](https://arxiv.org/html/2505.24864v1), [NVARC original paper](https://github.com/1ytic/NVARC/blob/main/nvarc_2025.pdf), [NVIDIA cuDNN runtime guidance](https://docs.nvidia.com/cudnn/installation/build-run-cudnn/).

## Remaining scientific and verification limits

1. Four or fewer updates on 32 parents are a signal/mechanism pilot. A null outcome does not settle broad RL capability, and a positive outcome needs an independently frozen task/family replication. Report paired gains/losses and uncertainty at the task-parent level; transformed views are not independent samples.
2. All-zero/all-one groups and forced tokens can hide absence of usable gradient signal. Retain mixed-parent counts, nonforced-token replay gaps and actual contributing work. An incomplete audit is not a clean zero-signal result; prior complete B commits and later not-reached slots must remain distinct.
3. Reused held32 and historical PUBLIC exposure remain limitations even with perfect current-run seals. A withheld training demonstration may already have appeared under SFT or augmentation. Maintain ancestor exposure rather than claiming semantic novelty from exact-byte deduplication.
4. A public-view timing surrogate is not measured stochastic RL replay/backward cost. Hard deadlines, actual charges, rollback, save/reload overhead and explicit unmatched C status matter. Neither idle padding nor tolerance changes may manufacture a matched comparison.
5. Synthetic ELF tests can falsify an unsafe loader search policy but do not prove actual cuDNN split-library selection, Torch kernels, 14B memory/numerics, throughput or four-L4 deployment. Final integrated bytes and fresh process topology need separate independent review and tests.
6. A provider terminal state, valid closure, preserved predictions, completed scoring and scientific success are separate gates. No available result supports promising 151/167.

## Baseline CPU validation

Tests ran in fresh normal and optimized Python 3.12.14 interpreters with PYTHONHASHSEED=0, offline model flags, bytecode disabled, repository-backed temporary storage (over 29 GiB available), and the verified local Git-object alternate with lazy fetching disabled. No missing historical fixture was invented and no failure was suppressed.

- Repository validator self-tests: 3/3 pass in each mode.
- Historical cuDNN mapping/consumer tests: 21/21 pass in each mode, including genuine synthetic shared-library subprocesses.
- Installer logging tests: 26/26 pass in each mode, including timeout/cleanup paths.
- Process ownership guard tests: 10/10 pass in each mode, including parent death, detached descendants, PID-reuse rejection and closure proof checks.
- Repository invariants: fail in each mode, also fail after the reviewed documentation edits. Seven existing README-term assertions remain: Engineering Trials, Decision 0010, Decision 0012, Decision 0014, Decision 0015, Trial 001 status page and ARC-AGI-2. They were not repaired or waived by this review.
- Direct source-tree flow discovery: 35 tests, 8 error events in each mode because assembled baseline panel/config fixtures are absent from that source-only directory.
- Direct support discovery: 109 tests, 74 errors and 2 failures in each mode. Missing historical sibling trees and wrapper/environment fixtures prevent those paths from executing; two rejection-message expectations encounter missing prerequisites first. These are explicit baseline blockers, not a claim that run008 introduced regressions.
- The first replay against the authentic assembled tree resolved missing configuration but exposed a test-launch import-root mismatch (foreign checkout module), retained separately. A corrected isolated replay and additional neural/runtime checks are in progress; they are not counted as passes here.

Reproduction commands (repository root; use the environment described above):

```sh
python -B tools/repository_check.py
python -B tools/repository_check.py --self-test
python -B tools/arc_qwen_rlvr004_20261013/cudnn_mapping_repair/test_cudnn_mapping.py -v
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/installer_logging_repair -p 'test*.py' -v
python -B -m unittest discover -s tools/arc_learning_agent_20261011/tests -p test_process_guard.py -v
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/source/experiment_flow/tests -p 'test*.py' -v
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/support/tests -p 'test*.py' -v
```

Repeat with `-O` immediately after `-B`. Full commands, return codes and original logs remain in ignored local review evidence; they are not uploaded with this sanitized report. An isolated ignored CPU environment now imports torch 2.8.0+cpu, transformers 5.8.1, peft 0.21.0 and tokenizers 0.22.2 successfully; CUDA is unavailable. Official CPU Torch and PyPI packages were used, without CUDA wheels, model downloads or credentials. This test environment is deliberately not a claim of exact Kaggle environment equivalence (including its Python patch version).

## Exact reviewed document bytes

- `AGENTS.md`: `0c479f83b50c7687d1d086382ec43eb7336b1dc1179997e1e1e97cd2eef78f72`
- `README.md`: `0aa80ea666ccc77b1119ffeda6000ff407293c005eefcc60d075e304d3e36b61`
- `docs/decisions/0075-continue-native-research-with-terminal-monitoring.md`: `02ff20b868de0dd468d2af87e697f99e63e6cd6ce4a406fcf99f99e74cc039f7`
- `docs/plan/2026-10-13-native-research-continuation.md`: `0ad20790ba9cbebee9a1f0b63e033687354374b001b27ef11c6d437d1e2b8392`
- `research/native-continuation-20261013/historical-experiments.md`: `36d2e3061dec1e07f605f885c9e28fdf82e0b8441dd00a3bee7b0c03494b2e34`
- `research/native-continuation-20261013/primary-method-assessment.md`: `26f1ade5a5393deffc5de9e79dabb9f7e44a05ff1d9c572d089f6fffd5fb9efe`
- `research/native-continuation-20261013/transfer-verification.json`: `5bc0f5ff5fafc8427689c3a60657290d66a628b8f5854fe93c3179dc08099da1`

## Inspected baseline source identities

- `tools/repository_check.py`: `f25c0d16b450707cddecb8ada1909c72f3ce50e2e8a6b98b081bcb2e10427d9c`
- `tools/arc_qwen_rlvr004_20261013/source/rl_session/plan.py`: `73fb2f1197270c821a9bb8f39653db5529609145ccb84a8173d4bd476f43ff02`
- `tools/arc_qwen_rlvr004_20261013/source/owned_runtime/planning.py`: `d966298f1b77d87bd391eeebbad99fb7bc4f2e65cbbfdbe6438bc126921bb5f2`
- `tools/arc_qwen_rlvr004_20261013/source/design/MEASURED-POLICY.json`: `3d278b7478fa859e23d60a69b5a12ae2a26964ea774354691aa7bc11dbb84bda`
- `tools/arc_qwen_rlvr004_20261013/source/design/COST-EVIDENCE.json`: `ae7dbc7584fe9f54db0444f54c72fed8ac2b56031d74f1e0d18f46bb38c8b1f2`
- `tools/arc_qwen_rlvr004_20261013/source/reviewed/rl_math.py`: `3de11b818eccb6a6bd8896245005a010abc3d930f04982490cfba79e0306b65a`
- `tools/arc_qwen_rlvr004_20261013/cudnn_mapping_repair/environment_v2.py`: `3d958c3707d14967977278b81581c57626eedd6ac9614384941cc70c058aa9e6`
- `tools/arc_learning_agent_20261011/process_guard.py`: `8bc66ac80499203bca9f583f0d5ea5ecc5d8a131a2aa267f661060fc69e0580c`
