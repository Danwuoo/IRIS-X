# Development

IRIS-X uses the lightweight, risk-based workflow adopted by Decision 0010.
Routine local, offline, reversible work proceeds through
**Build–Measure–Select** without a new decision record. Owner direction is
required only at durable or risky boundaries such as external execution,
sensitive data, paid resources, public contracts, frozen identities, promotion
claims, and irreversible operations.

Use these documents by purpose:

- [`nvarc-verification-schedule.md`](nvarc-verification-schedule.md) describes
  the local E10 opt-in FIFO schedule, replay gates and inert future screen;
- [`operating-model.md`](operating-model.md) defines the daily loop and the
  routine-versus-gated boundary;
- [`data-and-execution-policy.md`](data-and-execution-policy.md) defines secrets,
  data, provenance, budget, and external-execution safety;
- [`arc-agi-2-kaggle-handoff.md`](arc-agi-2-kaggle-handoff.md) retains the
  historical Trial 001 procedure and frozen identities; and
- [`arc-agi-2-trial-002-kaggle-smoke.md`](arc-agi-2-trial-002-kaggle-smoke.md)
  records the completed Decision 0015 Trial 002 replacement private CLI smoke,
  quarantine, and local-scoring procedure; and
- the [`Trial 001 status page`](../../trials/first-real-domain/README.md) is the
  concise source for current state, next action, and blockers.

Trial 001 is closed as `inconclusive-no-promotion`; no continuation is
authorized. The simplified process does not change its frozen identities or
evidence boundaries.

Trial 002 remains a separate baseline question under Decisions 0014 and 0015.
The failed first attempt and runtime-verified replacement are retained. The
replacement completed four valid generations but scored 0/4 exact match; its
external execution authority is consumed. Current state is maintained in
[`trials/arc-agi-2-baseline/README.md`](../../trials/arc-agi-2-baseline/README.md).

Default handoff validation:

```powershell
python tools\repository_check.py --all
```
