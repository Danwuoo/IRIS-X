# run007 v39 failed: development transfer

This transfer preserves the consumed run007 and performs no repair or new Kaggle
submission. Decision0074 is the current authority. Latest exact readback at
2026-10-14 00:42:14.611118 Taipei confirms private code Dataset20 and notebook39
ERROR, matching the saved source. This record is a failed checkpoint, not a
successful scientific baseline.

## Versions and failure

- Branch: `feat/run007-local-repair-20261013`; runtime publication commit
  `08aaf2f26caeff0c9e80bd1caefc4c1f6e01e077`; prior final handoff
  `3f47494bae41aa2457bac95925b1196aa48b8389`.
- Adopted/fetched main: `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`.
  Local `main` remains the frozen `e951604b...`; the bundle also preserves the
  fetched `refs/remotes/origin/main` separately. Do not move the frozen local ref.
  Keep snapshot `e951604b829497e81bc6e18b32662ff050bd54db`, tag
  `irisx-code18-run005-snapshot-20261013`, runtime
  `dbf21033b41aff9327cf4f91159df0133529f176` immutable and unsuccessful.
- [Code Dataset](https://www.kaggle.com/datasets/danielwuu/iris-x-learning-agent-code-20261011):
  ID12504696, private20; 269 files,15,842,904 bytes.
- [Notebook](https://www.kaggle.com/code/danielwuu/iris-x-learning-agent-20261011):
  ID138123872; inactive38 was a save; RUN39 is now ERROR.
- Saved source SHA256 `a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9`;
  submitted source `b70668018453a1bc14a996c54b7e0ea1f470405e492488a4c66dbb7c919da879`.
- Original clock1791908053/deadline1791951253, Taipei00:14:13–12:14:13.
  Consumed time and physical work cannot be reset by transfer/reconstruction.

The actual inner ValueError is `mapped cuDNN backend differs from exact pinned
wheel member`, phase `verify-mapped-wheel-bytes`. Actual mapping
`/usr/lib/x86_64-linux-gnu/libcudnn_graph.so.9.8.0` is3,134,416 bytes, SHA256
`8adf356b5509ee8b5f28846a81387ebca6de12ea6b19858f9b2f43c0f0e3fe2b`.
The expected installed member `nvidia/cudnn/lib/libcudnn_graph.so.9` is4,439,912
bytes, SHA256`787c955dce49091ead850e4536666594095ea9f92a8a08879d8ddad466674657`.
Installed wheel hashes pass, but this loaded backend differs; both observed API
values are90800. Loader order/already-loaded SONAME state remains a next
investigation. Do not admit this different system library or remove checks.

PUBLIC score/result/checkpoint are null, experiment/result.json is404, and no
checkpoint export was declared. The optional installation excerpt is404; raw
installation.log is not exported. All41 available selected files have verified
byte receipts; two unavailable requests are recorded and no required file is
missing. Complete evidence ZIP is41,793,870 bytes, SHA256
`02d5c203747f63a69b50db47de552f3cbccf1fda19cc4d7a73862bb3a3d6be6c`;
all48 member hashes/CRC match. Member bytes were streamed for integrity only;
answers/grids were not semantically read, extracted, scored or exposed to solver.

Source-bound wrapper replay verifies all original JIT bytes and wrapper/runtime
tree linkage: closure_valid=true, operational=false, terminal_status=diagnostic.
It does not verify model closure or VM teardown/billing. Inner model closure
records closed/synchronized/settled/model_stopped=true; outer safe_closure and
model_stopped remain false despite rc1 worker exit and empty session. Preserve
these distinct facts. Original durable charged counters are1 model load,4
training steps,12 generation calls,348 scoring forwards,434,560 input tokens and
24 output tokens; these are reserved physical charges, not billing or scientific
success. Public gold was not opened.

## Program, authentic inputs and proof separation

The delivery folder is `C:/Users/wurre/Desktop/IRIS-X-run007-transfer-20261014/`;
a backup copy is stored in the sibling
`IRIS-X-run007-transfer-backup-20261014/final/`. Final backup readback was not
performed after the owner's stop instruction. Follow its README and SHA256SUMS.

- `IRIS-X-run007-program-transfer-20261014.zip`: complete tracked repository
  source, scoped offline Git bundle/history, exact code20 runtime/code ZIPs,
  consumed notebook templates, original rescue ZIP, reports, status and prompt.
- `IRIS-X-run007-authentic-inputs-EVALUATOR-ONLY-20261014.zip`: complete genuine
  run005/006/007 candidates, original selected13-file states, reviews/proposals,
  state-run007 publication proof and v37 diagnostic evidence. Nested historical
  evidence ZIPs remain evaluator-only. Never upload this as a code Dataset.
- `IRIS-X-run007-v39-results-EVALUATOR-ONLY-20261014.zip`: downloaded exact39
  evidence/logs/closures/ledgers, source/status snapshots, unavailable receipts,
  independent diagnostic review and source-bound wrapper verification.
- `HANDOFF-PROMPT.md`, `CURRENT-STATE.json`, `TEST-RESULTS.json`, package manifest,
  `SHA256SUMS` and restore README are also supplied outside the ZIPs.

The new `transfer_handoff_20261014/rebuild_portable.py` checks authentic pinned
inputs and reconstructs the consumed source proposal and complete candidate in
a fresh ignored directory. It never reads credentials/calls provider/models or
creates a new clock. Historical absolute paths stay inert and unchanged.
Use the scoped Git bundle; the source ZIP alone lacks required snapshot objects.
The companion verifier rejects unsafe archive names, links, collisions, unknown
members and bad hashes before restoration. Evaluator-only archives are for
proof preservation/integrity validation, never training/solver/prompt inputs.

## Validation and limits

The portable wrapper's9 and restore helper's8 focused tests pass in normal and
Python-O under POSIX Python3.12 (17 per mode), independently repeated. The owner
then explicitly directed stopping further comparisons and producing the packages
and prompt. The in-progress relocated clean-checkout build was stopped, its
partial output preserved, and no completed relocated-build or final archive
readback PASS is claimed. Package hashes/inventories are generated for transfer;
the destination can perform further checks when requested. TEST-RESULTS.json
records this limit separately from completed earlier checks.

Historical run007 focused checks passed74 tests per mode (21 CPU ELF loader
fixtures,15 environment gates,22 transport/collector,16 adapters), plus owned
CPU payload/numeric-code20 acceptance. Earlier clean-checkout source/deployment
bytes matched. These tests did not establish GPU success; actual39 now failed.
Prior run006 full suite1583 tests had32 failures,68 errors,72 skips; it was not
rerun for this transfer. Failed-only comparison retained88 inherited signatures
and12 unresolved cases. CI for08aaf2f failed at the same seven upstream README
governance terms before unit steps:
[CI record](https://github.com/Danwuoo/IRIS-X/actions/runs/38425799034).
No full-project green claim follows from focused tests or a portable rebuild.

Keep GPU NvidiaRtxPro6000, private pinned Docker, offline model/wheels/CPython
and seven non-code Dataset pins from CURRENT-STATE.json. Preserve only the
existing ARC3 metadata association; no ARC3 task data/competition submission.
PUBLIC120 stays120 tasks/167 queries, scorer unchanged, public90 a long-term
goal without a score promise. Weights/bulk wheelhouse/raw datasets/credentials
are not included. Destination official authentication requires its own flow;
do not transfer credentials, spoof HOME, change accounts/resources or query quota.

Next developer should verify transfer hashes, restore a fresh repository, replay
the exact consumed CPU build, inspect the actual loader mismatch and outer
closure without weakening gates, then use a new branch for any local repair with
subagent implementation and independent review. New provider publication/RUN
requires fresh owner direction. No monitoring/automatic submission follows.
