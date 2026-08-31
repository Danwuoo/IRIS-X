# Model specialization execution substrate v0

Status: qualification substrate

This provider-neutral dry-run uses two local deterministic candidate configurations: one succeeds and one intentionally terminates with an explicit failure. It performs no model, provider, network, or paid API call.

Run:

```powershell
python experiments\substrates\model-specialization-v0\scripts\dry_run.py --run-id dry-run-20260901-local-01
python -m unittest discover -s experiments\substrates\model-specialization-v0\tests -v
```

