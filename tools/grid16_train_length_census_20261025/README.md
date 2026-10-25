# Grid16 TRAIN-only LODO length census

This is post-SFT experiment preparation, not resumed CPT generation, model training or new data admission. It outputs length metadata only. It uses the already recovered, exact pinned 800 official TRAIN demonstration episodes; original task.test fields are absent and never read. Each source pair uses user header 3 / EOS 1 and assistant header 3 / EOS 1. Strict rectangular digit grids prevent special-token injection.

For query demonstration q moved last, support pairs remain complete, the query output is withheld from the prompt, and the assistant header is included. Thus prompt length = full episode length - (query output characters + EOS). This is a length proof, not an implemented model-facing LODO adapter or evidence that an evaluator cannot leak an output through another path.

Measured with independent length arithmetic against prior actual grid16-tokenizer metadata: 800 parents, 2,573 views, 899,071 complete-episode IDs, 393,867 query target IDs including EOS. At context 3,072:

| Fixed generation reserve including EOS | Eligible views | Parents with any eligible view | Parents with all views eligible |
|---|---:|---:|---:|
| 160 | 1,789 | 586 | 484 |
| 320 | 2,233 | 708 | 657 |
| 512 | 2,380 | 743 | 727 |
| 930 | 2,350 | 733 | 725 |

Eligibility requires both prompt+reserve <= 3072 and the known TRAIN target fitting the reserve. The answer-length use is disclosed engineering screening, not evaluation selection. A larger reserve can exclude more prompts; it is not monotonic coverage. These are not new parents, rule families, clean holdout, model success or guaranteed EOS completion. No truncation. Parent/ancestor splits must precede view creation. Existing fixed16 discovery panel is unchanged.

`python -m unittest test_census -v` runs synthetic tests only. Real-input execution requires three explicit file paths whose full SHA256 pins are enforced; no download or provider API exists in this module. `--output` must be a new path. The source data are not distributed in Git. The small SUMMARY is an aggregate observed result, not permission to admit or train any records.

Independent review rechecked all800 existing metadata rows, 2573 prompt+target=full identities and all cap aggregates without decoding the original TRAIN body or re-tokenizing it. This reproduces arithmetic, not a second native model/tokenizer run. No known alias/semantic-family independence is implied by unique IDs or exact hashes.
