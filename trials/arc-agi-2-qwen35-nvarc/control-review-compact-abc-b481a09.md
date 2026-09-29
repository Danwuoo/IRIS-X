# Compact ABC engineering acceptance and research continuation

Date: 2026-09-29
Reviewed commit: `b481a09`

## Disposition

Accept the retained 002 observation as a completed bounded A/B/C runtime.
The scientific comparison is not complete: the retained report contains no
isolated correctness measurement, so neither SFT nor TTT benefit is established.
The owner explicitly asks the original development chat to continue tuning
after this review. A successful program exit is not the research stop condition.

## Independently checked evidence

The retained ZIP SHA-256 is
`965ac0622546efe2d2e996e925ab376f4e219e5657d705cbe45685e8e060f37e`.
The local analysis verifier rechecked all 27 data members, the approved 002
plan binding and its identical embedded plan. The visible test inputs have no
output labels. The ledger records 18 completed generation calls, 35 candidate
verifications and three TTT updates. All nine task/arm rows are complete.

The three arms use the compact base and its eight-step SFT descendant with
shared vocabulary/source grammar; C alone adapts. The 002 implementation's
differences from 001 are the optional Dataset metadata sidecar and exact
authorization identity, not a changed solve path. Tiny-model checks cover the
shared solve path, not actual 4B quality or all possible failures.

| Public dev parent | B/C top candidate identical | B/C candidate set identical |
| --- | --- | --- |
| `00576224` | Yes | No |
| `c9e6f938` | No | Yes |
| `0d3d703e` | Yes | Yes |

A/B top candidates differ on all three parents. These are observed changes,
not improvements. In particular, B/C equality does not prove the TTT update
was absent or ineffective on all metrics.

## Required continuation

1. **Measure the existing result before another model run.** Bind a legitimate
   local evaluator source for exactly these public development parents, check
   its inputs/demos against the frozen workload, and compute per-arm pass@1,
   pass@2 and candidate-pool oracle coverage. Keep labels and answer-derived
   metadata out of notebook inputs, model selection at inference time and
   result ZIPs. Do not access a locked holdout or use symbolic witnesses as
   truth. Repeatedly examined tasks are development data, not fresh evaluation.
   The current analyzer supports an isolated truth file but the retained
   analysis did not supply one; all nine correctness rows remain unknown.
2. **Make tuning diagnostic.** The existing TTT treatment is one step, rank 2,
   alpha 4, learning rate 5e-5, and one augmentation. Retain this control and
   test a small predeclared variation, first in adaptation effort/learning
   rate, with step/token/gradient and update evidence. Do not infer that a
   single weak treatment disproves TTT, or call an eight-step export a fully
   trained ARC solver. Do not change every parameter together.
3. **Separate generation from ranking.** `grammar_sequences` uses greedy
   legal tokens, with the second sequence changing only the first token to
   the second-ranked legal choice. This is a narrow candidate generator;
   128 permitted forwards do not imply broad DFS exploration. Compare pool
   coverage and selected correctness before deciding whether to adjust
   search diversity or ranking. All A/B/C arms need matching solve budgets
   and the same public-only grammar.
4. **Deliver a bounded next experiment.** Reuse the working official
   competition mount, L4 x4 hardware gate, existing private materials and
   result packaging. Keep USD 0, Internet disabled and the 1,800-second
   notebook envelope. Record concrete per-arm and total ceilings, unchanged
   controls, treatment settings and success/failure/stop criteria in a new
   identity and decision before one new owner-Editor QUICK_SAVE. Stop at its
   receipt; retain the owner's no-agent-run/no-monitoring workflow. Do not
   reuse consumed 001/002 bytes or quotas. Further owner-returned results
   should lead to measured conclusions, including negative conclusions.

No minimum accuracy or promotion threshold is invented by this review. The
deliverable is an evidence-backed comparison and a controlled next test, not
a promise of a positive SFT/TTT effect. Wider SFT, new Dataset uploads, teacher
work and TRM remain separate scope.

## Verification

Local truth-free result analysis and the direct candidate/ledger cross-check
passed. `python tools/repository_check.py --all` passed: 283 tests in 206.316
seconds, four optional skips. Full repository and tiny actual-Qwen logs are
recorded separately in `.irisx/nvarc-abc-control-review-tests.txt` and
`.irisx/nvarc-abc-control-review-strict.txt`. The tiny actual-Qwen CPU three-arm/reset test passed
without skips (one test, 58.101 seconds). No provider query, real 4B/teacher
call or scoring was performed by this review.
