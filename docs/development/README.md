# Development

P0 established a clean product-era repository. P1 adds deterministic offline
product contracts, a bounded qualification flow, and package verification. P2
has started with an admission package but remains blocked from real execution.

Current policies:

- [`operating-model.md`](operating-model.md) defines the product-first workflow,
  decision records, and authorization gates;
- [`data-and-execution-policy.md`](data-and-execution-policy.md) defines safe
  handling and execution boundaries.

Before a real P2 trial or later work, resolve the Decision 0003 admission gates
and record the owner-authorized scope in `docs/decisions/`. Do not select a real
domain, provider/model, backend, budget, deployment form, or detailed
architecture by implication.

Current validation:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```
