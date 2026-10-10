# Validation and execution qualifications

## Frozen release

- Baseline main: `f25a7cd4765de9fe815273bcd6060804324c183b`
- Final 51-file runtime source identity:
  `94956754f30a376ce6b059c8642528887a72b02a625e000503e49412c59f4ec1`
- Code Dataset manifest:
  `91a0b5b548de8345b4fdb51b89e5d6cea52a81ad5a5f340c00ff4e3c89b64507`
- Code source ZIP:
  `abf53a6c2bc6730842969d75363f316aed400cd0007c1f4413d2ed7325026013`
- Data material manifest:
  `c55073f8e9f44682dd7d7f31ee7f04f39754a9922ec246073555026452f047e3`
- Default-inert notebook:
  `aad1901048a99e895e42ba50262a07752ae28deddce91937cdf7bb10d1f767c7`
- Config-only GPU run001 notebook:
  `acb65cd7224afd092401fd83247b7d6956c9918636f2e2e9fab7f1ac7c2d1235`

The two notebooks differ only in MANUAL_START, ENABLE_MODEL and OUTPUT_ROOT.
The builder canonicalizes pin key order for reproducible bytes. Original scorer,
interpreter, compiler, consolidated package and five offline assets remain pinned.
The integration owner independently verifies existing repository blobs and modes.

## CPU checks performed

The final focused suite runs 162 tests: 160 executed successfully and two explicit
opt-in native-material/integration cases skipped in the standard interpreter.
Independent integration reproduced those counts. The exact final inactive
notebook's manual entry was then executed in three fresh processes with a short
124-second budget: original archive, root-extracted source and source/-extracted
source. Each performed 20–24 real bounded CPU checks, stopped admission as
expected to preserve cleanup, archived the incomplete controls and did not open
the evaluator or call a model. These are entry/transport tests, not scores.

Separate exact native tokenizer checks used the official pinned Dataset v2 small
files with Transformers 5.8.1 and tokenizers 0.22.2, without weights or GPU:

- All 5,965 canonical plans pass native encode/decode, compiler, every prefix and
  terminal-EOS checks.
- 33,911 trie nodes; longest content sequence 57 tokens; native EOS/pad 100257.
- Observed setup approximately 10 seconds and 34.4 MB incremental RSS.
- All 120 task prompts were measured without truncation: 88 paired admissions,
  32 paired exclusions, 122/45 corresponding test inputs. Maximum prompt 15,943
  tokens. Prompt serialization is compact JSON. The model call ceiling remains
  240; currently at most 176 calls can be admitted.

Actual Transformers CPU-logit/sampling integration was **NOT RUN**: the exact
CPU-only Torch wheel download supplied by the official index returned HTTP403.
That route was stopped; fake-session tests are not a substitute. Actual GPU
weights/loading/generation remain unverified until the separately authorized
existing-resource active run succeeds.

Tests cover strict trie dead-prefix/EOS behavior, native vocabulary identity,
paired prompts/cache separation, outside-inventory responses, process ownership,
no implicit retries, complete denominator handling, fresh fit/query receipts,
source/data corruption, sealed prediction reconstruction, query overruns,
resource admission, entry provenance, unknown reservations and bounded archives.
An independent 64-case synthetic abstract-semantics sample also passed. This is
finite validation evidence, not a proof that the grammar solves ARC tasks.

## Actual public CPU operational acceptance

A frozen pre-transport candidate completed the actual 120-task/167-test workflow
with model disabled: 15,488 bounded CPU checks, zero model calls, scorer status
SCORED, overall status complete, owned processes stopped and archive readback
verified. The notebook reported 1,064.82 seconds before archival; streaming archive
and full readback took 10.73 seconds; final journal closure was at 1,076.44 seconds. Its archive binds 15,995 inventoried files plus global-seal.json and is
bound by SHA256 `55b85365fdafb3b44ff2963091f255e1d9a1e55f65da6cce07064119ac5c9348`.

This run has source identity
`fcc2d32ef2064de765c8be4d10c3077068c80b163c3388d48881d045a88fd07a`.
The final release changes only the source transport loader and runner's strict
entry-provenance validation/ledger retention. All scientific/model/ranking/
scorer/VM bytes and hypotheses are unchanged. The final orchestration has the
fresh exact-notebook entry tests and regression suite above; the CPU study is
not mislabeled as a full run of the later transport identity.

Per the owner's latest instruction, this acceptance records operational integrity
only. Scientific score values and method comparisons are deliberately not
interpreted. The GPU workflow will likewise be monitored for operational success
and then stopped without result analysis.

## Reproduction

From a verified checkout with Python3.12, a workspace-backed temporary directory
outside the source tree, and offline environment variables:

    PYTHONHASHSEED=0 PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
      HF_DATASETS_OFFLINE=1 python -m unittest discover \
      -s tools/arc_public_research_20261010/tests -v

Use the opt-in native tokenizer tests only with the separately hash-verified
small asset directory. No development test silently downloads model weights.
The whole-repository aggregate has pre-existing unrelated failures; integration
must compare exact labels against unchanged main rather than claim a clean
repository-wide test suite.

Provider writes, Dataset roundtrips, inactive readback, activated-version dispatch
and terminal operational acceptance each have separate reviewed receipts. A
renderer COMPLETE or CPU-only run does not establish GPU success.
