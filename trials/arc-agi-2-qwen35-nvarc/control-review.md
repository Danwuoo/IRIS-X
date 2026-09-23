# NVARC development acceptance review — 2026-09-23

Reviewed main: `e7d74a68d4975e728a4a20cdf46d35dadaf1cda0`.
Verdict: **development acceptance incomplete**. Continue implementation in the
existing task; the passing fixture suite is not acceptance of the complete port.
The original [development plan](../../docs/plan/2026-09-23-qwen35-nvarc-reproduction.md)
remains the scope. The [continuation plan](../../docs/plan/2026-09-23-qwen35-nvarc-acceptance-continuation.md)
defines the repair order and evidence required for another review.

## Verified progress

The reviewed implementation adds bounded score-pruned DFS, TTT cleanup on
failure, verification reservations, SFT optimizer/scheduler/RNG/cursor resume,
TRM preprocessing specifications, and synthetic worker/result tests. These are
useful implemented components; they do not establish full-method readiness.

- `python tools/repository_check.py --all`: PASS; 174 tests, one skipped under
  default Python 3.14, which has no torch.
- The skipped `test_real_torch_sft_resume_and_token_limit_if_available` was
  separately run with the installed Python 3.12.10 and torch: PASS, one test.
  No pretrained weights, external service, or real Qwen/TRM workload was used.
- Python 3.12 at
  `C:/Users/wurre/AppData/Local/Programs/Python/Python312/python.exe` has torch,
  but the environment inspection found neither transformers nor peft there.
  Thus “torch is absent” describes the default interpreter, not the machine.
  This tiny synthetic test does not verify Qwen3.5 hybrid layers or PEFT.

## Reproduced acceptance blockers

All probes used synthetic data under `.irisx/nvarc-acceptance-e7d74a6/` in the
main checkout. Modified packages had their digests and bindings recomputed;
these are semantic validation failures, not bypasses of a hash check. Nothing
was uploaded or sent to a model/provider.

| Priority | Finding at reviewed head | Reproduction and consequence |
| --- | --- | --- |
| P1 | `arc_nvarc_runtime.py:114`, `verify_outbound` | Add `cases[0].test[0].output = [[9]]` to an otherwise valid workload, rebind, build and verify. Both accept; the answer remains in outbound bytes. Keyword checks cannot distinguish legitimate train labels from forbidden test labels. The normal workload builder strips test outputs, but an independent verifier must reject a malformed input too. |
| P1 | `arc_nvarc_runtime.py:291`, `verify_result` | Change a valid result checkpoint to `complete: false`, rebuild the ZIP with correct digests, then verify. It is accepted. The reader does not independently enforce its builder's completion requirement. Completion must mean every requested task is terminal, including explicitly accounted failures, not that every prediction succeeded. |
| P1 | `arc_nvarc_representation.py:230`, `verify_model_material` | A correctly hashed manifest with `files: []` passes even with an unbound `config.json` present. Loadable model files need required membership and complete digest coverage. In addition, conversion around line 147 accepts the caller's base-model manifest digest without verifying the original model material; conversion provenance is therefore not established by that argument alone. |
| P2 | `arc_nvarc_candidates.py:53`, `bounded_dfs` | A deterministic 300-token path plus EOS returns zero completions at `max_new_tokens=1024`, `max_expansions=256`. Raising the expansion cap to 2048 for a 1000-token path triggers `RecursionError`. The default expansion budget restricts reachable output length; the recursive traversal cannot safely use its advertised sequence limit. |

The DFS cap itself is a legitimate resource bound. Its interaction with grid
length must be explicit and observable, and traversal must remain safe when
the configured budget permits a long sequence. Increasing a cap alone is not
a repair for recursion, performance, or accounting.

## Remaining development versus execution gaps

The reproduction matrix already acknowledges partial components. In particular,
`train_torch_sft` is single-process; SDG currently replays saved responses and
trusts a caller-supplied executor-attestation dictionary; TRM helpers primarily
construct launch specifications. These are not yet evidence of distributed
SFT, actual sandbox enforcement, or an exercised upstream result adapter.

Local implementation, tiny CPU backend tests, schema enforcement, bounded
supervision, optional dependency setup, and source-backed adapter integration
can continue without running a real experiment. Source batch/cache behavior,
tiny actual Qwen3.5/PEFT compatibility, and unsupported backend combinations
must be tested or explicitly marked with a precise remaining blocker.

Real dataset/model acquisition, real Qwen/TRM/teacher runs, GPU throughput and
VRAM, learned checkpoint quality, and ARC accuracy remain separate material or
execution gates. Their absence neither invalidates a synthetic test nor excuses
the independently fixable implementation failures above.

## Local evidence

Retained in `C:/Users/wurre/Desktop/IRIS-X/.irisx/nvarc-acceptance-e7d74a6/`:

- `validation.log`: full repository validation at the reviewed head.
- `torch312.log`: supplemental installed-torch synthetic test.
- `review_probes.py`: executable synthetic reproductions.
- `review-probes.json`: probe results; SHA-256
  `ce10d1211c36e5c9e6fc90fc654b60ab6d8ade8ac1d1b5bf4598d8dd41540d5e`.

These ignored files support this local review; the descriptions above are the
durable findings. The development task must add independent regression tests
to the tracked suite rather than depend on these local probe artifacts.
No previous trial identity, retained scientific evidence, acceptance threshold,
or real-execution authorization changed in this review.
