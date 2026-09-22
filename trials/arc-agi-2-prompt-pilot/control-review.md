# Prompt pilot control review

Reviewed: 2026-09-23. Development head: `8837d2b47a2d4577a178649f6ec2332f156f1b0d`.
Disposition: retain and integrate the implementation and negative search result;
no candidate promotion, no complete holdout evaluation, no new external execution.

## Independent checks

The control task reran `score_result_package` for the recovered baseline and
`score_search_result_package` for each of the nine candidate result/outbound pairs.
Each recomputed report exactly matched its saved JSON, including identity bindings,
per-case records, group denominators, and invalid-output treatment. Packages were
located by their bound SHA-256 digests rather than filenames alone.

| Candidate | Train correct / 256 | Dev correct / 128 | Dev wins vs B1 | Dev losses vs B1 |
| --- | ---: | ---: | ---: | ---: |
| B1 | 18 | 12 | 0 | 0 |
| G1 | 7 | 5 | 0 | 7 |
| G2 | not evaluated | not evaluated | — | — |
| G3 | 14 | 9 | 1 | 4 |
| G4 | 11 | 8 | 1 | 5 |
| G5 | 9 | 7 | 0 | 5 |
| G6 | 10 | 6 | 1 | 7 |
| G7 | 11 | 10 | 1 | 3 |
| G8 | 10 | 10 | 2 | 4 |
| G9 | 7 | 8 | 2 | 6 |
| G10 | 8 | 8 | 0 | 4 |

G2 consumed a proposal attempt when the controller was interrupted to contain a
Dataset transport incident. No terminal proposer output was retained and no GPU
work followed; this is not evidence of a model reasoning failure.

B1 remains best on this **public-training selection-dev split**, at 9.375%.
G7/G8 each achieve 7.8125%. This is neither an ARC-AGI-2 public-evaluation score
nor evidence that GEPA is generally ineffective. It is a negative result for this
instruction-only, fixed-decoding experiment. Some candidates gained one or two
previously missed cases but lost more previously solved cases.

## Holdout and execution evidence

The control task checked the terminal runtime failure and its SHA-256:
`deaa2fbb8a780b31fd57642443f174971e21d8dde70af3cd980fcd70d31d5b4a`.
The exception was `runtime competition case differs: f3e62deb`, before model
loading or generation. No checkpoint or result ZIP exists for that attempt.
Holdout accuracy is **unavailable**, not zero; no final generalization comparison
can be claimed. No holdout answer was needed for this control review.

The ledger records ten proposal attempts, nine 384-job candidate workloads and
the already completed 384-job baseline: 3,840 completed Qwen invocations.
It conservatively reserves a further 128 for the failed holdout, totaling
3,968 reserved out of 4,480. Reserved budget is not observed model execution.

The nine completed proposal durations sum to 519.078 seconds, about 8.65 minutes.
G2's recorded zero is an incomplete interrupted measurement, not proof of zero
usage. Candidate runner wall times are about 18–20 minutes per 384-job batch;
these are four-card session durations, not GPU busy time. Ledger queue/transport
fields are not uniformly complete, so they must not be used to invent a precise
end-to-end duration or billing amount. Codex used subscription plan usage.

## Engineering follow-up

Before a later experiment, validate the visible content of **every selected
train/dev/holdout task** against the bound competition snapshot during local
preflight. The held-out answers can remain sealed while visible-input/source
compatibility is checked. Preserve the failed identity and do not silently
replace the pinned source or drop the mismatching task to make this run pass.

Analyze instruction changes, output truncation, and paired regressions using
existing train/dev results before spending further inference on the same search.
This review does not authorize another holdout attempt, new split, or candidate.
The full repository validation passed with 151 tests at the reviewed development
head; integration validation is recorded by the control task separately.
