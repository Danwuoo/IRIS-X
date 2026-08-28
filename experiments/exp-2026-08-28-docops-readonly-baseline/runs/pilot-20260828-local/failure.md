# Failed Pilot Attempt: `pilot-20260828-local`

- **Status:** invalid harness run; preserved failure evidence
- **Time:** 2026-08-28, Asia/Taipei host date; exact episode timestamps are in `raw/episodes.jsonl`
- **Code revision:** `21900b57c96c00e336e81d647fc27ae84b2c5be4`
- **External services / paid cost:** none / USD 0

## Procedure

From repository root:

```powershell
python experiments\exp-2026-08-28-docops-readonly-baseline\scripts\run_baseline.py `
  --manifest experiments\exp-2026-08-28-docops-readonly-baseline\inputs\task-manifest.json `
  --configurations experiments\exp-2026-08-28-docops-readonly-baseline\inputs\configurations.json `
  --output-dir experiments\exp-2026-08-28-docops-readonly-baseline\runs\pilot-20260828-local `
  --run-id pilot-20260828-local `
  --repetitions 3
```

## Failure

The runner wrote 72 terminal episode records and a derived `results.json`, then exited nonzero before writing `run-manifest.json`:

```text
NameError: name 'false' is not defined. Did you mean: 'False'?
```

The defect was a Python boolean misspelling in final run-manifest serialization. Because the required run manifest is absent, this attempt is invalid even though its generated `results.json` contains `"run_status": "complete"`. That aggregate must not be cited as a completed pilot result.

## Disposition

The directory is retained without alteration as failure evidence. The code fix changes `false` to `False` and writes the final run manifest before the aggregate results file. A rerun must use a new run ID and output directory.

Imported source status was clean after the failure. No source/paper bytes were intentionally written.
