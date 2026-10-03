# Original NVARC continuation acceptance (2026-10-04)

Reviewed main: `4ee7e6187391559001b9907d3d003d009a0b1d84`.
Comparison base: `c6e17968c2487db5289433144d59949a3a98ca42`.
The owner requests complete acceptance of the finished
**NVARC 原生 TTT 完整驗證與原版 SFT 開發** chat.
This review covers its five commits, the shared training/checkpoint/process
changes, original-family SFT policy and inert transport, native Editor
007/008 packages, and locally returned evidence.

## Acceptance decision

Accept the bounded engineering and the complete native TTT epoch/reset
observation. No blocking implementation defect was found in the critical
paths inspected and exercised. The standard optional ML profile omitted the
new original-Qwen3 SFT strict module; this review adds it and verifies the
entire resulting profile. No method, acceptance threshold or consumed
scientific package changes.

Full original NVARC reproduction remains incomplete. Native 008 closes
training for one source-derived long-task epoch using the pinned **published
ARC-SFT checkpoint**. It neither reproduces that checkpoint's SFT nor
demonstrates trained solver accuracy. The new original-family SFT code passes
CPU controls; its GPU restart/export package remains unsubmitted.

All consumed packages, receipts, journals, returned ZIPs, prior observations
and original runner bytes recheck unchanged. Native 006 remains owner-reported
cancelled and unqueried. Decisions 0055–0056's saves are consumed, and their
owner-Editor restrictions remain. This acceptance makes no provider request,
GPU run, external teacher call, Dataset mutation or ARC score. The completed
Goal's timer remains paused.

## Independently checked evidence

| Area | Fresh acceptance check | Practical limit |
| --- | --- | --- |
| Native 008 closed evidence | Fresh reader exactly reproduces the frozen proof; all 36 data members, saved plan, payloads, material bindings, receipt and journal hashes match | Local re-reading of owner-supplied evidence; no provider state query |
| Complete native epoch | 128 distinct prepared rows, 128 forwards/backwards/AdamW steps, 955,392 input and 476,160 supervised tokens; all actual rates match the same-platform source oracle | One sequential rank-zero model worker on a verified four-L4 allocation; no solve or generation |
| Native trained state/reset | All 506 saved tensor fingerprints individually change and all 506 restore the seeded baseline; 506 finite terminal BF16 Adam states reach step 128, with 528,564,224 parameter elements | Hash inventories and runtime observations are retained; GPU tensor and Adam bytes are not exported |
| Native timing/memory | Training/worker/parent: 862.043/974.204/1,068.026 seconds; CUDA allocated/reserved peak: 13,897,781,248/15,451,815,936 bytes | This observed epoch, not sustained SFT throughput or historical-clock parity |
| Preserved native 007 failure | Fresh reader reproduces the frozen 97-forward/96-step timeout prefix and its exact archive digest | No full epoch, terminal moments or reset is inferred for 007 |
| Original source prefix | Rehash the corpus's 53 closed members; re-read all first 512 shuffled rows and independently encode every message with the actual original WordLevel tokenizer; tokens, labels, lineage and exposure match | Complete source mixture remains exposed reproduction material; no clean evaluation claim |
| Original-family SFT controls | Three tiny two-rank steps, 12 actual forwards including dummy work, 114 physical/108 source input and 27 supervised tokens; every model/Adam/RNG/scheduler state resumes exactly, matches the unpacked oracle, and all 25 export/reload state tensors match | Actual CPU synthetic fixture on Torch 2.12.1 / Transformers 5.8.1; no original 4B GPU restart/export observation |
| Checkpoint failure controls | Failure after restore preserves the previous committed checkpoint; a partial step-2 transaction remains untouched and the next attempt uses a distinct directory | Controlled process restart/failure tests; no power-loss durability test |
| Original SFT 001 proposal | Exact offline preflight succeeds with unchanged plan `sha256:c14678e802c97247110af4c5ab2864d654f21d44d658e8a7df7a491c45139dbe`, two global-256 steps and at most 60 outer forwards | Only `package-l4` exists; no execution journal, submission or GPU result |

