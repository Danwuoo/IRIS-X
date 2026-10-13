# Local run006 reconstruction (2026-10-13)

The recovered `prepare.py`, `assemble_run006.py`, `accept_numeric_mount.py`,
`v35_lineage.py` and their available tests remain byte-preserved. Their original
receipts support only those exact original bytes. The following files are new
local implementations and need fresh independent review:

- `local_prepare.py` derives consecutive proposed Dataset/notebook versions from
  an authentic current observation. It preserves the frozen code18 source,
  model, materials, hardware, policy, process and scorer gates. Its source
  projection changes only the reviewed installer and the source-owned release
  environment/self-consistency pins.
- `local_inputs.py` seals only the actual thirteen original v35 state files and
  six official read-only source/metadata/status bodies. It records measured
  hashes, not fabricated provider receipts or historical runtime closure. Its
  original-state inventory must still pass the unchanged `v35_lineage.py`
  receipt/journal/claim/finalizer replay.
- `local_assemble_run006.py` requires the complete authentic code18 candidate
  and its unchanged v31/v33 admission validators. It accepts the newly measured
  closed current-provider packet and current owner direction, not the lost
  original observation/stop-attestation packet. It retains original v35 launch
  provenance and consumed clock. The owner identity for the frozen finalizer
  uses a request identifier derived from the actual current direction bytes;
  it does not invent a historical message identifier.
- `local_accept_numeric_mount.py` binds explicit reviewed candidate manifest
  and inventory hashes and derives the numeric code version from that candidate.
  It still needs an authentic official numeric download receipt and complete
  downloaded bytes before invoking the unchanged owned no-model mount helper.
  It cannot establish GPU, model, scorer or provider runtime success.
- `test_local_recovery.py` checks new allocation/scope/binding rejection gates.
  Positive current-packet tests use actual retained read-only input when present;
  clean source-only checkouts explicitly skip those missing authentic inputs.
- `posix_recovered_test_harness.py` runs unchanged available preparation tests
  in a fresh Linux filesystem checkout. It preserves primary Windows-filesystem
  failures and never synthesizes the unrecovered installer `REVIEW.json`.

All operational bodies, credentials, source ZIPs, original evidence archives,
state, receipts and generated deployment candidates remain outside Git under
the ignored `.irisx/run006-local` directory. Public answer-containing archive
members are never opened by these tools or supplied to solver/training prompts.

Use WSL Python 3.12 with the real HOME and explicit local paths. The POSIX APIs
are deliberate; replacing process ownership/security gates to emulate Windows
is outside this local reconstruction. Authentication/publication is provided
separately by the sole publisher's official local SDK operator.

From a clean checkout with the authentic retained operator inputs, rebuild in
new ignored directories in this order:

1. Run `local_prepare.py verify-code18-predecessor` against the exact complete
   `candidate-run005`. Its original inventory and manifest hashes are
   `de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0` and
   `76b2e004770e1f41e9c2352fa9817bc185ea5fded75d9fd8ce29d50453e7b7ca`.
2. Run `local_inputs.py --repository-root ... --state-root ... --observation-root
   ... --output-root ...` against the genuine original state and official
   current read-only six-body packet. Use its `LIVE-IDENTITY.json`, original
   state inventory and closed observation output in following commands.
3. Run `local_prepare.py prepare --repository-root ... --identity-path ...
   --output-root ... --solver-path ...` plus the four explicit installer
   overlay/review flags documented in `README.md`. Use a fresh independent
   installer review binding the exact selected installer bytes.
4. Independently review the original and projected target-free solver bytes;
   supply the exact two-path namespace review required by `solver_inputs`.
5. Run `local_assemble_run006.py --mode proposal` with the genuine base,
   source proposal, `--source-proposal-inventory-sha`, fresh observation,
   current `--stop-attestation-path`/hash (which records owner scope only),
   original/projected solver and independent solver review, separately reviewed
   collector, and all three v35 state inputs. The command's `--help` lists every
   finite input. It produces an inert complete candidate and exact proposal.
6. Independently review that proposal and emit new runtime/material approvals
   binding all `BINDING_KEYS`, preserving original content/escrow commitments,
   and explicitly recording no production GPU validation. Re-run the same
   assembly inputs with `--mode final` and its six approval flags in another
   fresh directory. Never edit a generated candidate in place.
7. The publisher reviews/binds the finished candidate and new operator, obtains
   a fresh provider bracket, uploads one private code successor, verifies its
   numeric readback and owned no-model mount, saves/re-reads the inactive
   notebook, then admits one fresh pre-dispatch clock and submits the active
   notebook. The total original session bound remains 43,200 seconds.

The current owner direction is one accepted run followed by the necessary
single submission readback and handoff. `QUEUED` remains `QUEUED`; source save or
accepted execution is not successful training/inference/PUBLIC120 scoring.
No monitoring, watcher, waiting for RUNNING, or automatic next run follows.

Run the new CPU regressions in normal and optimized modes:

```sh
python3 -B -m unittest tools.arc_qwen_rlvr004_20261013.preparation_successor.test_local_recovery -v
python3 -O -B -m unittest tools.arc_qwen_rlvr004_20261013.preparation_successor.test_local_recovery -v
```

For a Linux filesystem supplement to the original available suites:

```sh
python3 -B tools/arc_qwen_rlvr004_20261013/preparation_successor/posix_recovered_test_harness.py \
  --repository-root "$PWD" \
  --checkout-root /absolute/new/ext4/ignored/checkout \
  --report-root "$PWD/.irisx/run006-local/validation"
```

This preserves the missing original installer review as an explicit failure.
The new independently reviewed source build and authentic full predecessor
replay provide separate CPU evidence; neither repairs the unverified manual
run005 inner failure or replaces full project CI or actual GPU execution.
