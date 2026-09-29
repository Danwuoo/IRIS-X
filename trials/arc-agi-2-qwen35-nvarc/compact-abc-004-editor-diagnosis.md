# Compact ABC 004 owner-Editor diagnosis

The owner returned the saved 004 Editor `結果.zip`. Its SHA-256 is
`4f2fd94f28362882edeebaa3a6de8fd4f0ef7a079f6efb4dc6714db44b37c00b`.
The local verifier accepted all 27 data members against the exact Decision
0047 plan digest
`sha256:ab9a2427ae41a274f9db5f423e7fb19db4ba3868b2beaa3e7f9d647c59561ebf`.
Two byte-identical copies of the owner result are retained in ignored local
storage as `compact-abc-editor-004-result.zip` and
`compact-abc-editor-004-owner-original.zip` under
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`.

The Editor verified the exact official competition mount, four distinct
BF16 NVIDIA L4 UUIDs, and both retained compact model identities. A, B and
C each completed all three public development parents. The 522-second run
used 18 generation calls, 36 returned sequences, 900 generation forwards,
35 candidate verifications, 280 verification forwards, three TTT steps and
345 training tokens, all within the approved ceilings. No evaluator truth
was inside the notebook or ZIP.

An isolated local scorer bound the ZIP, the NVARC source commit and the
public `training2` challenge/solution file digests, then scored only these
three selected development parents:

| Arm | pass@1 | pass@2 | Candidate-pool coverage |
| --- | ---: | ---: | ---: |
| A: compact base | 1/3 | 1/3 | 1/3 |
| B: eight-step SFT export | 0/3 | 0/3 | 0/3 |
| C: B plus one task-local TTT step | 0/3 | 0/3 | 0/3 |

The two-path model beam changed the candidate sets compared with 003: each
task/arm had one to three new unique grids, while retaining one to three
old ones. It still did not add a correct candidate for B or C, nor a new
correct candidate for A. This points to the model state and task adaptation
interaction as a more useful next bounded comparison than another decoder
variation. The same three parents have been examined repeatedly; this is
development feedback, not a fresh holdout or full SFT result. No 004 save,
execution or scoring authority is reopened by this observation.
