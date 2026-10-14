# Offline component validation

Date: 2026-10-14 UTC. Scope: newly added bridge only; no producer/runtime change.
Upstream source: `a1836decb836cd52cf2b27f5022f6838cee75df3`.
Frozen IRIS-X math: `cc14bd1a79aac1fe6135017c9e09d4834300675d`.

## Author checks

| Check | Result |
|---|---|
| Normal targeted unittest discovery | **25 tests passed**, 0 failures/errors/skips |
| Python `-O` targeted unittest discovery | **25 tests passed**, 0 failures/errors/skips |
| Actual upstream `TrainingSample` validator | Executed; 64 samples, 8 groups |
| Actual upstream `DDISLoss.compute_unpacked` | Executed on CPU; 224 generated tokens, 6 mixed groups |
| Upstream vs frozen local scalar loss | Both `0.0014256983995437622`; absolute gap 0 |
| Underlying synthetic-logit gradient comparison | Max absolute gap 0; norm `0.017627257853746414` |
| Per-trajectory reduction comparison | Gradient max absolute gap 0 |
| Singleton legal support | Underlying synthetic-logit gradient 0 |
| Actual `MeanMetricState` aggregation | Unequal-sized partitions merged to full result; weighting mismatch rejected |
| Copied upstream bytes | All4 Git blob IDs and SHA256 match pinned source |
| Frozen local contract | Five exact source SHA256 checks pass; no frozen-source diff |

Tests cover all-zero/all-one groups; mixed groups; fixed same-parent prompt IDs;
single-actor cache-mode consistency; one-token and exact
3072-prompt/1024-generated/4096-total boundaries; variable sequence lengths;
prompt/padding masks; positive/negative/zero advantages; strict ratio endpoints;
detached ratio/behavior; incomplete slots; duplicates/order; stale actor/version;
public-lineage declarations; fatal/stop/error fields; exact forced probability;
NaN/Inf/float32 overflow/huge integers; malformed nested types; source-pin
mismatch; source receipt support/DFA binding; mutated prepared metadata; missing
replay; detached graph; and no-grad/inference-mode rejection. Compound negative
tests use subtests, so the 25 count does not equal the number of cases.

Exact upstream assertions remain unmodified. Hardened normal/optimized contract
validation applies to the bridge inputs, not arbitrary calls to the generic
upstream API. No source formula or normalizer was changed to obtain parity.

## Commands and retained local receipts

From repository root, `PYTHON` below is the ignored local proof interpreter:

```sh
PYTHON=.irisx/agent-factory3-proof/venv/bin/python
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 "$PYTHON" -m unittest discover -s tools/arc2_agent_factory3_bridge_20261014/tests -v
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 "$PYTHON" -O -m unittest discover -s tools/arc2_agent_factory3_bridge_20261014/tests -v
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 "$PYTHON" -m tools.arc2_agent_factory3_bridge_20261014.proof
```

The local ignored output receipts are not provider/model evidence:

| Receipt | SHA256 |
|---|---|
| `.irisx/agent-factory3-proof/tests-normal-final.log` | `9608aa609beaaf5c41485a6bc3e91f990c2c23ebaf73ff1463dfc77c1640e877` |
| `.irisx/agent-factory3-proof/tests-optimized-final.log` | `c4e1b794ffae3c6154c2693198326118bc7b086f7851068fee28976ec45dcffb` |
| `.irisx/agent-factory3-proof/proof.json` | `8c151a56ed74b214ebdb773882aabfa22cc3afbf2106bbb39e6c8fcf333f5290` |

## Dependency boundary

- Effective runtime: CPython3.12.14, Linux x86_64; torch2.9.0+cpu;
  `torch.version.cuda is None`; inherited NumPy2.3.5/Pydantic2.13.4.
- A new ignored venv uses system-site packages. New packages are installed only
  into the venv, but the environment is **not hermetic**. NumPy/Pydantic are
  inherited from the existing executor runtime; no global packages were changed.
- Observed venv-owned package set: torch2.9.0+cpu, filelock3.32.3, fsspec2026.7.0,
  jinja2 3.1.6, markupsafe3.0.3, mpmath1.3.0, networkx3.6.1,
  setuptools78.1.0, sympy1.14.0, typing-extensions4.16.0.
- Installation source was the official `https://download.pytorch.org/whl/cpu`
  index through normal permitted networking. No custom fork, framework setup
  script, security change or access workaround was used.
