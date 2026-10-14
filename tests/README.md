# Tests

Start with the [workstream guide](../docs/workstreams/README.md).
Use the [management guide](../docs/management/README.md), generated board and
[static inventory](inventory.json). `python tools/dev.py check` checks metadata
and exhaustive test-file coverage without importing tests. `verify --suite NAME`
selects static entries first and executes each selected file in a fresh process.
Reports live in new ignored `.irisx/core/verification/<suite>/<attempt>/` roots.
No metadata field can supply a shell command.

| Suite | Scope / prerequisites |
| --- | --- |
| management / navigation / integrity | Repository structure, catalog, research pins, runner/gate negatives; stdlib + available local Git objects |
| core / distribution | Shared contracts/reference flow/CLI, formal wheel safety; no ARC operational inputs |
| arc-unit | Explicit self-contained CPU smoke surface,124 tests in initial local run; `packaging` test-only dependency |
| line-b | Independent synthetic label engineering loop; no ARC implementation or inputs |
| arc-unit-audit | Remaining public ARC CPU modules, including tool-local suites and unresolved imports/platform failures; visible audit, never relabeled private merely because it fails |
| arc-reconstruction / operational | Authentic historical/private inputs; blocked before import under this task |
| arc-native | Optional native model/training dependencies; blocked before import because training is outside this task |

Every Python file under tests/ and every tools/**/test_*.py is indexed. Additional
tool-local helper/fixture modules are explicit helper entries, not zero-test passes.
Special `*_strict.py`, `load_tests` wrappers and four import-side-effect scripts
retain named classification reasons. Public audit modules remain executable and
visible in CI alongside the original legacy aggregate. No tests were deleted or
renamed to obtain a green public smoke gate. The small arc-unit surface is not
acceptance of all ARC source or research.

```sh
python tools/dev.py verify --suite core
python tools/dev.py verify --suite arc-unit
python tools/dev.py verify --suite line-b
python tools/dev.py verify --suite arc-unit-audit
python tools/distribution_check.py --output .irisx/core/distribution/new-attempt
python tools/repository_check.py --all
```

`verify` refuses empty selections,missing coverage,collection errors,zero-test
modules and unexpected skips. The only public skip allowances are exact test
ID + Windows platform + WinError1314 reason for two actual symlink negatives.
Mocked link guards still run;all skipped cases remain counted. Cancelled,timeout,
blocked and missing reports cannot pass the fixed workstream-gate.

Public and formal distribution CI matrices use Linux/Windows and Python3.11/3.14
with fail-fast false. All PRs run all public suites;there is no path filter.
ARC public audit and retained offline-validation remain separate red-capable
jobs without continue-on-error. The gate validates every expected matrix report
and actual tested commit;it is narrower than the full aggregate. Branch protection
is unchanged and no required-check registration is claimed.

Test-only pins are separate from dependency-free product metadata. Public pins
use existing packaging26.3. Audit pins list small numpy/Jinja2/IPython dependencies;
no ML stack,provider SDK,model or authentic inputs are installed by these jobs.
NumPy2.4.3 metadata lists Python3.11â€“3.14 ([primary package metadata](https://pypi.org/pypi/numpy/2.4.3/json));
pins do not prove cross-platform execution. Locally,the stage environment inherits
only the available Python3.14 packages,not a downloaded ML environment.

Full aggregates require a fresh interpreter,hashseed0,offline flags,an existing
ignored .irisx parent and workspace-backed TMPDIR with >5GiB free. Preserve raw
exit codes and test IDs. Missing historical inputs remain blockers;new synthetic
fixtures never impersonate authentic owner/readback evidence. Repeated preparation
attempts have separate receipts. A focused pass is not full CI,GPU or efficacy.

The owner also prohibits training, including the retained pure-Python synthetic
SGD. `arc-training` explicitly records those public cases, distinct from missing
private inputs. Scoped selection blocks them before import. The unchanged public
entry `python tools/repository_check.py --all` retains complete unittest discovery
through `tools/no_training.py --aggregate`, preserving every collected test ID,
order and count while reporting training cases as BLOCKED errors. They remain
nonzero failures, never passing skips. Keep `ARC_LEARNING_NEURAL_TESTS=0`.
Discovery is the original aggregate's import-based mechanism; this is not a
general Python sandbox or proof about arbitrary import-time generated code.

Earlier WSF-02/03 receipts are immutable observations: absent ML dependencies
did not stop `tiny_train` in original aggregate/public boundary tests. Those
parameter updates occurred during developer tests; WSF-04 records the scope
failure and the new barrier, and does not retroactively label earlier execution
training-free. No model experiment, provider run or new scientific score follows.

## WSF-R1–R4 corrective verification

For commit-bound acceptance use `python tools/dev.py verify --require-committed
--suite <suite> --output .irisx/core/<task>/<new-attempt>`. A clean source runs
from raw committed Git blobs in an isolated local snapshot. Inventory, runner
and whole-source manifest identities accompany both parent and module reports;
caller/snapshot changes invalidate attestation. No remote source fetch or Git
checkout filter/hook is used. Normal dirty iteration remains available without
the flag, explicitly `evidence_kind=development`, `attestable=false`, with null
`target_commit` and separate `head_commit`; it cannot pass an acceptance gate.

Tool snapshot entries declare `import_roots` and `module_name` for their single
owning source root. Each file gets a fresh isolated process. The gate reads
the tested commit's inventory Git object to derive mandatory modules and OS skip
policy; report-selected paths do not define completeness. Missing target Git
objects, source binding, required modules or valid skip records fail closed.

The owner-authorized corrective branch defers the original ARC audit and legacy
aggregate before execution. Their CI jobs remain explicit non-success BLOCKED
steps, while their original commands and earlier failures remain retained.
Public suites and formal distribution continue to run. This does not clear
historical audit errors, establish full-green CI or broaden no-training safety.

## Retained failure records

These are historical observations, not results of this PR:

- The code18 snapshot's [CI run 38353809559](https://github.com/Danwuoo/IRIS-X/actions/runs/38353809559)
  records 1,578 tests, 5 failures, 96 errors and 110 skips.
- Run008 `cc14bd1a79aac1fe6135017c9e09d4834300675d` had seven README findings in
  [CI run 38496849147](https://github.com/Danwuoo/IRIS-X/actions/runs/38496849147),
  stopping before downstream tests in the observed job.
- Its [separate aggregate review](https://github.com/Danwuoo/IRIS-X/blob/cc14bd1a79aac1fe6135017c9e09d4834300675d/research/native-continuation-20261014/transfer-package-review.json)
  records 1,583 tests, 2 failures, 35 errors and 74 skips, and explicitly no
  matched clean-baseline comparison. Do not label all errors inherited.

For each new check report commit, command, interpreter/environment, actual
counts and the tested scope. Separate assertion failures, missing inputs,
unsupported environments and unexecuted suites. No blanket continue-on-error,
removed tests, historical-evidence edits or skip-to-green claims. A focused pass
is not full CI, complete scoring, successful deployment or scientific efficacy.
