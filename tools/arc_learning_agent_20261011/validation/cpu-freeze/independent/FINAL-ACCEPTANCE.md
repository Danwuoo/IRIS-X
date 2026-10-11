# Independent CPU acceptance

Verdict: PASS, CPU engineering scope only. No unresolved blocking defect was observed in the frozen runtime after the reported corrections.

The independent full suite passed all 136 tests in 144.027 seconds, with no failures, errors or skips. A fresh interpreter used PYTHONHASHSEED=0, offline flags, hidden CUDA devices, opt-in tiny-neural tests, and a workspace TMPDIR outside the source tree. The 97-file runtime closure and 37-file package match SOURCE-FREEZE.json SHA-256 29d2f2989f43151115ae5a7db0befa2e529f19e88220f46a37e051fc892cd74b. Before/after source hashes are identical.

## What was verified

- Actual tiny neural full-native-head loss, gradients and LoRA updates; actual Granite tokenizer and 100,352-column head tests
- Completion/EOS masks, tokenizer grid admission, full-head shifted likelihood and complete common-view ranking
- Deterministic objective/family sampling, exact CPU checkpoint/restart, A/B task isolation and adapter/optimizer/RNG reset
- Training-only, held-out-demo-verified rollout and repair admission; no held-out target in generation/feedback
- Actual bounded AST execution with Linux resource limits; owned-process closure across setsid/double forks; forced failures rejected
- Fixed 120-task/167-input scoring denominators, source/request/run/process proof bindings and no evaluator launch before seal verification
- Two-task synthetic session from calibration/global SFT through controller, complete owned-process closure, sealed predictions, isolated scorer and verified evidence archive
- Ordinary cooperative deadline completion inside separate hard call/stage deadlines; hard failures remain fail-closed

The two-task session selected zero TTT and therefore does not itself establish nonzero task-local updates. Separate actual-neural controller/training tests establish TTT and exact reset. The synthetic scorer result is never an ARC public result.

## Corrections accepted in the final snapshot

Earlier findings were corrected: per-task output identities; metered native adapter-state propagation; failed-update admission; preserved historical train/dev partition; declared objective/family schedule with real token accounting; held-out training-demo rollout verification; complete declared dev comparison sets and actual update counts; process-tree closure; source/request/run bindings; cooperative versus hard deadlines. Current primary target remains existing project micro pass@2 >= 0.50, meaning at least 84/167, with task-macro and whole-task success secondary.

## Qualifications

This acceptance does not establish production Granite 8B GPU execution, G4/L4 memory fit, long-context throughput, worst-context calibration, original NVARC scale/numerical parity, official competition readiness, or an accuracy gain. The implemented three-update calibration is not a full worst-context generation/scoring/TTT calibration. Production materials, runtime resource admission and any future GPU/publication action remain separately gated.

The first independent pass is preserved in acceptance-v1: 114 tests ran, 113 passed, and one session test correctly rejected an output/source overlap caused by the reviewer's in-source TMPDIR. It is an environment-preparation error, not a runtime defect. The corrected independent pass is acceptance-v2.

Machine-readable result: acceptance-v2/INDEPENDENT-ACCEPTANCE.json. Full log, unchanged source snapshots and compact actual-neural session receipt are adjacent. No GPU execution, provider mutation, publication or Git push occurred in this review.
