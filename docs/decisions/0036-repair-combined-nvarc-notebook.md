# Decision 0036: Diagnose and repair the combined NVARC notebook

Status: Accepted
Date: 2026-09-27

The owner reports that Decision 0035's combined notebook failed and explicitly
instructs: 「kaggle notebook 回報錯誤，請修正後重新 push」.
This authorizes diagnosis and one corrected submission without another approval.

- Retain `nvarc-m2-m3-combined-001`, its submitted bytes and version-1 receipt.
  Retrieve that notebook's terminal diagnostic output once, binding returned
  evidence to its exact submitted plan and payload hashes. Any necessary status
  read is diagnostic only; do not resume continuous monitoring or query the
  Decision 0034 notebooks. Record reservations before provider calls.
- Repair the demonstrated program defect locally and add a regression that
  exercises the failed behavior. Preserve the original draft and submitted
  package/template. Stage a distinct `nvarc-m2-m3-combined-002` private notebook
  whose title equals its slug and whose exact approved plan names Decision 0036.
- Retain Decision 0035's two selected distinct BF16 L4 workers, existing
  Datasets, official competition mount, exact model/source/tokenizer materials,
  unchanged M2/M3 scientific workloads, Internet disabled and USD 0 paid cost.
  Total notebook time remains 1,800 seconds, setup at most 300 seconds and
  terminal reserve 30 seconds. No Dataset mutation, model acquisition, scoring,
  publication, competition submission or expanded model work is authorized.
- After offline tests and exact package preflight, reserve and send one push
  using the successful UTF-8 CLI transport with `NvidiaL4` and timeout 1800.
  Authentication refresh is permitted as needed without exposing credentials.
  Record the package hashes and receipt. Rejection/uncertainty consumes this
  request; no automatic third notebook follows.
- Stop at the replacement submission receipt, retaining the owner's preference
  against continuous monitoring. No retrieval of the replacement or heartbeat
  is authorized by this repair request.

Diagnostic findings, exact repairs, validation and transport outcome are
retained in `trials/arc-agi-2-qwen35-nvarc/combined-notebook-002.md`.
Provider acceptance does not establish startup or model completion.
