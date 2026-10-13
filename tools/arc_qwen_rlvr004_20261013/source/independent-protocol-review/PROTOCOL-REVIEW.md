# Independent RLVR experiment protocol review

Status: scientific design review complete for the scoped data/plan revisions in REVIEW-SEAL.json; no production admission, GPU execution, publication, model/evaluator/gold access, or edits to the author tree. Local source and metadata inspection plus synthetic tests only. The frozen code13/v25 line remains untouched.

## Decision

The proposed same-session A/B/C experiment is a scientifically useful **intervention-package pilot**, subject to the finite contract below. It can yield useful paired predictions even if RL produces no update. It cannot establish an objective-only causal effect when B and C use different learning rates, and it cannot turn the repeatedly exposed holdout32 into pristine project-level confirmation. The PUBLIC90 goal remains exclusively the original sealed scorer's result.

The mathematical, native trajectory, and genuine tiny PEFT prototypes establish mechanics only. No evidence in this review establishes full14B numerical alignment, memory capacity, generation throughput, reward signal, generalization, or a PUBLIC score.

## Required frozen choices

1. **Anchor and optimizer lineage.** A is a same-source/session SFT64 checkpoint genuinely persisted, reloaded, and checked against its trained FP32 adapter state. B and C both restore exactly A. New continuation optimizers/schedulers/RNG policy are declared; old optimizer progress or a physical cost ledger is not silently imported as training state. Control LR2e-4 and RL LR1e-6 with fresh constant schedules is a valid package comparison. Record clipping, Adam settings, sampler policy, and counted update units. An optional same-LR arm is a different experiment and is unnecessary for this pilot.

2. **Fixed data.** Freeze train32/dev16/holdout32 parent IDs, source inventory/hash, and order before content-based decisions. For each train parent, take only the identity-transform LOO record withholding the last original demonstration. Validate typed-source lineage and reconstructed native prompt, not a caller's rehashed JSON claim. Neither actor objects nor prompts receive reward targets, original test fields, dev/holdout labels, or PUBLIC labels. A held-out demo target equal in content to another visible demo is not automatically a leak: the structural source indices and boundaries matter. Do not demand impossible base-model-pretraining cleanliness.

3. **Exposure is descriptive.** Record the exact selected LOO record's SFT64 exposure without choosing the record based on exposure. Existing baseline `seen_record_ids` records attempted training rows before update success; use successful committed update/microbatch receipts to distinguish attempted exposure from committed optimization exposure when failures are possible. Report unknown explicitly rather than calling an attempted row trained.

4. **Fixed sampling and audit.** G8 fixed independent seeds per parent, temperature1/top_p1, unchanged native grid DFA and token/context cap. The first complete256-attempt sweep is at one policy version; no update until the sweep closes. The clean implementation is one mixed-group-normalized optimizer update per complete sweep, then a fresh policy version/sweep, maximum4 sweeps/updates. Never apply group1's update and then admit group2 sampled under the old version as synchronous on-policy data. Preserve original tokens, cached actor log-mu, complete support/mask reconstruction, and full original generated lengths. Source-bound normalization remains mixed-groups × eligible-full-group-size × original-generated-sequence-length; constant groups remain in reporting denominators.

5. **Audit denominators.** Separately report planned256 slots, actual dispatched attempts, reward-eligible attempts, infrastructure exclusions, context exclusions, and not-reached slots. Exact model invalidity/truncation receives0; infrastructure failure receives no reward. Report eligible mean reward and the explicit eligible denominator. pass@8 is only defined on groups with eight eligible outcomes; report its coverage. Include all-zero/all-one groups and parents in audit tables. No replacements or resampling until a mixed group appears.

6. **No-update branches are real results.** Complete zero-signal audit stops B at A, retaining actual audit cost, then runs C and all paired evaluations. A numerical/memory/time failure before completion is an incomplete audit, not a zero-signal finding. Preserve its cost, close B without an update (or restore the last declared committed checkpoint after a later-sweep failure), and continue C/evaluation if admitted. Never label unattempted slots complete attempts to satisfy a state-machine API. A no-update B must equal A at adapter identity and, with deterministic matched inference, predictions.

7. **Numerical gate must be immutable before samples.** Proposed conservative engineering default, not a learned GPU tolerance: unchanged-weight selected-logprob p95 absolute gap≤0.05, maximum gap≤0.20, and100% inside strict DDIS(.8,1.28), evaluated on nonforced generated-token choices globally and by trajectory/parent. Report all-token metrics too, but forced single-support tokens cannot dilute the check. Nonfinite probability, provenance/support mismatch, or unsupported memory aborts the update. If a parent has no nonforced choices, report not-applicable/no-policy-gradient evidence. Failure never authorizes raising thresholds after observing which values pass. The actual runtime author/parent must explicitly freeze the chosen numerical thresholds and test scope; the proposal here is not full14B admission.

