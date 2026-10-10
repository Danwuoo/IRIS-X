# Validation evidence and outstanding acceptance

Development base: `e946fb89a1deb155bb52f5c5b34e703491272853`.
This file separates historical v1 observations from v2 source checks. It does
not certify Linux resource enforcement, a GPU run, actual mounted Datasets,
or the full repository CI. The rebuilt v2 notebook and Windows portable
acceptance are recorded below. Historical N5-N14 scientific code and the N14 gate
remain outside this additive package's changes.

## Historical v1 evidence

The parent reported Linux v1 results of **150 tests: 149 passed and one import
ERROR**. This was not a clean test suite. Its bounded SMOKE completed **1,152
checks in 94.75 seconds**, and its separate semantic acceptance completed
**192 checks**. These are observations of the v1 package, before the v2 control
repair, dead-relation removal, automatic offline bootstrap and persistent
CP312 model-owner changes. They do not establish v2 throughput, witness
coverage, model startup, or FULL completion.

The earlier Windows v1 record reported **161 passing tests and eight skips**
(169 total, 129.937 seconds). Seven skips required Linux resource enforcement;
one required unavailable symlink privileges. Its source identity was
`6f092e16d48dd2ce38065e1cb6c6dcd56c645f54be29cbf829ea6905559c02d1`,
and its notebook SHA-256 was
`c448e7cda72ba498e1b1e69d5e2bd9309f5248fe6bea3f60475ad49e1b968813`.
Those identifiers are historical evidence, not current v2 deliverable hashes.
That notebook's default cells were checked as inert, with zero new files and
zero new `tools`/torch imports; its enabled workflows were not thereby tested.

The earlier complete repository check failed: **1,262 tests, two failures,
1,134 errors and 109 skips**. Reported categories included Windows temporary
directory ACL issues, absent resource/SIGKILL support, and retained-material
or package-validation failures. Repository invariants, three validator
self-tests and eight representative recovery checks passed separately.
No statement in this delivery claims the full CI is green.

## v2 changes and targeted checks

IR v2 removes `same_normalized_mask` from the legal schema and finite inventory.
Its core has 5,965 canonical plans; FULL coverage reserves 47,848 checks, and
the complete study ceiling is 52,536 verifier checks / 10,507,200,000 gas.
The original 200,000-gas, 2-CPU-second, 3-wall-second and 256-MiB per-check
limits remain. Concurrency is bounded to four verifier workers. A static
compiler pass does not attest resource-bounded execution or FULL completion.

The required controls now comprise 64 independent-reference positives and
64 legal wrong-program negatives, each with at least one independently
confirmed mismatching demo. All original positive task IDs, inputs and targets
remain byte-identical; one tied-anchor positive plan changed from the removed
relation to `right`, with revision provenance, preserving its no-op targets.
The earlier target mutants are 64 separate detector controls, outside the
required 128. The targeted controls suite passed **24 tests**, with **one
Linux-only acceptance test skipped** on Windows (25 total, 0.877 seconds).
All 192 required-plus-detector plans passed compiler admission without
executing generated source as host Python.

Canonical required-control SHA-256:
`4c1b631ee7090d24caf7b4da976cd6f81c4c273e8b59070802a8cbbacb479608`.
Canonical detector-control SHA-256:
`431920559bdbc34910eb138bd840119f1ef0a68cdb040cc7f2a506d305688b5e`.
Preserved positive-task SHA-256:
`d4f0168553db088409bfe5f4f2ec08f6bd39a194f4554ef5deb83856f0335d50`.

The notebook generator now uses readable English and the automatic preparation
configuration `{'input_root': '/kaggle/input', 'explicit_roots': {}}`. Model
paths/environment hashes are not notebook inputs. Model asset discovery,
offline installation and loading are behind complete FULL acceptance and
explicit `ENABLE_MODEL=True`. The production design has one persistent owner
process in the pinned CP312 environment. Notebook tests use an explicitly
synthetic runner; those tests cannot establish model or runtime8 acceptance.
Scientific/model code never semantically reads queries, gold or solutions.
The separate integrity child streams all runtime bytes, including evaluator
members, solely for hashes and returns aggregate proof. Evaluator paths,
per-file gold hashes and evaluator content are not supplied to the model.
The targeted notebook suite passed **17 tests**, with **one symlink-privilege
test skipped** on Windows (18 total, 6.240 seconds). It checked default inert
cells, pure Dataset-root configuration forwarding, rejection of legacy path
configuration, exact trusted-source extraction and retained file protections.
The final v2 notebook was subsequently rebuilt and its actual default cells
checked by the frozen portable acceptance below.

