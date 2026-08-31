# Configuration regression substrate v0

Status: qualification substrate

This paired harness compares a deterministic baseline candidate with an intentionally faulty experiment-local configuration. It records outcome, evidence, and cost changes independently.

Run:

```powershell
python experiments\substrates\config-regression-v0\scripts\qualify.py --run-id qualification-20260901-local-01
python -m unittest discover -s experiments\substrates\config-regression-v0\tests -v
```

The injected-failure result demonstrates measurement sensitivity only. It does not establish general maintainability.

