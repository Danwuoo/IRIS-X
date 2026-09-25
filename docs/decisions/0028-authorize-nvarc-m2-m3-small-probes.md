# Decision 0028: Authorize two bounded NVARC M2/M3 probes

Status: Accepted
Date: 2026-09-25

## Context

The owner approved the exact integrated request for the two independently staged
probes in the current task by replying “批准”. The reviewed packages and draft
plans are recorded in `trials/arc-agi-2-qwen35-nvarc/m2-m3.md`. This decision
supplies the external execution and data-use authorization required by
`AGENTS.md` and `docs/development/data-and-execution-policy.md`; older trial
decisions, including Decision 0027, do not authorize these runs.

## Decision

- `nvarc-m2-fsdp-feasibility-001`: create exactly one new private Kaggle Dataset
  version containing the verified compact Qwen3.5-4B material, then push exactly
  one private Internet-disabled L4 x4 kernel. Run at most 1,800 seconds, one
  unpacked BF16 FSDP full-parameter optimizer step, 128 ARC training tokens per
  rank and 512 in total, with zero generations. Use only the two-stage frozen
  public ARC training material and pinned model/dependencies in the package.
  Dataset ID: `danielwuu/irisx-nvarc-m2-compact-4b-001`; kernel ID:
  `danielwuu/nvarc-m2-fsdp-feasibility-001`.
- `nvarc-m3-teacher-small-001`: reuse the existing private full-vocabulary
  Qwen3.5-4B Dataset and push exactly one private Internet-disabled L4 x4
  kernel, using one GPU. Run at most 1,800 seconds on exactly two selected
  public ARC training parents. Make at most four dependent source-prompt teacher
  calls, each with at most 4,096 input and 1,024 output tokens, reserving at
  most 20,480 tokens total. Kernel ID:
  `danielwuu/nvarc-m3-teacher-small-001`.
- Private transport and use of the pinned NVARC source prompts for this teacher
  probe are approved despite the source root's absent declared license. The
  responses, usage and failures remain private retained evidence. No public
  publication or redistribution is approved.
- Both probes have USD 0 paid budget. Each allows bounded terminal status checks
  and exactly one terminal output retrieval. A failed push or run consumes its
  attempt; neither probe allows an automatic retry, a replacement identity or
  a second retrieval. The probes are independent.
- Preserve exact draft-plan digests, approved package digests, provider receipts,
  output files and token/step counts. Do not transmit evaluator answers or
  answer-derived metadata. No ARC scoring, competition submission, full 4B SFT
  run, original-scale TRM training, paid API or new source acquisition is
  authorized by this decision. A feasibility step cannot be reported as a
  completed ARC-SFT checkpoint.
