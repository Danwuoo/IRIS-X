# WSF-04 developer handoff

State: review_ready. Independent verification remains pending.

Base: refactor/workstream-pr3-validation at `756cd560f8d61256ed35e12c3c3637ec456c6141` (PR3 final delivery).
Branch: refactor/workstream-pr4-arc-boundary. Code checkpoint: `0e344020e73ba59c06051b598d1720a74e3fe990`.
Foundation: `08b1cee49b0c677ec9ca8bfdf76e5e4f16b26059`.
Fixed run008 reference: `cc14bd1a79aac1fe6135017c9e09d4834300675d`.
The later delivery commit contains metadata/handoff; it is reported via Git/PR,
not embedded as a self-referential hash. PR remains Draft against PR3; no merge.

## Implemented and checked

ARC registration and dispatch now have one implementation in
`src/irisx/domains/arc_agi_2/cli.py`. Shared `irisx.cli:main` preserves all names,
arguments and errors and passes the original path converter/repository root.
Six tests compare the full parser to the fixed PR3 delivery and mock all 24
dispatch routes; generic paths admit parser-only registration without loading
legacy ARC/Kaggle/ML/tools. Frozen implementations retain their exact paths.

`tools/dependency_check.py` statically checks registered core/domain edges and
facade-to-legacy exceptions through `tools/dev.py check`. Its 18 synthetic
negative/read-only tests cover reverse/cross-line edges, neutral namespaces,
relative and recognized dynamic imports, missing/schema/syntax errors.
The [migration map](MIGRATION.md) and [pins](MIGRATION.json) record every moved
scope, consumer, rollback and deliberately retained helper. No helper is moved
without authentic requalification; this is partial entry isolation.

Seven fresh-process public suites at the code checkpoint: **361 tests,
0 failures, 0 errors, 2 expected Windows symlink skips, 0 blocked**.
Counts: core63/distribution8/management128/navigation10/integrity15/arc-unit125/
line-b12. New/affected optimized checks:123 tests, no failures/errors, same2skips.
Raw commands/counts/report hashes are in [self-tests](self-tests.json).

Formal non-editable wheel: two identical SHA-256
`6f1551a0b63f42d970588b8b48a00fa9ba70a661253408fd766fb319a4d06cf6`,
128members with valid RECORD. A fresh consumer venv outside checkout completes
both synthetic core/line-b flows, installed root/ARC help and expected missing
path exit2; origin is consumer site-packages, no editable pth/PYTHONPATH shortcut.

The [actual onboarding exercise](onboarding.json) uses a new clean source-only
local Git clone. All18 commands succeeded. ONBOARD-LB-01 registers plan/guide,
runs line-b12tests, produces a review_ready handoff, checks generated BOARD and
returns WSF-04 context without changing original code/tasks. The actual docs →
BOARD → task → plan → code → handoff chain and ARC STATUS → RESEARCH → fixed
R4/R5 objects were checked. The disposable task stays only in ignored output.
Original private materials are not supplied, deleted or fabricated.

## Failure and scope correction

Earlier aggregate tests and WSF-03 public ARC boundary tests executed actual
pure-Python **synthetic SGD**, contrary to the owner's no-training constraint.
The prior assumption that absence of ML packages prevented training was wrong.
Original source/receipts and prior WSF-02/03 handoffs are preserved as history;
this supplement corrects their training-free interpretation. Exact total update
count is unverified. This was temporary toy test fitting, not a new ARC model
experiment, provider session or scientific score.

Both training test modules now have explicit training scope, separate from
private-input classification. `arc-training` blocks both before import (exit2,
tests0, blocked2). `tools/no_training.py` installs guards on the known fitting
calls before original aggregate discovery and retains classified tests as
same-ID/count/order BLOCKED errors, not skipped/passing tests. Fourteen synthetic
negative tests pass normal/-O; no real fitting body is called by those tests.
The stated environment has no Torch/NumPy model stack and neural opt-in is0.
The controls are bounded developer safeguards, not a general Python sandbox.

The retained `python tools/repository_check.py --all` is **FAIL, exit1**:
1424tests, 143failures, 281errors,
135skips; 26 classified training cases
remain explicit errors; runtime training calls blocked=0.
See [legacy audit](legacy-audit.json). Original aggregate collection and error
exit remain visible. Source preservation does not justify blanket attribution;
ID matches alone do not match causes, and unmatched/transient cases remain
unclassified. An unrestricted old baseline was not rerun because it would fit.

## Research preservation and review limits

ARC STATUS/RESEARCH retain R1–R5, previous results/limits and the current unanswered
hypothesis. Architecture A/B/C differs from SFT256/RL/extra-SFT A/B/C. Modified
BASE/TTT120/172 and exposed-family observations do not become canonical
PUBLIC120120/167 results. The map distinguishes eight retained run008 trees from
fourteen fixed reference-only trees, with original blob/tree IDs. Conditional
next experiments remain conditional; no new topic or experiment is selected.

Thesis, shared contracts/engine/package, original ARC/Kaggle modules, notebooks,
scorers, manifests, trials, research, archive and ARC tools have no byte/path
changes from foundation. No source/test file is deleted. Main/run008 refs and
all tag identities retain their initial values. No main/run008 push, merge,
force/reset/tag move, Kaggle call or restricted packet/model/input acquisition.

Local results are Windows11/CPython3.14.7 developer/subagent self-review only.
Linux/Python3.11/3.12, current remote CI, branch-protection enforcement, authentic
reconstruction, numerical replay, full14B/cuDNN/GPU/four-L4 execution, current
provider state and method efficacy remain unverified. Actual symlink privilege
is unavailable for two tests; mocked and junction negative checks pass. Static
AST checks cover recognized forms, not arbitrary Python-generated dependencies.

Return this branch, code/delivery SHA, Draft PR and these reports to the original
ChatGPT conversation. It must inspect exact remote refs/diffs/reports and rerun
the public/distribution checks in its own environment before a commit-bound
independent outcome. Tasks remain review_ready; no automatic merge or watcher.
