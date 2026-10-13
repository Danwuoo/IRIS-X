# Exact numeric19 no-model acceptance

`accept_numeric_mount.py` is a local prerequisite wrapper outside the immutable
candidate. It is pinned to final manifest `7ddb20441b0515ab0462d874d573c6080c9bca96ffaead97c97f61be62a9e9fa`
and candidate inventory `90f5fb13f22cf59d7b7638aef2c94a7de81accd1632945870b85a9d37aa122ca`.
It has no provider, authentication, installation, model, or evaluator action.

The sole publisher must first supply an authentic numeric19 transport receipt,
its independently checked SHA256, and the actual downloaded code root. A local
payload copy or a synthetic receipt does not establish numeric provider
provenance. There is no fixture switch, alternate version, or self-approval path.

Required arguments:

```
python -B tools/arc_qwen_rlvr004_20261013/preparation_successor/accept_numeric_mount.py \
  --candidate-root <exact-final-candidate> \
  --code-root <publisher-verified-numeric19-payload-root> \
  --code-receipt-path <authentic-dataset-code-v19-receipt.json> \
  --code-receipt-sha <independently-checked-receipt-sha256> \
  --output-root <fresh-repository-.irisx-directory>
```

The wrapper verifies the candidate's complete closed inventory, exact numeric
version/private owner/manifest/metadata bracket, receipt root, and every actual
downloaded filename, size, and digest. The unchanged candidate mount helper
(`646b547a…`) runs inside the unchanged owned-process guard (`8bc66ac8…`) with
isolated Python and an explicit credential-free offline environment. It imports
all259 exact source members without a model library or evaluator body.

The helper's own early receipt cannot pass the outer gate. Both supervisor and
worker must exit zero, the guard must prove complete ownership and an empty
tree, no forced cleanup is allowed, and fresh incarnation checks must pass.
Candidate, numeric receipt and downloaded bytes are verified again afterward.
Only then is `MOUNT-RECEIPT.json` written with numeric19, the exact publication
and code-receipt hashes, `model_calls=0`, and `owned_tree_closed=true`.

The separate publisher's persisted audit must bind this receipt, the exact code
receipt, and the authentic inactive36 receipt before activation. This wrapper
does not perform that audit, publish, sample a session epoch, or dispatch.
Its owned closure concerns only this local no-model subprocess tree. It says
nothing about the old notebook35's runtime/model closure, costs, manual failure
cause, a new GPU run, or a scientific result.

This is trusted-source lifecycle isolation, not a hostile same-UID sandbox.
Readback roots, candidate bytes and review pins must remain independently
controlled by the publishing workflow. CPU-only helper/guard smoke tests retain
`actual_provider_readback_verified=false` and emit no numeric mount receipt.
