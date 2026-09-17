# Development

P0 establishes a clean product-era repository and deterministic offline
validation. It does not begin product implementation.

Current policies:

- [`operating-model.md`](operating-model.md) defines the product-first workflow,
  decision records, and authorization gates;
- [`data-and-execution-policy.md`](data-and-execution-policy.md) defines safe
  handling and execution boundaries.

Before future work, identify the owner-authorized scope and record any material
choice in `docs/decisions/`. Do not select a domain, provider/model, backend,
budget, deployment form, or detailed architecture by implication.

Current validation:

```powershell
python tools\repository_check.py --self-test
python tools\repository_check.py
python -m unittest discover -s tests -v
git diff --check
```
