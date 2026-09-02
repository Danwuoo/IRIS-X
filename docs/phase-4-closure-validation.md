# Phase 4 Closure Validation

- **Status:** passed
- **Validated on:** 2026-09-03 Asia/Taipei
- **Starting main:** `a859399eafb294ea03290123c285c127426dfb5b`
- **Validated result milestone:** `972b6b99b0b7f99e9738721a42015b49197fb216`
- **Design run:** `design-20260902-chatgpt-03`
- **Blind run:** `blind-20260902-chatgpt-03`

## Commands executed from repository root

```powershell
python tools\model_baseline_check.py --check-local-catalog
python -m unittest discover -s experiments\substrates\model-specialization-v0\tests -v
python -m unittest discover -s experiments\substrates\docops-generated-heldout-v0\tests -v
python -m unittest discover -s experiments\exp-2026-09-01-luna-structured-program-specialization\tests -v
python tools\repository_check.py
python experiments\exp-2026-09-01-luna-structured-program-specialization\scripts\validate_experiment.py --design-run-id design-20260902-chatgpt-03 --blind-run-id blind-20260902-chatgpt-03
python experiments\exp-2026-09-01-luna-structured-program-specialization\scripts\validate_closure.py --design-run-id design-20260902-chatgpt-03 --blind-run-id blind-20260902-chatgpt-03
$changedPython = git diff --name-only a859399eafb294ea03290123c285c127426dfb5b -- '*.py'
python -m py_compile $changedPython experiments\exp-2026-09-01-luna-structured-program-specialization\scripts\validate_closure.py
git diff --check
```

The closure candidate was then staged and checked with:

```powershell
git diff --cached --check
```

## Results

- Model baseline: passed for one provider, one strong model, one cheaper model; bundled local catalog checked through Codex CLI 0.147.0.
- Corrected model-specialization substrate tests: 8/8 passed.
- Generated held-out substrate tests: 5/5 passed.
- H-P1a experiment tests, including provider schema preflight rules: 10/10 passed.
- Repository validation: passed with 13 sources, 7 paper artifacts, and registered hashes checked.
- Python compilation: passed for the 12 changed/new Python files in this batch.
- Whitespace/error checks: passed.
- H-P1a validation: passed with 96 blind entries, 382 total calls reconstructed, and 14 starting run directories preserved.
- Closure reconstruction: passed with 24/16/32 DEV/validation/blind tasks reproduced, six unique candidates, all selection keys reconstructed, 974 full/resolving commit fields, and all 96 blind raw outputs independently re-evaluated.
- Primary result reconstructed as C0 18/32, C1 32/32, C2 23/32; 14 paired C1 wins and zero paired C0 wins.
- Calls reconstructed as Luna 344/344, Terra 38/38, total 382/382.
- Subscription events, retries, recovery actions, prohibited tool attempts, routing, and escalation: zero.
- Authentication and billing on every current model-backed terminal: `chatgpt` / `chatgpt-subscription`; API-key fallback `prohibited`; provider cost `Unknown`.
- Canonical new outcome/evidence vocabularies: passed. The original dry-run's historical placeholders remain only in its unchanged immutable records.

## Preservation

- `sources/` tree: `10e28d83184c789fc468ca1edc3bebf42ba40b46` — unchanged from starting main.
- `references/papers/` tree: `ed29ebcde3f01b00a0e49eb33eef1688566dcad3` — unchanged from starting main.
- Original specialization dry-run: unchanged from starting main.
- All 14 run directories present at starting main: unchanged.
- `design-20260901-chatgpt-01` tree: `653ab82f1eb1a4d8f99e09c50ca54ae25bcb1a98` — unchanged after its failure milestone.
- `design-20260901-chatgpt-02` tree: `49b98340d2c10951dd04d42c564cec114582dd65` — unchanged after its pre-invocation failure milestone.

## Scope confirmation

No H-G1, H-W1, H-C1, or H-R1 experiment was executed. No fine-tuning, workflow search, router/cascade, architecture synthesis, architecture implementation, or Phase 5 work was performed. The validation establishes only the evidence and closure boundary recorded in `research/phase-4-closure.md`.
