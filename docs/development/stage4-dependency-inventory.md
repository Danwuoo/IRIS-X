# Stage 4 dependency inventory: inert auth-checkpoint package

Identity: `stage4-dependency-inventory-api-001`. This is a new CPU-only,
stdlib-only local evidence identity, separate from every GPU probe. Preparation
does not authorize authentication, provider calls, output downloads, uploads,
Dataset changes, notebook saves/runs or dependency execution. Paid cost is USD 0.

## Why no dependency-mounted notebook is supplied

The retained launch-gate review found an unversioned
`sorokin/pip-install-unsloth-flash-patch` source attachment and selected source
hash checks, not an exhaustive startup/native inventory. Its historical identity
is Version 2 / script-version 272622465. Those historical bytes are not evidence
of the current provider output version or actual current mount. Native binary
hashes/build provenance remain unknown.

The reviewed earlier renderer discovered a path already present on the notebook parent's
`sys.path`, then placed it in a child `PYTHONPATH`. Later coordinator-child repairs
remove that dependency startup path, but do not attest the platform parent's earlier
startup. Attaching `kernel_sources`
may affect interpreter startup before the first cell. No retained provider
evidence establishes a mount-only, no-startup-execution path. A later isolated
`python -I -S` child, or late `sys.path` clearing, cannot retroactively prove that
the parent executed no unknown startup code. Therefore this package contains no
notebook or dependency source attachment. The mount route fails closed.

Next action, after authentication is separately authorized and established:
read-only current identity/version, free quota and output-listing evidence.
No GPU, kernel save or bulk byte download is the next step.

## Staged read-only acquisition plan, not a transport implementation

The package includes no provider client, downloader, auth code, network IO or
external process launch. Its plan remains `approved: false`.

1. Metadata/listing stage only: at most 120 seconds, 128 listing pages, 132 total
   provider requests, 16 MiB identity response, and 16 MiB total listing response
   bytes. These are proposed ceilings, not authorization. Output-file byte
   download requests remain zero. Stop if complete pagination and a consistent
   current version cannot be established. Do not substitute a historical ID.
2. Independently review the normalized metadata against retained, redacted raw
   response bytes. Exact script-version identity must be established from actual
   provider evidence; the SDK metadata has no dedicated resolved dependency-ID
   field. If only the numbered version can be observed, retain it and stop at
   the missing-script-ID blocker instead of inventing the mapping.
3. Explicitly choose the minimum literal output paths needed for provenance,
   using that listing, including exact currently identified native binaries
   where needed. No glob selection or automatic whole-environment fetch.
   Prepare an inert exact path/size/request proposal with the command below.
4. Before byte-stage admission, measure destination free space. Require the
   exact proposed bytes plus a 5 GiB reserve and 80 MiB metadata/report headroom
   (with default limits). The proposal rejects insufficient space. `/tmp` had
   only approximately 4.87 GiB available in this environment and correctly fails
   that gate even for tiny selected files; use verified adequate storage.
5. The controller obtains authorization/admission for that exact path list,
   summed bytes and number of requests. Recheck current identity and free disk
   immediately before first bytes. One copy only, no archive downloads as a
   substitute for individually admitted files, no retries or automatic widening.
   A future transport must enforce exactly those admitted bounds, at most one
   redirect per file, and a finite 900-second whole-byte-stage deadline. No such
   transport has been implemented or run here.
6. For each admitted download, bind expected owner/slug/numbered version and the
   actual HTTPS `www.kaggleusercontent.com` path's script-version ID. Retain
   status 200, exact byte count and transfer SHA-256; never retain signed URLs,
   tokens or credentials in the artifact. A changed version/path/size or missing
   binding blocks. Reconcile the exact selected file set before local hashing.

The 65,536-file / 32 GiB parser limits are absolute inspector ceilings. They
grant no permission to fetch that volume. Byte-stage permission remains zero
until the exact smaller proposal is reviewed/admitted.

## Supported-field evidence from installed official client sources

