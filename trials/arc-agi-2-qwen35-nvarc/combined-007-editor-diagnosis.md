# Combined 007 owner-Editor partial startup diagnosis

The owner supplied `結果.zip` after manually starting combined 007 in Editor.
The truth-free ZIP is SHA-256
`33b3c34df7d0517a36166d44ab9bee19d136386a634dabc23714c797ec28c9c7`.
Its CRC and only listed file digest verify. Its manifest binds the exact
Decision 0041 plan digest
`sha256:3b32c1ce64662c5e108d8dfd494fa51d67b31a4da084d8d3434fb41727e9d77d`.
All 15 embedded payload hashes in each startup event match the saved package.
The original ZIP and verification report are retained at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-007-editor-observation-001/`.

The sole retained data file is `startup-events.jsonl`. Its three events are
`payload-validation`, `execution-guard`, and `hardware-inventory`; the last
was emitted 0.0087 seconds after notebook entry. There is no hardware raw
inventory, worker launch, model-ready record, branch ledger/result or
aggregate terminal record. No M2 or M3 outcome can be inferred. The owner
could not determine whether the Editor was manually interrupted or stopped
itself. The original `except Exception` handler would record an ordinary
Python exception and aggregate before packaging, but would not record an
interrupt-class `BaseException`. This is a diagnostic gap, not proof that a
particular exception occurred. No ARC score, accepted pair or method claim
follows from this partial startup evidence.
