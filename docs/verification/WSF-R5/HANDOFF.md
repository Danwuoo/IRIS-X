# WSF-R5 developer handoff

State: **review_ready**; independent re-verification remains pending.
Same branch `fix/workstream-review-r1-r4-20261014`, same Draft PR9, same base
`refactor/workstream-pr4-arc-boundary` at `c514e9d5b3c438b70c90824ec1fd2796aa840740`.
Starting reviewed delivery: `1a08648603e1af2fe66998a0e53b11d02abf5c6b`;
its reviewed code: `15c1209c88ee54738595b92cf9d35c2f0d4a3177`.
New code checkpoint: `41c5c164c255e4fd6df57bc60ccde480072b1a3e`.
The later metadata-only delivery SHA is supplied in PR9 and the final return;
this document does not embed its own containing commit SHA.

## One startup correction

The [independent PR9 review](independent-review.json) confirms original R1–R4
in 31 normal plus 31 optimized exact-helper constant-only regressions on
Linux/CPython3.13.5. Its overall outcome remains changes_requested for new R5:
`-I` ignores the declared seed, as documented by
[Python startup semantics](https://docs.python.org/3.13/using/cmdline.html#cmdoption-I).
The original PR6–8 denials, code/delivery identities, receipts and prior actual
synthetic-SGD scope violation remain intact; no historical outcome is rewritten.

`tools/suite_runner.py` now removes every case variant of inherited PYTHON*
before starting each interpreter, restoring only PYTHONHASHSEED=0 and
PYTHONDONTWRITEBYTECODE=1. Explicit child flags are **-P -s -B**, preserving
requested **-O/-OO**. Before any test import, actual sys.flags are read back:
hash_randomization=0, ignore_environment=0, isolated=0, no_user_site=1,
safe_path=true, dont_write_bytecode=1, optimize=0/1/2 as requested.
Parent and child reject mismatched startup reports. Environment-string-only
claims are insufficient. Reports contain only necessary startup allowlists.

Snapshot creation/binding, source-drift rejection, protected-before-import,
controlled owning roots and gate authority remain unchanged. No new loader,
global PYTHONPATH, product/runtime implementation or research design is added.
System-site/sitecustomize retain the same existing trust surface as -I;
this is not a comprehensive hostile-Python sandbox.

Necessary distribution/onboarding commands use the same controlled launch.
Only their own tools directory is explicitly bootstrapped for safe-path entry.
Distribution creates fresh venvs through controlled subprocesses, compares an
installed consumer probe to a fresh same-interpreter seed0 hash reference,
and validates the installed console wrapper under controlled Python. Original
native launcher --help remains an additional compatibility check, with explicit
fixed PYTHONSAFEPATH=1/PYTHONNOUSERSITE=1 allowlist additions and a separate
same-interpreter environment-support probe. Native CLI flags themselves are
not introspected from the frozen CLI; the report states that limit.

## Actual developer checks

Environment: Windows11 / CPython3.14.7, task-local venv using existing small
public dependencies; no model stack installed or inputs acquired. Parent
startup and explicit children use the recorded controlled flags/environment.
Offline settings remain enabled and ARC_LEARNING_NEURAL_TESTS=0.

The [self-test report](self-tests.json) records seven commit-bound public suites
at new code41c: **442 tests, 0 failures, 0 errors, 2 declared Windows symlink
skips, 0 blocked**. Counts:
core63/distribution9/management208/navigation10/integrity15/arc-unit125/line-b12.
Every module/source binding is checked against the target Git inventory, and
each child records effective seed/isolation flags. No OS/Python matrix is
fabricated from these local Windows results.

Ten affected test files pass direct-file **-O: 191 tests, 0 failures/errors,
2 declared symlink skips**, with stable before/after actual working-byte identity.
The original R1–R4 lifecycle/source/package/protected-import and 27-test complete
matrix negatives remain in these checks. Working-byte fingerprints, including
normal Windows checkout newlines, are distinct from formal raw-Git manifests.

New startup regression: **12 tests**, with real fresh processes and independently
computed same-executable seed0 references; repeated child hashes are identical,
normal/-O/-OO flags are effective, and polluted PYTHONHOME/PYTHONPATH/user-base/
optimize/unknown Python settings cannot alter initialization or import poison.
No version-independent numeric hash value is hardcoded. Two additional caller
constant tests cover distribution/onboarding environment/bootstrap integration.

Formal non-editable distribution passes **normal and -O**, each with 22 actual
expected command outcomes, two identical 128-member wheel builds and valid
RECORD, fresh consumer installation, external-cwd installed core/line-b/CLI
flows, entry wrapper/native --help and expected missing-path exits.
The report records actual wheel hashes, seed reference equality and effective
consumer flags separately for optimize0 and optimize1.

Actual short local source-only [onboarding](onboarding.json) also passes normal
and -O. Each creates its own exercise metadata commit, proves program/tool/test/
CI equality to new code, runs commit-bound line-b12 at its distinct exercise SHA,
records effective startup, verifies navigation and fixed ARC R4/R5 local objects,
then returns WSF-04 without changing original tasks or scientific source.

## Failures and limits preserved

The reviewed failure is reproduced locally with constants: old -I children see
the seed string0 but have ignore_environment=1/hash_randomization=1 and different
fresh hashes. New normal/-O same-interpreter references and controls pass.
This startup reproduction is separate from previously green CI tests and does
not recast all old passing results as invalid.

Two real Windows symlink negatives still lack privilege and remain declared
skips; mocked/junction controls pass. Earlier seven long-path preparation
failures remain in WSF-R1-R4 receipts. Short output/clone roots are used here;
arbitrary long Windows roots are not newly qualified.

Two first R5 onboarding attempts in the parallel batch timed out after180s during
line-b verify. Their startup probes passed with effective seed/isolation, but
the full exercises are preserved as failed, without final passing suite reports.
No matching owned Python orphan remained. Fresh-output sequential retries supply
the later passing evidence; the exact timing cause is unverified and no timeout
or failed receipt is relabelled as successful.

Original audit/aggregate remain unexecuted **BLOCKED/non-success** on this branch;
their historical errors and prior no-training scope violation are not cleared.
The review attributes prior PR9 28-public/4-formal/gate/navigation passes and
scope-deferred audits to comparison merge286611, whose tree matched delivery1a;
that is neither a merge nor current R5 CI verification. This local return does
not independently rerun the reviewer's Linux environment, original audit bodies,
authentic reconstruction, numerical replay, GPU/model/evaluator work or efficacy.
Current R5 remote CI and complete independent acceptance remain unverified.

## Preservation and return

Product src/thesis/metadata, original ARC tool/runtime, research/trials/archive,
ARC/line-b status and research direction retain bytes/paths from starting delivery.
R1 management, source-identity, gate and no-training implementations are unchanged.
Main remains `baaf47d4f449c534ddd4646ab9b3175bbaf1ef89`; run008 remains
`cc14bd1a79aac1fe6135017c9e09d4834300675d`; old stacked branches and tags retain
their heads. The original checkout/untracked ZIP is untouched. Only ordinary
commits append to PR9; no reset/stash/clean/force/rebase/history rewrite/tag move,
new stacked branch, merge, main/run008 push, provider/Kaggle, training including
synthetic SGD, or model/evaluator/transfer acquisition occurs.

WSF-R5 stops review_ready. WSF-R1-R4 records the new overall changes_requested
with its bounded R1–R4 pass and sole R5 blocker; WSF-02/03/04 retain historical
denials. Return this code/delivery SHA, updated Draft PR9 and handoff to the
original ChatGPT conversation for bounded independent re-verification.
