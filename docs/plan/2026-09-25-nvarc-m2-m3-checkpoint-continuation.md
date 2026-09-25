# NVARC M2/M3 checkpoint continuation — bounded execution proposal

Status: local implementation and draft package complete; **no new external
quota is approved by this file**. M2 is the real ARC-SFT checkpoint and M3 is
SDG/TRM, not the later four-worker benchmark. The current branch is `main`.

## Observed starting point

The retained `nvarc-m2-fsdp-feasibility-003` truth-free result
`4624b1c4e4c4079d7daf6d0e958d74a0fd4fe5ebe1d1559a9a7faf28b5ef28ba`
proves one full-parameter Qwen3.5-4B update on four distinct L4s: 240 public
ARC input tokens, finite loss/grad/weights and at most 9,426.9 MiB allocated
per rank. It did not save or export a model. The previous teacher `001` was
assigned two T4s, failed its four-L4 gate and made zero calls. Decisions
0028–0030 are consumed.

Independent review `control-review-0b7002a.md` found a chroot escape and a
joint verifier profile mismatch. The sandbox now drops all capabilities and
sets no-new-privileges before generated Python. A real namespace canary
regression expects initial canary absence, `EPERM` on a second chroot, and
absence afterward. Joint verification now selects `source-qwen` grammar,
augmentation and summed NLL from the shared source config; the actual tiny
Qwen differential test compares the joint score to a direct source verifier.
The old incorrect artifacts remain frozen.

## Local checkpoint proof

`arc_nvarc_fsdp_sft.py` uses the proven unpacked Qwen3.5 FSDP wrapping,
AdamW, a frozen coprime data schedule, global token accounting, finite checks,
Distributed Checkpoint model/optimizer shards, rank-local RNG and scheduler
sidecars, and a hash-inventoried cursor. A separate process consolidates the
final shards, saves HF safetensors and reloads them. This avoids the Windows
CPU FSDP full-state gather access violation seen during development; that
failed local attempt is not a 4B execution result.

The strict two-rank CPU test uses the real tiny Qwen3.5 architecture and public
ARC train sequences. It executes two full-parameter steps both continuously
and with a process restart after step one. Both exports have identical material
digest `sha256:a9051a0ba3e32144ed25fa83755bd21d73a9403797672eb103f9aaa214eb5e1e`.
The resumed run has four model forwards, 240 input tokens, a verified final
checkpoint manifest, and matching consolidated/reloaded weight fingerprints.
The exported model was actually passed to the source TTT/search/rank entry on
one visible dev task. This proves the local backend path; it does not prove
4B save/export viability or ARC quality. The strict regression also splits,
restores and tampers with checkpoint transport members.

## M2 proposed 4B package

