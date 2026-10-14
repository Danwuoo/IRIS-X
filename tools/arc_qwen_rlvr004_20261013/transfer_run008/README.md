# Run008 engineering transfer, 2026-10-14

## Scope and current status

This is a comprehensive engineering supplement to the separately delivered full
tracked repository source. It preserves exact public-safe run008 runtime,
assembly, deployment and terminal-consumer components plus reconstruction tools,
original hash inventories and dependency mappings. It is **not a complete closed
admission candidate** and is **not authorization to upload to Kaggle, save a
notebook, launch a run, access credentials or collect provider outputs**.

The implementation baseline is commit
`98b488a2fc3185a64c392933f087b72ab13f1989`, tree
`28d25f61fd040b7ea281d77f39e94bfbce76fb1b`. The external delivery
`PACKAGE-MANIFEST.json` identifies the final source commit/ZIP, including the
updated handoff and packaging review. Do not mistake this baseline for the final
published documentation commit.

The last verified actual provider state is code20 and notebook39 ERROR, exact
source SHA256 `a3076380789de383c1df7c710023d8ca9e9a64a37405547bcebf0e066405d4b9`.
No code21 publication is proven; no durable v21 claim/journal, run008 epoch,
new score or successful baseline exists. Code21/inactive40/active41 in historical
candidate documents are proposed numeric bindings, not allocated live versions.
Native transport was implemented and independently reviewed. The latest blocker
was formal network execution failing synthetic sandbox setup before command
start; ordinary local execution still worked. This is not evidence of an OAuth
problem. Preserve the original run007 epoch1791908053/deadline1791951253 and every
prior failure/charge. Full CI is not green: seven inherited README findings
remain; focused CPU passes are a separate claim.

## Contents and boundaries

- `components/`: 308 exact files from the 424-file reviewed original local candidate,
  including all259 runtime members, the exact source archive/code payload,
  five assembly helpers, all21 consumer helper members and its accompanying
  code/release metadata. Exact component byte identity is established; completeness
  or deployment admission of this subset is not.
- `provenance/ORIGINAL-CANDIDATE-INVENTORY.json`: untouched inventory of the
  original candidate. Never rename this into the component root to pretend
  omitted files exist.
- `provenance/COMPONENT-CORRESPONDENCE.json`: all424 original file hashes and the
  precise included/omitted decision. Original candidate manifest SHA256 is
  `beda6a5647df0431ac2ac8da26db170d84776be8f59181b5fee537e87423a857`; original
  inventory SHA256 is `bb096f6d53967523961f894c954daa1b4b1f956d54af3586d89bf544aea90cf2`.
- `provenance/OMITTED-COMPONENT-RECOVERY-MAP.json`: 102 omitted historical files
  have exact byte matches in the existing authentic-inputs archive. Remaining
  run008 owner/readback/approval dependencies require actual destination evidence
  and fresh independent review, not substitutions from historical files.
- `ORIGINAL-DEPENDENCIES.json`: original Drive IDs, outer archive hashes and
  inventory hashes; unchanged evaluator archives are referenced, not duplicated.
- `tools/verify_transfer.py`: unchanged stdlib-only safe verifier/restorer.
- `tools/rebuild_engineering.py`: offline reconstruction of authentic run007 plus
  the exact311-file inert run008 source proposal, with all gates retained.
- `NATIVE-ENVIRONMENT-REQUIREMENTS.json`: environment-specific limits and pins.
- `TEST-RESULTS.json`: tests of this transfer, distinct from GPU/scientific proof.

The original Drive folder is anyone-with-link writable. Treat these new files as
public. No account/OAuth/token/PKCE state, new private owner or conversation ID,
private launch config, raw provider readback, evaluator answer body or unrelated
log is included. Existing public source has historical nonsecret provenance
paths and fixed authentication-boundary code; these are preserved byte-for-byte,
not copied account state. Source archives are not snapshots of a working machine.
Never upload this whole supplement, source repository or evaluator archive as a
Kaggle code Dataset. Even the exact code payload here remains historical reviewed
bytes and does not establish current publication permission.

## 1. Verify and restore the supplement

Obtain the outer SHA256 from the external delivery manifest/SHA256SUMS. Use the
separate delivered verifier, or the identical verifier in the repository:

```sh
python3 -B verify_transfer.py --archive /transfer/IRIS-X-run008-portable-components-20261014.zip --sha256 EXPECTED_SHA256 --verify-only
python3 -B verify_transfer.py --archive /transfer/IRIS-X-run008-portable-components-20261014.zip --sha256 EXPECTED_SHA256 --output-root /work/IRIS-X/.irisx/imported-run008-components
```

The verifier requires absolute paths, a fresh output root, regular single-link
files, safe portable names, closed membership and every SHA256/CRC. It validates
all members before creating output. It never opens nested ZIP bodies or invokes
programs. Preserve failed partial output; investigate and select a new root.

## 2. Restore source and real Git history

Use the separately delivered final source ZIP or the public repository branch
`feat/run008-native-research-20261013` at the exact external delivery commit.
A source ZIP alone is insufficient for historical reconstruction: the builders
require original Git snapshot commit
`e951604b829497e81bc6e18b32662ff050bd54db`, tree
`f9b10d12b912f3a92238375451c0ad56d4cb7efb`, 2558 files.

The original program-transfer ZIP in `ORIGINAL-DEPENDENCIES.json` contains the
complete historical bundle `history/IRIS-X-run007.git.bundle`, 93,692,557 bytes,
SHA256 `5e9f0e64a67e41cb8c96f682e46190acb2ab8c66f9870fecc15fd72ebc628209`.
Its `refs/heads/main` is that exact historical snapshot. Verify the original
outer archive before extraction, then verify the bundle and fetch its historical
refs into a fresh private clone if the needed object is absent. Do not publish
or alter those old refs. A normal complete public Git clone can supply the same
objects. Check the exact commit/tree, never synthesize Git metadata from a ZIP.

