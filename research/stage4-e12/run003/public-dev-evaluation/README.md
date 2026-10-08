# E12 run003 / version 11: isolated public-development candidate correctness

The 64-step and 128-step arms each scored **top1 1/6 and top2 1/6 (16.7%)** over all six executed public-development tests. This is a descriptive retained-candidate exact-match result. It is separate from **qualified-test coverage, which is 0/6 for both arms**. The zero qualification count is not a zero correctness result.

| Measure | 64 steps | 128 steps |
| --- | ---: | ---: |
| Task clusters / tests | 4 / 6 | 4 / 6 |
| Top1 exact-match tests | 1/6 | 1/6 |
| Top2 exact-match tests | 1/6 | 1/6 |
| Full retained-pool oracle exact-match tests | 1/6 | 1/6 |
| Tests with a retained attempt | 4/6 | 6/6 |
| Retained top-two attempt slots | 6/12 | 9/12 |
| Missing attempt slots | 6/12 | 3/12 |
| All retained ranked-pool candidates | 8 | 10 |
| Qualified tests | 0/6 | 0/6 |

Top1 uses the first retained attempt. Top2 uses either of the first two retained attempts, in the original sealed ranking. Absent attempts count as misses; every actual test remains in the denominator. No filler, reranking, replacement, new generation, or exclusion was used. One fully solved task exists in each arm; task identities and per-test correctness remain evaluator-only under the existing isolation protocol.

## Provenance and checks

- Exact delivered ZIP: SHA-256 `faea1163e25990b655684e66cafd8d52b568478ecf140ea8debe194edf3aba89`.
- Immutable source revision: `1c040c7eb8c4e77bcce170dd36cbd5b933453489`.
- Candidate package: `run003-final-candidate-003`; plan SHA-256 `db8d4bf61f292c68fc45ba747be2908869bac089d98fbb4c00ad8b178a08f83f`.
- Read outputs through the reviewed bounded ZIP/JSON parser; no returned Python or native model package was executed.
- Verified frozen challenge bytes, original committed output projections, checkpoint/ranked-pool/top-two parity, arm identity, test ordering, and all six-test denominators before reading truth.
- Gold was read only from the four already-approved, locally present public-development source tasks, verified against the frozen upstream manifest at ARC-AGI-2 revision `f3283f727488ad98fe575ea6a5ac981e4a188e49`. Full train/test-input parity with the run was required.
- A separate canonical-JSON equality calculation reproduced all twelve arm/test outcome rows. Nine synthetic scoring tests passed, covering absent attempts, first/second/third-rank correctness, shape/color differences, filler exclusion, and the full denominator.
- No gold grids were printed or written, and no confirmation/holdout truth was opened. No provider requests, model calls, GPU runs, or external publication occurred during this scoring task.

## Interpretation limits

This is four selected, previously examined public-development task clusters, six tests per arm, and one technical repeat. It is not the full 24-task/35-test development screen or the planned two-repeat E12 comparison. Selection bias, historical exposure, and unresolved checkpoint training exposure remain. The observed tie does not establish equivalence or a causal benefit of either training budget.

Extra retained candidates in the 128-step arm did not increase exact-match tests here. Neither arm passed the independent native completion/deadline qualification gates. The measurements do not establish official Kaggle scoring, submission readiness, scientific promotion, generalization, or GPU-cost reduction.

## Retention boundary

`aggregate.json`, `validation.json`, this summary, and `manifest.json` contain no gold grids or per-test outcome labels. They may be retained as private development evidence. They must not be placed in a solver/runtime/GPU outbound package or used as answer-derived runtime features. The isolated per-test evaluator report is deliberately excluded from this shareable directory.
