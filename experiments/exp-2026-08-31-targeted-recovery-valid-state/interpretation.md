# H-RCV1a interpretation

Status: result

## Run

- Run ID: `hrcv1a-20260901-local-01`
- Frozen definition commit: `efa75a94cbe1fe76296d8c09256b4ad06f30f8ce`
- Horizon: 5 frozen failure states x 3 repetitions x 2 arms = 30 episodes
- Result: `Supported — task-local`
- Invalid attempts: none

## Observed result

Both arms began each pair from the same frozen failure-state manifest and detected the declared failure in all 15 pairs. The `detect-only-v0` arm attempted no recovery and had 0 of 15 valid final states. The `targeted-recovery-v0` arm completed exactly one predeclared recovery action per episode and had 15 of 15 final states pass the independent exact-manifest oracle. The observed valid-state difference was therefore 15 episodes at this horizon.

No targeted episode introduced a new side-effect violation. No recovery-induced failures or invalid episodes were observed. The independent oracle's deliberately failed-recovery self-test rejected a changed final payload as intended.

The terminal records retain failure detection, recovery attempted, recovery action completion, final-state validity, final actual outcome, final evidence status, and new side-effect violations as separate fields. The recovery implementation received the recovery specification only; it did not receive the oracle specification or a precomputed success label.

## Resource evidence

The detect-only arm used 0 recovery actions, 703,065,000 measured wall nanoseconds, and 109,375,000 measured CPU nanoseconds. The targeted arm used 15 recovery actions, 759,564,500 measured wall nanoseconds, and 125,000,000 measured CPU nanoseconds. Both arms used zero model calls and zero paid API calls. These local timing observations are descriptive and are not a performance benchmark.

## Bounded interpretation

The evidence supports the task-local claim that these five frozen, deterministic, copied-workspace failure states were restored to their predeclared valid final states by their corresponding targeted recovery policies under this 30-episode horizon. It does not establish arbitrary failure diagnosis, general recovery capability, real external compensation, production recovery reliability, or robustness to unmodeled failure states.

Imported VANTA fixture semantics identify the source cases. The recovery runner, final-state oracle, and claim boundary are IRIS-X experiment-local substrate and do not adopt VANTA as IRIS-X architecture authority.
