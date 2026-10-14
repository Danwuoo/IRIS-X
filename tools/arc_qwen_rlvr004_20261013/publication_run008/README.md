# Run008 native publication and exact-result transport

Decision0075 governs this new, separately reviewed native operator. Historical
run005/006/007 files, published versions, claims, clocks and physical charges are
unchanged. This directory provides a finite publication route and a separate
terminal monitor/collector. Local tests are not provider, GPU or scientific proof.

## Existing authentication boundary

`launch.py` derives the existing sibling `kaggle_setup/kaggle.sh` from the
repository location, checks its exact reviewed SHA-256, and execs only its
existing `venv/bin/python` with `-I -B`. It uses exactly the same existing
wrapper-owned HOME and KAGGLE_CONFIG_DIR; it never changes the wrapper, selects
a foreign store or accepts an arbitrary program. Explicit absolute operational
paths belong in the ignored, independently reviewed local config, not Git.

The official Kaggle API owns OAuth loading, token handling and normal renewal.
The adapter never inspects a token field, exports a token, creates an OAuth
grant or alters access. Existing credential files are checked through filesystem
metadata only. Legacy/API-token alternatives and unexpected auth/import
environment variables are rejected. The SDK package versions and complete
Python-source closure are pinned by `sdk-lock.json`. A narrow source-only loader
compiles these authenticated bytes directly, never a cached SDK bytecode file.

Before official authentication starts, every SDK client is bounded to an exact
HTTPS api.kaggle.com service/operation allowlist. Metadata has a16MiB streaming
cap,120-second total wall limit,15/90-second connect/read timeouts, disabled
redirects, and no implicit HTTP retry. The only auth mutation is the official
existing-credential refresh. It requires a durable one-attempt intent keyed by
old nonsecret expiration. Unknown refresh outcome stops; accepted renewal must
have finite expiration more than300 seconds ahead. The pinned SDK's late-expiry
predicate is wrapped to refresh five minutes early. Resource mutation counters
survive renewed official clients. No credentials are copied into adapter state.

## Pinned authentication lookup audit

This audit covers the exact Kaggle2.2.4 / kagglesdk0.1.37 sources in the lock:

- `kagglesdk/kaggle_env.py`: notebook token path from KAGGLE_KERNEL_RUN_TYPE,
  KAGGLE_DATA_PROXY_URL and KAGGLE_API_V1_TOKEN; KAGGLE_API_TOKEN as either a
  value or file path; HOME/.kaggle/access_token and access_token.txt; environment
  endpoint selection through KAGGLE_API_ENVIRONMENT.
- `kagglesdk/kaggle_http_client.py`: HOME/.kaggle/kaggle.json legacy credentials,
  and KAGGLE_IAP_TOKEN for nonproduction environments.
- `kaggle/api/kaggle_api_extended.py`: KAGGLE_CONFIG_DIR, otherwise HOME/.kaggle
  then Linux XDG_CONFIG_HOME/.config fallback; kaggle.json; every KAGGLE_* variable
  can enter API configuration, including USERNAME, KEY and TOKEN. VERBOSE and
  VERBOSE_OUTPUT can enable debug request logging.
- `kagglesdk/kaggle_creds.py`: official OAuth loads and saves the default
  HOME/.kaggle/credentials.json. The adapter never supplies another file path.

The reviewed execution entry is `launch.py`, whose closed environment allowlist
removes all inherited KAGGLE_* variables, XDG and verbose switches, then adds only
exact KAGGLE_CONFIG_DIR and HOME from the unchanged wrapper. It also excludes
Python path overrides and executes isolated Python. The metadata guard rejects
all three alternate local credential files before importing the official API.
The exact nonempty existing CONFIG_DIR makes HOME/XDG config fallback unreachable.
The sole permitted credential body is handled inside official OAuth methods.
Direct invocation with an arbitrary ambient environment is not a supported
provider entry; direct script help/local validation remains nonauthenticating.
The regression test covers every named alternate environment path above using
synthetic values, without opening an actual credential file.

