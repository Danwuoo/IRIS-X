# Document Ops robustness substrate v0

Status: qualification substrate

This IRIS-X-authored substrate qualifies four deterministic transformation families with independent equivalence validators and one intentionally semantics-changing negative case. It executes no candidate and makes no robustness claim.

Run:

```powershell
python experiments\substrates\docops-robustness-v0\scripts\qualify.py --run-id qualification-20260901-local-01
python -m unittest discover -s experiments\substrates\docops-robustness-v0\tests -v
```

Normal evidence is compact: a terminal record per case plus results and a run manifest. There are no copied source workspaces or model outputs.