- The official index identifies
  `torch-2.9.0+cpu-cp312-cp312-manylinux_2_28_x86_64.whl`, with advertised SHA256
  `28f6eb31b08180a5c5e98d5bc14eef6909c9f5a1dbff9632c3e02a8773449349`.
  The full compressed wheel was not separately retained for a second manual
  hash pass; installed version/source and upstream source-component hashes are
  separate checks.
- Installer reported a175.8MiB torch download; final venv disk use approximately
  760MiB and installer cache6.4MiB. These are observed setup figures, not Qwen
  training/inference memory or wall-time measurements.
- Reproduction records:
  [`requirements-contract.txt`](../../tools/arc2_agent_factory3_bridge_20261014/requirements-contract.txt),
  [`requirements-torch-cpu.txt`](../../tools/arc2_agent_factory3_bridge_20261014/requirements-torch-cpu.txt).
  These are dependency records, not a complete hash-locked environment or an
  instruction to run a framework/training installer.

## What this does not prove

No actual Qwen weights, LoRA optimizer, authenticated reward panel, real model
replay, GPU memory/timing, process ownership, checkpoint save/reload, provider
execution or ARC-AGI-2 gain was tested here. All numerical fixtures are fabricated
non-ARC CPU logits. The adapter's source/receipt consistency does not replace
producer authentication or release/admission gates. No production runtime was
rewired; original A/B/C method, budget, noTTT and PUBLIC120/167 remain frozen.
The upstream loss pads all supplied sequences. Tiny CPU fixtures are not proof
that64 real Qwen replay graphs fit one GPU. Any future wiring must retain the
existing per-trajectory gradient accumulation with its full-batch divisor, or
separately measure/admit the changed memory and wall-time behavior.

Independent adversarial/source review is recorded separately in
[independent-review.md](independent-review.md). Project-wide validation status
must be reported separately; these targeted passes are not a whole-repository
or deployment pass.

## Repository-wide comparison, separately red

`python tools/repository_check.py --all` was also run in the original default
interpreter, not the proof venv. Final result: **1,583 tests, 2 failures,
35 errors, 74 skips**. Every failure/error identity exactly matches the
stage0 retained comparison; there are no added or missing failure/error IDs.
The historical failures remain: missing retained source/test/material fixtures
and the root README invariant's seven findings. No old test or fixture was
changed, invented or waived; the global suite remains red.

The final aggregate run retained the inherited environment and added
`PYTHONHASHSEED=0`, a new workspace-backed `TMPDIR` with approximately29GiB
available, `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and
`HF_DATASETS_OFFLINE=1`. Unlike stage0, `CUDA_VISIBLE_DEVICES` was **unset**,
not explicitly empty. Thus failure identities match; an identical environment
is not claimed. No third aggregate rerun was required by the integrating lead.

The first invocation omitted workspace TMPDIR/offline additions. It had the
same two failures plus36 errors; its only extra error was
`test_inventory_preserves_original_zip_and_checks_member_bytes`, whose retained
trace says `archive extraction exceeds available disk reserve`. The corrected
workspace-TMPDIR run removes that error. The earlier receipt is preserved,
not overwritten or called a valid baseline comparison.

| Ignored aggregate receipt | SHA256 |
|---|---|
| `.irisx/agent-factory3-proof/repository-check.log` (first invocation) | `2fd7659cc1f17c1426242654654bdd25d771948df266df6203a0b701db5055f0` |
| `.irisx/agent-factory3-proof/repository-check-corrected.log` (final invocation) | `1ab1c6486ad227061f9d15f36c72fdfc9b011643ac6e205a80e90e32d0fcbce6` |

The exact-ID comparison is retained at
`.irisx/agent-factory3-proof/repository-comparison.json`. Default aggregate
discovery covers the historical root test suite; the25 new bridge tests are
explicitly exercised by the separate commands above. Final relative-link checks
find no missing link. The complete staged `git diff --cached --check` returns
one newly introduced vendor-formatting warning:
`vendor/losses/metric_state.py:38: new blank line at EOF`.
That blank line is present in the exact pinned upstream blob; it is retained
with the copied source bytes, hashes and license. The staged whitespace check
is therefore **not green**. This nonfunctional formatting warning is distinct
from the passing focused tests and the inherited repository-wide failures;
no source normalization or check suppression was applied.
