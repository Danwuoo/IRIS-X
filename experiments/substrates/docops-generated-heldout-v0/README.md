# Document Ops generated held-out substrate v0

Status: generator qualification substrate

This directory contains four IRIS-X-authored deterministic task-family generators with separate public inputs, hidden generation state, and independently derived hidden oracles. Qualification uses only the declared `development-visible` seeds in `inputs/qualification-protocol.json`.

It does not materialize the future real blind set and does not execute a candidate.

Run:

```powershell
python experiments\substrates\docops-generated-heldout-v0\scripts\qualify.py --run-id qualification-20260901-local-01
python -m unittest discover -s experiments\substrates\docops-generated-heldout-v0\tests -v
```

