# Combined 005 owner-Editor result diagnosis

The owner placed `結果.zip` at the main repository root after manually running
the Decision 0039 QUICK_SAVE notebook. Local analysis copied it unchanged to
the ignored evidence directory
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-005-editor-observation-001/result.zip`.
The original was then moved to the same directory as `owner-original-結果.zip`
because the repository's active root excludes ad hoc ZIPs; both copies have
the same SHA-256. No Kaggle status, log, output or
retrieval request and no model call was made during this analysis.

The owner ZIP SHA-256 is
`0990ab814e38c962a2de981f80067aff366f4fde91ba8b99b5a42a860c3a95f5`.
ZIP CRC, all 38 manifest-listed members and their byte lengths/SHA-256 values
passed independent local verification. Its plan bytes match the exact saved
combined 005 package and canonical digest
`sha256:24d2f2a1a31c49f968c8076c73b4c09cfec8bad5f8979b218c40c391c84aedf5`.
All seven embedded scientific input files match their saved-package bytes.
Both worker results independently pass the checked-in `verify_branch` gates;
their worker/parent artifact inventories, counters and assigned devices agree.
The two distinct BF16 L4 UUIDs completed in 248.104 notebook seconds with no
reported retry. The result declares no evaluator truth.

## M2: complete-grid candidates, unresolved task quality

M2 completed one task-local TTT step (108 training tokens, finite loss), four
generation calls and six verifications. The adapted-model mutation guard
passed; 430 explicit model forwards were recorded. Three of four views
returned two complete 6×6 grids; one view returned none. Six distinct grids
were ranked, with one vote apiece, and two were emitted as attempts. The
previous 1×2 truncation is resolved at the output-shape level.

The visible test input palette is `{2,3,7,8}`. Both public training examples
use only input colors in their outputs, but **all six** ranked 6×6 candidates
introduce colors absent from the test input. The two emitted attempts use
`{4,6,8}` and `{1,4,6,8}`. This is a concrete public-example consistency
failure, not an ARC exact-match score. No hidden test output or evaluator
truth was consulted. M2 is compute-complete and has candidate availability;
it is **not** established as a solved task or promoted method.

The one empty view carries a misleading `root_legal_tokens_below_score_threshold`
diagnostic: its root enqueued ten legal digits under the active 0.02 *per-token*
floor. That reason is calculated using the historical cumulative 0.2 score
threshold. The inconsistency affects the diagnostic label, not the retained
candidate count or the one-view empty outcome.

## M3: summary passes; mix fails before programs

M3 made two EOS-complete teacher calls, using 748 actual input and 111 output
tokens (9,728 tokens reserved). The first fenced JSON summary was accepted
under `qwen-rule-hinted-v4`: `boundary-pair-swap` for parent 1 and
`rotate180` for parent 2 independently reproduce every supplied public demo.
The second fenced JSON mix reply was rejected as `mix_schema_invalid`. It is
`{"output_from_input":[4,2,0,5,3,1]}`: it omits the required `shape` and
contains six indices for the declared 3×3 composition, which requires nine.
The trusted interpreter derives the expected public-rule composition
`[7,8,6,5,4,3,2,0,1]`. The raw reply and rejection are retained; there was
no dependent input/output program stage, isolated program invocation or
accepted SDG pair. This is a valid negative observation, not a teacher-method
promotion.

The local verification summary and unchanged ZIP are retained together in
the ignored observation directory. This diagnosis grants no new QUICK_SAVE,
kernel execution, Dataset mutation, retrieval, scoring or retry authority.