Source-only inspection; neither `kaggle` nor `kagglesdk` was imported or run.
Installed distributions are Kaggle CLI 2.2.4 and kagglesdk 0.1.37. The controller
reports these were installed from official PyPI. No source download or provider
call occurred in this task.

SDK source, relative to the installed package:
`kagglesdk/kernels/types/kernels_api_service.py`, SHA-256
`a7dd65206e7fc27950385e7b163cda48a40766eb8ff7f89d7a334b9bfb151b5c`.

- Lines 589–684: `ApiGetKernelRequest` has `user_name`, `kernel_slug`, optional
  string `version_label`; response has `metadata` and `blob`.
- Lines 891–958: `ApiKernelBlob.source` is a string. A returned notebook can be
  parsed as data, never executed. If its Kaggle metadata includes `sourceId`,
  retain the actual value and its origin; do not assume current-mount semantics.
- Lines 960–1014 and 1200–1212: `ApiKernelMetadata.kernel_data_sources` is a
  list of strings. Lines 1258–1268 expose `current_version_number`. There is no
  dedicated dependency script-version-ID or resolved mount-ID field here.
- Lines 1395–1526: `ApiListKernelFilesRequest` has optional string `version_label`
  and paging fields; response supplies `files` and `next_page_token`. Individual
  listed records at 1341–1393 have `name`, `size`, `creation_date`.
- Lines 397–477: `ApiDownloadKernelOutputRequest` supports an individual
  relative `file_path` and an integer `version_number`.
- Lines 1965–2047 and 2175–2192: `ApiSaveKernelRequest.kernel_data_sources`
  accepts a list of strings; the field documentation gives owner/slug syntax,
  with no separate script-ID selector. This is save-field evidence only; no save
  is authorized or attempted by this inventory package.

CLI source: `kaggle/api/kaggle_api_extended.py`, SHA-256
`210e589ab1f7359ffb560aacfe1c003ac1bc844c366f4ff709bf3d13de4d5458`.

- Lines 8955–8991: `validate_kernel_string` explicitly accepts
  `owner/slug/version`. Lines 6399–6402 validate dependency-source strings and
  line 6442 forwards them unchanged. This proves client syntax acceptance,
  **not** provider selection semantics, exact script-ID pinning, mount-only
  startup behavior or that a saved response resolves that version.
- Lines 6501–6544: pull parses a version and appends it to `kernel_slug` in its
  request. No behavior of that server-side string was tested here.
- Lines 6618–6620: pulled metadata copies returned `kernel_data_sources` into
  `kernel_sources`; it does not add resolved dependency script IDs.
- **Lines 6215–6232:** `kernels_list_files` parses a version but never puts it
  in `ApiListKernelFilesRequest`. Do not rely on the CLI versioned-reference
  listing wrapper to establish version-specific listing identity. The lower
  level SDK exposes `version_label`, but interpreting and verifying its response
  is an authenticated read-only checkpoint, not an inferred guarantee.

## Artifact and local inspector

Build our deterministic, uncompressed, closed ZIP locally:

```sh
python -I -S tools/stage4_dependency_inventory.py --build-package .irisx/stage4-dependency-inventory-api-001/inventory-package.zip
```

Exactly four members: `inventory.py`, `inventory-plan.json`, `README.txt`,
`package-bindings.json`. Fixed ZIP timestamps, ordinary regular-file member
attributes, no links/directories/extra members. `package-bindings.json` binds
the other three exact member sizes/SHA-256s; the external package receipt binds
all four and the whole ZIP. It contains our code and plan only, no third-party
dependency bytes, installed SDK code, evaluator/competition/model data or secrets.
Minimum remote disclosure at this checkpoint: **no code or datasets uploaded**.

After separately authorized metadata acquisition, normalized listing JSON has
format `irisx/stage4-dependency-output-listing-v1`, `ref`, positive current
`version_number` and `script_version_id`, UTC `observed_utc`, true
`listing_complete`, positive `listing_pages`, two raw response SHA-256s and
ordered `files` containing only exact `path` / `bytes` pairs. Raw redacted
evidence filenames are `identity-response.json` and `listing-response.json`.
The controller, not this parser, verifies normalization and provider semantics.

