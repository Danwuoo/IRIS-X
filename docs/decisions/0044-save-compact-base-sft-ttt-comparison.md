# Decision 0044: Save one compact base / SFT / SFT+TTT comparison

Status: Accepted
Date: 2026-09-28

The owner directs a single new, private owner-Editor notebook comparing (A)
the existing 16-symbol compact Qwen3.5-4B base, (B) its retained eight-step
ARC-SFT export without task adaptation, and (C) the same export with one
task-local TTT step. The owner authorizes development, offline verification
and one `KernelExecutionType.QUICK_SAVE`, then will run the notebook in Editor
and return `結果.zip`. The agent must stop at the save receipt. Combined 001–009
and all earlier execution allowances remain consumed and immutable.

The distinct identity is `nvarc-compact-abc-editor-001`. Its exact approved
plan is `trials/arc-agi-2-qwen35-nvarc/configs/compact-abc-editor-001.json`,
canonical digest
`sha256:430f144b6f58482aee2870a857429f9bf73d2126fd64f983518d26d9f8936b97`.
Only that plan may be packaged or saved. One atomic local ledger reserves the
single request before transport; rejection or uncertainty consumes it.

The base material digest is
`sha256:1a8eebd70d811e58c35dc5b1ee27dc18bd73a1066c3ab33adf96ed8427d4c982`.
The SFT export digest is
`sha256:481d9f12d573b39b0703e47b5f8f6f518a7ccd7847824ffb3f0fb96b11f2c3e6`,
and its training identity is
`sha256:40804d408005b666cb377aab623bd6b0edcfbcdaa4743049d26e7e65500f5fc4`.
The shared vocabulary identity is
`sha256:573199335acdb16205158d55457ea6e1c49fb64fb677e3817091b6f46e533422`.
The export is an **8-step SFT pilot** with 2,578 observed training tokens. It
is not full NVARC training. Exact training parent IDs and the three selected
public dev parent IDs are bound in the plan. `00576224` was already explored
in combined 009; the other two are newly selected for this comparison, not
proven unseen relative to any outside source. Exact parent IDs do not overlap;
semantic near-duplicate status remains unknown.

All arms share the source-compatible role/newline/EOS grammar, 16 token IDs,
public tasks and views, deterministic seed, public-derived shape and palette
gates, model-ranked grammar completion, verification and truth-free ranking.
For each of three tasks and each arm, reserve at most two generation calls,
two returned sequences per call, 64 tokens per sequence, 128 expansions per
call, four unique candidate verifications and eight public views per
verification. Totals across the notebook are at most 18 calls, 36 returned
sequences, 2,304 generation forwards, 36 verifications and 288 verification
forwards. Only C may take one TTT step per task, at most three steps and 768
training tokens total. New SFT steps and teacher calls are zero. A and B cannot
inherit C's adapter. The notebook loads A, unloads it, then loads B/C from
the same export, recording arm order, time and memory. Two distinct BF16 L4s
must be verified; one selected L4 performs the sequential comparison. The
session limit is 1,800 seconds with a 60-second terminal reserve, Internet
disabled and USD 0 paid cost. Existing private Datasets are reused without
mutation or a large download.

Notebook evidence is truth-free and includes raw sequences, inverse-mapped
candidates, deduplication and ranking, call reservations and completions,
task outcomes, hardware, stage time and memory, material/source/plan digests
and partial failures. The public symbolic witness is an independent diagnostic
only. No hidden answers, answer digests, outcome-derived metadata, competition
submission, exact ARC scoring, or promotion enter this save. Correctness and
oracle candidate coverage remain unknown pending a separately authorized,
solver-isolated local evaluator after the owner returns the ZIP.

Exact offline package preflight, small real CPU-model tests and the repository
check are required before the sole save. No agent run/session, status, log or
output query, retrieval, Dataset mutation, monitoring, automatic retry,
additional kernel or paid operation is authorized. Status is
`trials/arc-agi-2-qwen35-nvarc/compact-abc-editor-001.md`.

The sole QUICK_SAVE was accepted as version 1 with provider kernel ID
`136275587`; its request and receipt are retained in the status page. This
allowance is consumed. The agent did not run or query the saved notebook.
