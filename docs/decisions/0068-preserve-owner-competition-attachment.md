# Decision 0068: Preserve the owner's existing competition attachment

Date: 2026-10-08. Status: accepted owner scope; sole source-only save consumed.

## Observed precondition change

The first offline-v2 pre-save SOURCE check returned notebook 137630087/version 1
with unchanged complete source bytes, private visibility and GPU/TPU/Internet
OFF, but with competitionDataSources containing arc-prize-2026-arc-agi-3.
The frozen accepted v1 SOURCE had no competition attachment. The strict gate
stopped before any SaveKernel send, reservation or claim. Preserve the original
prepared package, review, live readback and no-send ledger unchanged.

Only the competition association and lastRunTime metadata differed. Neither
the timestamp nor that readback establishes any runtime execution.

## Exact owner direction

The assistant asked whether this was the owner's attachment for paid RTX PRO
6000 access and whether the offline successor should preserve it or remove it.
The owner replied “是” at 12:13:39 UTC and “保留” at 12:13:47 UTC, in messages
Sentinel_29ffe7de754881919ea7ee89b857b687 and
Sentinel_c90503ea9b3c8191b4dee9a401f494eb.

Preserve exactly this existing ARC-AGI-3 competition metadata association.
This does not authorize reading or using its data, changing the ARC-AGI-2
scientific task, a GPU RUN, paid provisioning/execution, or official submission.
All manual switches remain False and GPU/TPU/Internet remain OFF in the save.

## Publication contract

Keep the frozen original v1 SOURCE as original evidence. The fresh live
predecessor must contain exactly the confirmed competition list and must still
have the identical original notebook bytes. The successor must contain exactly
the same competition list plus these three independent private Dataset pins:
runtime/4, Granite/2 and CPython-3.12 CUDA-12.8 wheels/1, each bound to its actual
verified manifest. Any other external input or changed notebook predecessor
remains a hard failure.

Prepare a new journal and independently review the actual official SDK request
again. The prior precheck made zero saves, so the single intended offline-v2
QUICK_SAVE remains unconsumed. Require exact successor SOURCE readback; never
infer attachment retention from an omitted request field. No runtime query or
execution is part of this reconciliation. After the verified offline stage,
integrate and push main normally under Decision 0067, verify remote/CI, then
pause as the owner directed.

## Accepted save and readback qualification

One genuine SDK QUICK_SAVE was accepted as 137630087/version 2. The SOURCE
readback retains the exact ARC3 association, private visibility and all
accelerator/Internet flags OFF. Its only notebook-content representation change
is joining each cell's string list into one string, which the official nbformat
specification permits. Every resulting source character and all remaining
notebook fields must match the reviewed request.

The provider exposes sorted bare Dataset references through GetKernel, rather
than their requested numeric versions. The installed supported Kernels API has
no separate selected-Dataset-version field. Preserve the strict gate failure;
do not reinterpret the bare names as independent version attestation. The
coordinator accepted this documented observability limit: numeric pins were
sent explicitly and are retained in the exact saved code, all pinned assets
passed complete local readback and CPU checks, and runtime manifests/hashes
reject missing or different mounted bytes before use. Kaggle mounted-version
selection, full model loading and GPU execution remain unverified. No resave,
RUN or hidden-endpoint probing is authorized to conceal that limit.