## Existing native TLS and proxy configuration

The initial native readiness attempt failed TLS certificate verification before
any Dataset/notebook mutation or dispatch epoch. The launcher had retained
SSL_CERT_FILE while dropping REQUESTS_CA_BUNDLE. Requests uses its own bundle
selector, so preserving SSL_CERT_FILE alone did not reproduce the already
working official wrapper's transport environment. The failed readiness evidence
is retained privately; it is not success evidence.

The narrow launcher correction retains the existing REQUESTS_CA_BUNDLE selector
only after checking its canonical regular-file path, bounded bytes and the exact
SHA-256 of the bundle already trusted by this runtime. No certificate is added,
installed, edited or transmitted, no hostname is changed, and TLS verification
is never disabled. The existing SSL_CERT_FILE/SSL_CERT_DIR selectors remain
inherited unchanged. When no Requests selector is present, default certificate
verification remains True; no new bundle is guessed.

The complete Requests environment audit covers REQUESTS_CA_BUNDLE with its
CURL_CA_BUNDLE fallback and upper/lowercase HTTP_PROXY, HTTPS_PROXY, ALL_PROXY and
NO_PROXY. The current established Requests selector takes priority; the launcher
preserves that selector and the existing proxy/no-proxy settings, while excluding
CURL_CA_BUNDLE and arbitrary client-cert or verification-disable switches. It
does not reinterpret SSL_CERT_FILE as another Requests trust source. Authentication,
Python-import and verbose settings remain closed as described above.

Offline regression tests exercise actual Requests environment merging and all
four send paths (SDK, upload, download and metadata-only download) with mocked
HTTP sends. Every path receives the exact existing CA file as verify; malformed,
false-like, missing, linked or changed bundle paths fail before provider creation.
The supported interface has no verify=False option, and a source regression
forbids adding that override. Existing proxy and NO_PROXY behavior is covered.
Runtime, common transport, collector, candidate and consumer bytes are unchanged
by this launcher-only production correction.

## Independently reviewed contracts

Native config format: `irisx/run008-native-operator-config-v1`. It retains the
run007 explicit repository/candidate/scratch/state/evidence/stop paths, username,
publication-manifest SHA, five actual numeric versions, and remote-predecessor
fields. Replace the old `credential` object with:

```json
{"native_wrapper":{"path":"<repository-parent>/kaggle_setup/kaggle.sh","sha256":"46134808e2705d45d70bdc9aadd26a1e1863628d3d045a32a507efa56616b4bc"}}
```

State must be `<scratch>/state-run008` and evidence `<scratch>/evidence-run008`.
The original observed predecessor snapshot hash must equal the new manifest's
current-predecessor descriptor. Code/notebook successors are derived from real
current numeric versions. No default/latest output version exists.

Publication format is `irisx/qwen14b-rlvr-run008-publication-contract-v1`.
Dataset/notebook/JIT/terminal/consumer/material schemas retain the original
reviewed safeguards and unchanged historical proof validators. The current
owner scope is a distinct `irisx/run008-native-owner-direction-v1` document.
The current notebook and dataset bracket is independently hash-bound and must
show the exact private targets and terminal predecessor; plain ERROR never
implies GPU unavailability, safe closure or a score.

Transport review includes exact hashes for config.py, native_auth.py,
sdk-lock.json, operator_common.py, rl_transport.py, rl_collect.py and launch.py,
plus manifest/material/config and the admitted action list. Synthetic receipts
cannot admit execution. Every mutation additionally requires the reviewed Git
commit, independently verified remote publication, and exact committed local
operator bytes. Monitoring has a separate consumer review and closed helper
inventory bound to the actual collector hash.

## Finite operator sequence

