# Output lifecycle boundaries deferred to E01

This is an inventory and synthetic contract matrix, not an E01 dispatch. No
atomic exporter, root-copy or new fallback behavior is enabled by E00.

| Existing boundary | Observed contract | Remaining gap |
| --- | --- | --- |
| `nvarc_native_multitask.write` | Temp file, flush/fsync, single-path `replace`; synthetic denied replace preserves old checkpoint and leaves uncommitted temp | No multi-file transaction, directory fsync or generation recovery contract |
| `ResultStore.flush` | Separately replaces submission, audit, pools, coverage and timings; full denominator and model/filler audit retained | Interruption between writes can mismatch generations; no common commit marker |
| `arc_kaggle_submission.write_new` | Exclusive create + fsync, rejects overwrite | Not atomic replacement; interrupted first write can leave a partial new file |
| `nvarc_native_export.export` | Fresh CPU hash seed, strict replay, sequential evidence/audit/submission/process files | No all-files transaction or recovery from partial export |
| Official working-root export | `shutil.copyfile` after strict export | Root submission/audit/summary are not an atomic transaction; interrupted copy can truncate |
| Public archive | Closed member inventory/digests, bounded temp ZIP, verified before rename | Completed archive timing cannot be inside its own members; logger/archive failure can still defeat finalization |
| Existing missing-output filler | Two named attempts remain present and explicitly audited | No new early fallback/promotion policy; filler has no model-pool credit |

The reliability matrix below maps the retained research IDs to existing or
new offline checks. A mapping is a test contract, not a claim that every
research acceptance variant has run. The handoff records actual suite status.

| Research case | Existing/E00 evidence | Deferred or unverified |
| --- | --- | --- |
| F01–F05 | Submission/public/offline evaluator fixtures: actual IDs, unequal test counts, ordering, sparse/missing denominator, duplicate indices | Real fresh canonical run not made |
| F06–F08 | Existing grid/strict JSON tests plus E00 nested telemetry injection and bool index rejection | No permissive runtime fields added |
| F09 | Existing empty/one pool versus duplicate-first/constant filler audit | New fallback policy not enabled |
| F10 | Native source hash tamper, bound-file tamper, strict record bindings | New model material compatibility not run |
| F11 | Existing rendered early hardware/dependency failure fixtures | Provider-specific missing dependency remains unprobed |
| F12 | Existing infeasible full-workload reject, finite forward/token caps | No reduction of full epoch or skipped actual tasks |
| F13–F14 | E00 independent next-test deadline and before/after reservation fakes; existing official partial continuation | Cooperative clock only |
| F15 | E00 slow in-flight model fake and separately actual bounded CPU-child watchdog with return code/PID | No GPU OS-kill or kernel timing claim |
| F16 | E00 4/8 verifier retains earlier full candidate and never ranks partial | No new partial-candidate promotion |
| F17–F18 | E00 CPU exit 17/watchdog distinctions, existing full tiny training fault/reset mismatch retirement | Not actual CUDA OOM or signal qualification |
| F19 | E00 undispatched full denominator; existing parent dispatch reserve | No new scheduler method |
| F20 | E00 denied checkpoint replace preserves last bytes and leftover temp | Actual kill during write and directory durability not tested |
| F21 | Separate file writes inventoried | Common generation recovery/commit marker not implemented |
| F22 | Synthetic permission-like replace fault tested | Disk-full/initial-unwritable storage and full exporter write failure deferred |
| F23 | Existing strict fresh-CPU export and earlier checkpoint survival | Root-copy/export interruption recovery deferred |
| F24 | Existing stale run/task and chain binding rejects | Terminal logger double failure recovery deferred |

The four outcomes must remain independent: legal complete submission
(`output_valid`), process/notebook exit (`notebook_exit`), strict digest/source/
reset/transcript evidence (`evidence_qualified`), and authorized method
promotion (`promotion`). Existing tests demonstrate legal output with a failed
terminal status and false strict GPU gate, and empty pools with legal filler.
No offline test establishes Kaggle scoring. A future E01 must declare which
file set forms a committed generation, initial-write limitations and recovery
rules before changing those behaviors; source/reset/promotion gates cannot be
relaxed to make a fallback count as solver success.

For official 56840442, needed diagnostics remain input/model/code bindings,
hardware/material gates, failing phase, traceback, process exit/signal, last
committed output generation and exporter/root-copy observations. They are
unknown where not retained; this task makes no external request to obtain them.
