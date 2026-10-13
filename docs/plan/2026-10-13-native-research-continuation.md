# Native research continuation: evidence and first experiment

Date: 2026-10-13 UTC. Starting commit:
`2901a97a1aa934d15e468e3e6d57bd96d95791e9`.
New branch: `feat/run008-native-research-20261013`.

This synthesis precedes runtime implementation. It separates historical
observations, the current falsifiable experiment, and conditional future work.
The owner's new continuation authorizes verification, analysis and planning,
delegated development, independent testing/review, preservation, submission and
monitoring, result retrieval, and another evidence-driven round. Historical
stop-after-submission instructions remain accurate for their original tasks;
they do not govern this newly authorized continuation. No new paid resources,
legal agreements, official competition submission, or relaxed scientific gates
are part of this continuation.

## 1. Why this project and why these methods

`PRODUCT_THESIS.md` defines domain specialization as a measured engineering
configuration problem: Domain Specification -> Build–Measure–Select ->
Engineering Trial -> Domain Package. Models, prompts, tools, SFT, RL and agent
coordination must earn adoption through useful measured outcomes. A complete
training loop or elaborate verifier is not itself product or research success.

The initial ARC trials established transport and model feasibility but did not
establish a useful specialized package. Trial001 ended inconclusive without
promotion. Trial002 produced four valid grids and 0/4 exact matches. The prompt
pilot plateaued; subsequent budget/thinking diagnostics did not establish an
improvement. The correct lesson is to test a different intervention, not to
rename valid syntax as reasoning success.

Sources: `trials/first-real-domain/README.md`,
`trials/arc-agi-2-baseline/README.md`,
`trials/arc-agi-2-prompt-pilot/README.md`,
`trials/arc-agi-2-budget-ablation/README.md`.

## 2. What the historical results do and do not support

1. The compact 16-symbol model preserved grid generation but discarded native
   code/text capacity. Its eight-step SFT pilot and short task adaptation did not
   beat base on the repeatedly inspected three-task diagnostics: base and
   base+TTT were 1/3, SFT and SFT+TTT 0/3. Those tiny exposed cases do not refute
   properly scaled SFT/TTT; they do refute treating an eight-step pilot as an
   established adaptation advantage. See
   `trials/arc-agi-2-qwen35-nvarc/compact-abc-005-editor-diagnosis.md`.
2. Complete native TTT was later demonstrated mechanically. On the modified
   NVARC/TinyRecursive public input, base scored 5/172 and TTT128 10/172. This
   input differs from the pinned ARC-AGI-2 120-task/167-query input. Exposure and
   portable numerical-replay caveats remain. These scores cannot be transferred
   to PUBLIC120 or to a new model. See
   `trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001-diagnosis.md`.
3. A completed private Stage3 preview did not guarantee official execution:
   the official rerun failed with a notebook exception and null scores. Provider
   terminal status, model completion, evaluator completion and method efficacy
   require separate evidence. See
   `trials/arc-agi-2-qwen35-nvarc/stage3-official-score-001.md`.
4. E13 did not answer its paired 120/240-second search question: the event cap
   interrupted it before a matched pair completed. The subsequent uncapped run
   completed 512 TTT updates, 24 batches/96 views, six searches and 41 distinct
   candidates, yet top1/top2/pool-oracle were all 1/6. Reranking those same
   candidates cannot solve the five absent answers. This is a local diagnosis
   of proposal/representation/adaptation, not proof that additional search
   never helps. See `research/arc-next-line/uncapped-result/README.md`.
5. The next-line design therefore restored full vocabularies and compared direct
   grids, independent program proposals, and execution-feedback repair. These
   are useful controlled hypotheses; AVO/Duck/Prime names are not evidence that
   an 8B offline ARC-AGI-2 system will work. The bounded interpreter deliberately
   interprets model programs as data without host exec/import. See
   `research/arc-next-line/architecture-memo.zh-TW.md`.
