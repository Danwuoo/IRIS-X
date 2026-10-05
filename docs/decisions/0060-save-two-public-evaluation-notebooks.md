# Decision 0060: Save two public evaluation notebooks for owner Editor

Status: Accepted
Date: 2026-10-05 (Asia/Taipei)

The owner directs: 「實作兩份 notebook，盡量在本地就完成 debug，提交 quick
save 由我跑，輸出 zip 要分別命名 不要泛稱 結果,zip」. This supersedes the
inert-only status of the public notebook development proposal for these saves.

Implement and verify locally, then authorize exactly one private QUICK_SAVE
for each distinct identity:

- `nvarc-public-base30-001`: all 120 public ARC-AGI-2 evaluation tasks / 172
  tests, published Qwen3-4B SFT139 without TTT, 30 seconds shared search and
  verification per test, 3,600-second session, archive
  `nvarc-public-base30-001.zip`.
- `nvarc-public-ttt128-30-001`: the same tasks, model and inference budget,
  complete original 128-row task-local epochs, at most 15,360 optimizer steps
  and 30,713,088 training input tokens, 1,200 seconds per training epoch,
  14,400-second session, archive `nvarc-public-ttt128-30-001.zip`.

Both retain four distinct BF16 L4s, existing model/dependency materials,
Internet disabled and USD 0 paid cost. Reserve 900 seconds for startup and
300 seconds for export. Each GPU loads one persistent model; TTT uses fresh
Trainer/optimizer/scheduler state and verified tensor restoration per task.
Incomplete epochs cannot supply TTT-qualified candidates. Search limits and
candidate acceptance from the development design remain bound; ordinary
deadlines retain partial output without altering the denominator.

The exact public challenge SHA-256 is
`e7c62a4bd211867c6b538f66b8013b81f299663c82ca062f49a52bf439d6e4e8`.
Embed only this input and public-demo-derived workload bindings. The existing
competition attachment may be retained for the successful L4 transport context;
runtime never reads its files or selects a hidden-rerun branch. Evaluator
solutions and scores never enter either GPU notebook. Independent public
scorer implementation and synthetic local scoring tests are included; actual
public scoring waits for the owner's returned outputs. Exposure in SFT139 is
unresolved; these are public development measurements, not hidden scores or
method promotion. Lightweight public evidence does not satisfy the frozen
native portable GPU gate, which remains false.

Bind each exact package, implementation commit, decision digest and actual SDK
QUICK_SAVE request after offline debug. Atomically reserve each sole save before
credential or provider IO. Necessary existing credential inspection/refresh is
included without retaining secrets. Accepted, rejected or uncertain requests
consume their own identity's allowance; no automatic retry follows. The two
saves are independent, not a retry of one another.

Current quota hours, observation time/factor, reservation ID and session closure
are unavailable and remain null. Saving does not assert resource sufficiency.
The owner starts the notebooks manually. Stop at the two receipts: no agent
execution, runtime status/log/output request, retrieval, monitoring, Dataset
mutation, publication, formal competition submission or new solver is included.
Preserve official 001 and every consumed previous identity.

Exact packages and receipts belong in
[`public-eval-notebooks-001.md`](../../trials/arc-agi-2-qwen35-nvarc/public-eval-notebooks-001.md).
