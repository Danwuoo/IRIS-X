# Decision 0053: NVARC development goal until 07:00

Status: Accepted
Date: 2026-10-02 (Asia/Taipei)

The owner explicitly requests a Goal to develop NVARC to substantial
completion or 2026-10-02 07:00 Taipei, whichever comes first, using a timer
instead of frequent clock reads. The owner separately authorizes autonomous
use of Kaggle GPUs. These instructions supersede the earlier per-attempt
execution stop points for new development under this goal; consumed identities,
packages, observations and prior results remain immutable.

Continue on main. Complete the source-recipe implementation and integration,
prioritizing sample packing and attention/state isolation, streaming distributed
SFT with global token loss and gradient accumulation, checkpoint/resume/export,
complete task-local adaptation and search/ranking, then SDG/TRM integration.
Use local differential/tiny-model checks and private free Kaggle GPU probes as
needed. Each changed package receives a new immutable run identity with exact
source/material/config/notebook bindings and an atomic submission/retrieval
ledger. Runtime failures may be repaired and re-tested in distinct identities
within this goal; do not mutate an already submitted version or reuse its
identity. Necessary private runtime/material Dataset preparation, submissions,
bounded monitoring and terminal retrieval are included in the owner's GPU
direction. Keep paid cost USD 0 and preserve truth/exposure isolation.

Published original-reproduction material remains separate from clean research.
Existing public tuning tasks may test integration, but do not claim a fresh
holdout or use hidden competition answers. Original model/tokenizer/backend
and scale parity are evidence requirements, never inferred from a port's small
successful run. No competition submission, public publication, paid execution
or external teacher API follows from free GPU authorization.

The native one-shot thread timer `nvarc-07-00` is scheduled for 07:00 with one
occurrence. Do not restore prior monitoring automations or poll wall-clock time.
At the timer, stop new development/submissions, preserve completed and pending
work, and pause the Goal at the owner's requested cutoff unless substantial
completion was verified earlier. Report the actual implementation/runtime
state, remaining gaps and retained evidence. A provider job already accepted
at cutoff may continue within its own recorded finite session limit; identify
that pending work without claiming an observed terminal result.
