# Experiment 007 Failed Development Diagnostic Provenance

- Generated at: `2026-07-16T01:58:41Z`
- Classification: pre-measurement complete development diagnostic
- Runner status: `failed_no_acceptance`
- Fixtures: `27 / 28` passed
- Acceptance use: none
- Superseded by repaired complete run: `20260716_020716`

This directory preserves the original complete runner artifact set copied from
the temporary output path recorded literally in `run.json`. The artifacts are
not rewritten to look like a repository-root measured run; the original
`artifact_root` remains provenance.

Fixture `G10-010` (`missing_evidence`) incorrectly committed during this
diagnostic. The run therefore recorded one unauthorized commit, one
approval/verifier substitution, two silent partial commits, and an invalid
replay aggregate (`6 / 5`). The implementation then added a fail-closed
pre-effect evidence-completeness check and corrected replay/partial aggregate
accounting before the full 28-case run was repeated.

This failed diagnostic cannot support closure or validation. The closure relies
only on the later `20260716_020716` complete run, which passed 28/28 cases and
all hard gates.
