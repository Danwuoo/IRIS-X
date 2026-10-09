# Runtime6 source integration and loading-receipt repair

This is an additive reconstruction on main `077bb4680706b95f196621dab4360ffe03504354`.
The exact fourteen runtime6 `runtime/tools/*.py` members are mapped to `tools/*.py`
in `source-import-manifest.json`. Three of those sources additionally contain the
reviewed repair from `4c7ad516b66ad2c6fc572d0ba1d625b2fcd59880`. The Dataset is a
deployment subset, not a recovered repository or replacement for research history.
The missing frozen commit, nine lost commits, and original Decisions 0069/0070
are not reconstructed. Existing research, original decisions, source locks and
readiness evidence remain unchanged.

Independent review of candidate `55a01cea4cbc342a69ce1ba1412b6ecb20cfefc2`
identified a legacy migration regression: current installer guard, launcher and
`-B` command identities had replaced the trusted pre-hook v3 expectations.
The main-only follow-up freezes the exact guard/launcher digests and `-I -S`
flags from main `077bb468`, and binds the migration hook to that verified legacy
guard. Migration still changes only the hook and two receipts; rehashed tampering
is rejected. Fixed historical fixtures are independent of current constants.
New installations and portable workflow admission retain current identities and
`-B`; legacy migration does not admit that environment to the portable workflow.
The source manifest attributes this follow-up separately from `4c7ad516` and
preserves the original runtime6 member hash. The prepared Dataset package,
original `4c7ad516` repair and all publication identities remain unchanged.

The worker failure was a `TypeError` while writing the model-loading receipt:
Transformers 5.8.1 reports missing/unexpected/mismatched keys as sets. The receipt
was written before LoRA construction. The repair normalizes only those known
loading-info fields to sorted lists after loader validation. Generic canonical
JSON still rejects sets. Worker/supervisor/workflow diagnostics retain the original
traceback, and the exact 128-update and confirmed cleanup gate remains enforced.
CPU reproduction does not establish full-model GPU loading or training success.

Runtime6 also contains changes already present in the deployed snapshot but absent
from fetched main: portable CPython 3.12 dispatch, structured host ABI diagnostics,
immutable interpreter handling, dispatcher-session worker ownership, and removal
of the program monetary-cap gate. These are distinguished from the new loading
repair in the source manifest. The cost field remains deprecated compatibility
input; workload/token/wall budgets, pilot opt-in, hardware gates, and manual
False-by-default execution remain separate. No compute execution is authorized by
this integration or by preflight acceptance.

The initial broader suite ran 227 tests: eight failures, zero errors, sixteen
skips. Six failures were the same three wrong-host subcases repeated by an
inherited test class: the tests expected old exact error strings instead of
`RuntimeCompatibilityError`. The revised assertions require the typed error,
the precise failed ABI predicate, incompatibility, zero network/install/GPU calls,
and rejection before dependency resolution. Wrong ABI is still rejected.

Two failures expected an enforced monetary ceiling in training/workflow preflight,
contrary to the existing runtime6 contract and the owner's cap-removal direction.
Only those expectations were updated. Tests now assert the optional estimate and
billing caveat, the explicit false enforcement flag, no provisioning/network/
upload/GPU success, inert disabled execution, and retained finite wall/integral
workload budget checks. CI thresholds and historical aggregate expectations are
unchanged. The initial failing receipt is preserved separately from the rerun.

Twelve new interpreter tests use a tiny synthetic archive and a non-runnable ELF
header. Only its archive hash/size constants are substituted. Tests exercise real
hash/source/target/host/path/member/relocation/private-permission/receipt checks,
cached-tree tampering, interruption and hardlinks. No interpreter, package manager,
shell or GPU execution is used. Native Linux temporary storage permits meaningful
POSIX permission tests without touching the accepted base interpreter or venv.

Kaggle publication was rejected twice by automatic approval review before process
start. Zero upload/publication requests were sent; no Dataset version or notebook
save receipt exists. The prepared successor source remains unpublished and includes
an unresolved runtime-version placeholder. Do not save that candidate. Existing
Notebook 137711693/version 1, runtime6/model2/wheels1/interpreter2, and all GPU,
TPU, Internet and manual switches remain as recovered. This integration makes no
claim of a new notebook, Dataset, provider-selected mount attestation, or GPU run.
