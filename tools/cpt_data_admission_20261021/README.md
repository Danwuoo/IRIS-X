# CPU-only corpus-admission prerequisite

This is an **offline JSONL grid-record admission tool**, not a trainer, a tokenizer,
a data-acquisition command, a license adjudicator, or permission to start a run.
It requires Python 3.11+ and the standard library on POSIX (the local lock uses
`fcntl`). It makes no network requests and never executes dataset programs.

## Current evidence boundary

This publication exercises self-authored synthetic positive and negative
fixtures only. A license card does not resolve missing dataset lineage; an exact
repository commit does not prove freedom from excluded ancestry; successful JSON
parsing does not establish correctness. No real corpus admission is claimed by
this standalone checkpoint.

This stage stops before rendering/tokenization. Its grid JSON output is **not**
tokenizer-ready or model-training-ready. Code/text/program-target formats need
separately reviewed adapters and verifiers. The existing user-owned Qwen run is
not queried, changed, or restarted.

## Commands

```sh
python -m tools.cpt_data_admission_20261021 admit \
  --registry /approved/local/window/registry.json \
  --registry-sha256 <independently-reviewed-registry-SHA256> \
  --output .irisx/cpt-prerequisites-20261021/data/my-window

python -m tools.cpt_data_admission_20261021 verify \
  .irisx/cpt-prerequisites-20261021/data/my-window/bundle

PYTHONHASHSEED=0 python -m unittest discover -s tests \
  -p test_cpt_data_admission_20261021.py -v
```

Do not invent evidence to make a registry pass. The caller must review the actual
source, origin, license/notice and ancestry evidence, then supply its reviewed
registry hash. A hash binds an assertion; it does not authenticate the assertion
or establish its truth. All ancestors, known family members and historical
splits relevant to the window must be represented, even when their records are
not materialized in the selected window. Omitted/unreported ancestry cannot be
discovered by this offline tool.

## Registry schema, version 1

The registry is strict JSON, with these exact top-level keys:

- `schema_version`: integer `1`.
- `scope`: `synthetic-fixtures`, `local-public-sample`, or `bounded-corpus-window`.
  None means the whole upstream corpus was reviewed.
- `artifacts`: object keyed by stable artifact ID. Each value contains exactly
  `path`, `bytes`, `sha256`. Paths must be relative to the registry directory,
  with no `..`, absolute path, backslash or symlink component. Local source
  shards, provenance evidence and license/notice documents are byte-pinned.
- `sources`: object keyed by stable source ID. Each value contains exactly:
  - `url`: HTTPS upstream URL, or `fixture://...` only in synthetic scope.
  - `revision_kind`: `git_commit` (40 lowercase hex), `sha256` (64 lowercase hex),
    or `dataset_version` (`owner/dataset:vN`, N positive). Floating names fail.
  - `revision`: exact revision string in that format.
  - `parents`: all upstream source IDs, or `[]` for a reviewed original source.
  - `origin_status`: `resolved` to pass; unknown/unresolved quarantines.
  - `rearc_status`: `clear`, `derived`, or `unresolved`. `clear` must come from
    reviewed ancestry evidence, never a repository name or author claim alone.
  - `evidence`: nonempty list of pinned artifact IDs supporting the origin.
  - `license`: exactly `status`, `spdx`, `evidence`, `notices`. Passing requires
    `status: resolved`, a nonempty reviewed SPDX expression, nonempty evidence
    artifact IDs and a list of required notice artifact IDs (possibly empty).
    Unresolved/conflicting licenses never become admitted through inference.
- `lineage`: object keyed by stable lineage node ID. Each value contains exactly
  `source_id`, `parents`, `family_ids`, `original_split`, `iris_split`, `evidence`.
  `parents` includes **all** parent nodes. `family_ids` is a nonempty list of
  globally stable, audited family/generator/program identities. `evidence` is a
  nonempty list of pinned artifact IDs supporting those assertions.
- `shards`: nonempty list of objects with exactly `artifact_id` and `source_id`.
  Each artifact is consumed once, in deterministic `(source_id, artifact_id)`
  order, independently of JSON object insertion order.

Splits are `train`, `dev`, `evaluation`, `source_test`. Anything unresolved is
quarantined. `original_split` and `iris_split` remain distinct. Original training
roots can be assigned to development by a reviewed fixed split; evaluation or
source-test roots cannot be relabeled as train/dev. A child's ancestry must
remain within its assigned IRIS partition. This tool does not resplit the
existing 800/200 mapping or erase historical exposure.

## Streaming record schema

Each JSONL line contains exactly:

```json
{
  "record_id": "globally-stable-record-id",
  "lineage_id": "registered-node-id",
  "source_locator": "original-object/path:row-or-offset",
  "transforms": [],
  "task": {
    "train": [{"input": [[0, 1]], "output": [[1, 0]]}],
    "test": [{"input": [[0, 2]], "output": [[2, 0]]}]
  }
}
```

