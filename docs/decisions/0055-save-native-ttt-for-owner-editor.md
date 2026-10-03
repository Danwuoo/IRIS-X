# Decision 0055: Save the original native TTT notebook for owner Editor execution

Status: Accepted
Date: 2026-10-03 (Asia/Taipei)

The owner instructs: 「我不想等了，你重新提交成 quick save，我在 editor 跑，
notebook 結尾要把需要的檔案壓縮成 zip 供我下載」. The owner subsequently
reports personally cancelling native TTT 006. Preserve its immutable package,
accepted version-1 receipt and existing observations. Record owner-reported
cancellation without querying that session or inferring its actual model work.

Authorize exactly one distinct private `nvarc-original-qwen3-native-ttt-007`
`KernelExecutionType.QUICK_SAVE`, after exact offline verification and an atomic
single-save reservation. The owner will start it manually in Editor. An uncertain
or rejected save consumes this allowance; no fallback or automatic retry.
This direction supersedes Decision 0054's agent execution and monitoring workflow
for this notebook. Stop after saving the receipt. No agent cell execution,
status/log/output request, retrieval, Dataset mutation or resumed monitor follows.

Retain native 006's exact published Qwen3 SFT checkpoint, original pinned runtime,
41 source/metadata bindings, portable same-platform source cosine oracle, 128-view
epoch, 128 optimizer steps, 955,392 input tokens and 476,160 supervised tokens.
Retain four distinct BF16 L4s with one sequential rank-zero worker, official
competition mount, Internet disabled, USD 0 and the 1,500/1,200-second parent/child
limits. No generation, teacher call, checkpoint export, ARC scoring, promotion or
scientific threshold change is authorized.

Only identity/authority and owner-Editor download transport change. The notebook
finally packages its closed truth-free settings, material/hardware verification,
prepared tokens/labels, training/gradient/moment/fingerprint observations and logs
as `/kaggle/working/結果.zip`, with per-member sizes and SHA-256 digests. Keep the
complete uncompressed archive within 16 MiB. Both successful and handled failed
outcomes reach packaging; abrupt session termination may prevent finalization.
The final download cell checks the exact archive identity and can be rerun without
starting model work. Large model/optimizer tensors are outside this diagnostic
workload. The exact package and receipt are retained in
[`native-ttt-007-editor.md`](../../trials/arc-agi-2-qwen35-nvarc/native-ttt-007-editor.md).
