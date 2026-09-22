# Decision 0017: Authorize the prompt-pilot mount repair

Status: Accepted

Date: 2026-09-22

## Context

The owner explicitly directed repair after `prompt-pilot-baseline-001` failed
before its hardware gate. Kaggle mounted the private Dataset under the current
owner-qualified Dataset topology, while the submitted notebook assumed only a
legacy unqualified path. The failed run emitted no `model_ready` event and made
zero solver generations. Its identity, notebook, outbound package, runtime
wheel, traceback, and version 1 Dataset remain frozen evidence.

The workload, solver, data split, model revision, hardware requirement,
generation quota, and stopping condition from Decision 0016 remain suitable.
Only the mount transport needs repair.

## Decision

Authorize one replacement run, `prompt-pilot-baseline-002`, with exactly these
changes and boundaries:

- preserve all `prompt-pilot-baseline-001` submitted bytes and evidence; never
  reuse its run or kernel identity;
- update the existing small private runtime Dataset as immutable version 2
  with only the new identity-bound wheel and truth-free outbound package;
- submit exactly one new private kernel,
  `danielwuu/iris-x-arc-agi-2-prompt-pilot-baseline-002`;
- resolve the two exact private Dataset refs and exact competition source by
  owner-qualified current Kaggle paths, with only their explicit legacy paths
  as compatibility alternatives. Require exactly one match for every mount and
  never search across `/kaggle/input`;
- accept only the exact `prompt-pilot-baseline-002.zip` or its exact extracted
  directory and reconstruct an archive from the fixed closed member list;
- preserve the Decision 0016 bindings: 384 train/dev test-index-0 jobs, pinned
  Qwen3.5-4B revision, four distinct L4 GPUs, one persistent model per GPU,
  greedy single generation, 300-second per-job deadline, no warm-up, retry,
  TTT, LoRA, second solver, Internet, evaluator truth, competition submission,
  publication, or paid cost; and
- permit only bounded server status and log reads until four identity-bound
  `model_ready` events on four distinct GPU UUIDs and initial scheduler dispatch
  are retained. At that point stop development and monitoring immediately and
  leave the notebook running. Do not retrieve or score results, reflect, or
  start another candidate.

If the replacement fails or cannot produce live startup evidence, retain the
trace and stop. This decision authorizes no automatic retry, third baseline
identity, result retrieval, or later GEPA proposal.

## Consequences

This is a transport-only repair, not a change to the scientific comparison or
acceptance threshold. Trial 001, Trial 002, and `prompt-pilot-baseline-001`
remain unchanged. The new run may reach `startup-verified`; it cannot reach
`baseline-measured` under this authority.
