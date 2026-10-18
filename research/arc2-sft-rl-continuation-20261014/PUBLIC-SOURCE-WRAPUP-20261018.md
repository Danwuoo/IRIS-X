# Public source wrap-up: compact controls and numerical contracts

This is a bounded source checkpoint of work already implemented and reviewed.
It is not a new experiment, an official-model acceptance report, or permission
to run, monitor, publish a notebook, or submit to a competition. Development
and notebook monitoring are stopped for this wrap-up.

## Included implementation

- Compact fixed-view batching preserves the existing codec, deterministic view
  order, inverse transforms and vote/likelihood ranking. It records attempted
  forwards, padding and finished-row work, and has a bounded singleton fallback
  after a multirow out-of-memory failure. BF16 batch parity is not claimed.
- Exact sampled-trace validation and probability probes distinguish cached
  sampling/replay from full training-mode probability agreement. The explicit
  FP32 compact-head policy preserves named trainables and is recorded in model
  and checkpoint contracts. Neither diagnostic evidence nor cached agreement
  replaces the independent full-pool probability gate.
- Matched controls compare an unchanged anchor, known-target CE, exact-positive
  CE and the pinned AF3/DDIS loss. The finite convergence screen adds a fixed
  hybrid schedule, charged no-signal/failed slots and fresh policy-bound pools.
  These are implemented mechanisms, not established effectiveness improvements.
- Paired demo-only TTT retains exact checkpoint resets, functional reset probes,
  complete held-demo denominators and parent/group separation. Selection cannot
  promote incomplete, tied, late, poisoned or unverified work. CPU consumers
  independently reconstruct source, numerical, checkpoint and closure evidence.
- The separate depth factory constructs a strictly checked identity-initialized
  expansion from the pinned model architecture. It preserves frozen-tensor
  accounting, cache/full-forward parity contracts and explicit capacity identity.
  It is not silently substituted for the baseline in the owned controller.
- Scorer interchange now carries source-derived task digests and explicit
  unknown wall time, with regression checks against the unchanged scorer and
  complete synthetic denominators. No concurrent timings are invented.
- A reusable session-owned adapter cache checks bounded disk usage, immutable
  bindings, regular-file/inode ownership and snapshot integrity. It has no
  reopening, eviction, crash-recovery or notebook-execution authority.

## Deliberately separate material

The public subset omits private-bound exact/diagnostic delivery modules,
operational notebook and Dataset bindings, private run reports and raw evidence,
matched/convergence delivery builders, the competition candidate/transport and
its frozen provenance, and the prior notebook-title publication change.
The cache module is not a published competition runner. Existing public files
and already-published references remain unchanged unless listed in this source
checkpoint. No credentials, model weights, raw protected inputs or outputs are
included in this delta.

Selected source and tests retain their reviewed implementation bytes. The only
code-file sanitization removes one non-executable private provenance comment;
its executable syntax tree, memory admission thresholds and all integrity gates
are unchanged. Excluding a private-bound builder is not permission to bypass
its checks or to execute an unbound source capsule.

## Validation and limits

The local review resolves the 23 selected source entrypoints to 80 existing
source files without dependencies on the excluded private-bound modules.
Focused tests exercise real tiny CPU Qwen models, autograd, updates,
checkpoint save/reload, full-vocabulary probability paths, source isolation,
owned subprocess closure and filesystem adversarial cases. Scripted and
synthetic fixtures remain explicitly labeled as such.

The public aggregate runs the repository's existing public-checkout lane,
including its explicit optional-dependency and retained-evidence skips. No
skip manifest, test assertion, historical fixture or runtime gate is weakened.
This lane does not establish strict retained-evidence acceptance. The separate
focused ML environment expands actual CPU mechanism coverage rather than
turning skipped model tests into evidence of official-model success.

Validation recorded for this checkpoint on Linux / Python 3.12:

- Focused real-ML CPU checks: 300 passed, no skips.
- Affected upstream CPU regressions: 83 passed, no skips.
- Existing complete public lane: 2,278 tests, 441 explicit skips, PASS.
- Existing portable-subset lane: 2,278 tests, 983 explicit skips, PASS.

The portable subset was executed on Linux; this is not native Windows proof.
Both aggregate lanes also passed repository invariants and whitespace checks.

Official-weight GPU execution, full-context behavior, memory feasibility,
gradient stability, equal measured-compute comparisons and capability gains
remain unverified by this checkpoint. There is no new PUBLIC score, clean
holdout claim, competition result or completed-notebook claim here.
