# Decision 0070: Publish and run the bounded learning agent

Date: 2026-10-11. Status at approval: accepted owner scope; reviewed implementation and CPU
validation complete; publication and existing-resource admission pending.

## Owner direction and exact scope

After receiving the learning-agent design, implementation, test evidence and
delivery, the owner approved this explicit question:

> 要我接著發布 Git／Kaggle 與所需 Dataset，再於你原有 GCP 環境啟動單一、總時限 12 小時的 session 嗎？

The owner answered 「要」 in message
Sentinel_0e7365b1829081918ba5e833ca37ebc0. This authorizes publication of this
reviewed learning-agent release to the existing private IRIS-X main branch and
private Kaggle destinations, its required Datasets, and one bounded session on
the owner's existing configured GCP/BYOD NvidiaRtxPro6000 resource.

The prior development-only statements in the immutable source freeze and the
new package's original AGENTS/README describe the completed development stage.
This decision supersedes only those publication/execution restrictions for the
exact reviewed release and authorized session. Preserve those historical bytes,
all previous decisions, the successful PUBLIC120 evidence and the old scorer.
It does not reopen a previous run or authorize an additional research cycle.

## Frozen implementation and provenance

The additive package is tools/arc_learning_agent_20261011. Its 37 source, test and
documentation files are bound by SOURCE-FREEZE.json SHA-256
29d2f2989f43151115ae5a7db0befa2e529f19e88220f46a37e051fc892cd74b.
The runtime archive binds 97 exact files, including unchanged existing project
dependencies. Its code manifest SHA-256 is
7ab8a14641f2712e45e32cca11c94a70bca5583033ae7ae6d8ef2ff03501bc02.
The inactive notebook SHA-256 is
c1d12bc2ac148e1697166709ca4462d9213858fa3d6367e10315f32f2a40c700.

Independent CPU acceptance passed 136 tests, including tiny genuine neural
training fixtures. That evidence does not claim actual 8B/GPU throughput,
learning quality or operational completion. Any admission-specific notebook
variant, timestamp or identity must have its own exact reviewed wrapper or
configuration delta, preserving the 97-file runtime and historical notebook;
it must not silently change the scientific contract.

The inactive notebook hash above identifies the immutable development
predecessor. The separately reviewed deployment notebook adds an executable
stdlib parent supervising the entire loader, installation and session in one
owned child under the fixed epoch. This wrapper change must have its own tests
and exact source binding. The later deployment-inactive to deployment-active
transition is limited to the three reviewed activation configuration fields
plus the explicitly approved numeric dispatch epoch. Provider admission and
terminal status belong in separate receipts, not retroactive edits to this
approval-time record.

Exclude the superseded arc_program_agent_20261011 prototype, Python bytecode,
training/evaluator payloads, model weights, credentials, signed URLs, installed
environments and result archives from Git. Use the reviewed file allowlist,
not a recursive copy of the development workspace. Compact sanitized source,
review, test and provider receipts may accompany the release.

## Dataset and evaluation boundaries

Publish the new private code and clean training assets as independent version-1
Datasets. The reviewed target identities are
danielwuu/iris-x-learning-agent-code-20261011/1 and
danielwuu/iris-x-learning-training-20261011/1. Reuse the existing private
danielwuu/iris-x-public120-data-20261010/1 and the five unchanged native runtime,
model, wheel, interpreter and adapter references. These are intended pins until
verified create/readback receipts establish the actual provider identities.

Global learning admits only the pinned official training source, its existing
800-train/200-dev partition and independently verified authored targets under
the reviewed lineage checks. Public-evaluation ancestors, unknown parents and
split-crossing descendants are rejected. Original training-file test fields are
stripped before model-row construction. Optional synthetic derivatives are not
implicitly authorized merely because a larger corpus exists.

Task adaptation uses public-task demonstrations only, with independent adapter,
optimizer and RNG reset for each task. Solver processes receive query inputs,
never query answers. Only after owned model/solver processes are stopped, work
is reconciled and predictions are sealed may the separate CPU evaluator read
the pinned public answers. Keep all 120 tasks and 167 test inputs in the stated
denominators. This is public-development research, not official competition
GPU inference or an untouched holdout; no score or success threshold is promised.

Preserve the owner's existing ARC-AGI-3 metadata association only. No ARC3 task
data is admitted to training or solving, and no competition submission follows.

## One session, existing resource and total budget

Use only the existing configured integration and reviewed NvidiaRtxPro6000
selection. Do not provision another resource, change billing or access, create
credentials, bypass quota/security checks, or substitute another machine. Keep
Internet and TPU off. Preserve provider admission errors as actual evidence.

The outer maximum is 43,200 seconds, including bootstrap, calibration, data
admission, global SFT, training-only verified rollouts/refinement, training-dev
selection, frozen public solving/TTT, prediction sealing, scoring and closure.
Bind a finite, real PREDISPATCH_EPOCH in the sole active wire immediately before
dispatch, so queue/startup time is included in the 43,200-second total. Fail
closed if this epoch cannot be bound; the deployment must not fall back to a
runtime-only clock starting at the first notebook cell. Preserve the
3,600-second solver closure reserve, per-stage limits and all physical counters
in the frozen code.

