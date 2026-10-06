# E10 local delivery

Controller dispatch: 2026-10-06, starting main
`90ea1bcd40d9e8c88fb7e849e55257704e9b3c16`. E00/E01 were accepted foundations.
The original incoming research and all consumed run identities are preserved.
This batch implements and tests only interleaved versus deferred verification.
No E11/E12/E20 dispatch, source/model acquisition, external/API/GPU/paid work,
QUICK_SAVE, scoring, promotion, push, Goal or automation is included.

The [implementation contract](../../docs/development/nvarc-verification-schedule.md)
records the actual baseline, FIFO, score reuse and vote multiplicity, optional
schema, strict replay, cooperative overrun and E01 preservation limits.
The [screen draft](inert-screen-plan.json) is inert. It selects no actual tasks,
reads no evaluator labels and defines no fresh holdout. Its resource ranges
are unmeasured research estimates, never authorization. All real mechanism and
quality gates remain pending execution and independent controller acceptance.

Finite tests are in `tests/test_nvarc_verification_schedule.py`, with actual
source/tiny CPU integration in the existing native/public tests. Evidence under
`.irisx/stage4-e10-001/` retains each validation command, environment, exit,
whole/unit wall, stdout hash, failures/skips and synthetic transcript/128-step
parity artifacts. `handoff.json` will bind the final local commit, changed file
hashes, evidence manifest and the sole repository-wide result. It does not
claim controller acceptance. Historical native/public/official transport tests
are included in the full repository regression; their stagers remain unchanged.

Targeted commands use the retained ML Python environment, startup hash seed 0,
offline Hugging Face flags, CPU-only visibility and the local code-only source.
The final validation is one `tools/repository_check.py --all`. No second full
suite runs concurrently or retries a failure to obtain green evidence.
