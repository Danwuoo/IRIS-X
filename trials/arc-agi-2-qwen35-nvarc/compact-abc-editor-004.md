# Compact ABC owner-Editor beam comparison 004

Decision 0047 authorizes one distinct private QUICK_SAVE of
`nvarc-compact-abc-editor-004`. Its exact plan is
`configs/compact-abc-editor-004.json`, canonical digest
`sha256:ab9a2427ae41a274f9db5f423e7fb19db4ba3868b2beaa3e7f9d647c59561ebf`.

The [003 result diagnosis](compact-abc-003-editor-diagnosis.md) shows no
exact-match gain from changing TTT steps or learning rate on three repeated
public development parents. The 004 notebook instead compares the same A/B/C
material and one-step TTT settings with a two-path legal model beam. The
grammar, two views, two generation calls per task, two candidates per call,
verification and ranking remain fixed. The previous decoder branched its
second path only at the first grid digit; this one may branch at any digit.
It uses cumulative model log probability, with no evaluator truth or
answer-derived prompt content.

The notebook checks the official competition mount
`/kaggle/input/competitions/arc-prize-2026-arc-agi-2` and four distinct BF16
L4 UUIDs. A, B and C run sequentially on one selected GPU. The same three
private Datasets, Internet-disabled USD 0 configuration and 1,800-second
session remain. The owner will run the saved notebook in Editor and return
its `/kaggle/working/結果.zip` for a separate local development score.

## Sole save receipt

The one private `QUICK_SAVE` was accepted on 2026-09-29 as version 1:
[nvarc-compact-abc-editor-004](https://www.kaggle.com/code/danielwuu/nvarc-compact-abc-editor-004)
(kernel ID `136344090`). The agent sent exactly one `SaveKernel` request and did
not start a session or query its runtime. The owner will run it in Editor and
return `結果.zip`. The save authority is consumed.

The exact plan digest is
`sha256:ab9a2427ae41a274f9db5f423e7fb19db4ba3868b2beaa3e7f9d647c59561ebf`.
The staged notebook SHA-256 is
`9d1fd88bf8e5b954b8dd1124550c53cd22f3ae7da3732de400ba5bf9f328779d`;
runtime wheel SHA-256 is
`9010b3ec2688d0f7e8c506d61d1959b0ff74aaaecd6be13355fe1252a1b6b012`;
metadata SHA-256 is
`d44b365033590da230e502f32f4237307e2c07e8719ff7f3ea1b3effd3fd4c0b`.
The local preflight SHA-256 is
`42536af1108be4c93c258f9ec3e8a609b5ffbf73f977dc52a0c983eb5a628e23`,
the exact SDK request SHA-256 is
`35853978ea3870f64926c0c00330797bbb31c68b1f24fef0f5f0ddd495f34f1b`,
and the provider receipt SHA-256 is
`95cc598c504b421cb835b10ebb0ce38104124d6bcd2e3b85389244cbfcd3d54e`.
The ignored local ledger records the sole reservation, send and receipt at
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/decision-0047-save-ledger.json`.

Offline verification included exact material and embedded-payload preflight,
a tiny Qwen one-step TTT and beam-generation replay, and
`python tools/repository_check.py --all` (287 tests, four skipped, pass).
No additional save, agent execution, status/log/output query, retrieval,
Dataset change or automatic retry is authorized.
