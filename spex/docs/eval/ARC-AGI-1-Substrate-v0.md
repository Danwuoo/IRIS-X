# ARC-AGI-1 Substrate v0

- **Version:** v0.1
- **Date frozen:** 2026-08-05
- **Status:** Current operational Stage 0 freeze
- **Scope:** Local ARC-AGI-1 training and public-evaluation task identity, task/rule reference snapshot, and governance labels
- **Document role:** Durable operational identity record. It is not an official evaluator, a run manifest, a score report, or empirical adjudication.
- **Authoritative evaluation definition:** [ARC Evaluation Definition v0](./ARC-Eval-Definition-v0.md) sections 6, 7.1, and 9.2

## 1. Frozen identity

| Component | Frozen value | Basis |
|---|---|---|
| Canonical repository | `https://github.com/fchollet/ARC-AGI.git` | Canonical-source role is source-stated by ARC Evaluation Definition v0 section 9.2; remote URL directly observed from the local checkout. |
| Repository commit | `399030444e0ab0cc8b4e199870fb20b863846f34` | Directly observed from the local checkout. |
| Git tree | `404585f14e148f2315aaa566b2179a4d528cecfa` | Directly observed from the local checkout. |
| Dataset manifest | [`artifacts/arc-agi-1/manifest.json`](../../artifacts/arc-agi-1/manifest.json) | Machine-readable, deterministic, file-level inventory. |
| Dataset manifest SHA-256 | `ee26dc8d3731cd670b3ed5e8712b675a6504ba741e428307200ab52e26a6f932` | Computed over canonical JSON excluding the self hash. |
| Rules snapshot | [`artifacts/arc-agi-1/rules.json`](../../artifacts/arc-agi-1/rules.json) | Immutable local-reference task-format and attempt-policy snapshot. |
| Rules snapshot SHA-256 | `237b2565904d50aaa03eed91dec90781f0ab2162e51b0c510530498679c76e68` | Pinned in the dataset manifest. |
| Manifest schema | [`schemas/arc-agi-1-dataset-manifest.schema.json`](../../schemas/arc-agi-1-dataset-manifest.schema.json) | Machine-readable artifact contract. |

The manifest deliberately carries no creation timestamp. Regeneration from this unchanged checkout and rules snapshot must reproduce the stated manifest hash.

## 2. Non-recursive task inventory and tier labels

| Manifest tier | Source directory | Direct `*.json` count | Required label | Use and boundary |
|---|---|---:|---|---|
| `training` | `data/training` | 400 | `training` | Training, prototype work, synthetic-data work, primitive discovery, and error analysis. |
| `public_evaluation` | `data/evaluation` | 400 | `public-exposed` | Final-algorithm evaluation source in the repository; development-only for this project unless an accepted governance record establishes a stronger boundary. |

The manifest scans only direct task JSON files. Nested task JSON files are invalid, and a missing, extra, renamed, or content-modified direct file fails validation. There is no separate local A1 `development`, `milestone holdout`, `sealed`, `semi-private`, or `private` tier in this checkout. Their status is **Unavailable in checkout**; the sealed split and custodian remain **TBD**. No public set is relabelled sealed or private.

## 3. Task, policy, and evaluator boundary

The rules snapshot freezes the local reference description of the ARC JSON task shape (`train` and `test` pair lists; `input` and `output` grids), 30×30 rectangular grids with values 0–9, exact all-test-output task success, and the source-stated A1 native maximum of three attempts.

| Component | Source identity | Status |
|---|---|---|
| Official parser | `Unavailable in checkout` | No official identity or parity claim is made. |
| Official scorer | `Unavailable in checkout` | No local score is official or parity-validated. |
| Official evaluator | `Unavailable in checkout` | No official evaluator is reconstructed. |
| Official submission writer | `Unavailable in checkout` | No local submission writer is treated as official. |
| Local Stage 0 validator | [`scripts/arc_a1_substrate.py`](../../scripts/arc_a1_substrate.py) v0.1 | Checks identity and file integrity only; it does not parse solver tasks or score predictions. |

The repository's static testing interface is not identified here as an official parser, scorer, evaluator, or submission writer. Its presence does not change any `Unavailable in checkout` status above.

## 4. Contamination and development-query record

- Training tier exposure status: `training`.
- Public-evaluation exposure status: `public-exposed`.
- Pretrained-model exposure: `unknown-model-exposure`.
- Historical development-query use before 2026-08-05: `Unknown`; it has not been reconstructed.
- Sealed validation: `TBD`; no custodian or separate split has been accepted.
- Append-only development-query log: [`artifacts/arc-agi-1/development-query-log.jsonl`](../../artifacts/arc-agi-1/development-query-log.jsonl). Its initialization event records no task query, model call, score, or architecture decision.

Any future public-evaluation query, task-specific inspection, aggregate-score feedback, solver modification, or architecture-selection use must be logged there before it is interpreted. Public-exposed results remain benchmark-proxy/development evidence and cannot establish sealed, private, or verified generalization.

## 5. Reproduction and validation

From repository root:

```powershell
python scripts/arc_a1_substrate.py generate
python scripts/arc_a1_substrate.py validate
python -m unittest discover -s tests -p 'test_arc_a1_substrate.py' -v
```

`validate` emits structured JSON and exits nonzero if the frozen manifest hash, rules snapshot, repository URL/commit/tree, tier definition/count, or any tracked task file differs. The regression suite exercises deterministic regeneration and modified, missing, extra, renamed, nested, and rules-snapshot mismatch cases.

## 6. Stage 0 acceptance record

| Acceptance condition | Result |
|---|---|
| Unchanged checkout regenerates the same manifest hash | Pass: `ee26dc8d3731cd670b3ed5e8712b675a6504ba741e428307200ab52e26a6f932`. |
| Missing, extra, renamed, or modified task files fail validation | Pass: regression coverage and validator implemented. |
| Public data is not described as sealed or private | Pass: the only local evaluation tier is labelled `public-exposed`; stronger tiers are unavailable/TBD. |
| Absent official scorer material is not reconstructed or called official | Pass: parser, scorer, evaluator, and submission writer are each recorded `Unavailable in checkout`. |

## 7. Remaining blockers and status impact

The sealed-validation split/custodian and private or semi-private access path remain `TBD`; official parser, scorer, evaluator, and submission-writer material remains `Unavailable in checkout`. These block official/parity-validated scoring, sealed generalization, and verified-completion evidence. They do not invalidate the completed local Stage 0 identity freeze.

- **Empirical claim impact:** none.
- **Evidence adjudication impact:** none.
- **ARC stage-status impact:** none; this is infrastructure completion, not an `A1-Research-Qualified`, public-complete, or verified-complete result.
- **Winning-hypothesis impact:** none.

## 8. Change log

| Date | Version | Change | Status impact |
|---|---|---|---|
| 2026-08-05 | v0.1 | Added canonical A1 source identity, deterministic 800-file manifest, rules snapshot, query-log location, and validator contract. | Operational Stage 0 substrate freeze only; no empirical or ARC stage-status change. |
