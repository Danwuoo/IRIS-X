# Phase 6 Post-Batch-3 Predicate/Provenance Authority Repair

This is a zero-model-call, research-local repair surface. It re-derives
capability predicates from the immutable Phase 6 Batch 3 terminal evidence
without modifying the historical Batch 3 definition, run artifacts, Result D
note, durable handoff, or retired plan.

The repair reuses the deterministic evaluator at
`experiments/phase-6-pressure-sampling-v0/scripts/derive_direct_predicates.py`.
It adds no runtime or architecture mechanism.

Run the focused checks from the repository root:

```powershell
python -m unittest discover -s experiments\phase-6-predicate-authority-repair-v0\tests -v
python experiments\phase-6-predicate-authority-repair-v0\scripts\validate_repair.py
```

Generate the deterministic derived artifacts only after the definition/test
surface is committed and supply that commit as `--definition-freeze-sha`.

```powershell
python experiments\phase-6-predicate-authority-repair-v0\scripts\derive_repair.py `
  --definition-freeze-sha <40-hex-git-sha> `
  --output-dir experiments\phase-6-predicate-authority-repair-v0\runs\authority-repair-20260910
```

Model/provider calls: `0`.