## Frozen v2 portable acceptance

Python 3.12.10 on Windows executed the complete package from a freshly extracted
directory **outside the repository**: **255 tests, 242 passed,
13 skipped**, in 241.827 seconds. The skips remain unaccepted platform
checks; they are twelve Linux-only checks and one Windows symlink-privilege check.
The exact command, complete log and receipt are in the archive's
`evidence/portable-tests.txt` and `evidence/portable-validation-receipt.json`.
Runtime source and test identities were unchanged throughout that run. The
rebuilt notebook's default cells created zero files and imported no `tools` or
torch modules. This is package CPU/mock acceptance, not full IRIS-X CI.

- Package source identity: `758c58ac1dced5797b37dae73572386551c5274a6dfa657429102d131a153e87`.
- Complete executable overlay: `f839a3ad81ab65f7a4f441b2cec00784521b7483ff716778d1b425dd1ca4899f`.
- Notebook SHA-256: `d189bd47d07242b8c41859dc3ef33e921536f568ae83e1edab740a84d25fb95a`.

The first v2 portable attempt is preserved under `evidence/first-portable-attempt/`.
It ran 254 tests and failed with nine reported failures (including subtests),
one error and thirteen skips. Notebook fixtures reached Windows MAX_PATH in a
long extraction directory; subsequent acceptance used a shorter fresh Temp path
without changing OS policy. Two remote-error timing assertions exposed Python
3.12 Windows `monotonic()`'s 15.625-ms clock resolution. Observed parent/child
dispatch elapsed time now uses `perf_counter()`; all deadlines remain monotonic.
A deterministic coarse-clock regression and independent review passed before
the next full portable rerun. That second attempt ran 255 tests with seven
reported notebook failures (including subtests) and thirteen skips: the shorter
extraction path still put the nested notebook demo-file fixture beyond MAX_PATH.
Its record is retained under `evidence/second-portable-attempt/`. Test-only scratch
directory names were then shortened while retaining inherited ACLs, full UUIDs
and checked cleanup; production source and boundaries were unchanged. A focused
notebook rerun passed before the final successful full portable rerun above.
Both failed source ZIPs and receipts remain local immutable evidence and are
not presented as accepted v2 test snapshots.

The final bootstrap and owner review also checked PID/birth-bound child cleanup,
an independent bootstrap parent-loss/deadline watchdog, exact admission schema,
immutable actual-environment bindings across resume, source consistency with the
CPU gate, and export time retained within the shared initialization allowance.
Those mock/static checks do not substitute for the Linux and real-asset work below.

## Reproducible checks and remaining work

From the repository or portable-package root, on an existing Linux CPU host:

```sh
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 CUDA_VISIBLE_DEVICES= python3 -m unittest discover -s tools/arc_consolidated_20261010/tests -t . -p 'test_*.py' -v
```

Remaining acceptance is explicitly version-specific:

- Run the v2 suite on Linux, including real AS/CPU/FSIZE enforcement and all
  128 repaired controls; retain failures, skips and logs without converting
  them into passes. Re-measure bounded v2 SMOKE throughput. FULL coverage and
  the two-task witness gate are not yet established by the evidence above.
- Verify the actual five pinned Dataset mounts (runtime8, model, wheels,
  CPython and adapter), offline environment preparation, persistent-owner
  lifecycle and native-vocabulary/token accounting. Synthetic fixtures do
  not certify real mounted bytes or startup.
- G4 inference, training and four-L4 deployment have not been run. Four-L4
  official submission remains a separate unvalidated boundary. No GPU or
  paid provisioning is implied by successful CPU tests.

Windows fails closed for resource-limited verifier work. Earlier local WSL
access was denied and the Docker Linux engine was absent; neither restriction
was bypassed. Reports and archives retain partial/inconclusive results, unknown
reservations and unvisited candidates. Cleanup may outlast a deadline;
program return and evidence sealing do not stop VM billing.