8. **Physical time contract.** B's extra cost is the synchronized model-phase wall interval including optimizer setup, sampling, replay, reward, gradients/steps, checkpoint/save/reload/verification, failure, and rollback. C includes corresponding setup/training/persistence/verification costs. Queue and initial common model loading are separate but still count against the original12h session. Never call this CUDA kernel time or billed GPU-seconds. Count failed dispatched work permanently; restoration cannot refund elapsed time. Start/end timestamps and a monotonic physical ledger are needed, not a sum of selected successful event durations that omits overhead.

9. **Control matching.** Proposed predeclared tolerance epsilon=min(120s,max(5s,0.05×B_seconds)), all inputs finite and nonnegative. C uses deterministic train-only sampling and fresh constant2e-4 continuation; no dev-guided checkpoint or LR choice. Include projected final checkpoint/reload cost before another update. Stop before another indivisible update would exceed B+epsilon. Never idle-pad to manufacture equal compute. If finite steps/checkpoint cost or the8192-step cap leaves C outside epsilon, report unmatched and do not claim a compute-matched result. B and C each≤7200s; this tolerance cannot authorize exceeding either absolute cap. Exact tolerance still needs v25-grounded feasible work/verification estimates.

10. **Reserve and ordering.** Before additional B work, reserve both its projected incremental cost and C's matching growth, all paired main evaluations, reload/persistence, failure margin, and the chosen PUBLIC opportunity. A/B/C dev16+holdout32 with two transforms is288 generations before any optional TTT. The existing PUBLIC path is334 generations for167 queries. Keep the original session origin and42000/42180/42300/43200 cutoffs; no resetting clocks on phase/reload/rollback. v25 observations can ground forecasts; outcome labels cannot change them. If resources cannot cover the fixed audit and main comparison, state not-admitted or incomplete rather than pruning parents. PUBLIC and optionalTTT admission priorities/reserves must be explicit before sampling.

11. **Evaluation and selection.** Freeze same decoding/precision/prompt packing/transform/token cap and fixed dev tie rule across arms. Persist actual per-task predictions and seals; derive exact scores from those seals, rather than accept unbound caller-supplied counts. Select once on dev only before opening current-run holdout labels. Holdout32 is still held out from training but is reused project evidence; report raw exact counts and paired gained/lost task IDs without presenting it as untouched confirmation. B no-update and incomplete audit status travels into the comparison table.

12. **Optional TTT and PUBLIC.** Primary no-TTT paired evaluation is easiest to interpret. Optional TTT requires identical fixed parents, visible-demo-only folds, update counts, selector, token cap, and all-or-none admission across A/B/C. Equal inference allowances are not equal measured wall cost; report both. The PUBLIC goal evaluation should use one dev-selected frozen method with the unchanged sealed scorer. Evaluating all arms on PUBLIC would cost three such blocks, cannot be called compute-matched without explicit allocation, and must not enable PUBLIC-based selection or target tuning.

## Open launch blockers

- Final integrated source/data/proof APIs and independent review are not frozen yet.
- Production numeric gate and memory/throughput gate need explicit source binding; full14B validation is conditional in-session before updates.
- v25-grounded phase estimates, fixed reserves/priority, control tolerance, and watchdog enforcement need a coherent<=12h admission receipt.
- Data/plan APIs passed the independent synthetic suite. Actual production predicted/rewarded/updated result seals remain unmeasured and production-closed.

These are bounded implementation/admission requirements. They are not grounds to ask the user to recertify already authorized local development, to obtain new compute/quota, to alter live v25, or to stall unrelated implementation.

## Sources inspected

- `/workspace/shared/agent_factory3_rl_review_20261012.md`
- `../portfolio63-checkpoint-repair-20261012/rl-design/EXECUTION-CONTRACT-ADDENDUM.md`
- Frozen baseline `tools/arc_qwen_transfer_20261012/{protocol,data,experiment,backend}.py`
- Frozen baseline `tools/arc_learning_agent_20261011/training.py` exposure bookkeeping
- `../portfolio63-checkpoint-repair-20261012/rl-prototype/rl_math.py` full-group loss normalization
- `../portfolio63-checkpoint-repair-20261012/rl-trajectory-prototype/INTEGRATION-CONTRACT.md`
- `../portfolio63-checkpoint-repair-20261012/rl-peft-prototype/README.md`
- Evolving `rl_session/{plan,common}.py`, inspected without author-tree edits
