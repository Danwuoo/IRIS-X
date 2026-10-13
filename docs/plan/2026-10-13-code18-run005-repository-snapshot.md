# Owner-frozen code18/run005 repository snapshot

The owner stopped repairs on 2026-10-13 (Asia/Taipei) and requested fixing this
repository version. This is a reproducible source snapshot with unresolved
runtime failure, not a successful execution baseline or a promoted model.
Automatic repairs, downloads, Kaggle publication, dispatch and monitoring have
stopped. Future work requires a new owner instruction and a new branch/version.

The freeze commit changes only repository guidance and this record. Its parent
is the exact published runtime commit below; source, deployment, operator,
tests, source maps, reviews and historical records retain their original bytes.

| Repository binding | Value |
| --- | --- |
| Snapshot tag | `irisx-code18-run005-snapshot-20261013` |
| Published runtime commit | `dbf21033b41aff9327cf4f91159df0133529f176` |
| Published runtime Git tree | `e45a5dd49a2e91e20730777e3b447ebecb984481` |
| Run identity | `irisx-qwen14b-rlvr-20261012-run005` |
| Logical source SHA256 | `4050616ed0ed34d19501be416650a09ae5cc9c86c875b349a056baec9308f3e3` |
| Canonical source ZIP SHA256 | `22fc93ae1dfbc4d4a7c90cf9907668af5d697dece28cb9211dea82c776d7dc9e` |
| Environment005 SHA256 | `0f7133bdb22d8cba124537622ab09a98e9450e1649df1b07d4e6661d48e33e28` |
| Publication manifest SHA256 | `76b2e004770e1f41e9c2352fa9817bc185ea5fded75d9fd8ce29d50453e7b7ca` |
| Assembly inventory SHA256 | `de68ffa281990b844e41ea41d11357b2214a973048cd8e14ae64cab39159a5a0` |
| Source members | 259; 200 inherited baseline members unchanged |

The complete existing bindings remain in
[`RUN005-BINDING.json`](../../tools/arc_qwen_rlvr004_20261013/driver_path_repair/RUN005-BINDING.json)
and the source map/freeze beside it. That original candidate record keeps its
historical pre-publication status; this snapshot record adds actual subsequent
observations without rewriting the original artifact.

## Actual publication and unresolved execution