`transforms` is optional and defaults to `[]`. No arbitrary program/text fields
are accepted or executed. Grids must be rectangular, nonempty, at most 30×30,
and contain only integers 0–9 (not bools/floats). Train/test lists each contain
1–128 pairs. All training targets are mandatory. Evaluation test targets may
all be present or all absent; partial gold is rejected. **Every test is retained
and validated**, not just test index zero. Unknown fields, duplicate JSON keys,
nonfinite numbers, invalid UTF-8 and empty lines fail closed.

## Isolation, rejection and deduplication

1. Verify immutable artifact bytes and registry pin before staging.
2. Resolve complete source and lineage graphs. Cycles, missing parents, depth
   limits, missing evidence/licenses and unresolved origins quarantine. Explicit
   ReArc labels/URLs/locators and declared derivatives reject; descendants and
   linked families inherit the exclusion. Keyword detection is a defensive deny
   check, never the basis for granting ReArc-free status.
3. Connect every registry node by all ancestors and family IDs, including known
   nodes absent from the selected shards. Any incompatible split or unresolved
   member taints the entire component.
4. Stream records to a private SQLite staging cache. Connect materialized records
   by registry family component, exact task hash, transform-canonical task hash,
   and answer-free visible-task canonical hash. Provenance taint propagates
   through those links; omitting evaluation gold cannot evade isolation.
5. Quarantine **all** members of cross-split components, not merely the row read
   last. Duplicate record IDs quarantine all occurrences. Within an otherwise
   valid isolated split, keep the lexicographically smallest record ID for each
   transform-canonical duplicate.

Transform canonicalization uses the eight joint D4 grid transforms plus one
consistent bijective relabeling of all colors, including zero, across the whole
task. Train/test pair order stays significant. Exact and finite-transform
deduplication are **not semantic/rule/program deduplication**. Similar unseen
rules, renamed source identities and omitted ancestry need an independent audit.

## Outputs and security boundary

A sealed `bundle/manifest.json` contains exact output digests/counts, pins,
limits, reasons and honest limitations. There are separate allowlisted outputs:

- `training/train.jsonl`: accepted train records only.
- `evaluation-inputs/{dev,evaluation,source_test}.jsonl`: only record ID, complete
  demonstrations and query inputs. No query outputs, raw-body hashes, family
  metadata or target-derived metadata are copied into these solver inputs.
- `evaluator-only/gold.jsonl`: query gold keyed by record ID and test index.
- `audit/decisions.jsonl`: every row's outcome, including rejection reasons.
- `audit/provenance.jsonl`: accepted record lineage, source/row byte hashes,
  offsets, transforms and dedup fingerprints.
- `audit/registry.json`: exact supplied registry content, preserving graph and
  source/license evidence references. It does not copy the evidence bodies.

Only exact allowlisted training or prompt files may enter a later consumer.
**Never mount the whole output root or bundle into a training/solver process.**
The SQLite cache, failed export directories, audit hashes and evaluator gold are
private evaluator/admission-side material. Gold is mode 0600 and new output
subdirectories are 0700, but the same OS user can still read them. Separate
runtime identities/mounts are a required later gate; folder names alone do not
provide physical access isolation. This tool performs no uploads or sharing.

## Bounds, seals and restart

Defaults are 64 MiB total pinned input artifacts, 1 MiB per JSONL line, 100,000
records, 4 MiB registry, 20,000 source/lineage/artifact entries, 4,096 ancestors
per closure and graph depth 128. Corpus bodies stream through SQLite; metadata
and dedup indices are bounded by those caps. The bounded lineage cache holds at
most 128 closures. Resource-cap exhaustion stops without a sealed partial corpus.
No truncation, sampling-as-full-corpus claim or automatic acquisition occurs.

Use `--stop-after-records N` for a controlled checkpoint. It returns
`paused_not_sealed`; re-run the same command without that flag to finish.
Registry/tool/limit bindings must match. Each row and cursor commit together.
A restart replays and validates the stored prefix against raw source bytes;
SQLite is not trusted evidence. Stream digests and all inputs are reverified
before export. Classification reuses original immutable staged rows, including
after interrupted classification/export. An exclusive local lock prevents
concurrent writers. A completed bundle is atomically renamed into place, then
future invocations verify it rather than overwrite it. A failed export may
leave a private `.export-*` directory; no incomplete directory is training-ready.

For a new registry, source revision, tool version or limit, use a new output
identity. Manifest identity has no wall-clock/random build component, so an
interrupted/resumed build matches an uninterrupted build byte-for-byte. An
existing seal with changed/missing/extra output files fails instead of silently
rebuilding. Local tamper-evident hashes are not signatures or WORM storage.

## Public-checkout platform coverage

The admission tests exercise actual POSIX locking and filesystem behavior on
Linux. The explicitly named Windows-portable lane reports this test class as
unverified rather than simulating locks or claiming equivalent isolation.
