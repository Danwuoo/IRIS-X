# H-SR1a Run Interpretation — `hsr1a-20260901-local-01`

- **Status:** result — reviewed measured run
- **Definition commit:** `01eaa325d9e9c2e28b59dea89c00e15c5c0b0b86`
- **Result:** `Stable under declared horizon`
- **Horizon:** six reversible fixtures × ten cycles × two arms = 120 cycle records
- **Invalid attempts:** none

## Directly observed result

Both arms completed 60/60 applications with the frozen changed-state SHA-256 and required backup metadata, completed 60/60 rollback actions, and independently restored the exact baseline path set, file hashes, and byte counts after every cycle. All 120 actual outcomes were `success`; empirical evidence was sufficient and verified-success eligibility was true. Acceptance was `not_applicable` and supplied no state truth.

The persistent arm reused one copied workspace per fixture through cycle 10 and exhibited zero drift, no first drift cycle, zero residual paths, and zero residual bytes. The fresh arm also exhibited zero drift. Starting baseline identity was checked before each application, and post-rollback truth came from the independent filesystem oracle rather than the rollback return value.

The pre-run sensitivity test inserted `residual.tmp`; the oracle rejected exact restoration and identified the path and its 17 residual bytes. This establishes sensitivity to that injected residual case only.

## Artifact and resource observations

No complete successful workspace tree was retained. Durable evidence consists of six baseline manifests (2,195 bytes), 120 post-apply/post-rollback terminal records (372,128 bytes), action/state hashes, metadata checks, changed paths, and residual-state results. Raw terminal SHA-256 is `242bc9bacfb1de33087b84180ec0139264adba111466d38e8fb5cb1103c992e6`.

Fresh-workspace cycle wall/CPU sums were 3.959/0.922 seconds; persistent-workspace cycle wall/CPU sums were 3.889/0.859 seconds. These host-local timings are descriptive and are not a performance claim.

## Bounded interpretation

For these six deterministic local mutation contracts, persistence of the same copied workspace across ten apply→verify→rollback cycles caused no observable cumulative state drift relative to fresh workspace copies. This supports stateful reversible-cycle stability only under the declared fixtures, implementation, and horizon.

- **Not established:** general rollback correctness, filesystem-crash durability, journaling durability, external-system compensation, or long-running production state reliability.
- **Not evaluated:** concurrency, interrupted writes, permission errors, disk exhaustion, adversarial paths, model-produced actions, or recovery after a failed rollback.
- **Unknown:** maintenance effort, electricity/hardware cost, and real deployment cycle horizon.
