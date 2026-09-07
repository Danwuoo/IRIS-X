# Capability Pressure and Failure Attribution v0

- **Status:** Phase 6 Batch 1 research-local offline instrument
- **Scope:** deterministic evaluation of predeclared pressure, attribution, and
  trigger fixtures plus selected Phase 5 replay
- **Architecture authority:** none; this instrument does not implement a
  deferred capability or define a final ontology
- **Model/provider calls:** prohibited; `0 / 0`

This experiment keeps six layers explicit:

```text
observation
  -> shortfall classification
  -> failure attribution
  -> intervention hypothesis
  -> trigger evaluation
  -> research decision
```

No layer silently authorizes the next. Gate-positive synthetic fixtures show
only that the evaluator recognizes a frozen predicate. They cannot produce or
mutate a direct-evidence capability trigger.

## Layout

- `definition/` contains the candidate vocabulary, eight finite gates, and the
  assessment-record schema.
- `fixtures/synthetic-pressure/` contains 24 cases: negative, near-trigger, and
  synthetic-positive for each gate.
- `fixtures/attribution-boundaries/` contains eight collision cases, including
  two intentionally ambiguous cases.
- `fixtures/phase-5-replay/` contains hash-bound references to immutable Phase
  5 evidence. The evaluator reads the referenced source artifacts directly.
- `scripts/` contains the explicit standard-library validator, evaluator, and
  derived-summary generator.
- `tests/` contains focused definition, gate, attribution, replay, and
  determinism checks.
- `runs/batch-1-offline/` is created once from the frozen definition/code SHA.

## Offline commands

From the repository root:

```powershell
python experiments\capability-pressure-attribution-v0\scripts\validate_definitions.py
python -m unittest discover -s experiments\capability-pressure-attribution-v0\tests -v
python experiments\capability-pressure-attribution-v0\scripts\assess_pressure.py --output-dir experiments\capability-pressure-attribution-v0\runs\batch-1-offline --starting-sha 4aa7256e2237e997425e8712638334088056037d --freeze-sha <definition-code-freeze-sha>
python experiments\capability-pressure-attribution-v0\scripts\validate_definitions.py --validate-run experiments\capability-pressure-attribution-v0\runs\batch-1-offline
```

The assessment command refuses to overwrite an existing run directory, checks
that `HEAD` equals the supplied full freeze SHA, performs no network or model
operation, and emits canonical JSON without timestamps.

## Boundaries

The candidate shortfall axes and failure stages are provisional research
labels. They are intentionally outside `irisx/core`. The experiment is not a
router, retry loop, recovery runtime, persistence mechanism, workflow engine,
model judge, specialization system, action executor, or architecture planner.