The parent remains the sole publisher. Each invocation accepts the same explicit
`--manifest`, `--manifest-sha`, `--material`, `--material-sha`, `--review`,
`--review-sha`, `--local-config`, `--local-config-sha` arguments. Use
`python -B launch.py publish --help` or `collect --help` for the complete flags.
Help and local `validate` do not create a Provider.

1. `validate`, then `readiness`: verify all source/material/owner/review contracts
   and the actual terminal predecessor bracket. No version is guessed.
2. `update-code`: reserve one durable claim, initialize one upload, perform one
   bounded official-origin PUT, recheck the predecessor, and request one private
   Dataset successor with delete_old_versions=False. Each intent is fsynced before
   sending. A failure never silently repeats any mutation.
3. `verify-code` (or exact numeric `verify-code-files`): reconcile any uncertain
   Dataset write through the expected numeric successor, closed archive/file set,
   full byte hashes and historical retention checks. Run the separately reviewed
   no-model numeric-mount acceptance tool against that real receipt.
4. `save-inactive`, then `verify-inactive`: one private QUICK_SAVE; verify exact
   normalized notebook source, settings and Dataset identities. GPU/TPU/Internet
   remain off. Numeric Dataset byte verification remains a separate proof.
5. Obtain the persisted-readback audit and independent monitor/consumer review.
   `prepare-active` verifies those gates, samples the fresh predispatch epoch,
   writes the four exact JIT outputs plus wire, and returns for independent exact
   active-wire review. It makes no SaveKernel call.
6. `activate` requires `--active-review` and `--active-review-sha`. The review's
   `irisx/run008-active-wire-review-v1` object must be PASS, nonsynthetic, and
   match publication/material/transport/config hashes, exact wire/finalization/
   source/prepared-journal hashes, epoch and numeric notebook version. The same
   bytes are dispatched once within60 seconds, rechecked after final readiness.
   A stale preparation is preserved and never resampled/reused automatically.
7. `verify-run` is read-only reconciliation after a failed/uncertain send or
   readback. One durable initial-read intent references the original launch
   claim; interrupted read recovery does not create another RUN or reset clocks.
8. `collect poll`, `collect collect`, or `collect watch` monitors the admitted
   numeric run to terminal and retrieves only the selected source-bound outputs.
   Transient reads back off; access denial, explicit GPU unavailability,
   or invalid evidence yields an honest blocker. Missing/indexing-pending
   selected outputs continue with backoff without an arbitrary polling cutoff. No collector action can publish or relaunch.

All roles share the same publisher lock. Actual GPU-unavailable/zero-hours
reports latch the stop file and forbid later dispatch; no quota query exists.
Keep the existing model, seven non-code Dataset pins, Docker, NvidiaRtxPro6000,
ARC3 metadata association, Internet-off runtime, and absolute43200-second
session/42000 execution/42180 outer/42300 provider limits. PUBLIC120 remains
120 tasks/167 queries with the original evaluator and data/process gates.
Provider COMPLETE, safe runtime completion, complete valid scoring and efficacy
remain distinct claims. Raw outputs, archives, logs, evaluator bodies and local
operational receipts stay ignored and never enter the public repository.

## Offline checks

Use the existing venv interpreter without activating authentication:

```sh
python_path="$(dirname "$PWD")/kaggle_setup/venv/bin/python"
"$python_path" -I -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_run008/tests -v
"$python_path" -I -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/publication_run008/tests -v
python -B tools/arc_qwen_rlvr004_20261013/publication_run008/launch.py publish --help
python -B tools/arc_qwen_rlvr004_20261013/publication_run008/launch.py collect --help
```

Tests mock all provider/authentication operations. They exercise staged actual-
wire admission, source/version/settings rejection, stale-clock handling,
write uncertainty/read interruption, durable refresh uncertainty, client/counter
preservation, timeout and session cleanup, source-only imports, origin/operation
allowlists, zero mutation retries, partial downloads and GPU-stop classification.
The generic workspace Python may lack `requests`; use the already installed
pinned venv for transport tests. No test invokes a provider, model or scorer.
