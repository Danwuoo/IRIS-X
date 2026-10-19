# Prospective acceptance logic only

This public slice contains `acceptance.py`, a documentation-only package
initializer, and synthetic standard-library tests. It is not the full fusion
experiment, an experiment runner, a model delivery, or evidence of model gain.
The initializer's plan/run CLI description refers to the wider experiment; no
CLI, model loader, trainer, provider client, or runtime capsule is included here.

The gate keeps three distinct questions separate:

- Engineering: declared all-800 training, complete fixed-96-parent evaluation
  (192 views), exact checkpoint reload, and required runtime evidence bindings.
- Scientific adoption: at least three preregistered paired seeds against a
  strong SFT control, explicit cost accounting, and parent-clustered comparisons.
  Development data are reused; these are not hidden-generalization claims.
- Formal stability: every preregistered selected seed model must have a bound
  official score strictly above 90 in the predeclared score population.

Missing or inconsistent evidence blocks the corresponding gate or raises an
error. Receipt fields and hashes do not independently establish truth, provider
authenticity, or hidden validation. A separate trusted evidence audit is needed.
Synthetic fixtures exercise the logic, including passing branches; their
boolean outputs and numeric scores are not real model or provider results.

No output grants authority to run experiments, spend cloud funds, create
resources, submit to a competition, or start a new agent framework.

Run only this slice's tests from the repository root:

```sh
python -m unittest discover -s tests -p 'test_nvarc_full800_fusion_acceptance.py'
python -O -m unittest discover -s tests -p 'test_nvarc_full800_fusion_acceptance.py'
```