Native 008's archive SHA-256 is
`2a8acbc25e5f4b673e3982c550914728ddf8db350191cc4b9cf823db8014dfec`.
The independent proof SHA-256 is
`33ecfdcaecb4b1967a026ac5d1871af66d64cc75c782019657641d0e17b7e4b4`.
Training loss spans 0–0.0022874773; it is not an ARC exact-match score.

The original SFT proposal requires **98,775,862,272 bytes** of durable
working space: two full FP32 model/Adam checkpoint transactions, the BF16
export and a 4 GiB reserve. The previous verified Qwen3.5 run observed
20,938,477,568 working bytes; its much larger scratch disk was ephemeral.
This is a historical resource comparison, not a current Kaggle capacity
measurement or a failed original SFT submission. Discarding optimizer state
or substituting scratch cannot establish the proposed durable restart/export.

## Validation and retained records

`python tools/repository_check.py --all` passes: **405 discovered tests,
four optional skips**, validator self-tests, repository invariants and
whitespace checks. The discovered suite takes 254.948 seconds.

The amended `tools/nvarc_ml_profile.py` passes **63 actual ML tests with no
skips**, in 421.943 seconds. These cover original Qwen3 packing and SFT,
shared Qwen3.5 accumulation/resume/export, TTT reset, source differentials,
TRM, SDG replay and runtime controls. They do not qualify full-scale GPU work.

The small [durable evidence record](configs/original-acceptance-20261004-evidence.json)
binds all fresh proofs, source recounts, local logs, the profile correction and
unsubmitted package. Review outputs live separately under ignored
`.irisx/nvarc-original/review-20261003-002/`; the directory was allocated before
the local date changed and is retained under that exact name.

| Review record | SHA-256 |
| --- | --- |
| Full repository validation log | `7ad7f9938f2968667576960987a8aa3370695a3d908c449144e1533178944974` |
| Complete strict ML profile log | `c3962b2df0ea02249348415a4de0215a960226493815b7e5a257bbf9de61bf04` |
| Independent native 008 recount | `89aa605de8a7ce386bb448bba3329ad0ce0c7252a39718776435612a9d13c86e` |
| Independent original WordLevel prefix recount | `ab4aa35b0041e7fdd26c305475b08a9192576802fc257351f0a6aebd573a8d28` |
| Unchanged original SFT package preflight log | `23918ef0d97378a62df9a4a85b4ab71594836432a06f9f369e18cdd2047093af` |

## Remaining acceptance gates

1. Complete the original-runtime **TTT → solve → inverse/dedupe → ranking →
   reset** loop, including cache/numerical controls, source generation
   thresholds, nonempty candidate ranking and second-task isolation. The
   full 008 training epoch has zero generations and cannot qualify this loop.
2. Verify original-family 4B GPU SFT durable process restart, full model/Adam
   retention and HF export/reload. Establish sustained rate before the full
   12,716-step source schedule. Resolve storage without silently weakening
   the checkpoint contract; historical NeMo/Megatron identities and parity
   remain separate missing evidence.
3. Reproduce whole-archive SDG program execution and unchanged source filters,
   resolve historical response/group differences, and distinguish published
   response replay from actual teacher regeneration and accepted-pair yield.
4. Establish original TRM notebook v18 and full training/task-adaptation scale.
5. Perform an isolated independent ARC quality comparison after the method
   prerequisites exist. Reused tasks and exposed ancestors remain tuning
   evidence; no accuracy, generalization or promotion claim is accepted here.

The next concrete engineering gate is the native trained solve/ranking/reset
loop. This report does not submit or execute it; any new external work must
follow the owner's active execution direction and exact distinct envelope.
