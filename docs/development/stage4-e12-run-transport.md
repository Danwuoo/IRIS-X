# Exact E12 run002 transport

`tools/publish_nvarc_e12_run.py` adds a single explicit private Kaggle run of
`stage4-e12-probe-prefix-20261007-002`. It preserves the distinct inert001 package.
It targets numeric notebook **137327571**, reference
`danielwuu/stage4-e10-probe-20261006-001`, current version **9**, expected new
version **10**. The plan's semantic `RUN` maps to the actual official SDK enum
`SAVE_AND_RUN_ALL`; there is no invented `RUN` wire enum.

The exact reviewed outbound includes `sessionTimeoutSeconds: 3600`,
`machineShape: NvidiaL4`, private true, Internet false, TPU false, competition
`arc-prize-2026-arc-agi-2`, dependency
`sorokin/pip-install-unsloth-flash-patch/2`, model
`sorokin/qwen3_4b_grids15_sft139/transformers/bfloat16/1`, and the retained Docker
image. Four actual L4 GPUs and selected dependency bytes remain runtime gates;
a request or accepted receipt does not establish physical execution.

## Offline preparation and independent review

Use the official installed Kaggle SDK interpreter. `prepare` performs no
credential discovery or external IO. It uses an explicit noncredential sentinel
and intercepts the actual SDK-generated `Session.send` request, checks its closed
JSON schema including inner notebook bytes against an independently constructed
wire dictionary, and stops before sending. Duplicate JSON keys fail closed.

```
python tools/publish_nvarc_e12_run.py prepare \
  --package <immutable-run002-package> --journal <new-journal> \
  --previous-notebook <verified-original-v9-notebook.ipynb>
```

The result is the complete required independent-review binding. The reviewer
must inspect the final package, plan, exact notebook, retained
`prepared-request.body`, and controller source. Add only `verdict: PASS`,
`reviewer` and `reviewed_at` to that binding and save it as a separate review
JSON. Preparation is not an independent review or authorization. Changes to
package bytes, controller implementation, or actual prepared body invalidate it.

The recovered original v9 notebook is anchored by SHA-256
`959d75f9cc18aef6c7944c31831f981839473aa817cd11445536f9e3f999d74f`.
The executable digest uses `stage4_provider_evidence.execution_source_digest`:
ordered code-cell strings, joined source fragments, canonical JSON of
`{"nbformat":4,"ordered_code_cells":[...]}`, sorted compact keys, UTF-8,
non-ASCII preserved, followed by **one LF**, then SHA-256. That LF belongs to
`stage4_execution_ledger.canonical`. The matching v9 digest is
`57ef0e27de6fe0b157cbf24c59cd716952da64fef2283cc9f41f206607a4394f`.
A notebook file hash, executable digest, and a no-LF JSON hash are distinct.

## Actual resource evidence and one publication

Only explicit provider commands import the official CLI and use its ordinary
stored authentication. The controller verifies the authenticated owner is
`danielwuu`; it does not extract or retain token values. Keep the platform's
proxy and CA environment intact.

```
python tools/publish_nvarc_e12_run.py observe-quota --output <new-quota.raw.json>
python tools/publish_nvarc_e12_run.py publish \
  --package <immutable-run002-package> --journal <journal> --review <independent-review.json>
```

Quota observation retains exact bounded primary response bytes and the typed
SDK duration projection, independently reconciles total/used/reserved, and
retains the normalized snapshot. The normalized snapshot is not itself a
permission grant. No `.to_dict()` duration serialization is used. The runtime
package binds a reviewed snapshot and the exact owner authorization reference;
it labels that observation historical at offline runtime rather than pretending
to refresh quota or declare four free hours.

Immediately before mutation the publisher reads current version/source/settings
and fresh quota. Actual remaining free seconds must be positive, reserved seconds
zero, pay-to-scale disabled, and the 900-second freshness/current-window checks
must pass again at actual send. Below 14,400 seconds is admitted only under the
exact explicit owner quota waiver; no paid quota or other guard is waived.

The current-source metadata comparison admits only two exact, recorded provider
read representations from
`research/stage4-continuation/HISTORICAL-CURRENT-cb5ea253.json`:

- The dependency read may omit the terminal `/2` from this exact owner/slug.
- The exact model framework may be `Transformers` rather than `transformers`.

All other identity, source, version, privacy, accelerator, Docker and mount fields
remain exact. Outgoing pinned strings are unchanged. This does not establish a
provider dependency-version echo or actual mount contents; selected-byte equality
remains a fail-closed check before installation/native runtime.

A repository-wide exclusive reservation survives crashes and blocks reusing this
identity with another journal. The journal reserves the mutation before send,
records `sends=1` durably before HTTP, rejects retry/redirect/second requests, and
retains bounded raw receipt bytes atomically before parsing. Strong acceptance
requires matching ref (only exact owner/slug or documented `/code/owner/slug`), URL, numeric kernel ID and new version10 in the original
receipt, with no error or invalid sources, and typed SDK agreement. A timeout,
interrupt, rejection, malformed receipt or ambiguous response freezes the
identity. Never delete a claim or repeat a send to resolve uncertainty.

## Terminal observation and exact output

```
python tools/publish_nvarc_e12_run.py status --package <package> --journal <journal>
python tools/publish_nvarc_e12_run.py retrieve --package <package> --journal <journal>
python tools/publish_nvarc_e12_run.py terminal-logs --package <package> --journal <journal>
```

Status uses the supported current-status request, bracketed by current source,
version and settings reads. The status endpoint does not echo a version; no
unsupported numeric status variant is tried. Observations are at least60 seconds
apart, with at most180 reserved checks per journal. The caller owns active
waiting and must surface a real observation blocker rather than infer terminal
state or claim completion. QUEUED's zero-valued SDK enum is read from the typed
response. COMPLETE, ERROR and CANCEL_ACKNOWLEDGED permit terminal retrieval.

Retrieval reserves exactly one request for the exact filename
`stage4-e12-probe-prefix-20261007-002-delivery.zip` using the SDK's explicit
`version_number=10`. It neither lists arbitrary files nor downloads model weights.
Only one official Kaggle output redirect is allowed, then a separate anonymous
session streams at most261 MiB for at most900 seconds. No signed URL or headers
are logged; no API credentials are forwarded. Before/after source/version guards
and the offline delivery verifier bind the downloaded envelope to the exact run
and plan. The observed output script-version path is retained as an observation,
not invented independent identity proof. A failed/partial retrieval is preserved
without repeat. A separate, once-only `terminal-logs` command retains up to8 MiB
of original provider log text using one bounded current-output request bracketed
by exact source/version reads. It retains a primary-response hash and discards
file URLs; no pagination, files, or replacement run follow. It is available when
a quota kill or startup failure leaves no delivery ZIP. A verified envelope can still describe failed or partial runtime;
it does not establish candidate correctness, quality or official submission.

## Offline validation

`python -m unittest tests.test_nvarc_e12_run_transport` runs deterministic provider
doubles for reservation, raw receipt, exact identity, closed wire and failure
handling. When the official SDK is installed it also checks genuine prepared
serialization with network access forbidden. Neither tests nor ordinary import
perform provider or credential IO. Run repository aggregate validation before
handoff; passing these controller tests alone is not native GPU verification.
