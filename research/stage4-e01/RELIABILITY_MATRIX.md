# Stage 4 E01 finite reliability acceptance

E01 starts from E00 repair `089589652f6f4f9b3d9c3d68f4b65a2dbe331641`.
Only output/checkpoint lifecycle changes. The contract was written before code
in [nvarc-output-lifecycle.md](../../docs/development/nvarc-output-lifecycle.md).
This matrix specifies the evidence mapping; the local handoff records exact
run counts, times, failures, skips, commands and SHA-256s after validation.

`tests.test_nvarc_output_lifecycle.FiniteFaultReplayTests` runs F01–F24 twice
with finite fake clocks and synthetic inputs. No neural model is used in those
48 replays. F14/F15 reuse the existing fake forward fixture; their OS lifecycle
evidence comes from distinct bounded real CPU tests. Fake time is not OS kill
or actual GPU evidence. Other tests reuse the existing permitted tiny CPU model.

| ID | Two-replay check | Additional targeted regression / limits |
| --- | --- | --- |
| F01 | Actual synthetic ID, one test, exact schema | Submission/full native tiny export tests; no official score |
| F02 | Unequal four/one test counts, full denominator | Evaluator-only synthetic micro/macro/whole-task ratios; truth stays outside store |
| F03 | Reordered test inputs invalidate task binding | Offline content join and native multi-test source IDs |
| F04 | Reordered task/record completion mapping | Public mailbox and native task-order tests |
| F05 | Foreign task and duplicate index rejected | Missing tasks remain in full coverage; third attempts rejected |
| F06 | Duplicate JSON/NaN/bool cell rejected | Strict exporter input parsing and generic JSON tests |
| F07 | Ragged/empty/oversized/illegal colors rejected | Bad committed bytes reject recovery with no older fallback |
| F08 | Test output and nested evaluator metadata rejected | Public telemetry and native recursively rehashed truth gates |
| F09 | One model, duplicate-first and constant filler distinct | Offline model-only metrics keep filler credit absent |
| F10 | Model/source/code bindings differ: reject | Real native source-program digest tamper blocks recovery after tiny strict export |
| F11 | Synthetic missing dependency traceback retained | Rendered early material/hardware failure preserves denominator; no provider diagnosis |
| F12 | Infeasible actual allocation rejected | Existing original complete epoch/token/forward caps unchanged |
| F13 | Ordinary test-zero timeout, test-one candidate retained | Public independent next-test deadline and native partial continuation |
| F14 | Expired admission never adds a reservation | Existing fake forward reservation/completion accounting |
| F15 | Late fake return, next entry denied | E00 real finite CPU watchdog/exit-17 tests; no GPU kill claim |
| F16 | Four/eight partial never ranked; prior full retained | Original eight-view and multiplicity parity regressions |
| F17 | Later worker failure keeps prior test | Real CPU process receipts; native killed-worker checkpoint regression |
| F18 | Unqualified next task rejected | Existing tiny full-128-step fault/reset/retirement tests; no CUDA OOM claim |
| F19 | Undispatched tasks stay in all-test coverage | Existing finite parent reserve/no-dispatch checks |
| F20 | Member write interruption before commit keeps previous | Real OS kill in partial member write, after member, and before commit; exact old member hashes retained |
| F21 | Manifest/commit publication boundary | Marker loaded once under a changing writer; real kill immediately after marker replace and after commit; mixed projection rejected |
| F22 | ENOSPC publication keeps previous | ENOSPC and EACCES write injection; initial no-storage creates no successful marker/submission; actual filesystem-full not forced |
| F23 | Export deadline after commit preserves new candidates | Real kill after root submission replace/before projection marker; strict gate failure; real tiny replay repairs root, source tamper blocks it |
| F24 | Primary and secondary logger errors separate; stale run rejected | Actual official-parent exception identity preserved; public errors returned; corrupt/rehashed semantic files reject recovery |

Real publication fault tests use seven bounded CPU child barriers, OS process
termination/wait, and on Windows a handle to the actual writer (which may differ
from the venv launcher PID). Lock removal is explicit only after that handle
signals termination. Receipts preserve PID, actual writer PID/exit, barrier,
platform, elapsed time and stdout/stderr. No owner or historical files are removed.

Generation outcomes describe output validity and evidence separately, with
notebook exit unknown until terminal handling. Public lightweight evidence is
false; native strict replay uses existing gates, with explicit tiny fixture
provenance in tests. Terminal legal-output + failure fixtures keep
`output_valid=true`, `notebook_exit=failure`, and `promotion=false` independently.
No recovery qualifies a source/reset/transcript/hash failure or permits promotion.

Never run here: Linux OS kill/power-loss/network filesystem/GPU storage faults,
true full-volume disk exhaustion, real model benchmark, Kaggle operation,
official/hidden/locked scoring or method promotion. ENOSPC/EACCES are injected
IO faults, not claims about actual media exhaustion or a specific ACL.
Official 56840442 remains Notebook Threw Exception with null score and unknown
cause. E10/E20 and further execution are outside this task.

[Control-review repair 001](REPAIR_001.md) records the later independent cleanup
and missing-barrier findings, the finite protocol repair and its separate evidence
root. Original E01 and controller failures remain retained.
