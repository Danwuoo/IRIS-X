# Offline next-line preparation

Latest verified code: private `danielwuu/iris-arc-next-runtime/4`, 26 files,
614,221 bytes, exact-version download verified. Manifest SHA256:
ab4e3058f56df5878627520adcf1d172f4121bfed8309c3de0afcefb482f391b.
This includes the strict Granite index repair, root wheel metadata fix and
isolated early child-guard bootstrap with no-reinstall migration.
The corrected model Dataset v2 and wheels Dataset v1 passed complete local
hash roundtrips and actual isolated Linux CPU acceptance, including parent/plain/
spawn network denial. The single private offline notebook QUICK_SAVE was
accepted as 137630087/version 2 with the owner-confirmed ARC3 association.
Exact source-content review allows only standard list-to-string cell source
normalization. Numeric Dataset pins are explicit in the submitted wire and
saved code; the provider returns bare names, so selected mount versions remain
unattested. Runtime hash checks fail closed on different bytes. No Kaggle RUN,
full model load or GPU execution was performed. Earlier code versions remain
Ready and preserved.

## First code asset (retained history)

Status: independently reviewed runtime code is uploaded and round-trip verified
as private `danielwuu/iris-arc-next-runtime/1`, Dataset ID 12441532. All 25 files
match their expected paths, sizes and SHA256 (580,466 actual file bytes).
Manifest SHA256: `5294f89b95d51c0003dfd4b5da16e73050ed11ed3d8456ded912ef3927343605`.
The code Dataset binds source commit `1a996dce0bdb08a3002cba69527dadb72a37bba9`.
Its provider totalBytes field reports 569,115; exact file listing/download sums
580,466. Both are retained without rewriting provider evidence.

Real model/wheel physical closure and private bulk Dataset uploads are still
being prepared separately in the owner's Linux WSL environment. No offline
notebook version 2 has been published; original version 1 remains preserved.
See research/arc-next-line/offline-code-dataset-v1/ for the completed code asset.

## Layout

- Model Dataset root: official Granite model files, LICENSE and
  irisx-model-material.json. Exact upstream bytes: 17,593,020,491.