6. The earlier PUBLIC120 program-only experiment was operationally complete but
   produced zero eligible answer grids (0/167). Grammar fixed output legality,
   not demonstration fit. The learning-agent successor added genuine global
   LoRA, training-only verified trajectories, demo-only adaptation and a direct
   grid path that sees query inputs. These were substantial method changes,
   not proof of improvement. See `tools/arc_learning_agent_20261011/README.md`.
7. The documented Qwen14B v18 pilot provides a limited positive signal:
   program LoRA update16 improved six seen-family disjoint queries from2/6 to5/6.
   A retrospective checkpoint portfolio reached6/6 on that inspected panel.
   The prospective63-case design explicitly separates old regression,
   same-family, new-family, selector-canary and genuine ARC-development strata.
   Do not report the retrospective portfolio as fresh confirmation. See
   `research/qwen-portfolio-20261012/{PLAN.md,panel-plan.md}`.
8. The true-ARC successor moved to fixed train32/dev16/held32 and real demo-LOO
   SFT64/SFT256, checkpoint reload, and optional complete PUBLIC120. Retained
   v25 cost evidence records actual256 updates in about323s and334 public-view
   generation timings totaling about7403s. These are cost observations, not
   independent score verification. The referenced v25 science-analysis files
   are absent from the transferred inventory; no missing score is invented.
   See `tools/arc_qwen_transfer_20261012/README.md` and
   `tools/arc_qwen_rlvr004_20261013/source/design/COST-EVIDENCE.json`.

## 3. Current experiment, resolving stale design documents

The executable `rl_session/plan.py`, `owned_runtime/planning.py` and bound
`design/MEASURED-POLICY.json` supersede the earlier SFT64/full256-sweep draft.
The first recovered experiment preserves the current policy:

- A: same-session, genuinely trained, saved and reloaded SFT256 anchor;
- B: at most four disjoint eight-parent batches, eight sampled outputs per
  parent,64 slots per batch,256 total planned attempts, at most four updates;
- C: extra supervised continuation from A, bounded against B's whole extra
  model-phase wall interval, without idle padding or refunded failed work;
- same dev16 and reused held32; greedy identity plus fixed D4 view; at most two
  answers; choose once on dev, fixed A/B/C tie order;
- selected method frozen before PUBLIC and held scoring; full PUBLIC120
  denominator120/167,334 planned generation views, unchanged original scorer;
- no optional task adaptation added to this first no-TTT comparison.

This tests whether the small verifiable-reward intervention package adds value
over its supervised anchor and an extra-SFT cost control. Different learning
rates mean it is not an objective-only causal comparison. Reused held32 is
experiment-held-out, not pristine project confirmation. The target151/167
(micro pass@2 above90%) is a goal, not a forecast or result.

All-zero/all-one reward groups, actual dispatched/eligible/infrastructure/
context/not-reached counts and fixed parent coverage must be reported. A clean
zero-signal audit leaves B at A; an incomplete audit is not zero signal. The
immutable unchanged-policy replay gate checks nonforced token choices without
letting forced choices dilute numerical error. No post-result tolerance change,
reward-conditioned resampling or public-answer-driven checkpoint selection is
allowed.

## 4. First repair question and bounded development

Verified v39 state is ERROR, not a failed score. Its installed pinned cuDNN
wheel members are intact. The worker mapped the owned `libcudnn.so.9` and the
different system `libcudnn_graph.so.9.8.0`; Torch and owned API observed90800.
The graph mapping fails exact pinned-member bytes. No PUBLIC result or
checkpoint was produced. Calibration consumed physical work that remains
recorded. Inner closure and outer unsafe-closure are different observations.

The current child policy constructs LD_LIBRARY_PATH entirely from system driver
directories; the owned cuDNN directory is absent. This is a concrete mechanism
to test, not yet a proven explanation of every historical loader choice.
NVIDIA documents cuDNN's split-library/runtime dependency search, and dynamic
loader reuse/search ordering makes an absolute shim path insufficient to prove
all dependent backends came from that installation.