The inert package is
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/fsdp-sft-review-004/`, built from
`configs/m2-fsdp-sft-draft-001.json`. Its independent offline preflight passed.
The exact draft SHA-256 is
`8e69cdf03d9f4e3146349f3abe8bb8fa6e6cc4ce2a2a0010245b705579397e1f`;
plan SHA-256 `4f16baf031c7ffb63a002ab61ce6cae3713f4296899173216ac1baf33410f6af`,
runtime wheel SHA-256 `523285fadb96ada0a9483cb63a63655a1584b5d524592eecdf6e3c016ac051ce`,
and notebook SHA-256 `46d392ad48e4c351acb8bbfd29fbb3dd8af2e184603fb10a1d116c57a722b1e3`.
This draft is guarded by `approved: false` and an unpushable kernel ID.

| Bound | Proposed exact scope |
| --- | --- |
| Provider | One new private, Internet-disabled Kaggle kernel, `danielwuu/nvarc-m2-fsdp-sft-001`; existing private compact-model and offline-wheel Datasets; official competition source mount only to reproduce the successful four-L4 allocation |
| Hardware and time | Exactly four distinct BF16 L4s; 45-minute kernel wall ceiling; preflight requires at least 60 GB free working disk; USD paid 0 |
| Data | Existing public ARC training freeze, 8 train and 8 disjoint dev parents; 128 train-only augmented sequences; data manifest `sha256:2903887f4603cb76540c97a0162c2687199003ff92b502e040f0417579b015b4`; no evaluation6/holdout derivatives |
| SFT | Compact Qwen3.5-4B base `sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982`; unpacked BF16 full-parameter FSDP; AdamW; 8 steps, 2,578 scheduled input tokens, sequence length at most 128; stride 17 covers all 8 train parents |
| Resume/export | Save after step 1, restart all four workers, resume through step 8, save final model/optimizer/RNG/cursor, consolidate shards in a separate process, export and reload HF weights, and retain a truth-free identity chain |
| Post-SFT | One visible dev task `00576224`, one demo-only LoRA TTT step, at most four source DFS generation calls of at most 64 new tokens each, at most 128 DFS expansions per call, inverse/dedupe and source `kgmon` verification/ranking when valid grids exist; no dev labels or scorer |
| Retention/transport | One terminal retrieval. Keep final sharded checkpoint, export, source result, first checkpoint manifest, per-rank traces and run chain; remove only the superseded step-1 shard files after final export; split final DCP files into parts at most 1.75 GB with an independently verifiable reconstruction manifest |

The selected visible and source config SHA-256s are respectively
`e5a645cdf7809c60ae00a1a5cc6b78555a9da271ecdb3b0bd6ba4cb461c2a503`
and `c6e1260667689446a73ba716ca0d13503d5a8463af52d867853485dbfd4ef906`.
The solver may return missing candidates; a valid ranked Qwen candidate is an
observed outcome, not a promised result. GPU DCP save, export host memory and
large terminal retrieval remain unproven. A gate failure consumes this proposed
attempt; there is no automatic repair or retry.

## M3 proposed teacher package

The inert `teacher-review-004` package uses a new identity
`nvarc-m3-teacher-small-002`, with the official competition source mount that
was present in the successful four-L4 case. Its independent offline preflight
passed. Draft SHA-256
`1b9f03dca16dfeadc3e3d2520d5989a2f1734eefbbbe1c159c05a91317ec49f6`,
plan SHA-256 `e2cdbd1275bd41c645e262a93eaf6bef17be09d8845aba105e8194c0f4cf837d`,
runtime wheel SHA-256 `523285fadb96ada0a9483cb63a63655a1584b5d524592eecdf6e3c016ac051ce`,
notebook SHA-256 `0dcb0b7ddd99f6d45c2e4f20d51aff0bf06bdb256863c024cbc551ac0f057e33`.
The exact proposal is one private, Internet-disabled, USD-0 Kaggle kernel,
four-L4 hardware gate, 30-minute wall limit, one accepted version, one terminal
retrieval and no retry. It uses the existing Qwen3.5-4B **full vocabulary**
model at pinned revision as a local teacher, not a paid API or Codex
subscription. On two public ARC train parents it reserves four dependent
source-prompt calls, each at most 4,096 input plus 1,024 output tokens:
20,480 total tokens reserved. Actual token use, raw responses and all four
stage ledgers remain private. This teacher differs from the NeMo-Skills
GPT-OSS-120B tutorial linked upstream; NVARC does not pin its original
teacher, so original-teacher parity cannot be claimed.

After retrieval, the existing `sdg-teacher-replay` consumes only saved raw
responses and runs generated programs only in the repaired WSL namespace
sandbox. Pairing/filter counts, rejected programs, execution limits and output
digests become the M3 evidence. The current TRM path already has actual tiny
CPU training, save/reload, task-local TTT, visible-only inference and a joint
candidate scored by the corrected Qwen verifier. Any new teacher pairs must be
kept out of dev/evaluator labels, with checkpoint exposure recorded before a
TRM retrain.

## Approval boundary

AGENTS.md and `docs/development/data-and-execution-policy.md` require new
owner direction for each external/provider run and its exact budget. The old
four-L4 feasibility and teacher `001` authorities are consumed. This proposal
requests only the two new packages above: one M2 kernel and one M3 teacher
kernel, each with one terminal retrieval, no Dataset mutation, no retry, and
USD paid 0. It excludes heldout scoring, competition submission, public
publication, original-scale H100 training and large data acquisition.