Generated program text is interpreted only by the unchanged bounded AST VM.
It is never executed with unrestricted host exec, compile or import. Retain
existing per-verifier gas, memory, CPU, wall and output limits. Unknown dispatched
work keeps its reservation and blocks scoring rather than being silently retried
or discarded. Preserve checkpoints and failure evidence with their identities.

## Publication, admission and completion evidence

Verify exact Dataset contents and the private inactive notebook before the
reviewed active configuration is admitted. Use durable intent/checkpoints for
each external write. Reconcile an uncertain response by bounded read-only
checks before retrying the same operation; never duplicate an accepted save or
launch while an owned session is active or its status is unresolved.

Only one active session is authorized. Record the concrete provider ID/version,
source/settings readbacks, mounted-byte verification and actual terminal state.
Provider metadata that returns bare Dataset names does not independently attest
mounted versions; keep runtime hashes and readback limitations explicit.
Renderer COMPLETE alone is not model/session completion. Partial work,
SCORING_BLOCKED, missing output and operational errors must remain distinct.

Operational success requires provider COMPLETE and a production-origin session
whose actual global_sft evidence shows positive optimizer updates with finite,
changed adapter tensors. Require session COMPLETE rather than PARTIAL_SCORED,
stopped model/process ownership proof, SCORED, valid post-seal closure evidence
and an independently verified final archive. The frozen summary reaches COMPLETE
before export finishes, so a summary alone does not establish successful archive
delivery or process closure. Tiny CPU fixtures are not production-run evidence.

For Git, refresh main immediately before the expected-parent update, preserve
unrelated remote changes, never force push, verify the exact remote commit/tree,
and report terminal CI separately from focused package tests and historical
baseline failures. For the session, monitor to a terminal outcome and retain
sanitized operational evidence. A terminal outcome does not authorize another
session, a new experiment or a resource expansion.

## Owner-authorized v2 launcher repair and replacement (2026-10-11)

This addendum records the later repair scope without changing the approval-time
record above. The owner reported that learning-agent notebook version 2 failed
and requested repair (Sentinel_efdfcc9d0ea8819180ef7dc8a5193298). After the failure
was localized to the offline launcher, the owner answered 「確認」 in
Sentinel_db5b32a1fff08191b8f4e17892351d97 to this question:

> 修復只涉及啟動參數，會更新程式 Dataset 與 notebook，其他模型、資料和實驗設定不變。
> 測試與推送完成後，要我直接重新啟動，仍沿用本輪原截止時間（台灣時間明天 01:52），確認 RUNNING 後就停止監看嗎？

The narrow repair may update the session launch-command construction and its
regression tests. The guarded offline-run.py prefix already consumes Python
isolation flags; do not append interpreter flags where the launcher requires a
script path. Keep the direct-interpreter path isolated and bytecode-disabled.
The accompanying bootstrap-stage correction measures monotonic elapsed time
from the current replacement attempt, bounded by the existing 1,800-second
bootstrap allowance and the original global remaining time and closure reserve.
It must never restart or extend the global session clock. No scientific
algorithm, model, training data, evaluation contract, resource limit or process
ownership safeguard is relaxed.

Publish the reviewed repair and compact validation/deployment records to the
same private IRIS-X main. Update the existing private code Dataset to a reviewed
successor version and the same notebook to a new private inactive version before
one repaired replacement activation. The planned code Dataset version 2 and
inactive notebook version 3 are intentions until exact provider readback
receipts establish them. Preserve all original version-1/version-2 source,
publication and failure evidence; do not overwrite historical notebook files or
approval receipts. All seven non-code notebook Dataset pins, including the training Dataset,
remain unchanged. Preserve the ARC3 metadata association without reading ARC3
solver data or making a competition submission.

The replacement retains PREDISPATCH_EPOCH 1791697978 and the absolute deadline
1791741178 (2026-10-11 17:52:58 UTC, 2026-10-12 01:52:58 Asia/Taipei).
Time consumed by the failed attempt, diagnosis, repair, publication and queueing
remains consumed. Admit no replacement after that deadline or while the earlier
owned execution is active or unresolved. Use a fresh repair output identity,
verify closure of the failed execution, and apply the remaining-time provider
limit and fixed-deadline outer watchdog. No new 12-hour allocation, new resource,
new credentials, billing change or access bypass is authorized.

Before activation, require the exact reviewed source/notebook bindings, passing
repair regressions, private code-Dataset and inactive-notebook readbacks, and a
verified expected-parent Git main commit. Report CI separately from focused
repair tests and retained historical baseline failures. Keep raw training and
public-answer payloads, weights, archives, credentials and detailed private
process/runtime receipts outside the repair Git overlay; use compact sanitized
provenance instead.

The owner's latest stopping condition supersedes the earlier terminal-monitoring
instruction for this repaired replacement: verify the new provider version,
submitted source/settings and actual RUNNING state, then stop monitoring.
RUNNING is admission evidence only, not successful training, scoring, archive
completion or scientific improvement. Do not start another run, collect results
or perform further scientific analysis under this stopping instruction.
