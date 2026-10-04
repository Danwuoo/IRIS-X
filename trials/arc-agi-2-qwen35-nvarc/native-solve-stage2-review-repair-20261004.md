# Native solver stage 2 acceptance repair (2026-10-04)

Baseline: clean local `main` at `a42698104f151b27646fbefa30a4f80bd3cfa31c`.
Delivery commit: resolve with `git log -1 --format=%H -- trials/arc-agi-2-qwen35-nvarc/native-solve-stage2-review-repair-20261004.md`.
This is a stage 2 repair for the controller's changes-required review, not a
stage 3 dispatch. Only local implementation, offline verification and CPU
fixtures are authorized. There is no provider call, GPU execution, Dataset
mutation, external model/teacher call, scoring, publication, competition
submission, git push, new chat, goal or automation.

## Full archive qualification

The previous verifier could qualify the GPU gate with a failed fourth
`baseline-after-fault` process. Earlier checks did not close that gap.
The external archive verifier now requires all four exact attempts, their
mode, actual dispatch/exit receipts, successful worker outcomes for both solve
tasks and the baseline control, and complete cache/reset controls. The sole
exception is the exact `fault-first` Python exception after two completed
updates, with return code 1, its changed pre-reset fingerprint, and verified
cleanup. A signal, timeout, extra error, incomplete result or failed baseline
cannot become a completed acceptance observation.

Each required control recounts six initial model entries and one final reset
entry, all completed, with their exact inputs/positions and 168 input tokens.
Cache transcript and reset metadata bind their actual retained vectors and
call counts. A flag or an artifact left by an earlier phase is insufficient.
The two solve results must match committed full-test checkpoints, and the
parent must have finalized the exact four receipts. The expected injected
failure remains a failed child and parent disposition.

Per-attempt cache/reset, result and overall qualification are reported
separately. Earlier verified candidate export and observed baseline equality
remain available when an auxiliary attempt fails; the overall GPU gate stays
false. Contradictory/unknown receipts, modes or closed result data fail closed.

`tests/nvarc_native_multitask_archive_strict.py` exercises the actual `verify()`
archive reader, ZIP closure, member digests, token/epoch recount, event chains,
receipts, controls and parent accounting. Package admission and downstream
candidate replay are explicitly synthetic substitutions; they provide no GPU,
model-quality or ARC evidence and cannot pass ordinary package admission.
Fourteen regressions include success with only the intended fault, fourth
process nonzero/signal/timeout after writing artifacts, failed or missing
results, failed receipts, unexecuted work, every attempt missing its reset
call, incomplete call completion, wrong metadata/mode and uncleared optimizer.
One regression also starts real CPU subprocesses, fsyncs their synthetic reset
and result artifacts, then observes a nonzero exit or terminates the owned job
before passing the actual receipt and retained bytes through the full reader.

## Windows descendant cleanup root cause

The controller's full check and isolated retry both failed an existing process
fixture. The combined runtime/test had no changes in `a1f68d2` to `a426981`;
this is not attributed to a stage 2 regression. This repair reproduced the
original isolated failure, including locked `stderr.log` during teardown.
An attempted explicit job termination/drain-reserve fix alone still failed;
both failures remain in local evidence.

The Windows venv `python.exe` redirector can spawn the real interpreter before
`AssignProcessToJobObject`. The Python stdin gate prevents worker code but
does not suspend the redirector. Job assignment is not retroactive for those
children. A controlled 0.35-second assignment delay against retained
`a426981` source produced a successfully exited bootstrap, an empty owned
job, a still-running recorded descendant and two blocked pipe readers.
Terminating only that exact fixture tree then released both readers. No
unrelated process was terminated and no ACL/security token changed.

The launcher is now created with `CREATE_SUSPENDED`, assigned to the owned
job, and only then resumed and released through its original Python gate.
Job termination waits for zero active associated processes before closing
the handle. The terminal report retains owned process IDs and the zero-active
observation. Readers must terminate and release log files within the caller's
existing terminal deadline; the process kill grace is not a reader scheduling
deadline. Errors still prevent `complete`.

The same 0.35-second delayed-assignment probe now records the descendant in
the owned job, zero remaining processes, no live drains and one launch per
branch. The original fixture's work/terminal limits and success assertion are
unchanged. Two added regressions check delayed redirector assignment and
finite log-close latency within the existing reserve, including real log-file
rename after successful cleanup. No tests are skipped to obtain a pass.

## Delivery and verification

Final commands, results, environment, file bindings, failure history and
retained proof digests are in
[`configs/native-solve-stage2-review-repair-20261004-evidence.json`](configs/native-solve-stage2-review-repair-20261004-evidence.json).
Local evidence is `.irisx/native-solve-stage2-review-repair-20261004-001/`.
The controller review and its original partial temporary directory are
preserved. Changed historical source files also have exact baseline copies
and remain recoverable from `a426981`.

The native producer and plan bytes did not change. The existing inert
`proposal-006` remains bound to plan digest
`sha256:6addcdc7c292cfb3a562b47e629690f2ff6f8fbd3c85c3f82ea843d9eadc7557`.
There is no new execution admission or GPU proposal identity. The external
verifier changes and Windows combined supervisor changes affect local code;
no historical notebook, run, model, package or result bytes were rewritten.

Re-run using the existing ML environment with the controller's exact offline
variables (`PYTHONHASHSEED=0`, `PYTHONUTF8=1`, `PYTHONDONTWRITEBYTECODE=1`,
`PYTHONPATH=<repo>/src`, `IRIS_NATIVE_CODE_ONLY_DIR=<repo>/.irisx/native-solve-stage1-20261004-001/code-only`,
and all three HF/Transformers offline flags set to 1):

```powershell
.irisx/nvarc-ml-venv/Scripts/python.exe -m unittest tests.test_nvarc_native_solve tests.test_arc_kaggle_submission tests.test_nvarc_native_multitask tests.nvarc_native_solve_strict tests.nvarc_native_multitask_strict tests.nvarc_native_multitask_archive_strict tests.test_nvarc_combined -v
.irisx/nvarc-ml-venv/Scripts/python.exe tools/repository_check.py --all
.irisx/nvarc-ml-venv/Scripts/python.exe tools/stage_nvarc_native_multitask.py preflight --package .irisx/native-solve-stage2-20261004-001/proposal-006
```

Native GPU cache, nonempty trained rankings, target GPU process isolation,
resource sufficiency and cross-profile DFS numerical replay remain unverified.
No official score or method promotion follows. The next step is controller
acceptance of this repair; stage 3 and external execution remain undispatched.
