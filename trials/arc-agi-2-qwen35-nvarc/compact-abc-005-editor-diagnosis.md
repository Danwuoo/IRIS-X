# Compact ABC 005 owner-Editor diagnosis

The owner returned the 005 Editor `結果.zip`, SHA-256
`09a85730fbc0432b9f1f22860156837cdff1f684534655301f911254aa75a42c`.
The local verifier accepted all 31 listed data members against the exact
Decision 0048 plan digest
`sha256:e99993fda56f204c2dab8ac64882d94713004c8c41d6b4e628ce7ac3f88066a2`.
Two byte-identical copies of the owner result are retained in ignored local
storage as `compact-abc-editor-005-result.zip` and
`compact-abc-editor-005-owner-original.zip` under
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`.

The Editor verified the exact official competition mount and four distinct
BF16 NVIDIA L4 UUIDs. A, AT, B and C each completed all three selected public
development parents in 1,054.7 seconds. The run used 24 generation calls,
48 returned sequences, 1,200 generation forwards, 46 verifications,
368 verification forwards and six task-local optimizer steps using 690
training tokens. All remained within the approved ceilings. No evaluator
truth was in the notebook or ZIP. Worker stderr contained only model-loading
progress and dependency warnings, with no application error.

An isolated local scorer bound the ZIP, NVARC source commit and public
`training2` challenge/solution file digests. It scored only the three
repeatedly examined development parents:

| Arm | pass@1 | pass@2 | Candidate-pool coverage |
| --- | ---: | ---: | ---: |
| A: compact base | 1/3 | 1/3 | 1/3 |
| AT: compact base plus one-step task TTT | 1/3 | 1/3 | 1/3 |
| B: eight-step SFT pilot export | 0/3 | 0/3 | 0/3 |
| C: B plus one-step task TTT | 0/3 | 0/3 | 0/3 |

Every missed task lacks a correct grid in its retained candidate pool;
changing the ranking of these candidates cannot recover those answers.
All six TTT steps had finite loss, changed 500 adapter tensors and verified
fresh adapter reset. On the three tasks, A and AT shared respectively 3/3,
3/4 and 4/4 ranked candidate grids. B and C shared 4/4 on every task. The
single new AT grid was incorrect. These observations show that the applied
one-step TTT changed weights but gave no exact-match or coverage gain under
this fixed beam and selected workload. They do not establish that other
adaptation methods or checkpoints cannot work.

The owner's conditional repair request was evaluated against the complete
result. There is no runtime or package fault to fix, and these data do not
identify a justified next parameter change. No 006 QUICK_SAVE was submitted.
Further experiments require a distinct, reviewable question and should avoid
tuning repeatedly to these three development parents. No accuracy promotion
or hidden-answer claim follows from this result.