Propose a literal selection offline (replace paths with actually listed paths):

```sh
python -I -S inventory.py --prepare-acquisition normalized-listing.json --root ADEQUATE_DESTINATION_DIRECTORY --evidence EVIDENCE --select qwen3.patch --select unsloth/models/qwen3.py --output NEW_UNAPPROVED_PROPOSAL.json
```

The proposal is not permission. Add actually identified current native paths
only after listing evidence supports them. No native filename is guessed here.

After exact byte-stage admission and acquisition, the normalized receipt has
format `irisx/stage4-dependency-output-receipt-v1`, fixed inventory `run_id`,
`provider: kaggle`, identity and evidence fields above, `provider_file_count`,
`scope` (`selected-provider-output-files` or `complete-provider-output-files`),
and ordered selected `files`. Each selected row has exact `path`, `bytes`,
`sha256`, `download_host`, `download_status`, `download_path_script_version_id`.
Control receipt/evidence/output paths stay outside the selected byte tree.

```sh
python -I -S inventory.py --root SELECTED_OUTPUT_BYTES --receipt receipt.json --evidence EVIDENCE --output NEW_REPORT.json
```

Use a trusted local controller/interpreter and an independent 900-second
supervisor with bounded kill cleanup. Never invoke this from a mounted-dependency
notebook parent or set a dependency `PYTHONPATH`. `-I -S` is a local child-startup
condition, not retroactive notebook-parent evidence. The CLI also arms a POSIX
wall timer. POSIX no-follow, directory-fd and interval-timer support is required;
other platforms fail rather than weaken checks.

Inspector ceilings: 900 seconds; 65,536 files and 65,536 directories; 2 GiB per
file; 32 GiB aggregate file bytes; 1,024 UTF-8 path bytes and 32 path components;
16 MiB receipt and each evidence file; 32 MiB report. No CLI option increases
them. Exceeded caps, unlisted files/empty directories, missing files, symlinks,
hardlinks, special files, device changes, metadata/size/digest changes, duplicate
JSON keys/paths, unsafe names and incomplete bindings fail. No successful report
is finalized on a failed inventory read. Existing outputs or partial attempts
cannot be overwritten/reused. Inputs must be immutable local acquisition copies;
metadata/read checks do not provide an atomic snapshot against arbitrary
concurrent writers.

Paths are exact NFC UTF-8 relative POSIX names. No absolute paths, dot/dot-dot,
empty components, backslashes, drive colons, control characters or credential/
solution filenames. Files are opaque bytes: Python/startup code is never imported,
patches never applied, models never loaded, native files never linked, and
archives never opened/extracted for member discovery. An archive's outer bytes
are hashed and its **member inventory remains unverified**. Dependency archive
member semantics are not inferred from ZIP filenames.

Reports explicitly distinguish selected-file count from complete provider
listing count; historical and observed identities; and byte-bound,
operator-normalized receipt evidence from provider-authenticated proof. Actual
current mount inventory, output-to-mount equivalence, import safety, full native
build provenance, license/redistribution closure and whole-stack certification
all remain false/unverified. The GPU launch permission gate is still open.

## Offline verification

```sh
python -I -S tests/test_stage4_dependency_inventory.py
```

Only tiny synthetic fixtures are used. Coverage includes inert startup/.pth/
Python/patch/native/archive bytes; exact stable hashes; selected/full scope;
identity/download/evidence binding; duplicate and unsafe names; file/single-byte/
total-byte/metadata/directory/output caps; insufficient/exact disk-reserve
boundaries; missing current script identity; explicit path selection; symlinks,
hardlinks/FIFOs; during-read mutation; isolated CLI startup with a synthetic
dependency `PYTHONPATH`; nonisolated rejection; wall interruption; no final report
on failed reads; and deterministic closed-package member pins. These are narrow
scanner tests, not execution approval or a broad security certification.
