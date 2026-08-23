# PS1-G10 Fixture-Local COMMITTABLE Fixtures

These immutable fixture definitions drive Experiment 007. `workspace_template/`
is copied to a temporary run workspace before every effect. Source fixtures are
never targets. Each JSON file under `cases/` names one deterministic scenario
and its expected high-level outcome; the schema-backed validator rejects unknown
scenarios or incomplete fixture definitions before the runner starts.

Fixture oracles are evaluation comparators, not runtime approvals. Runtime
Approval Records are constructed as standalone schema-valid artifacts from the
fixture scenario and passed through the explicit G10 approval-record input.
