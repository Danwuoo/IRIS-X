# Engineering Trials

This directory contains the historical P2 admission package and the workspace
reserved for the first admitted real Engineering Trial. Decision 0004 selects
ARC-AGI-2, the official public data boundary, a local/offline path, one static
specialization intervention, and a zero-USD external paid-execution budget.
The synthetic qualification fixture generated under `.irisx/` is not a real
trial and is not retained here.

Decision 0005 selects the exact frozen Qwen3.8-27B revision and a manual,
private-Dataset Kaggle handoff using one network-disabled NVIDIA RTX PRO 6000
96 GB. The tracked [`first-real-domain/`](first-real-domain/) workspace contains
only the static notebook and instructions; model bytes, ARC bytes, handoff ZIPs,
returned predictions, and evaluation evidence remain under `.irisx/`.

[`p2-admission/`](p2-admission/) is a decision package, not trial results. It
records the historical blocked state, required owner choices, first-trial
draft, acceptance criteria, falsifiers, and Unknown fields. It remains immutable
historical evidence and is not an authorization token. Decision 0004 now
authorizes creation of the ARC-AGI-2 implementation under the reserved
`first-real-domain/` location.

The real ARC-AGI-2 model/solver run is not yet authorized. After the concrete
local model/solver and immutable execution envelope are bound, all preflight
gates pass, and a separate explicit owner execution authorization is recorded,
the trial must record its goal, baseline, candidate intervention, workload,
measured result, relevant costs, and resulting engineering decision.
