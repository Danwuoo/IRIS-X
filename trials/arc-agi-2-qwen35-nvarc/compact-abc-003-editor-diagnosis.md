# Compact ABC 003 owner-Editor diagnosis

The owner returned `結果.zip` from the saved 003 Editor notebook. Its retained
SHA-256 is `195c7c4df43c53efb07d12af47d8f870f8723d968c61c5308e5fc5a2846fa68c`.
The local verifier accepted all 35 data members against the exact Decision
0046 plan digest
`sha256:3ae9ebf9786e775be7c0d96981982c884257c0fbd562444a8278af1fb49f4734`.
The result remains in ignored local storage at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/compact-abc-editor-003-result.zip`.

The Editor reported the exact official competition mount, four distinct BF16
NVIDIA L4 UUIDs and both retained compact model identities. All five arms
finished their three public development tasks. The 824-second notebook used
30 generation calls, 60 returned sequences, 1,530 generation forwards, 59
candidate verifications, 472 verification forwards, 12 TTT steps and 1,389
TTT training tokens, all within its pinned ceilings. No evaluator truth was
inside the notebook or its ZIP.

An isolated local scorer checked the frozen ZIP against exactly the three
selected public `training2` solution grids. The public challenge bytes and
NVARC source commit match those used for the 002 score. Results per arm:

| Arm | pass@1 | pass@2 | Candidate-pool coverage |
| --- | ---: | ---: | ---: |
| A: compact base | 1/3 | 1/3 | 1/3 |
| B: eight-step SFT export | 0/3 | 0/3 | 0/3 |
| C0: B + one step, 5e-5 | 0/3 | 0/3 | 0/3 |
| C2: B + two steps, 5e-5 | 0/3 | 0/3 | 0/3 |
| CH: B + one step, 1e-4 | 0/3 | 0/3 | 0/3 |

All B/C misses occur before ranking: no correct grid enters their candidate
pools. C2 and CH made finite nonzero adapter updates with exact task-local
resets, but neither treatment changed exact correctness on this selected set.
These same three tasks have been examined repeatedly; this is development
feedback, not fresh holdout evidence or full-SFT evidence. The next distinct
experiment may vary candidate search while retaining model, TTT and task
budgets. No further 003 save or execution follows from this observation.
