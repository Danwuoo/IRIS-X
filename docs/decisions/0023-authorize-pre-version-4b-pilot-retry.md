# Decision 0023: Authorize one pre-version 4B pilot retry

Status: Accepted

Date: 2026-09-23

## Context

Decision 0022's `nvarc-4b-compat-pilot-002` push was rejected by Kaggle's
`SaveKernel` API with HTTP 400 before a version receipt. A status check could
not access the intended slug and the ten newest own kernels did not contain
it. There is no evidence of notebook execution, model loading or any training
step. The server did not identify the invalid field. The proposed title and
slug had 54 characters, while the previously accepted pilot 001 title was
50 characters; length is a repair hypothesis, not a diagnosed cause.

The owner explicitly directed retry of a submission rejected before runtime,
because no model result or generation budget was consumed. To preserve the
submitted pilot 002 bytes and its failed push record, this correction uses
the distinct `nvarc-4b-compat-pilot-003` identity.

## Decision

Authorize one new private Kaggle `SaveKernel` attempt for
`nvarc-4b-compat-pilot-003` with intended kernel ID
`danielwuu/iris-x-4b-lora-pilot-003` and title `IRIS-X 4B LoRA pilot 003`.
Both are 24 characters after the owner prefix and the title resolves exactly
to the slug in the installed Kaggle CLI. Bind the unchanged [pilot 003 draft
plan](../../trials/arc-agi-2-qwen35-nvarc/configs/draft-4b-pilot-003.json)
SHA-256 `14f95a83953777e7261b530e38d5cf2d0b33486ee4dc62fe52ad435f91cfb443`.
If Kaggle accepts a kernel version, make bounded status checks to terminal and
retrieve its output once. Capture a provider rejection's response detail if
available. Never send the same rejected package again unchanged.

The run retains pilot 002's exact private model Dataset v2, pinned
`Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` material,
offline wheels, official `arc-prize-2026-arc-agi-2` competition mount, private
visibility, Internet disabled and `NvidiaL4` request. The notebook and runner
check only challenge-file presence, never challenge contents or solutions.
Hardware diagnostics are recorded before model work. Device 0 must be an L4
with at least 22,000 MiB; one to four GPUs may be visible, but only one is
used. Maximums remain USD 0 paid cost, 1,800 seconds notebook wall time,
1,500 seconds worker time, 300 seconds finalization reserve, two synthetic
LoRA steps, 128 training tokens, zero generations and zero teacher calls.
No ARC scoring, full SFT, competition submission, publication, external model
API, model retry or resume is authorized.

Reserve the attempt in a local atomic ledger before submission. A server
rejection without a kernel/version receipt may be analyzed and repaired under
the owner's direction, but this decision binds only the exact pilot 003
package. A created kernel version, whether the notebook succeeds or fails,
uses the one accepted-run allowance and cannot be resubmitted under this
decision. Preserve pilot 001 and 002 identities and evidence.
