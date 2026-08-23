# PS1-G8 Side-Effect Planning Fixtures

These fixtures exercise the named `committable_docops_planning_pilot` without
executing a runtime action. `base_proposal.json` is a deterministic planning
proposal template. Each `case_*.json` file defines proposal overrides or field
removals plus a fixture oracle for evaluation only.

The runner materializes proposals in memory, validates them, and records the
oracle comparison. Fixture oracles and human labels are not runtime approvals.
The fixture root is read-only during a pilot; pre-run and post-run tree hashes
must match.

Covered families:

- valid fixture-local restore proposal
- valid fixture-local supersession proposal
- missing target identity
- missing approval boundary
- missing idempotency key and duplicate guard
- missing rollback or compensation statement
- path escape
- source-fixture mutation target
- irreversible misclassification
- memory-write smuggling