Primary context:
https://docs.nvidia.com/cudnn/installation/build-run-cudnn/
https://man7.org/linux/man-pages/man3/dlopen.3.html

The finite local work is:

1. Reproduce the mixed-system/owned selection with real synthetic ELF shared
   libraries in fresh processes, including matching SONAMEs, deferred backend
   loading, system-first search and already-loaded foreign backends.
2. Implement one coherent source-owned child loader policy using independently
   authenticated installed cuDNN paths before native imports/exec. Do not change
   system settings, inherit arbitrary loader paths, use LD_PRELOAD, substitute
   wheels, or relax byte/API/kernel device/inode/foreign-backend checks.
3. Preserve the notebook/bootstrap/process infrastructure and scientific policy;
   create new successor source identities and explicit assembly bindings rather
   than rewriting old snapshots or manufacturing old review receipts.
4. Run normal and optimized tests, actual CPU subprocess integration, failure,
   deadline, timeout and cleanup cases; independently review final bytes.
   CPU ELF fixtures prove loader mechanics only. They do not prove real cuDNN,
   full14B GPU execution or scientific improvement.
5. Save source/config/tests/plan and compact sanitized evidence early, then
   commit/push and verify the remote commit. Preserve all prior attempts.

## 5. Acceptance, publication and next-round decisions

Transfer verification has independently passed all11 external checksums and
all three archive inventories. Genuine relocated CPU reproduction matches all
283 source-proposal and426 candidate files. Transfer tests pass17 normal and17
optimized. Existing complete-suite/CI failures remain separate; no full-green
claim follows. The new runtime must get fresh tests and independent review.

Before any provider mutation, the sole publisher must verify the actual latest
notebook/code identities and absence of another active run, then publish only
the new code payload. Weights/wheels/data retain separate exact pins. Re-read
numeric dataset bytes and inactive notebook source/settings/mounts before one
active submission with one new pre-dispatch epoch. Each session includes queue,
setup, model work, scoring and closure inside43200s; no phase resets its clock.
Then monitor to terminal, retrieve the exact outputs, verify source/closures/
prediction seals/scorer denominator, and analyze before another attempt.

Current publication blocker: authenticated CLI own-listing works, but the exact
private notebook status call returned a401/403-derived permission message.
Its cause is unresolved; the SDK rewrites multiple errors to the same text.
Do not infer a missing scope or evade the denied target through another route.
Local work continues; submission waits for legitimate exact-resource access.

Conditional next steps after authentic results:

- Environment or artifact failure: repair its demonstrated root cause; retain
  failed identity, charges and partial evidence; do not change the scientific
  method to hide an infrastructure failure.
- Complete reward audit with no mixed groups: report no useful gradient signal
  at this scale. Prioritize train-only proposal/data curriculum or verified
  trajectory diversity before increasing RL steps blindly.
- Numerical replay gate failure: characterize cache/mask/precision mismatch
  on original tokens, retaining thresholds. Never raise tolerance to admit an
  observed failing trajectory.
- Valid B updates: report paired A/B/C gains and losses, coverage, exact counts,
  physical cost and control-matching qualification. No net gain means no
  promotion. If promising, predeclare a new independent training-source panel
  before another method comparison.
- Missing candidate coverage: improve representations/proposals/training.
  Oracle gain without top2 gain supports selector work; repair losing to
  independent proposals supports shallower feedback and more diverse starts.

Training on a single RTX Pro6000 is distinct from competition inference on
four L4s. A BF16 14B model's weights alone exceed a single24GB L4; four devices
are not a transparent96GB pool. Tensor-parallel or quantized inference needs
its own reload, numerical, memory, longest-context and throughput evidence.
No present result establishes that deployment path. Official submission and
successful-baseline tagging stay gated on actual qualifying evidence.
