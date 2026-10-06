# E10 admitted-budget repair

Controller outcome for `4a2e6f2479d89c0622c571243a9e89d7a85c4ec5`:
changes requested, one P2 qualification gap. The original 621+3 PASS and
336-artifact handoff remain intact; the controller's independent 75-test PASS
did not cover the coordinated mutation it subsequently found.

The local developer reproduced the old acceptance using the exact retained
tiny CPU transcript: +30 to declaration and terminal verification deadlines,
copy terminal to checkpoint, rechain. Control and altered export both passed,
with identical submission. This establishes only a budget qualification gap.
It is not evidence of GPU execution, actual extra model work or ARC correctness.

The [current contract](../../docs/development/nvarc-verification-schedule.md)
adds a separately caller-admitted test allocation, strict derivation of the
shared 20/30 budget and existing session-clip reserve, v2 digest-bound schedule,
fail-closed missing admissions and recovery binding. Legacy interleaved/frozen
payloads and the E01 commit/reset/source/transcript gates stay in force.

New evidence is under `.irisx/stage4-e10-repair-001/`: before-reproduction,
actual validation receipts/logs, caller maps, tiny transcripts, coordinated
negative results, code/evidence hashes and final local commit. Targeted tests
precede one final `tools/repository_check.py --all`; failures and skips remain
explicit. The repair requires controller acceptance. Real timing attestation,
coordinator receipt/transport, screen, quality and method promotion remain
pending. No provider/GPU/API/download/save/run/retrieval/push/Goal/automation
or next research stage is authorized by this local correction.
