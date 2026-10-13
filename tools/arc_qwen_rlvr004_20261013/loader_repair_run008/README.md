# run008 authenticated child loader repair

Status: local CPU candidate; separate exact-byte independent review and successor
assembly are required. No provider action, full-model/GPU observation, scientific
result or successful-baseline claim is established here.

The lead's `docs/plan/2026-10-13-native-research-continuation.md` was read before
implementation. This directory owns four full replacement overlays only; it does
not edit historical run007 source, receipts or evidence.

## Verified sequence and bounded diagnosis

The installed parent (`deployment/parent_entry.py`) calls `reviewed_bootstrap`,
then `runner.run_owned`. The existing runner creates a minimal worker environment
and the existing supervisor launches that same installed interpreter with `-I -B`
and a fresh process session. In run007 its LD_LIBRARY_PATH contained only five
fixed system driver roots. The child imports source factory/backend/flow modules
and Torch; native loading/calibration precedes the final cuDNN mapping admission.
The owned cuDNN directory was absent from the child loader search path.

The preserved v39 observation is owned shim + foreign system graph, both reported
APIs90800, with intact installed9.10.2.21 wheel members. The exact mapping gate
correctly rejected the foreign graph. This evidence does not record every prior
dlopen call or the vendor libraries' ELF dynamic tags. CPU fixtures establish a
concrete compatible mechanism, not a unique retrospective proof of the GPU
process's loader history.

Primary references consulted before implementation:

- https://docs.nvidia.com/cudnn/installation/build-run-cudnn/ describes split
  runtime libraries and dependency search.
- https://man7.org/linux/man-pages/man3/dlopen.3.html documents startup-time
  LD_LIBRARY_PATH, SONAME/object reuse, and RPATH/RUNPATH distinctions.

An absolute shim pathname does not force an unqualified deferred backend name to
come from the same directory. Changing os.environ after Python starts does not
change glibc's startup-cached search path. RPATH and already-loaded objects can
still affect selection; the independent exact mapping checks remain required.

## Four-file source delta

`OVERLAY-MANIFEST.json` supplies complete original and replacement hashes against
source89d19e7e9859d756f320d28fe55f908aee3c7b568f31ea10ecc82cb1be13b14b.
`SOURCE-DELTA.patch` records deterministic textual differences.

1. environment_v2.py: factor the existing exact installed-wheel verifier for
   reuse before any native import. Preserve source wheel/version/lock pins, full
   vendor library inventory, headers, ABI, API agreement, aliases, kernel
   device/inode and mapping-byte gates. Require an unambiguous canonical owned
   vendor root. Because it becomes a loader search root, additionally reject
   unpinned direct files and loader subdirectories (including glibc-hwcaps/tls),
   verify any nonlibrary direct wheel files, and allow only an ordinary optional
   Python __pycache__ directory. The post-import API/mapping admission suffix is
   byte-identical to run007.
2. parent_scoring.py: prepend only that canonical owned vendor directory to the
   existing unchanged five driver roots. No inherited paths are forwarded.
   The existing parent-private scorer disjointness check examines this new path
   too. Child verification repeats complete installed-wheel authentication and
   compares actual whole environment with the parent-bound source policy. The
   driver preflight compares against this same source-owned loader path.
3. runner.py: authenticate the full installed vendor payload under the existing
   original inner deadline before constructing the environment and execing the
   worker. No new clock or child respawn is introduced.
4. worker.py: reconstruct the original clock and repeat startup verification
   immediately after request/source verification, before planning, factory,
   backend, native, flow or Torch imports. Preserve the later independent
   native/environment/mapping admission and existing failure/closure code.

The existing supervisor, launcher, notebook, interpreter, physical ledger,
A/B/C scientific plan, fixed scoring denominator and consumer gates are not
changed by these overlays. No LD_PRELOAD, host mutation, alternate wheel or
arbitrary inherited directory is used. Repeated full hashing has real startup
cost and consumes the original session deadline; no work is refunded.

## Reproduction and coverage

Requires Linux `/proc`, gcc and Python standard library. No Torch package is
needed for these synthetic loader tests. By default they read the verified
portable run007 reconstruction under `.irisx/transfer-verification-20261013/`.
For a relocated verified reconstruction set `IRISX_RUN007_SOURCE_ROOT` to its
`producer-source` directory. Four base-target hashes and all replacement bytes
are checked against the manifest before testing.

Run from repository root:

    python -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/loader_repair_run008/tests -v
    python -O -B -m unittest discover -s tools/arc_qwen_rlvr004_20261013/loader_repair_run008/tests -v
    python -B tools/arc_qwen_rlvr004_20261013/loader_repair_run008/tests/run_inherited_mapping.py
    python -O -B tools/arc_qwen_rlvr004_20261013/loader_repair_run008/tests/run_inherited_mapping.py

Actual gcc-built ELF shims/backends use matching SONAMEs with both dlopen and
DT_NEEDED. Historical/system-first/late-env cases return90800 and reject.
Owned-first before exec returns91002 and accepts. A foreign backend already
loaded in the same child is reused and rejected; an exec removes a parent's
old mappings. Tests also cover changed child environment, missing/tampered
wheel/vendor data, extra native shadows, symlink roots, noncanonical path
separators, wrong metadata/prefix, complete inventory and invalid deadlines.

The unchanged real supervisor is also exercised with an actual sleeping child:
startup timeout kills/reaps it, leaves no session members and never fabricates
safe model closure. An expired original deadline prevents spawn. Original
run007 map/consumer negative and positive cases are separately re-executed
against this new environment overlay; the historical tests remain untouched.

These tests substitute explicitly synthetic tiny wheel pins and metadata, one
synthetic driver directory, and an API wrapper in place of Torch. They exercise
actual ELF/process selection and unchanged verifier logic, not real cuDNN GPU
operations, full14B fit/throughput, numerical replay or PUBLIC scoring. A separate CPU dependency environment is now available for actual tiny neural
owned-runner integration. Its results are reported separately from ELF tests;
tiny CPU execution does not exercise the production cuDNN path or validate the
full14B/GPU experiment.

## Assembly contract

Apply each full replacement only after checking its original_sha256 against the
verified run007 reconstructed source. Bind the new bytes, new normalized source
contract, source archive and successor descriptors through the successor
assembler. Preserve all old artifacts and reviews; do not copy historical review
approval to the successor. The overlay manifest introduces no runtime modules,
policy schema change or consumer compatibility exception. Publishing/activation
remains the sole lead publisher's responsibility after fresh review and access.

## Final local results

- 34 new tests pass normally and under `-O`.
- 21 inherited mapping/consumer cases pass against the new overlay in each mode.
- Actual tiny CPU neural owned-runner success passes with normal and optimized
  parent invocation, authenticated safe closure, exited/empty worker session,
  and complete evidence export. The unchanged supervisor starts its child with
  `-I -B`; optimized-parent testing is not an optimized-child claim.
- Actual before-load and after-load failure fixtures stop incomplete, retain
  unsafe closure, exit cleanly with no worker session members, and export
  diagnostic evidence only.

Compact, hash-bound logs and summaries are in `results/CPU-RESULTS.json` and
`results/TINY-CPU-RESULTS.json`. Raw tiny-neural artifacts stay outside Git.
The separately assembled successor still requires fresh source identity,
independent review and provider validation.
