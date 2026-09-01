# Maintenance Tools

This directory is for lightweight, standard-library-first repository and corpus maintenance utilities only. It is not a runtime implementation area.

Run from the repository root:

```powershell
python tools\repository_check.py
python tools\repository_check.py --self-test
python tools\model_baseline_check.py
python tools\model_baseline_check.py --check-local-catalog
python tools\migration_audit.py
```

`model_baseline_check.py` validates only the committed provider/model contract
and, optionally, the model catalog bundled with the installed Codex CLI. It does
not authenticate, execute a prompt, or make a model call.
