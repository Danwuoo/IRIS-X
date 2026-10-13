# Owned preparation diagnostics repair

This is a local development overlay on the owner-frozen, unsuccessful code18 /
run005 snapshot. It repairs demonstrated diagnostic loss. It does **not** claim
the cause of the owner's manual Editor failure has been established or repaired.
The original inner stderr, closure and request/version bindings are still needed.

## Fixed reference and evidence

- Snapshot commit: `e951604b829497e81bc6e18b32662ff050bd54db`
- Snapshot tree: `f9b10d12b912f3a92238375451c0ad56d4cb7efb`
- Runtime parent: `dbf21033b41aff9327cf4f91159df0133529f176`
- Runtime tree: `e45a5dd49a2e91e20730777e3b447ebecb984481`
- Logical source: `4050616ed0ed34d19501be416650a09ae5cc9c86c875b349a056baec9308f3e3`
- Canonical source ZIP: `22fc93ae1dfbc4d4a7c90cf9907668af5d697dece28cb9211dea82c776d7dc9e`

All 2,558 snapshot paths were verified by their Git blob bytes and complete tree.
The local source reconstruction reproduces all 259 runtime members exactly.
The existing files and historical evidence are unchanged; this directory adds
reviewable successor overlays and tests only.

The reported outer RuntimeError aggregates nonzero child exits, forced shutdown
and deadline conditions. It does not establish an installer, driver, model or
scientific failure. Saved v35 was last documented CANCEL_ACKNOWLEDGED; the manual
Editor attempt has no independently verified version binding here.

## Demonstrated source defects and repair

1. `prepare_entry.py` previously had no internal stage record. The wrapper could
   only report `owned-result`. The overlay emits a fixed-enum stage journal and
   bounded, source/request-associated failure JSON in the existing owned cwd.
2. Installer stderr/stdout was written only to `/tmp/.../installation.log`, which
   the selected-output collector does not retrieve. On an installation failure,
   the overlay retains at most 128 KiB of first/last bytes under the launcher.
   Its descriptor explicitly records original size, extent offsets, truncation
   and a digest of retained bytes only. The separate raw excerpt is private
   diagnostic evidence and never appears in the safe failure summary.
3. The outer launcher now adds a safe exception note with the context-matching
   preparation stage. Missing, mismatched, unsafe or malformed reports remain
   unknown; arbitrary exception text and log contents are never surfaced by it.
4. The collector overlay adds precisely three **optional** bounded output paths.
   Its required evidence set, original admission and failure classification,
   process-closure gates and scoring rules are unchanged.

Directory acquisition walks components with `O_DIRECTORY|O_NOFOLLOW`. File reads
reject aliases, nonregular files, hardlinks and detected mutation; writes are
exclusive and private. Diagnostics are best effort and never replace the original
exception, renew clocks, authorize closure, prove GPU work or admit scoring.

## Local validation

Run each suite in a fresh interpreter from the repository root, using an ignored
workspace-backed temporary directory with more than 5 GiB free:

```sh
mkdir -p .irisx/tmp
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 TMPDIR="$PWD/.irisx/tmp"
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/preparation_diagnostics_repair -p 'test_*.py' -v
python -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/preparation_diagnostics_repair -p 'test_*.py' -v
```

The tests cover safe metadata projection; source/request mismatch; duplicate and
nonfinite JSON; symlinks, ancestor replacement, hardlinks and FIFOs; log size and
mutation; exclusive evidence writes; producer/reader exception-enum parity;
original exception preservation; real pidfd-owned child success/nonzero exit,
pipe overflow and setup failure; immutable clocks; collector nonpromotion; and
AST parity of the original preparation and collector behavior.

The integration test uses the real reconstructed 259-member source and genuine
owned process guard. It authenticates source/policy/environment, then stops at
an empty **synthetic** Dataset mount before any installer, tensor import or GPU.
Deeper successful preparation stages use explicitly mocked CPU fixtures. Neither
kind establishes real pinned installation, driver/GPU admission or PUBLIC score.

Build an inert reference bundle for review:

```sh
python -B tools/arc_qwen_rlvr004_20261013/preparation_diagnostics_repair/build_local_bundle.py --output-root "$PWD/.irisx/preparation-diagnostics-review-001"
```

The bundle has a coherent inherited source005/run005 namespace, unchanged source
ZIP, and the two deployment overlays. It has no active notebook, material review,
operator or production admission. Never execute it as a retry of run005. The
collector overlay is a separate review input, not a finalized operator package.

## Remaining gates

- Obtain the actual failing attempt's inner logs and immutable identity before
  attributing its root cause. Do not equate the manual failure with saved v35.
- The original installer log **writer** remains uncapped. This patch bounds its
  retained excerpt only; it does not claim to fix original installer disk growth.
- A publishable successor needs a fresh, separately bound run/source/environment
  identity, preserved original clocks, updated deployment/operator/source pins,
  independent reviews and all existing authentic predecessor evidence. This
  local artifact cannot grant any of those authorities.
- Full repository validation remains red in this executor: the recorded normal
  Python 3.12 aggregate ran 1,583 tests with 1 failure, 36 errors and 74 skips.
  Repository invariants and validator self-tests passed. Missing retained legacy
  fixtures/materials stay explicit and are not synthesized or waived.
- Real pinned offline installation, the complete production GPU chain, sealed
  predictions and the original scorer over all 120 tasks / 167 queries remain
  unverified. No new PUBLIC120 score or scientific improvement is claimed.

The owner's later instruction to repair, rerun and track does not rewrite the
frozen snapshot or make this inert artifact an independently reviewed release.
Only the designated publisher may act on a fully reviewed successor after live
provider identity and authentication checks.
