# E12 RUN 002 admission

Decision 0062 permits one automatic private, offline, USD 0 RUN under
`stage4-e12-probe-prefix-20261007-002`, targeting notebook 137327571 version 10.
The separate original INERT001 packet stays immutable and verifies with its own
frozen source bytes. Its plan SHA-256 is
`f8000ab7db2a40795e93ff7482ad17ffa7fc817057207da7a9aadd6266739349`.
The identical fixture under `tests/fixtures/e12/` is historical public-input plan
data, never execution authority or native-runtime evidence.

The default staging path remains INERT. `construct` accepts explicit
`resource_snapshot`, `authorization_ref` and `quota_policy` keyword arguments
for RUN. The snapshot is the exact `normalize_quota` projection, retaining the
primary and typed response hashes, account, observation/refresh times and actual
used/reserved/total/remaining seconds. Its permission field remains false. The
publisher must reconcile original provider responses, require no conflicting
reservation, keep paid scaling off, and check freshness within 900 seconds at
submission. The factor-one quota conversion is explicitly a conservative planning assumption,
not an independently verified provider conversion. Default conservative admission
still needs 14,400 quota seconds.
Only `owner-positive-free-quota-waiver-v1` and the exact owner message reference
allow a smaller, strictly positive free quota. No workload is shortened.

The scientific workload remains four selected public-dev tasks, independent
64/128-update arms, 768 total updates, 12 tests, four L4 devices, and 120/150
seconds per test. Native model/dependency material pins, the 3,600-second global
limit and all process-cleanup guards remain unchanged. A provider rejection or
termination is a possible outcome; neither admission nor the planning budget
report guarantees completion or establishes feasibility.

Automatic startup writes `e12-agent-run-start.json` with actual session clocks
and exact plan/source/admission bindings. It explicitly disclaims owner-edited
configuration, an owner four-hour declaration, current offline-runtime quota,
and startup hardware attestation. Hardware is checked separately before model
work. Offline runtime validates submission-time quota as historical evidence;
it does not invent a fresh provider read after time spent queued.

The entry point requires the independently supplied plan SHA-256, propagated from
the literal notebook pin to the coordinator and each worker. It validates bounded
canonical plan copies, every source/material
payload digest and the execution receipt before importing runtime modules.
Admission failures after unpacking enter bounded prelaunch diagnostics. A
complete runtime archive requires its honest start receipt; diagnostic-only
archives can record missing/rejected admission without claiming completion.
The output store binds its admitted plan, challenges and unique run identity.

CPU validation: `python -m unittest tests.test_nvarc_e12_run_admission -v`.
The tests use synthetic quota observations solely to exercise closed admission,
real rendered notebook branches, pre-import failures and output/archive gates.
They make no provider, installation, model, OAuth or GPU calls.
