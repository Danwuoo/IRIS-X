# Reviewed public source checkpoint

This bounded checkpoint preserves an independently complete subset of reviewed
implementation and local validation, not a new experiment, deployment or
model-effectiveness claim. It is based directly on public source commit
`0ad791775545cf95a8f74f7f2cfde2aa4acda9db`, without importing private integration
history. No provider operation, notebook update or watcher restart follows;
further external execution requires a new owner direction.

Operational deployment identities, private provider links/receipts and
run/source-transport/output-specific hashes are retained privately. Raw
training/protected grids, weights, private outputs and per-case feedback are not
part of this source checkpoint. Existing functional provenance checks remain
unchanged.

## Included routes and their limits

- The existing dual-specialist NVARC route gains a save-only manual-start
  envelope with a process-birth session clock and exclusive start receipt.
  Draft creation performs no provider call or model execution. This delivery
  mechanism is not proof of hardware admission or model effectiveness.
- Separate CPU-only capacity controls provide function-preserving depth and
  FFN-width initialization plus tiny routing controls. Their depth-training
  bridge admits at most one million parameters and has no production loader,
  GPU admission or official-weight training/export route. Local mechanism
  verification is not evidence of useful learned capacity.
- Transactional TTT, batched transformed views and the ordinary dual-specialist
  NVARC route already existed in the public base and are not duplicated here.

The notebook-title correction and its package-test amendment are retained only
in the private recovery deliverable. The public package implementation and its
package tests remain byte-identical to the public base; the manual-start clock
and CPU capacity controls do not depend on that correction.

The complete train-only diagnostic and exact-control routes, including their
future-source private-evidence auditability fixes, are retained in the private
recovery deliverable pending separation of private configuration from public
source. Their new modules, tests and route-specific documentation are not
included in this public subset. Their integrity gates have not been weakened or
removed from the complete private implementation.

The unqualified opt-in inference-context prototype is also excluded. Its longer
context path has not established real-model CUDA memory, timing or accuracy
readiness; this checkpoint does not activate it or change the central runner.

## Source provenance

The included implementation and tests retain their reviewed bytes:

- NVARC manual-start clock: `fbec03515a32cc1a91fd3d7268f7385df7af4e02`.
- CPU capacity controls: `8bae0c6101b98a8408b871c1d333ddba0ab74df2`.
- CPU depth-training bridge: `9a552548ee9131d2e64370a913c3ac8365be066b`.

Technical documentation has been sanitized independently of these source bytes.
Historical local test qualifications are retained as historical evidence, not
promoted into production or benchmark claims.

## Validation scope

Validation uses the actual public subset with offline flags, a fixed Python
hash seed and workspace-backed scratch. The minimal Linux public lane and the
optional-ML numerical lane are distinct: dependency or environment skips never
count as numerical proof. Full retained-evidence acceptance, native Windows
execution and real GPU validation are not established by these lanes.

On Linux with Python 3.12.14, this public subset passed:

- The complete minimal `tools/repository_check.py --public` lane: 2,026 tests,
  1,761 passed and 265 explicit/optional skips, plus validator self-tests and
  repository invariants. This minimal environment is not an ML numerical pass.
- All 89 focused capacity, depth-training, manual-envelope, package, compact
  engine and experiment regressions in the ML environment, both normally and
  under optimized Python, with no skips.
- Source-preservation and disclosure scans: all seven changed/new Python files
  match their reviewed implementation bytes; the excluded private bindings and
  diagnostic/exact-control dependency closure are absent from this subset.

The local numerical environment uses CPU PyTorch 2.8.0, Transformers 5.8.1 and
PEFT 0.21.0. These checks are not a substitute for production CUDA execution,
model effectiveness, or the separate Python and Windows CI matrix.
