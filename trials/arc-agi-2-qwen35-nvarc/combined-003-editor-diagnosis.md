# Combined 003 Editor-session diagnosis

Date: 2026-09-27
Status: owner-supplied compute-complete diagnostics; no usable M2 candidate or accepted M3 SDG pair

The owner manually executed the Decision 0037 quick-saved notebook and supplied
`combined-003-diagnostics.zip`. This is an Editor observation; no provider query,
output retrieval, submission or model call was made during local diagnosis.

The original archive was moved unchanged from the main root into ignored
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-003-editor-observation-001/diagnostics.zip`.
Its SHA-256 is
`937a6091143a4bfe997f53fb3f1635fc90b0ee467ddc4536886825ddd069c3de`.
The adjacent `verification.json`, SHA-256
`92564032bff16540b5a5a53b3b1225d0db887004019e6fbfef33b3d6c03c4e0e`,
binds all 44 retained members and the local diagnostic calculations.

The retained plan matches the approved owner-Editor plan exactly, with digest
`sha256:13790f5930800a9614555cae183eecfe12b0443d9a8f4ba83f9d3976039410cf`.
Both child plans, terminal envelopes, independent branch verifiers, 25
aggregate-referenced artifact hashes, all startup-reported payload hashes and
10 retained embedded payloads match. The two assigned BF16 L4 UUIDs are
distinct and their hardware/model-ready bindings match. The archive omits the
executed notebook, runtime wheel, source notebook and model weights; reported
startup bindings do not independently reconstruct those executed bytes.

## Runtime result

The reported wall time is 306.509 seconds, with no shared error and no retry.
Both workers exited with code 0 and passed the existing terminal checks. Their
stdout files are empty: the notebook writes its aggregate but does not print a
success summary. `complete` describes runtime/accounting completion; it does
not imply an ARC answer or accepted generated data.

| Branch | Verified work | Scientific disposition |
| --- | --- | --- |
| M2 | One TTT step, 108 training tokens, finite loss 2.2320025, four generation calls; no extra SFT | Zero candidates, zero ranking verification calls, one missing test output |
| M3 | Four EOS-complete stages, 1,071 input and 459 output tokens | Structurally accepted responses; semantic contract failure, no accepted SDG pairs |

The logs contain dependency fast-path fallback and PEFT warnings, without a
retained OOM, hardware failure or timeout. Those warnings do not explain the
observed root pruning or teacher semantic errors.

## M2: every legal root digit is below the fixed score threshold

All four calls use `source-qwen`, 120 query tokens, one full-prefix expansion,
zero children enqueued and zero completed candidates. Each records
`root_legal_tokens_below_score_threshold`; all ten legal digit edges are score
pruned, with zero token-limit edges and no generated suffix.

| Call | Best legal digit | Probability | Legal-digit probability mass |
| --- | --- | --- | --- |
| 1 | 7 | 0.190190 | 0.998867 |
| 2 | 1 | 0.174695 | 0.992508 |
| 3 | 7 | 0.156369 | 0.997847 |
| 4 | 7 | 0.190764 | 0.998447 |

The fixed threshold is 0.2, equivalent to maximum cumulative NLL
1.6094379124. Each best legal digit already exceeds that NLL at the first
token. The best symbol is legal in every call, with more than 99% of the
probability on legal digits. This is not a highest-probability grammar-masked
symbol or a parsing/EOS rejection. Even conditioning on the legal digits would
leave all four maxima below 0.2. More expansion or output-token allowance alone
cannot create an edge after this root is fully pruned.

The root trace establishes this proximal cause; it does not establish the
upstream cause of the uncertain distribution or the quality of a hypothetical
lower-threshold answer. No threshold was changed and no counterfactual model
generation or ARC scoring was performed.

## M3: complete responses violate the requested puzzle semantics

| Stage | Input tokens | Output tokens | Finish |
| --- | --- | --- | --- |
| summary | 321 | 118 | EOS |
| mix | 286 | 32 | EOS |
| input-logic | 155 | 170 | EOS |
| output-logic | 309 | 139 | EOS |

The improved transport and short structured outputs avoided the prior mix
truncation, but EOS/schema/AST acceptance did not check the following semantics.

1. Summary calls the first parent's rule a 180-degree rotation. Both retained
   public demonstrations show boundary-pair swaps with the middle cell kept.
   For `[9,0,1,6,8]`, the public output is `[0,9,1,8,6]`; reversal would produce
   `[8,6,1,0,9]`. The second parent's rotation description matches its demos.
2. Mix returns `[8,7,6,5,4,3,2,1,0]`. This is a valid nine-index permutation,
   but the prompt's boundary-pair swaps followed by rotation require
   `[7,8,6,5,4,3,2,0,1]`. The current parser verifies the permutation schema,
   not that required composition.
3. `generate_puzzle_input` selects a random shape with dimensions 2..5,
   raises when there are more than ten cells, and returns a dictionary with
   `shape`, `output_from_input` and `grid`. The required output is a fixed 3x3
   integer grid with independently drawn colors 0..9.
4. `generate_puzzle_output` expects that dictionary rather than a grid. It
   assigns `flat_input` but never reads it; its return array contains source
   indices rather than selected input colors. It also takes the random
   permutation from the input dictionary, ignoring the mix specification.

These violations are established from the digest-bound generated source,
AST checks and public-demo counterexamples. Generated programs were not
executed on the host or in a sandbox, and no pair acceptance is claimed. This
is a semantic rejection, independent of the previously observed local sandbox
NumPy dependency limitation.

## Next local engineering direction

Add summary/demo, exact composition and input/output contract checks to a
future local proposal, including replay of these retained wrong responses as
negative cases. Keep raw teacher responses immutable and preserve EOS gates.
Treat a root-threshold experiment as a distinct scientific proposal; the
current trace is evidence for planning, not execution authority.

This diagnosis changes no frozen notebook, runtime package, threshold, model
identity or workload. Combined 003 remains a compute-complete observation with
no scientific promotion; no new Kaggle submission or execution is authorized.

Historical frozen files and both inert/approved combined 003 packages remain
unchanged. Both aggregate records in the ZIP equal the owner's earlier
standalone JSON. The adjacent preservation record has SHA-256
`8522ac4a5c9fc2f9385cd13449cdd244b34b7fa6fe77b26167c6a9d9adaa421f`.

Handoff validation: `python tools/repository_check.py --all` passed (256 tests,
four optional skips). The log is
`.irisx/nvarc-combined-003-editor-diagnosis-repository.txt`.
