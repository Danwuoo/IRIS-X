# Original NVARC continuation acceptance (2026-10-03)

Reviewed main commit: `a9abaef799d1460dc134f2d2f0d437ae577c0a5d`.
Comparison base: `e325fea`. The owner requested acceptance of the completed
continuation chat. This is a local engineering/evidence review, not another
Kaggle execution, quota query, teacher invocation or ARC evaluation.

## Decision

Accept the bounded implementation and retained observations. Do not accept
the original NVARC reproduction gaps as fully closed. No new blocking defect
was found in the critical packing, accumulation, native epoch guards and
evidence paths inspected here. Passing local controls does not qualify an
unexecuted original-runtime epoch, full training or solver quality.

The existing source/model material, failed versions, receipts and exposure
bindings remain immutable. Review outputs are separate under
`.irisx/nvarc-original/review-20261003-001/`. No provider request was made.

## Independently checked results

| Area | Acceptance evidence | Limit |
| --- | --- | --- |
| Original published ARC-SFT material | Re-read all ten files and all 399 actual finite BF16 tensor byte digests; material `sha256:27de51ef22658a0cce3a9fc04fac8fc456165645e2665a82b215f72e20194b03` matches | Published weights acquired; their training was not reproduced and clean exposure is not established |
| Original-family numerical probe 004 | Fresh closed-archive reader exactly reproduces the retained proof: 504,864 full logits and 38 sampled state slices agree bitwise; two tiny backwards and later-sample isolation pass | Qualifies the segmented GEMM/varlen variant on the fixed batch; historical NeMo/Unsloth parity remains open |
| Packed full-gradient step 002 | Fresh reader reproduces all four rank ledgers, 31 real plus one dummy outer forward, one global-256 AdamW step, 916,739 source input tokens and changed finite global weights | One cold step took 446.777 seconds; no model/optimizer checkpoint export, sustained throughput or full SFT |
| Native TTT 004 | Fresh strengthened reader reproduces all 28 data members, actual native preparation, 50 completed forwards/backwards, 373,200 input tokens and 49 AdamW steps | Failed before optimizer index 49; full 128-view epoch, final moments and trained-state reset remain unverified. The first AdamW step has zero learning rate |
| Native TTT repair 006 | Exact inert package preflight and all 129 pinned-source scalar schedule indices recheck locally; actual local oracle matches the Windows reference exactly | No execution journal/provider request exists; GPU completion/reset is still an unmet acceptance gate |
| Complete published SDG join | Independently recount 2,244,042 input/output response records, all 103,223 published puzzles and 2,984,385 pairs; all ordered-parent/SID bindings match the retained proof | Metadata/structural reconciliation is complete; generated-program semantics and full source filter replay are not |

The native 004 stderr reports `exact native cosine learning rate required`.
The retained scalar Windows/Linux replay first differs at the same index by
one ULP, but the rejected Kaggle float was not retained. The cross-platform
explanation is supported inference, not a recovered runtime value. Repair 006
requires exact optimizer equality to the same-platform pinned source oracle;
its four-ULP allowance applies only to the cross-platform reference comparison.

The independent SDG recount confirms 43,936 published `nvarc_full` members
without twenty retained same-order output responses. Historical CLI/group
selection remains unknown. Twenty responses are only a necessary condition
for twenty usable programs; neither structural checks nor the partial
ten-program diagnostic establish the full SDG recipe.

## Validation

Fresh repository validation passes: 386 discovered tests, four optional ML
skips, plus validator/layout/whitespace checks. The review additionally runs
24 actual ML differential/control tests with no skips, including original
Qwen3 packing/gradients, unequal-rank accumulation, checkpoint backward,
segmented linear restoration, BF16 Adam guards and static prefix recovery.

| Retained review output | SHA-256 |
| --- | --- |
| `repository-check.log` (345.079-second discovered test suite) | `79a7a11fbc705030cb6c850b603ad620ec0bf834f9eb97bd60902a8b6f25e320` |
| `focused-ml.log` (24 tests, 70.875 seconds) | `b321b2eedca4a0c84be9ed85d83046ea4d2a2dc5354751fc5028107c69ae1a03` |
| `nvarc-original-qwen3-probe-004-verification.json` | `5287640750119929edf156e5b99e0c40cdac6b425c193e78c65514615262dac1` |
| `nvarc-original-qwen3-packed-step-002-verification.json` | `f61c126d7230d84036ba3204b979219d15eb341b309f64e7ae672ea4685853d9` |
| `nvarc-original-qwen3-native-ttt-004-verification.json` | `11e8c1f62bc122aec4f3b0ada30aaf51cdbb7b82d8b840b51675dadbb9bf4629` |
| `published-sft-material-check.json` | `232a21c9a03ff3eb931b3919225312351ecd6cbfab089e47ecd77027b556e067` |
| `sdg-groups-verification.json` | `c47091e46f9b4748419765903d388bfb37dd2024eb267434fa7b5ef282b4f88c` |
| `native-006-offline-check.json` | `69e1ed38580830d8c693abd2fcff3ca0e799de26c6d87e6282c2bd69101732ba` |

The first scalar review harness chose the optimizer-only material directory,
which lacks the separately acquired `training_args.py`. Its failed log is
retained; the corrected check uses the existing exact dependency layout and
is the successful observation above. This did not mutate candidate bytes.

## Remaining acceptance gates

1. Complete original-runtime TTT 006 on GPU: all 128 views/steps, finite final
   moments, measured memory/time, optimizer discard and exact trained-state
   reset. Snapshot 015 at staging did not admit its conservative free-quota
   reserve; this review makes no claim about current account availability.
2. Establish original NeMo/Megatron identities and numerical/config parity;
   implement and verify sustained original-Qwen3 whole-corpus SFT with durable
   process restart and model/optimizer export before all 12,716 steps. The
   reusable `arc_nvarc_source_sft` runner still has the Qwen3.5 multimodal loader
   and layer topology; the new Qwen3 runner is deliberately a one-step probe.
   Previous Qwen3.5 resume/export evidence cannot qualify this original path.
3. Reproduce whole-archive SDG input/output program execution and unchanged
   source acceptance gates, with historical response-count/group differences
   resolved. Original teachers have not been regenerated.
4. Complete original TRM version/scale evidence: exact notebook v18, full
   pretraining and 2,000-epoch task adaptation. This continuation adds no
   original-scale TRM run.
5. Run an isolated, genuinely independent ARC quality comparison after the
   method/training prerequisites exist. No accuracy, generalization, promotion
   or competition-submission claim is accepted here.

The next concrete gate is the complete native TTT epoch/reset, subject to a
fresh free-resource check. Full SFT and SDG/TRM/quality gates remain separate
work; this review does not start or resubmit any of them.
