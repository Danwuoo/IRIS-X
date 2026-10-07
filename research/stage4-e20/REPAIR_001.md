# E20 provenance/resource repair and first screen outcome

## Frozen screen preserved

Initial implementation `432bb061f0362d27ecb6450a7d7ba705f4f846d1` was committed
before execution/scoring. The first config was run once, using only the
coordinator's frozen 24-task/35-test solver-visible development inputs.
Every task launched under the same source/config bytes. No production source
was changed until every worker finished and the manifest was closed.

Observed result: **zero candidate vectors and zero tests with candidates**.
Seventeen workers reached the ten-second wall cutoff; seven completed bounded
search at 50,000 expansion attempts. Parent elapsed time was
216.02972244400007 seconds. Maximum observed **completed-worker** peak RSS was
76,664,832 bytes; timed-out worker peaks remain unknown. All 53 run manifest
members were checked by actual size and SHA-256. `DEV_SCREEN_001.json` binds
input/config/grammar/source and pool/manifest identities.

This operator/depth/budget configuration is rejected under E20's coverage gate.
There is no branch-quality or complementary-coverage gain. No evaluator labels
or confirmation inputs were opened, and no answer-driven operator/depth/routing
expansion or second public screen was made. An independent evaluator can check
the retained standard pools against its source-bound solutions. No official
score, GPU feasibility or unseen generalization is established.

## Independent review findings and repairs

Review of the original committed bytes found two P2 engineering boundaries:

1. A fabricated, replay-valid worker could exceed its embedded depth/AST,
   candidate count, cache or measured wall caps while claiming complete status.
   The real producer was not observed exceeding these bounds. Neutral v2 now
   retains complete digest-bound Limits and enforcement provenance and checks
   depth/AST/count/state/cache/search-wall/parent-wall/CPU/RSS at both conversion
   and direct validation. Completed search cutoff reason is retained. LOO support
   is rejected when the config did not request it. Historical v1 records remain
   frozen; their standard offline pools are unchanged and separately usable.
2. Optional LOO excluded retained main candidates and prior-fold references from
   its serialized cache allowance. The default screen used LOO=false and is
   unaffected. Each fold now reserves the live main candidate list against its
   allowance; prior folds are released before the next search. Reported cache
   usage is the aggregate peak across main/folds. The original 300-byte negative
   witness now yields null support; at 400 bytes all folds complete with the
   independently checked aggregate peak of 322 bytes.

Additional explicitly resolved contracts:

- Same-depth semantic dedup keeps the first-enumerated minimum-depth prefix,
  which need not be the globally lexicographically smallest equivalent program.
  This is now explicit grammar/documented provenance; retained candidate ranking
  remains deterministic by AST cost and retained canonical program bytes.
- The original one-each policy could lose a novel symbolic second choice when
  branch heads matched. The unselected fixed-one-each-v2 policy now keeps the
  baseline head plus the first distinct symbolic grid. Policy version is retained.
- Tasks with any newly correct test are named separately from newly all-tests-
  correct symbolic tasks and newly all-tests-correct union tasks.
- Linux bootstrap virtual mappings/historical RSS are checked before RLIMIT_AS;
  an already-oversized bootstrap fails without search. The limit cannot reclaim
  prior mappings, and is not a memory measurement.
- Producer-file hashes are not a closed dependency/interpreter attestation.
  Final runtime packaging remains the coordinator's responsibility.

## Validation scope

After repairs: 89 focused tests PASS (24 implementation/interface/resource
tests, 36 independent synthetic witnesses, 29 existing interoperability tests),
zero failures/errors/skips, ResourceWarning promoted to errors. Actual final
unittest interval: 1.273 seconds on Python 3.12.14.
`CPU_VALIDATION_REPAIR_FINAL.json` binds the exact command, source/test hashes and
retained log. Full-suite validation is not claimed; the coordinator serializes
it after integration. The independent reviewer separately reran original
fabricated-cap and LOO-overrun probes against repaired bytes and observed
fail-closed behavior.

The repair is engineering work after a rejected frozen configuration. It does
not transform zero coverage into a scientific improvement or authorize another
confirmation, GPU run, official submission, publication or paid operation.

The independent reviewer confirmed both P2 repairs and found no remaining P1/P2
issue in the reviewed diff. Original cheap negative probes were repeated. The
minor review suggestion to include policy_version in evaluator briefs and
confirmation locks was implemented and covered by the final 89-test regression.
The earlier `CPU_VALIDATION_REPAIR_001.json` and log retain the pre-metadata
repair observation separately. No full-suite acceptance is implied.