The final source ZIP restores tracked files only. It must not overwrite another
working tree or change unrelated local work. Repository guidance and the current
transfer-only direction take precedence over historical continuation authority.

## 3. Reproduce original source and inert run008 source proposal

Historical reconstruction needs the existing
`IRIS-X-run007-authentic-inputs-EVALUATOR-ONLY-20261014.zip`, SHA256
`09da465d0f82f3d83802d116f3f41c77a8071a8792c7ce9ea7d45b1c134e7c99`.
Verify and restore it using the same safe verifier into an isolated private
location. It restores an `authentic-inputs/` directory under the chosen root.
Do not inspect evaluator answer bodies or expose them to solver/training/prompt
contexts. Unchanged historical validators may hash opaque proof members for
integrity; this does not authorize semantic answer reads.

Use POSIX/Linux and Python3.12, actual account HOME, no linked paths and a fresh
checkout with more than5GiB free. No GPU or Kaggle setup is needed for this step:

```sh
export PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1
python3 -B /transfer/restored-supplement/tools/rebuild_engineering.py --repository-root /work/IRIS-X --authentic-inputs-root /private/restored-inputs/authentic-inputs
```

The helper retains the inherited environment plus offline flags, including
`GIT_NO_LAZY_FETCH=1` before the first Git object read and for both child builders. It refuses
existing output roots, checks real historical Git objects and pinned overlays,
then calls the existing CPU-only builders. It reconstructs:

- `.irisx/transfer-verification-20261013/rebuild-offline-2/source-rebuild`: all283
  authentic run007 source-proposal files
- the sibling `candidate-rebuild`: all426 authentic consumed run007 candidate files
- `.irisx/run008-packaging/independent-reviewed-proposal`: all311 exact inert
  run008 source-proposal files, inventory SHA256
  `fc32f98bef4188761fd51275bb05dd26c6fbd237afb8b8403b492f61442055cd`

The runtime source identity remains
`c61025e67354272099e40941cadcd77202964846d9a4c42c51a1817f77bb661b`; its source
archive SHA256 remains
`4d8b414bd35ca79a2eaaec7042880966879ed13bdeaf96762eaee7932ee1de4c`.
All original physical charges, source pins, clocks and isolation remain intact.
The reconstructed proposal is inert and is not an admitted numeric candidate.

## 4. Continue engineering and classify tests honestly

The full tracked source contains the loader repair, successor builder, admission,
native transport, independent active-wire verifier, collector and reviews.
Run focused suites normally and under `-O`; retain normal canonical children
where their process contract requires them. Tiny CPU fixtures and synthetic ELF
checks do not validate the real14B/cuDNN/GPU workload or PUBLIC120 accuracy.

The authentic dependency requirements are explicit:

1. `rebuild-offline-2/source-rebuild`, `candidate-rebuild`, `REBUILD-REPORT.json`:
   reconstructed by the helper from the original inputs and genuine Git history.
2. `run008-packaging/independent-reviewed-proposal`: rebuilt byte-identically by
   the helper. The original source inventory is also supplied as provenance.
3. `run008-live-20261014/bracket-0001`: not distributed; contains private raw
   metadata/source/status readbacks. A new authorized read-only reconciliation
   and `admission_run008/seal_inputs.py` are required. A new observation has new
   hashes and requires fresh proposal/review; it is not the original bracket.
4. `run008-live-20261014/OWNER-DIRECTION.json`: not distributed. Create only from
   actual qualifying owner authority, with a new private local identity. The
   current packaging instruction does not authorize the continuation booleans
   required by the production admission builder. Do not fake them to pass tests.
5. `run008-admission/draft-0001`: the active-wire regression suite expects this
   authentic local draft. It is not supplied. Restore through an explicitly
   authorized private route or prepare a separately identified equivalent test
   fixture with independent test-source review; do not silently substitute
   `components/` or manufacture an authentic old draft.
6. Final original candidate and native stage1/local action reviews: original
   inventory/hashes are preserved, but private owner/config bindings are absent.
   Fresh destination paths/config, actual observations and full dependent reviews
   are required. Existing source-bound reviews are historical evidence only.

Consequently admission and active-wire fixture suites are blocked on a clean
public-only download, not passed or skipped-to-green. Missing-input failures
must remain visible. The source-proposal and transfer suites can run after step3;
mocked transport suites need the exact official SDK source versions but no login.
Run `python tools/repository_check.py --all` and distinguish inherited findings.

## 5. Native environment and future publication gate

The reviewed transport pins Kaggle2.2.4 and kagglesdk0.1.37 with a complete
Python-source lock. It also pins a source-environment wrapper and already-trusted
CA file. These account/TLS assets are intentionally not transferred. A destination
with different supported wrapper, virtualenv or trusted CA must receive a narrow
new portability implementation/review, not a disabled check or a copied account
store. Never change protected paths, proxy settings, TLS trust, credentials or
permissions to work around the current execution blocker. Never spoof HOME.
Use only the supported official destination authentication flow if later needed
and authorized; credential or access changes retain their separate confirmations.

Only a new qualifying instruction can reopen provider work. The first step then
is fresh read-only reconciliation of exact code/notebook identities and any
unknown mutation, not a blind code21 retry. Single-publisher claims, exact numeric
readback, owned no-model mount acceptance, inactive save/readback, independent
static/dynamic wire review and one immutable predispatch clock remain gates.
The full session cap is43,200 seconds; PUBLIC120 remains120 tasks/167 queries.
There is no new run, clock, allocation, success tag or scientific result in this
package. Stop here for the current packaging-only task.