The [private notebook](https://www.kaggle.com/code/danielwuu/iris-x-learning-agent-20261011)
is ID 138123872. The private code Dataset is
`danielwuu/iris-x-learning-agent-code-20261011`, ID 12504696.
Code Dataset v18 was processed and downloaded at its numeric version; all 269
published files were verified. Inactive notebook v34 was saved with GPU/TPU/
Internet off and inactive switches. One active notebook v35 was accepted and
read back with its exact reviewed source/settings. Its observed state was
QUEUED and then CANCEL_ACKNOWLEDGED; RUNNING was not observed. A bounded official
SDK read-only snapshot after the manual error report again found saved v35,
code v18, CANCEL_ACKNOWLEDGED and the same saved source hash.

| Provider binding | Value |
| --- | --- |
| Code Dataset version | 18 |
| Numeric code18 provider archive SHA256 | `fa70251d4c60d67627d210ecbe244e251cb2726d80cf55a5f9d5c6fd4c817857` |
| Numeric code18 file inventory SHA256 | `89e7243c3fb80974ea0fa7bfb78c7e9693d082ccb1f8c3656ea4574e755917fc` |
| Inactive notebook version | 34, QUICK_SAVE |
| Active notebook version | 35, RUN |
| Last verified saved-run status | CANCEL_ACKNOWLEDGED |
| Submitted v35 notebook SHA256 | `f1f665d9309b396992e6e62274655b51cb193062ff55e0368971973fcd89e83d` |
| Provider-saved v35 notebook SHA256 | `778c014ccea8b0f376d06afeeeceb318e50b3bce926ef13a6da068c9b3d5d917` |
| Original pre-dispatch epoch | 1791871874 |
| Original absolute deadline | 1791915074 |
| New PUBLIC120 score | None; not zero and not an earlier version's score |
| Required scoring denominator | 120 tasks, 167 test queries, 334 planned views |

Submitted and provider-saved notebook hashes remain distinct. Their admitted
difference is only nbformat cell source-list to string normalization. The
consumed v35 epoch/deadline is immutable; it cannot be reset for a manual retry.

The owner subsequently reported an Editor traceback from source005:
`RuntimeError: owned parent preparation/runtime failed; preserve closure and logs`.
This is the outer nonzero/forced owned-child result, not the inner exception.
The manual attempt's exact version/source and original child stderr were not
available for verification. Do not assign its failure to saved v35 or infer a
driver, model, epoch or installation root cause from this wrapper alone.
The diagnosis was stopped at the owner's direction; no speculative repair was
incorporated into this snapshot.

The locked model reference remains `qwen-lm/qwen-3/transformers/14b/1` on
`NvidiaRtxPro6000`, private and Internet-disabled, with Docker image
`gcr.io/kaggle-private-byod/python@sha256:2757e0c7d1e0a9cb43da657b97e223c321a98f5014bdf64f44f2f6b083ad2b2f`.
Exact model/config/tokenizer/weight hashes remain in the existing
[`material contract`](../../research/qwen14b-materials/material-contract.json).
The seven non-code Dataset pins are unchanged:

- `danielwuu/iris-x-public120-data-20261010/1`
- `danielwuu/iris-x-learning-training-20261011/1`
- `danielwuu/iris-arc-next-runtime/8`
- `danielwuu/iris-arc-granite42-8b-offline/2`
- `danielwuu/iris-arc-next-cu128-cp312-wheels/1`
- `danielwuu/iris-arc-next-cpython312-offline/2`
- `danielwuu/iris-arc-granite42-run003-adapter-20261009/1`

The existing ARC-AGI-3 attachment is retained as metadata only. No competition
task reads or submissions occurred in this freeze. The original scorer pins
remain `58216d4cf1ced5740b7f66b7be845d38ce327f5fb84048876aa54d3ca29f9f72`.
No complete GPU inference, sealed predictions, original full-denominator score,
authenticated model closure or operational success has been established.

## Rebuild and validation limits

From a checkout of the snapshot, reconstruct the exact source using a fresh
ignored directory (Python 3.12 or the previously verified Linux interpreter):

```sh
python -B tools/arc_qwen_rlvr004_20261013/prepare_successor_release.py --mode source --repository-root . --parent-overlay tools/arc_qwen_rlvr004_20261013/driver_path_repair/parent_scoring.py --parent-overlay-sha 0ccdeecc8398098c0240d919c8ff9f4f51e5455ee96debd35c8c7c8ce10bb24b --output-root .irisx/snapshot-source-rebuild-001
```

The freeze verification reconstructed all 259 members from Git and reproduced
the source ZIP and environment hashes above. It executed no provider, model or
GPU calls. More details are in
[`REBUILD.md`](../../tools/arc_qwen_rlvr004_20261013/driver_path_repair/REBUILD.md).
Full proposal/final operational assembly separately requires the original
authenticated predecessor evidence and independent reviews outside Git; a
source-only rebuild grants no execution or publication authority.

Previously completed source005 checks include 21 focused driver tests, 11
successor-assembler tests and 34 local operator tests in both normal and
Python `-O` modes, plus 8 controlled-batched CPU simulation tests in each mode.
Assembly acceptance and numeric code18 mount import checks also passed. These
results are retained CPU/deployment evidence. The actual locked offline
installation followed by the entire production GPU launcher chain was not
validated end to end locally; synthetic and mocked native-driver positives
cannot attest the private BYOD driver, library mounts or actual GPU/model work.

The published runtime commit's
[complete CI run](https://github.com/Danwuoo/IRIS-X/actions/runs/38353809559)
failed. Ubuntu Python 3.11 ran 1,578 tests: 5 failures, 96 errors and 110 skips;
the other three test jobs were cancelled. Repository checks passed. Independent
comparison against the prior two revisions found the same 101 failed/error
identities and normalized tracebacks, with no newly introduced CI failure.
CI remains red; this comparison does not repair or waive those failures.

For the documentation freeze, repository validator self-tests (3 cases),
repository invariants, source reconstruction and diff whitespace checks passed.
A newly started native full test suite was stopped before completion; it has
no final result and is not counted as a passing validation. No fixes or waived
checks followed from that partial invocation.

## Retained evidence

Original code17/v31 and v33 artifacts remain unchanged. Raw archives, provider
receipts, detailed logs, process proofs and local credentials are excluded from
Git. Local evidence locations are:

- WSL operator root:
  `/home/wurre/.cache/irisx/code17-local-20261013/repository/.irisx/code17-ops/`;
  retain `state-run005/`, `evidence-run005/`, `candidate-run005/`, reviews,
  `ACTIVE-V35-SUMMARY.json`, `OWNER-MANUAL-HANDOFF-V35.json` and watcher logs.
- Native read-only saved-version snapshot:
  `.irisx/code17-local-20261013/manual-error-recon-1791873747065310900/`.
- CPU test receipts: `.irisx/code17-local-20261013/test-results/`.
- CI comparison: `.irisx/code17-ci-audit/INDEPENDENT-CI-FINDINGS.json`, SHA256
  `9422fb5d9f3046953bb6d8f36bea113c2998ad16dcba0013dfa332cc4b1080a0`.
- Freeze source reconstruction: `.irisx/repo-freeze-20261013-source-001/`.

The automatic watcher was terminated and the previous heartbeat was absent at
handoff. No active replacement dispatch is authorized by this snapshot.
Unexecuted diagnosis drafts and any bounded CPU failure fixtures created during
the subsequent investigation stay in ignored scratch, outside the frozen
runtime and its scientific evidence. Model weights, credentials, raw outputs
and unreviewed sensitive logs are not included in the freeze commit or tag.
