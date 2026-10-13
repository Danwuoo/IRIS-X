# Exact run005 publication successor

This directory is a separate successor of the consumed local code17/run004
operator. Do not edit or reuse its original claims, wire, source, epoch,
evidence or reviews. The owner's continuing repair authorization retains the
12-hour bound for every independently reviewed, one-shot attempt.

The exact profile is code Dataset 17 → 18, notebook 33 ERROR → inactive 34
QUICK_SAVE → active 35 RUN, with `run005`, `source005` and `environment005`
namespaces. `release_role` and the active role remain `rlvr004`, the frozen
method-family label. This retains helper contracts while assigning fresh
source, manifest, provider version, namespace, state and review identities.

`config.py` and `operator_common.py` are byte-for-byte copies of the consumed
local operator. Official local credential storage, real HOME, live Windows
ACL/reparse checks, bounded requests, credential redaction, unknown-write
reconciliation and the shared scratch publisher lock are unchanged. No quota
API or implicit numeric version is available.

Supply the reviewed local config path/hash and manifest path/hash through the
existing CLI. In addition to the copied generic config schema, this transport
requires exactly:

```json
{
  "versions": {
    "code_predecessor": 17,
    "code": 18,
    "inactive_predecessor": 33,
    "inactive": 34,
    "active": 35
  },
  "state_root": "<reviewed scratch_root>/state-run005",
  "evidence_root": "<reviewed scratch_root>/evidence-run005"
}
```

The fresh manifest format is
`irisx/qwen14b-rlvr-run005-publication-contract-v1`. Other Dataset pins, native
model, Docker image, ARC3 metadata association, privacy/offline/GPU settings,
clock offsets, storage/byte bounds, source hashes, scorer and process/evaluator
guards remain independently verified. The active epoch is sampled once before
dispatch. A stale epoch consumes the claim without sending; neither retries nor
monitoring can reset that attempt's epoch or deadline.

The predecessor format is `irisx/rlvr005-predecessor-evidence-v1`, with exact
identity fields, 13 evidence descriptors, a complete numeric selected-output
descriptor map and a separate unchanged historical v31 proof. The actual v33
provider-saved notebook SHA-256 is
`e7747c8013a9149cf7331954fd583fd8770adb416b2881074c9875f94c3f7761`;
its submitted source SHA-256 is
`a3bdc6b13870a0dcc6862a08b2ebbef6f07419e9147c1c989fb6a4403abba037`.
They are compared using only the documented notebook source-list → string
normalization. The v33 epoch remains 1791866719 and deadline 1791909919.

The predecessor validator pins the observed v33 diagnostic, selected retrieval
and archive hashes; checks original launch/JIT/wire, code17 byte receipt,
required raw outputs, ordered same-source ERROR bracket and ZIP/terminal links;
and preserves the unsealed/absent journal, unknown physical total, unauthenticated
model closure and absent PUBLIC result. Verified process termination and archive
integrity cannot become scientific or operational success. Original v31 partial
evidence is preserved under `historical_v31` and never relabelled as v33.

Each mutation still requires its exact reviewed bytes, durable exclusive claim,
safe uncertain-write reconciliation and exact provider readback. Numeric
Dataset receipts, inactive receipts and journals must match this profile;
old run004 cache or receipts cannot admit run005. The new collector needs a
fresh external consumer operator/entry binding after its final hash, retaining
the unchanged 21 validation helpers. Publication does not imply execution or
success; terminal scoring and closure evidence remain mandatory.

Offline tests use synthetic SDK/credential/ACL objects and never call provider,
read real credential bodies or execute a model:

```sh
python3 -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_run005/tests -v
python3 -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_run005/tests -v
```
