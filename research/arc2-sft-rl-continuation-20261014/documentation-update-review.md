# Independent review: research navigation and next-stage preparation

Reviewed locally on 2026-10-14 UTC against the actual working-tree/index diff
from `0d4d19c71d2c84720d4956b36d8e99108e8c0a2b`, on
`feat/arc2-sft-rl-continuation-20261014`.

## Verdict

**Pass for documentation and bounded next-stage preparation.** No new
documentation correctness, placement, or broken-link blocker was found.
This does not approve execution or establish model, GPU, method, publication,
or repository-wide success. The reviewer changed only this report.

The review covers the new [status index](README.md) and
[next-stage plan](NEXT-STAGE-PLAN.zh-TW.md), plus the changed root README,
research index, docs index, Stage 0 tool README, local handoff, and three dated
method/architecture documents. The three baseline indexes are explicitly in
the new navigation scope; changing their guidance is separate from changing
frozen runtime bytes. Historical code18 and earlier research states are now
distinguished from current progress.

## Source-grounded plan

- The proposed adapter consumes explicit training-only
  `experiment/audit/sweep-N.json` files. The frozen
  [`experiment_flow/flow.py`](../../tools/arc_qwen_rlvr004_20261013/source/experiment_flow/flow.py)
  lines 221–246 preserve the batch, summary, update and failure state there.
  The compact collector report is not misrepresented as raw trajectories.
- [`audit_checks.py`](../../tools/arc_qwen_rlvr004_20261013/release/terminal-consumer/consumer/audit_checks.py)
  lines 199–275 establish the original replay/log-probability and detached-loss
  checks. Saved log probabilities do not reconstruct a Qwen/LoRA model graph.
- [`runtime.py`](../../tools/arc_qwen_rlvr004_20261013/source/rl_session/runtime.py)
  lines 420–489 compute group statistics for the complete batch, replay each
  admitted trajectory, use the fixed full-batch divisor, release graphs, and
  defer commit until admission. The proposed streaming glue preserves those
  responsibilities instead of recomputing a single-trajectory baseline.
- The documented 88 MiB bound follows from
  [`owned_runtime/evidence.py`](../../tools/arc_qwen_rlvr004_20261013/source/owned_runtime/evidence.py)
  lines 36–76: `64 × (1024 × 1024 + 256 × 1024 + 2 × 64 × 1024)` =
  **92,274,688 bytes = 88 MiB per planned batch audit**. This is a source-derived
  planning bound, not a measured file size. The new plan correctly retains the
  Stage 0 16 MiB reader limit and requires separate review for a larger reader.

The implementation/future boundary is accurate: real upstream components have
been invoked on synthetic CPU inputs, while the new adapter/streaming successor,
production wiring, genuine model replay, LoRA gradients, optimizer state,
save/reload, and resource measurements remain unimplemented or unverified.
A=SFT256, fixed 32-parent/disjoint 64-slot B, full-B model-phase-wall-matched C,
fixed dev selection, no-TTT, and PUBLIC120 tasks/167 queries remain intact.
Shadow work and failures are explicitly charged rather than treated as free.

## Independently executed local checks

- `python3 -B tools/repository_check.py` and the corresponding `-O` command
  both exit 1 with the same **six existing root README term findings**:
  `Engineering Trials`, `Decision 0010`, `Decision 0012`, `Decision 0014`,
  `Decision 0015`, and `Trial 001 status page`. No new layout, local-link,
  archive, or source-separation finding appears. The formerly missing
  `ARC-AGI-2` term is now genuinely present in the new research heading;
  the validator was not changed or waived.
- Validator `--self-test`: **3/3 pass normally and 3/3 under `-O`**.
- Across the ten reviewed documents: **123 relative link occurrences**, their
  one linked heading anchor, and **24 pinned IRIS-X source links** resolve.
  Pinned source paths and quoted line ranges were checked through local Git
  objects, without a new network request. This is not an external URL/service
  availability check.
- The documentation-only `git diff HEAD --check` is clean. The complete diff
  still reports exactly the disclosed upstream
  `vendor/losses/metric_state.py:38: new blank line at EOF`; copied source bytes
  were not normalized to suppress it.
- No change exists against `cc14bd1a79aac1fe6135017c9e09d4834300675d` in
  `tools/arc_qwen_rlvr004_20261013/`, the original scorer/submission helpers,
  or `src/irisx/arc_agi2.py`.
- SHA256 was independently recomputed for `bridge.py`, `proof.py`,
  `provenance.py`, `fixtures.py`, `tests/test_contract.py`, and
  `tests/test_torch_conformance.py`: **all six exactly match** the reviewed
  implementation identities in the
  [Agent Factory 3 independent review](agent-factory3/independent-review.md).

## Evidence and publication limits

The earlier aggregate result remains **1,583 tests, 2 failures, 35 errors,
74 skips**, with the previously recorded stage0-equivalent failure/error
identities. **The full suite was not rerun after this documentation update.**
The earlier CI's seven findings and cancelled jobs remain historical facts;
the new local six-finding invariant result is not a fresh full-suite or CI pass.

At the 2026-10-14 review recorded here, local HEAD was
`0d4d19c71d2c84720d4956b36d8e99108e8c0a2b`. The integrating lead's then-current
readback and cancelled publication attempts did not establish remote publication
of the then-new Agent Factory 3 work and navigation.
This reviewer performed no remote read/write, publication retry, commit,
ref mutation, dependency installation, model/provider operation, training,
or full-suite run. A later successful publication requires its own exact
commit/readback and CI evidence.
