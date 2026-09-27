# Decision 0037: Save the repaired NVARC notebook for owner execution

Status: Accepted
Date: 2026-09-27

The owner instructs: 「提交 notebook，但先不 run，由我從 editor 跑再回報」.
This authorizes one private save of the reviewed combined 003 candidate, with
no provider execution initiated by the agent. The owner will run it in Editor
and report the outcome. No further confirmation is required.

- Preserve the inert combined 003 plan, template, reviewed package and local
  repair record. Create a separate exact Decision 0037 envelope for the same
  unexecuted `nvarc-m2-m3-combined-003` candidate. Bind its provenance to the
  candidate plan digest. Its child scientific fields remain byte-equivalent:
  M2 root-pruning diagnostics and M3 `qwen-direct-permutation-v2` are the
  reviewed changes. No acceptance, scoring or method promotion follows.
- Retain two distinct BF16 L4 workers, the existing private Datasets and
  official competition mount, pinned model/source/tokenizer materials,
  Internet disabled, USD 0, 1,800-second notebook bound, 300-second setup and
  readiness bounds, and 30-second terminal reserve. M2 remains one TTT step,
  four calls, 64 new tokens and 128 DFS expansions with score 0.2; M3 remains
  four dependent calls and the unchanged stage/total token limits.
- Complete offline package and execution-guard verification. Reserve one
  save before calling `SaveKernel` with the exact
  `KernelExecutionType.QUICK_SAVE` value used by Kaggle's official `--no-run`.
  Never fall back to the ordinary save-and-run operation. Local transport
  inspection and credential refresh are permitted without exposing secrets.
  Any rejected or uncertain save consumes the request; no automatic retry.
- Stop after retaining the receipt. The agent must not start an Editor
  session, run any cell, request status/logs/outputs, retrieve results, mutate
  a Dataset, query older sessions, or resume a monitor. The owner retains
  control of manual execution and subsequent reporting.

The exact package and save receipt are recorded in
`trials/arc-agi-2-qwen35-nvarc/combined-notebook-003-editor.md`.

Transport reference: Kaggle's [kernel documentation](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md)
and [official implementation](https://github.com/Kaggle/kaggle-cli/blob/main/src/kaggle/api/kaggle_api_extended.py).
