# Fresh preparation successor, source-only

This directory adds new local tools; it does not modify the frozen code18/run005
snapshot or the separately reviewed preparation diagnostics overlay. It is not a
publisher, final assembler, operator or source of production authority.

## What can be reproduced now

`prepare.py prepare` authenticates the exact snapshot commit
`e951604b829497e81bc6e18b32662ff050bd54db` and tree
`f9b10d12b912f3a92238375451c0ad56d4cb7efb`. Each used frozen file must match its
Git blob, and each runtime-map member must additionally match its recorded
SHA256 and byte length. It reconstructs the canonical code18 259-member ZIP
`22fc93ae1dfbc4d4a7c90cf9907668af5d697dece28cb9211dea82c776d7dc9e` and logical
source `4050616ed0ed34d19501be416650a09ae5cc9c86c875b349a056baec9308f3e3`.

The supplied identity is explicitly **proposed**, never reserved or published:
code19, inactive notebook36, active notebook37, run/source/environment006 dated
20261013. Only the sole publisher may establish live allocation before a write.
If the live predecessor changes, this code18/v35-specific profile must stop and
be separately revised; callers cannot substitute unrelated predecessors.

The default source projection changes exactly `owned_runtime/release.py` to bind
three new environment source paths and its normalized self-consistency digest.
The other 258 runtime members and all baseline200 are exact. The source-owned
scorer, full167 denominator, policy, material/model/hardware bindings and process
gates are unchanged. Both diagnostic deployment overlays are pinned to their
independently reviewed hashes before exact namespace substitution. The other
three deployment files derive from authenticated frozen originals. An unchanged
run005 collector is retained only as a review reference, outside executable
operator layout. Its three optional diagnostic paths do not become required
runtime/closure proof.

The output includes the canonical source ZIP, materialized source, projected
five-file deployment, projected wrapper verifier, review-only release, one
inactive notebook, complete input/source/proposal inventories and required-input
ledger. It does **not** contain a production publication manifest, finalizer,
material approval, active notebook, auth/config/state, or successor epoch.
Everything remains explicitly inert. A caller-supplied PASS document is never a
production capability. No provider, GPU, model or scorer is called.

Run from the repository root, with a new ignored output directory:

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
mkdir -p .irisx/tmp
export TMPDIR="$PWD/.irisx/tmp"
python -B tools/arc_qwen_rlvr004_20261013/preparation_successor/prepare.py prepare \
  --repository-root "$PWD" \
  --identity-path tools/arc_qwen_rlvr004_20261013/preparation_successor/proposed-identity.json \
  --output-root "$PWD/.irisx/preparation-successor/review-001"
