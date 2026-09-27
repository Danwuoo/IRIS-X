# Combined 004 Editor-session diagnosis

Date: 2026-09-28
Status: verified compute-complete observation; M2 candidate availability at 0.02,
M3 summary rejected, no ARC quality or method-promotion claim

The owner supplied `結果.zip` in the main root after manually running the
Decision 0038 notebook. Local diagnosis made zero provider requests and zero new
model calls. The unchanged archive was moved into ignored
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-004-editor-observation-001/result.zip`.
Its SHA-256 is
`4d63a36d44b47ffd8bffbba27e94ac482b7741475b6f75d9b5b4b619d87a2565`.

The archive contains 38 members: an analysis manifest and 37 digest-bound
artifacts. Closed inventory, sizes, CRCs, SHA-256 values, all eight retained
input bindings, the exact approved plan, both worker envelopes/artifacts and
aggregate counters pass independent local verification. Both distinct L4
workers reported model-ready. The aggregate completed in 296.807 seconds with
one launch per branch and no retry. These are owner-supplied Editor observations,
not an agent query of provider session state.

## M2: lower cumulative threshold permits short candidates

One shared LoRA TTT step consumed 108 training tokens with finite loss
2.2320025. All arms share the same adapter digest, four query digests and
bit-identical retained root logits. Each arm made four generation calls.

| Threshold | Root survivors per view | DFS forwards | Explicit forwards including ranking | Ranking calls | Complete candidates |
| --- | --- | --- | --- | --- | --- |
| 0.2 | 0 / 0 / 0 / 0 | 4 | 4 | 0 | 0 |
| 0.1 | 5 / 5 / 6 / 6 | 26 | 26 | 0 | 0 |
| 0.02 | 10 / 10 / 10 / 10 | 53 | 69 | 2 | 2 |

The 0.2 arm prunes every legal root digit: the best probabilities are
0.193666, 0.179316, 0.163261 and 0.182927. The 0.1 arm unlocks the root but
exhausts cumulative score/grammar paths after one suffix token. The 0.02 arm
unlocks every legal root digit and reaches two suffix tokens. View index 1
returns two EOS-complete grids; its sequence cap is reached. The other three
views still exhaust score/grammar paths. Neither the 64-token cap nor the
128-expansion cap explains their failures.

After inverse augmentation, deduplication and source ranking, the retained
attempts are `[[7,8]]` and `[[7,5]]`, both 1x2. Their generation NLLs are
3.6128663 and 3.8722326; mean verification NLLs are 6.8723080 and 6.9651820.
There are no parsing or missing-EOS rejections. The shared workload totals
twelve generation calls, two ranking calls and 99 explicit inference forwards
(83 DFS plus 16 verification forwards), apart from the single TTT step.

This establishes candidate availability and its increased compute cost for
this task and these views. It does not establish an ARC solve. Both public
training examples map a 2x2 input to a 6x6 expanded grid; the two returned 1x2
candidates do not exhibit that demonstrated expansion structure. No test answer
was loaded, no exact-match score was computed, and no threshold was promoted.

## M3: formatting rejection also hides a wrong rule

Only the summary call ran: 343 input tokens, 95 output tokens, EOS completion,
4,608 reserved tokens. The accepted-stage count and accepted-pair count are
both zero. The dependent mix/input/output calls and isolated program suite were
not entered. There is no observation of Kaggle sandbox availability in this run.

The unchanged raw reply is one fenced JSON block. The active validator rejects
it as `teacher description contains an unexpected code block`. Its contents
claim `flip-rows` for puzzle 1 and ordered `flip-rows`, `flip-columns` for puzzle 2.

A separate diagnostic projection removes only the fence and applies the trusted
rule interpreter to the already exposed public demonstrations. It is not a
repaired or accepted response. Puzzle 1 fails both demonstrations; puzzle 2
matches both. For puzzle 1's first demo, input `[9,0,1,6,8]` would reverse to
`[8,6,1,0,9]`, whereas the public output is `[0,9,1,8,6]`. The unwrapped summary
therefore still rejects as `summary_demo_mismatch:puzzle1:0`.

Removing the formatting restriction alone would not make this summary usable.
The semantic gate correctly prevents this wrong rule from entering the dependent
SDG pipeline. The two parents are expressible by the restricted rule language;
this observation does not show that the language lacks the required operation.

## Retention and next local direction

The adjacent `verify.py` and `verification.json` retain every member digest,
paired-root arithmetic, reconciled counters and public-demo counterexamples.
The verification report SHA-256 is
`13bba21d8ffadd9dff1116ab21e0efb0854b1533a8ad40180e2865152d9e8635`;
the retained verification script SHA-256 is
`6de75f1f80fed59d41bc1c1ce1f174bc11d3a382fb2eaa8ef5d784c80b5e1fc6`.
Raw replies and the original archive remain immutable. A future local proposal
can address fenced-JSON handling while preserving demo validation, and examine
M2's premature small-grid/EOS candidates against the public training structure.
This diagnosis grants no generation, scoring, new save, Dataset mutation,
provider retrieval or retry authority.
