# Development

P0 established a clean product-era repository. P1 adds deterministic offline
product contracts, a bounded qualification flow, and package verification.
Decision 0004 admits the bounded local/offline ARC-AGI-2 Trial 001 repository
implementation and preflight, while real model/solver execution remains
separately authorization-gated. Decision 0005 narrowly selects a manual,
network-disabled Kaggle execution venue and the frozen Qwen3.8-27B revision;
Decision 0006 uses its unpacked model Dataset directly under provenance checks.
Decision 0007 verifies the Kaggle-extracted trial Dataset tree directly.

Current policies:

- [`operating-model.md`](operating-model.md) defines the product-first workflow,
  decision records, and authorization gates;
- [`data-and-execution-policy.md`](data-and-execution-policy.md) defines safe
  handling and execution boundaries.
- [`arc-agi-2-kaggle-handoff.md`](arc-agi-2-kaggle-handoff.md) defines the
  trial ZIP plus unpacked-model handoff and local trust boundary.

Decision 0004, as narrowly amended by Decisions 0005, 0006, and 0007, resolves the Decision 0003 owner-choice gates for one trial; the
historical admission snapshot remains unchanged. Before the real P2 run, bind
the concrete local model/solver and immutable execution envelope, pass every
Decision 0004/0005/0006/0007 preflight gate, and obtain a separate explicit owner execution
authorization. Do not broaden the backend, provider/model, budget, deployment
form, or detailed architecture by implication.

Current validation:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```