- Wheels Dataset root: wheels/*.whl, requirements.lock, wheel-lock.json,
  source provenance and license/notice inventory. Actual size is recorded after
  native Linux CPython 3.12 resolution, never estimated as a completion fact.
- Code Dataset root: runtime/tools and runtime/research allowlists,
  training/ demonstration-only data, training/evaluator/ answer file,
  licenses/ARC-AGI-2-LICENSE.txt, NOTICE.txt and bundle-manifest.json.

The model and wheel Datasets are reused unchanged across code iterations.
Code updates create a new Dataset version and a new explicit notebook binding.
Mount discovery is owner-qualified or exact slug-only fallback; no globbing for
an arbitrary matching model, dependency or code directory.

## Reproducibility

Use tools/stage_arc_next_offline.py to stage a committed runtime payload and
an inert notebook bound to actual published Dataset versions/hashes. Staging
has no upload or execution side effect. The original first-notebook builder and
published bytes are preserved.

Runtime sequence, each separately manual: input checks; isolated offline
install; CPU import/tokenizer/safetensor checks; G4 smoke2; explicitly opted-in
pilot16/pilot128; A/B/C; stopped-output development scoring; evidence export.
No phase automatically launches the next one.

CPU-only checks do not establish Blackwell kernel compatibility, LoRA training
success or accuracy. Four-L4 deployment remains a distinct unexecuted gate.

## CPU validation

Independent runtime review passed 134 CPU tests with one explicit optional
Jinja2-unavailable skip, plus three adversarial tests. It verified fail-closed
inputs, immutable writable source, isolated interpreter/receipt binding,
subprocess/spawn network guard and evaluator isolation. Actual real CUDA
wheel closure and full model/GPU loading are not established by these tests.

The required full repository aggregate remains a historical FAIL: 1,474 tests,
35 missing retained-fixture errors, one native-export fixture failure, 60 skips
in its recorded run. Those historical fixtures were not synthesized or hidden.

Fresh source-only offlinev2 publication transport is independently reviewed
with 76 focused socket-blocked tests. It does not reuse the consumed v1 journal.
It retains safe HTTP header/body bindings, requires three real ready/private
Dataset receipt sets, performs a fresh exact-v1 SOURCE check, and permits one
QUICK_SAVE request for expected version 2. A final actual-wire review is still
blocked on real model/wheel Dataset closure. No ready attestation or publication
reservation has been fabricated.

## Material closure blocker diagnosed

The independently hash-verified original Granite source files fail the index
consistency gate. Public-header audit independently confirms the defect:
241/363 shard assignments disagree, without missing or duplicate tensor names.
The payload total must be 17,583,185,920 bytes. A strict provenance-preserving
derived-index artifact is under implementation; source weights remain frozen.
Code Dataset v1 remains immutable. The next code Dataset version will add the
explicit narrow v2 material contract, rather than silently bypassing validation.

The strict repair implementation passed independent review: 35 focused tests
and 25 independent controls, including recomputation from real public header
prefixes with production constants. Expected derived model manifest is 3,488
bytes with SHA256 cd845822cd2c0ca749dd3e6f580f51e68b91c0e5c5886fe239fc3c14f5bb0b99.
This is a metadata prediction, not a claim that cloud weights were downloaded
or production material has already passed local repair. The separately reviewed
code update is ready to publish; actual local verification remains pending.

## Repair helper delivery

Private code Dataset `danielwuu/iris-arc-next-runtime/2` is ready and exact-version
round-trip verified: 26 files, 597,964 bytes; bundle manifest SHA256
914de50d8bc963be00cba7e252dc232ec4e6dd4d998f77d700521d6534b15858.
It binds source commit6990c2e023560fe901e49a79e56f5a2808810ad0 and preserves
code Dataset v1. Use a fresh interpreter for the v2 source; do not mix cached
imports from different runtime versions. The isolated dependency environment
can be reused because the environment helper/guard and original source lock
are unchanged. Actual production repair and model/wheel Dataset publications
remain separate pending gates; no notebook version2 save or GPU run occurred.

## Vendored wheel metadata parser repair

The real setuptools84.0.0 wheel legitimately contains one root distribution
METADATA and twelve nested vendored distribution METADATA files. The previous
parser counted every nested file as a competing wheel identity and rejected
this valid official wheel. The official 818,216-byte wheel's SHA256 matches
PyPI:51a52592b3b99e102b609654876bd65f19f999935166d1352678931132b0c670.

Both parsers now require exactly one root-level dist-info/METADATA, with
matching root-directory, filename, Name and Version identities. All archive
members still undergo traversal/symlink/duplicate checks. Nested vendor files
remain unchanged. Source hashes, ABI checks and complete dependency-closure
resolution are not weakened. The invalid old tiny.whl synthetic positive
fixture was corrected to a valid matching wheel identity.

Independent review passed the real official wheel and 44 adversarial probes;
41 focused tests pass. Code Dataset v3 will deliver this parser-only repair.
The Granite derived-index and model-manifest hash expectations are unchanged.

## Latest validation and delivery

Code Dataset v3 is private, Ready and round-trip verified, with all 26 members
matching their hashes, sizes and paths. It binds commit
94135a858fb650bb0bc7c299ea582184983509ad. The source-side next-line suite
passes 196 tests with one documented optional Jinja2 skip. The last required
full retained-repository aggregate still fails on the same historical fixtures:
1,536 tests, 35 errors, one native-export failure and 71 skips; no fixture was
synthesized. The source-only offlinev2 transport remains reviewed but unused,
pending real model/wheel Dataset receipts and final actual-wire review.

The final aggregate was rerun after the root-metadata fix; every error/failure
identity exactly matches the preceding aggregate. No new failing test was
introduced by that parser repair.

## Model Dataset v1 transport layout blocker

Private model Dataset `danielwuu/iris-arc-granite42-8b-offline/1` exists as ID
12442718 and provider Ready, with 19 files totaling 17,593,054,916 bytes.
Independent cloud file-list review found the three required provenance members
under irisx-model-provenance/provenance/ instead of provenance/. Core file
paths/sizes match, but this mount must remain runtime_ready=false; the unchanged
v2 material validator rejects missing canonical provenance. No model weights
were downloaded or modified by the cloud reviewer. The existing local uploader
owns a fresh corrected Dataset version, preserving v1 and checking supported
reuse/retention before any repeated large upload.

## Model v2 complete; isolated child startup repair

The current authorized local task reports private Ready model Dataset
`danielwuu/iris-arc-granite42-8b-offline/2`, ID 12442718: all 19 canonical
members, 17,593,054,916 bytes, complete download/hash readback PASS. The exact
derived manifest remains cd845822cd2c0ca749dd3e6f580f51e68b91c0e5c5886fe239fc3c14f5bb0b99.
Cloud independently reviewed provider metadata, all paths/sizes and nine small
provenance/config/license files; it did not download model weights. The local
task report and its receipt/inventory digests are retained separately in
research/arc-next-line/offline-local-model-v2-checkpoint.json.

All 52 official-hash wheels (3,959,690,542 bytes) passed actual isolated Linux
offline installation, dependency checks, installed versions and post-install
input rehash. CPU imports, full native tokenizer/template, CPU matmul and
safetensor headers passed. Plain-child guard failed because Ubuntu's standard
library sitecustomize wins over the venv module; the local test correctly
stopped before unguarded DNS. Spawn remains unverified in that receipt.

The minimal v4 fix adds an exact-path early .pth bootstrap inside only this
isolated venv, with bound bytes and an explicit migration of the existing
installation. It does not reinstall packages or modify OS/network settings.
Local plain/spawn acceptance must pass after migration before wheels upload.
Full model loading remains untested due available RAM; no GPU was executed.

The v4 implementation passed 179 active next-line tests (one optional Jinja2
skip), all 47 environment tests, and 21 source-only transport tests with the
official SDK. Independent probes verify stdlib/custom-module precedence,
plain/spawn descendants, optimized-mode guard tamper abort, strict migration
preconditions and fail-closed interrupted writes. Migration preserves both
original receipts verbatim and changes only the early hook and two receipts.
These are cloud CPU fixtures; actual Ubuntu installation acceptance must still
be repeated by the local task before publishing the wheels.

## Verified v4 helper delivery

Private code Dataset v4 binds commit b9470a1c93fd80d6a337adcff110d577ab6c0c14.
All 26 files were downloaded from the exact version and reverified against the
closed manifest. Provider privacy, Ready state and retention of v1–v3 were
checked. The same Library helper identity was replaced as Library version 2
(163,483-byte ZIP), retaining prior versions. The local worker receives the
exact Dataset reference and hash, verifies before import, and migrates the
existing isolated environment with its actual legacy receipt digest.

The post-v4 required full repository check ran 1,547 tests and retained the
exact same 35 historical fixture errors, one native-export failure and 71 skips.
No new failure identity was introduced, and no fixture was fabricated or hidden.
See research/arc-next-line/offline-final-cpu-validation.json for both passed
active checks and this explicit aggregate FAIL.

## Owner-confirmed existing competition attachment

A live predecessor check observed one added ARC-AGI-3 competition association
while every original v1 SOURCE byte remained unchanged. It correctly stopped
before reservation or SaveKernel. All blocked preparation/readback evidence is
retained. At 12:13 UTC the owner confirmed that this was their attachment and
explicitly directed preservation (Decision 0068).

A new reviewed journal requires exactly that list in both live predecessor and
successor, plus the same three private Dataset versions. Original frozen v1
evidence still has an empty competition list; no evidence is rewritten. The
request now includes the preserved association explicitly. The ARC-AGI-2 runtime
does not read competition files. No GPU/paid RUN or broader input is authorized.
All switches remain False; publication remains pending exact accepted readback.

## Accepted offline notebook v2

The one reviewed QUICK_SAVE returned kernel 137630087/version 2. It explicitly
preserves only the owner's existing ARC3 association alongside private code/4,
Granite/2 and wheels/1; all switches remain False and GPU/TPU/Internet are OFF.
Every cell's exact text, remaining notebook fields and source-embedded numeric
pins match after the standard nbformat list-to-string normalization. Both the
submitted and provider-returned source are preserved. No runtime was requested.

The original strict verifier expected numerical Dataset refs in GetKernel and
therefore remains accepted-source-unverified. The provider instead returns a
sorted exact set of the three bare names. A separate independent read-only audit
records source-content verification without claiming provider-selected mount
versions. The submitted numerical pins, full published-asset readbacks and
fail-closed runtime byte checks remain bound. This explicit API observability
limit was accepted; no second save or hidden API was attempted.

The final focused official-SDK/runtime suite passed 47 tests. The required full
repository aggregate ran 1,553 tests: the same 35 historical fixture errors and
one native-export failure remain, with 74 skips. No historical fixtures were
fabricated and no workflow was weakened. Full-model/G4/four-L4 qualification
remains a future manual gate. Complete this main integration, then pause.
