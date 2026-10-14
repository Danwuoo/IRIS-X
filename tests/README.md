# Tests

Start at the [workstream guide](../docs/workstreams/README.md). The existing suite
still covers P1 contracts/reference evaluation/selection/package/CLI, historical
P2 admission, retained ARC trials and transport, evaluator isolation, checkpoint
and result bindings, and the P0 archive catalog. Existing tests are not deleted,
relocated or exempted by this foundation. Archived tests stay in the cold tag.

## Dependency classes, not a claim of a completed suite split

| Class | Examples / scope | Required context |
| --- | --- | --- |
| Navigation | `test_workstream_navigation.py` | Python stdlib and current documentation; no installation, archive, model or login |
| Shared product | contracts, engine, reference flow, package and CLI checks | Product installation and their declared local fixtures; not GPU evidence |
| ARC CPU | loader, assembly and mocked transport checks | Exact tested source, supported environment and declared SDK/native test dependencies where applicable |
| Historical reconstruction | old source/candidate/inventory checks | Genuine pinned Git objects and original authenticated inputs; missing data is not a pass |
| Private operational integration | run008 admission and active-wire regression fixtures | Authentic private readbacks/owner bindings/drafts or separately reviewed new synthetic fixtures; public checkout alone is insufficient |

This table is a dependency guide, not an exhaustive machine-readable test
inventory. Some run-specific tests live under `tools/` and are not covered by
`unittest discover -s tests`; read the pinned run guide before running them.
The run008 implementation is on a separate branch, not added to main by this PR.
No new suite selector, nested package support or domain test split is claimed.

## Standalone foundation checks

```sh
python -B tests/test_workstream_navigation.py
python -O -B tests/test_workstream_navigation.py
```

The `workstream-navigation` workflow runs these independently from the original
`offline-validation` workflow. These checks validate the navigation schema,
local status paths, required status sections and pinned cross-branch references.
They do not validate truth of external status, remote availability, product
behavior, historical reconstruction, provider admission or GPU/scientific results.

## Complete validation remains available

From a properly prepared checkout:

```sh
python -m pip install --no-build-isolation -e .
python -m unittest discover -s tests -v
python tools/repository_check.py --all
```

The last command includes validator self-tests, repository invariants, the tests
under `tests/` and diff checks; it does not discover every tool-local suite.
The existing full CI workflow is retained. Restoring README's historical index
may allow previously masked tests to run; it does not prove they pass.

For historical Stage 4 aggregates, follow the original setup: fresh interpreter,
`PYTHONHASHSEED=0`, recorded offline flags, a workspace-backed TMPDIR with the
ignored `.irisx` parent and sufficient space (the guidance specifies >5 GiB).
Keep the inherited environment rather than `env -i`. Do not manufacture original
Git objects, approval, observations or missing fixtures. New synthetic fixtures
must be separately named/reviewed and must never masquerade as original evidence.

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
