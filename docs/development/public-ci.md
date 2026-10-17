# Public-checkout CI and retained-evidence acceptance

The public Git checkout does not include ignored `.irisx` historical packages,
native model/tokenizer material, private review receipts, or returned run ZIPs.
A public CI pass cannot attest to those inputs, historical execution, GPU
behavior, a model score, or complete Stage 4 acceptance.

## Complete Linux public lane

From a clean checkout in a fresh Python environment:

```sh
python -m pip install --no-build-isolation -e . packaging==26.3 numpy==2.3.5
python tools/repository_check.py --public
```

The package has no mandatory third-party dependencies. CI explicitly installs
`packaging==26.3` for the real wheel-platform/ABI compatibility tests and
`numpy==2.3.5` for the synthetic tensor/uncapped-inference tests, rather than
skipping them or relying on a developer environment's incidental install.
The workflow checks Python 3.11 and 3.14 on Linux and Windows, with
`fail-fast: false` so one failure cannot conceal the other matrix outcomes.
Linux executes the complete public lane above; Windows executes the explicitly
smaller portable lane below. Both run repository invariants,
validator self-tests, the public test suite, whitespace validation, and the
existing CLI fixture/trial/package/admission smoke checks.

The public test subprocess inherits the environment and adds a fresh-process
`PYTHONHASHSEED=0`, offline Hugging Face flags, `OMP_NUM_THREADS=1`, and an ignored
workspace-backed temporary directory under `.irisx/public-ci/tmp`. It does not
download or synthesize historical data. Existing optional dependency tests
continue to report their own skips when dependencies are absent. Installing
optional dependencies expands executed coverage and can expose additional
environment constraints; it does not authorize fetching private fixtures.

`tools/run_public_tests.py` enumerates the exact retained-evidence test IDs and
their required inputs. Each is reported as an **UNVERIFIED skip**, not a passing
assertion. New tests are not automatically excluded by module or class name.
A stale manifest, missing public fixture, test import error, or unclassified
test failure fails the public lane.

The separated historical checks cover:

- ABC001–005 exact package/SFT provenance, private visible-task replay and
  predecessor result archives.
- Native exporter replay using the retained tokenizer/source material and
  immutable historical notebook reconstruction.
- Native transport tests whose class setup constructs the complete retained
  native008 package before exercising its fake provider.
- The exact native009-to-010 positive admission replay and prior native007
  admission, which require the original private review receipt/packages.

Tracked ABC plan/budget/arm assertions, material-sidecar unit checks, malformed
admission rejection, repository/source integrity, and other self-contained
tests remain active. The malformed-admission unit tests explicitly mock only
the historical review digest lookup and assert rejection before package
preflight; they do not establish that the original review exists or is valid.

## Explicit Windows-portable subset

```sh
python tools/repository_check.py --public-portable
```

This named lane is a portable subset, **not complete Linux public acceptance**.
The native Kaggle/Linux tooling uses real `resource` accounting, process groups,
procfs, directory descriptors/fsync, no-follow paths, `fcntl` locks, interval
signals and anonymous-inode publication. Those contracts are not emulated or
weakened for Windows. Annotated tests report **UNVERIFIED Linux-only capability**
with their original test IDs and concrete requirements.

`tests/platform_requirements.py` provides metadata-only `@requires_linux`
annotations. Only `--public-portable` interprets them. Neither ordinary unittest
nor `--all`, `--public`, or `--retained` changes execution because of this metadata.
A class annotation is used only where its common fixture/runtime import requires
Linux; mixed modules annotate individual methods. Deferred test imports preserve
independent model, bundle, JSON, admission, source, receipt, and schema checks.
No module-name exclusion, import-error suppression, fake OS constant, or blanket
skip of an independently portable module is used. Unclassified failures and
import errors still fail. The retained-evidence exclusions remain separately
identified, and retained acceptance cannot be combined with the portable subset.

The portable selector can also run on Linux for boundary regression testing.
Capability-negative discovery can demonstrate that unavailable POSIX imports do
not mask portable tests, but it is not an actual Windows execution result. Only
the Windows CI jobs establish that platform's behavior. Windows-supported tests,
including the combined supervisor's owned Windows Job cleanup, remain enabled.

## Strict acceptance remains separate

The existing strict commands are unchanged:

```sh
python -m unittest discover -s tests -v
python tools/repository_check.py --all
```

Missing required historical evidence remains an explicit failure in these
commands. Follow the repository's Stage 4 preparation requirements, including
a fresh hash-seed-zero interpreter, offline flags and a workspace `TMPDIR`
with more than 5 GiB available. Do not fabricate the missing data, weaken the
native checks, or treat a public-lane pass as strict acceptance.

To execute only the enumerated historical integrations against genuine local
inputs:

```sh
python -m tools.run_public_tests --retained
```

This command runs the original test bodies and fails when their evidence is
missing. It never retrieves historical inputs or changes execution authority.

## Repair verification limits

The public fixture repair uses the existing SHA-256-pinned E12 INERT001 plan
only as data for its native learning-rate reference. Its original four-ULP
comparison limit remains unchanged. New literal E12 helpers are explicitly
synthetic CPU test doubles, not recovered run evidence or native validation.

The distributed launcher now passes a selected nonzero loopback port to
PyTorch static rendezvous. The original two-rank test and 45-second limits are
retained. A sandbox that prohibits Gloo network-device initialization cannot
establish real collective/resume/failure behavior; a mock launcher test or a
dependency-free public CI pass must not be presented as that validation.

The combined supervisor repair keeps the owned Windows Job query handle open
after a retirement-thread startup failure. It requests termination immediately,
then deferred finalization measures zero active descendants before closing the
handle. The first observed membership is retained, while the startup failure
still makes the branch fail. Stop/query failures retain errors and use
kill-on-close without inventing measured cleanup proof. Synthetic WinAPI tests
and Linux process regressions do not substitute for the real Windows Job test.
This legacy supervisor is outside the immutable AF3 goal-source package.

The real owned-descendant retirement-start-failure regression passed on both
Windows/Python 3.11 and 3.14 in [run 39003998472](https://github.com/Danwuoo/IRIS-X/actions/runs/39003998472)
at commit `51e575778b3a54d59692a5f9b428a51cbcc61a04`. Both Linux jobs also
passed. That matrix was not all green: Windows exposed unrelated default-code-page
notebook writes, Git newline conversion of pinned notices, and synthetic quota
timestamp rounding. Their fixes retain UTF-8 script bytes, exact notice hashes,
and strict future/stale quota rejection; no additional platform exclusions apply.
