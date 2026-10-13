# Portable run007 development transfer

`rebuild_portable.py` reproduces the already consumed run007 source proposal and
complete reviewed candidate on a different POSIX host. It only calls pure CPU
preparation and assembly. It does not load credentials, call Kaggle, start an
owned runtime, execute models, obtain a new epoch or authorize another run.
Original v39 state, clocks, charges and failure remain historical facts.

Restore the accompanying scoped Git bundle into a clean repository with the
run007 branch and frozen `irisx-code18-run005-snapshot-20261013` tag. The frozen
snapshot's complete Git objects are necessary. A source ZIP alone cannot
authenticate the predecessor. Keep the tracked core files unchanged to reproduce
the old candidate; use a new branch and fresh reviews for later development.

Safely extract the separately marked evaluator-only authentic-inputs archive.
Do not expose this directory to training, solver or prompt inputs. Its required
layout is:

```text
authentic-inputs/
  run005/
    candidate/                         complete original candidate-run005
    state013/                          13 original v35 files, exact inventory
    target-free-solver.json             genuine target-free descriptor
  run006/
    candidate/                         complete original candidate-run006
    state013/                          13 original v37 files, exact inventory
    reviews/installer-review.json       genuine run006 installer byte review
  run007/
    candidate/                         complete original candidate-run007
    candidate-proposal/SUCCESSOR-PROPOSAL.json
    source-proposal-v2/                 complete original source proposal
    sealed-inputs/                     original identity, state inventories and observation
    reviews/                          original final byte-binding reviews
    OWNER-REQUEST.json                  original run007 owner direction
```

For each supplied transfer ZIP, obtain its expected outer SHA256 from the
separate `SHA256SUMS` file and use the stdlib restore helper. Verification checks
the closed canonical `PAYLOAD-INVENTORY.json`, all member SHA256/CRC, regular file
modes, portable names and byte caps before creating any output. ZIPs inside the
outer transfer are copied as opaque files; this helper never opens their members.
The program archive may contain the authentic-inputs ZIP as a separate payload;
restore that ZIP separately into the evaluator-only location before CPU rebuild.

```sh
python3 -B /work/IRIS-X/tools/arc_qwen_rlvr004_20261013/transfer_handoff_20261014/verify_transfer.py \
  --archive /transfer/IRIS-X-run007-program-transfer.zip --sha256 EXPECTED_SHA256 \
  --verify-only
python3 -B /work/IRIS-X/tools/arc_qwen_rlvr004_20261013/transfer_handoff_20261014/verify_transfer.py \
  --archive /transfer/IRIS-X-run007-authentic-inputs.zip --sha256 EXPECTED_SHA256 \
  --output-root /private/evaluator-only/restored-authentic-inputs
```

An extraction error retains any partial output. It never overwrites or deletes
an existing destination. Use a fresh destination after investigating the error.

The complete old candidates include opaque v31/v33 evaluator proof ZIPs. The
unchanged historical admission validators stream archive members only to verify
integrity hashes and CRC; they do not parse answer/grid content or expose it to
the solver, training or prompts. This does not authorize semantic answer reads
or reusing old proof receipts for modified code. Historical absolute paths inside proof documents remain unchanged as
recorded data. Only the new wrapper's input-root arguments adapt to the new host.

Use Python 3.12, real account HOME, an ext4/POSIX working directory and a fresh
ignored output directory below the restored repository's `.irisx`. Keep the
existing offline flags and deterministic hash seed. Replace the sample absolute
paths with actual destination paths:

```sh
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
python3 -B /work/IRIS-X/tools/arc_qwen_rlvr004_20261013/transfer_handoff_20261014/rebuild_portable.py \
  --repository-root /work/IRIS-X \
  --inputs-root /private/evaluator-only/authentic-inputs \
  --output-root /work/IRIS-X/.irisx/transferred-run007-cpu-rebuild
```

The wrapper first checks exact pinned inventories/reviews/overlays, complete
closed candidates and the original 13-file v35/v37 states. It then reproduces
`source-rebuild/` and `candidate-rebuild/` and requires **every file** to match the
authentic old run007 source proposal and candidate. `REBUILD-REPORT.json` is only
written after both complete comparisons pass. It does not change old documents
or replace a partial failed rebuild. Keep any failed output; retry in a fresh
directory after investigating the actual error.

The reconstructed active notebook is an old unfinalized template, and the
restored claims/JIT/wires describe a consumed submission. Neither is permission
to dispatch again. Only `candidate/code-upload.zip` is a code payload; never
publish the full deployment, transfer or evaluator-only archive as a code
Dataset. Model weights, wheelhouse, CPython runtime and raw data are separate
versioned materials named in the original publication manifest. Destination
authentication must use the official local flow if later publication is
authorized; no credentials are supplied in this transfer.

Run the focused wrapper tests in both modes, followed by the genuine relocated
build above:

```sh
python3 -B -m unittest tools.arc_qwen_rlvr004_20261013.transfer_handoff_20261014.test_rebuild_portable -v
python3 -O -B -m unittest tools.arc_qwen_rlvr004_20261013.transfer_handoff_20261014.test_rebuild_portable -v
```

CPU reproduction cannot establish GPU installation, model inference, predictions
or scientific scoring. Keep inherited full-suite/CI failures and run007's actual
terminal retrieval beside the new handoff record.
