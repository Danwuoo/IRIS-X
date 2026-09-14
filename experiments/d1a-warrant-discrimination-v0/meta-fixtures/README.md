# D1a Deterministic Meta-Fixtures

These coordinator-authored cases test instrument behavior only. They are not
held-out assets, do not satisfy a custodian role, and cannot support F1-B/C/D/E.

`cases.json` compactly fixes synthetic outcome, verifier, evidence, authority,
action, and rival-region conditions. `qualify_instrument.py` expands each case
to the canonical episode schema without a model/provider call. Paired identity
groups test evidence-volume and outcome-fixed authority invariance. The fixture
set deliberately contains verifier false accepts, false rejects, disagreement,
error, and unknown states.

`calibration.json` is a synthetic admitted calibration rule only for exercising
P0 in the instrument. It is not an exact-configuration empirical calibration
bundle and cannot be assembled into real D1a.