```

Build artifacts stay outside Git. Repeating in a different fresh directory with
identical inputs produces byte-identical file inventories. Output files are
exclusive and mode0600; directories are mode0700. The local builder rejects
symlinks, hardlinks, nonregular files, oversized/changed inputs, duplicate JSON
keys, nonfinite numbers, traversal and control-character member names. It is not
a security sandbox against malicious same-UID ancestor replacement.

## Original evidence is still required

`REQUIRED-INPUTS.json` records exact known sizes/hashes and original filenames.
`LOCAL-INPUT-AVAILABILITY.json` defaults to ROOT_NOT_SUPPLIED, not an assertion
that provider outputs or original owner files do not exist. Missing or unreadable
bodies never become synthetic receipts or success. The original code18 candidate
is preferred: its authenticated closed inventory embeds the genuine v31 and v33
proofs. It is not necessary to transfer duplicate evidence in multiple layouts.
An alternative rebuild needs the original complete code17 candidate and original
v33 state/evidence plus independently reviewed run005 material inputs.

Important unresolved inputs in this replacement workspace:

- Original code18 complete assembly, inventory `de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0`, manifest `76b2e004770e1f41e9c2352fa9817bc185ea5fded75d9fd8ce29d50453e7b7ca`
- Original v31 archive, 20,130,674 bytes, SHA256 `4f24e0e44455d0862d72803c1a852294e26d52ca0335a1fe2393406e235b4b65`, and all 12 other hash-bound evidence bodies
- Original v33 retrieval `8f7446f1182bdeacba86e982793222203b948ab4dac6831b712a786fa3c29042`, selected numeric33 downloads including archive `06825c68f991fd8e9b4f1a3cf76cf5e06fae18607918bf0840991f1a9a6591cd` (15,908,385 bytes), terminal diagnostic/checkpoint and original code/launch/JIT/wire/saved-source files
- Authentic code18 target-free solver descriptor `4c13f788cabe2213002593991cffcc15ffdcd6c04167967cbb9d2532536b5f47`; its two escrow-reference paths may be projected only after exact authentication, without opening escrow bodies
- Original v35 launch/code receipt, journal, claim, wire and JIT state; exact source/status observations and any genuine available diagnostics. Missing v35 runtime outputs remain unknown, not valid closure.
- New independently hash-bound runtime/material/solver/operator/collector/final-wire reviews, and a separately implemented final assembler/operator preserving every mandatory historical gate

Consumed run005 epoch1791871874/deadline1791915074 remain immutable and are never
reused by this tool. A genuinely new admitted attempt needs its own one-shot
identity and immutable clock, with the original 43,200-second total bound.
The manual Editor failure's inner cause remains unverified. Provider
CANCEL_ACKNOWLEDGED and missing selected logs do not prove successful closure,
model admission, zero costs, inference or PUBLIC scoring.

To inspect supplied local roots without altering them, pass `audit-inputs` a
JSON root map whose keys are `historical_v31`, `code17_assembly`,
`code18_assembly`, `v33_evidence`, `v33_state`, `v35_state`, and/or
`target_free_solver`. Each value must be an absolute local directory. Each
requirement path is resolved relative to that directory. The report distinguishes
ROOT_NOT_SUPPLIED, MISSING, UNSAFE_OR_UNREADABLE, PIN_MISMATCH,
PRESENT_CHAIN_VERIFICATION_REQUIRED and EXACT_BYTES_PRESENT. It never grants
admission or claims the full chain has been checked.

```sh
python -B tools/arc_qwen_rlvr004_20261013/preparation_successor/prepare.py audit-inputs \
  --repository-root "$PWD" --root-map /absolute/local/input-roots.json
```

Once an authentic complete code18 candidate is available, this strict command
requires its exact inventory, closed file set and every original body, then calls
the byte-frozen run005 `contract` validator including v33 and historical-v31
admission. It has no preview/skip/missing-fixture option and performs no provider
or credential calls. Passing it validates the old package, not new production
readiness or historical scientific success.

```sh
python -B tools/arc_qwen_rlvr004_20261013/preparation_successor/prepare.py verify-code18-predecessor \
  --repository-root "$PWD" --candidate-root /absolute/authentic/candidate-run005
```

## Optional separately reviewed installer overlay

The default retains the original uncapped installer log writer. An optional
local-only variant may replace exactly
`baseline/tools/arc_qwen_transfer_deployment_20261012/bootstrap.py`, whose old
SHA256 is `4ddac4166b154e1506fb029373b14297f7b0bfc7c87f37d9e83bcb9f554909f8`.
It requires all four explicit flags: `--installer-overlay-path`,
`--installer-overlay-sha`, `--installer-review-path`, `--installer-review-sha`.

The independent review JSON must have format
`irisx/bounded-installer-log-review-v1`, status PASS, scope
LOCAL_SOURCE_REVIEW_ONLY, target equal to the exact runtime path above,
original_bootstrap_sha256 equal to that frozen hash, and overlay_sha256 equal to
the supplied exact source. This schema only records local source review; it
cannot admit publication. No optional installer source has been selected by
default, and source-only preparation does not claim GPU installation validation.

Such a variant changes exactly bootstrap.py plus release.py, reports baseline199
and runtime257 unchanged, and explicitly sets original_baseline200_exact=false.
It must use a separate output directory with separate source/proposal hashes.
Do not call this variant baseline200-identical. All missing-evidence and
independent production-review requirements remain in force.

## Tests and remaining limits

```sh
python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/preparation_successor -p 'test_*.py' -v
python -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/preparation_successor -p 'test_*.py' -v
```

These CPU tests do not replace actual offline installation, native tensors/GPU,
full production process closure, sealed predictions or the unchanged original
scorer over all 120 tasks / 167 queries. Full repository aggregate failures from
missing retained historical fixtures remain explicit and are never waived.
