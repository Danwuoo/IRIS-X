# Independent review: actual Agent Factory 3 offline bridge

Reviewed on 2026-10-14 UTC. Scope: the new offline component bridge and its
synthetic tests, source provenance, license attribution, and research claims.
The reviewer did not author the implementation, modify frozen runtime sources,
install packages, commit, push, invoke a model, or contact a compute provider.

## Verdict

**Pass for the bounded offline component-integration scope.** The adapter
constructs the actual pinned upstream `TrainingSample`, calls the actual
`DDISLoss.compute_unpacked`, and receives actual `MeanMetricState` objects.
This is executable component reuse rather than a renamed local formula.
No remaining implementation blocker was found after the corrections below.
Final independent acceptance was rerun after the cache-mode and fixed-parent
prompt corrections, with 25 tests in each interpreter mode.

This verdict is not production admission, model replay verification, GPU
acceptance, or evidence of improved ARC performance. Frozen production code
still uses its existing implementation. The implementation does not install or
invoke the upstream framework, trainer, rollout servers, or optimizer.

## Independent provenance and scope checks

The reviewer read the complete copied Python components and license, then
independently retrieved the untruncated GitHub tree for
[`a1836decb836cd52cf2b27f5022f6838cee75df3`](https://github.com/ycchen-tw/agent-factory-3/tree/a1836decb836cd52cf2b27f5022f6838cee75df3).
Local `git hash-object` values exactly matched the pinned tree:

| Original upstream path | Git blob ID |
| --- | --- |
| `src/agent_factory_3/trainer/types.py` | `e1f25644fd04ed996cdcd72d1814979be585f165` |
| `src/agent_factory_3/trainer/losses/ddis_loss.py` | `28afd41a146e1bc2c178f50c0b68eb5d2fa7fdfb` |
| `src/agent_factory_3/trainer/losses/metric_state.py` | `bb805e047c1609f7228e14f46a09e731e38720f2` |
| `LICENSE` | `127de4b0d1b382c870f2c4949720875481e7b1e7` |

The SHA256 values and lengths also match `source-manifest.json`. No NOTICE
file exists in the pinned upstream tree. The local NOTICE identifies itself as
an IRIS-X addition; the complete upstream Apache-2.0 license is retained.
Local glue is distinguished from byte-identical copied components. This is a
source/attribution check, not a legal opinion.

The frozen local `rl_math.py` hash also matches its bytes at baseline commit
`cc14bd1a79aac1fe6135017c9e09d4834300675d`. The original actor, plan, factory,
runtime reduction, and policy were inspected without modification. The bridge
checks the existing vocab/context/prompt/generated-token capacities, support
ceiling and numerical gates against pinned local source identities.

The scientific contract remains group-centered binary reward, no advantage
standardization, no critic/reference-KL/OPSM/entropy term, exact G8/64-slot
completeness, and divisor `mixed_groups × 8 × original_generated_length` for
mixed batches. All-zero/all-one groups remain reported with zero advantage;
an entirely zero-signal batch stops before loss execution. The source does not
change A/B/C selection, full-B wall-time matching, PUBLIC120/167, or no-TTT.

## Defects found and corrected before acceptance

1. Native batch order was initially used as an upstream weight version. It is
   now an explicitly batch-local symbol `0` mapped to the original policy
   declaration; generation epoch remains separate. No global weight-version
   history or staleness filtering is claimed.
2. Same-sized support edits and missing DFA-state declarations initially left
   the prepared contract digest unchanged. Required state shape is now checked,
   and a complete raw-receipt digest binds support, state, and other original
   declarations. A changed declaration is detectable without pretending its
   truth has been authenticated.
3. Explicit fatal/stopped/error receipts and boolean attention-mask values
   could previously be silently accepted. They now fail closed.
4. Forced-token behavior/replay probability now requires exact zero, matching
   the frozen actor. Generated/prompt/context/vocabulary caps and malformed
   huge-integer/unhashable-field handling were also corrected during review.
5. Valid `requires_grad` inputs inside `torch.no_grad()` or
   `torch.inference_mode()` initially returned a non-differentiable loss.
   The bridge now rejects those contexts and verifies the output remains
   differentiable. Both contexts have regression coverage.
6. A single declared actor initially accepted mixed cached/full-prefix modes
   in one batch. All 64 samples now require the same selected mode; uniformly
   cached and uniformly full-prefix receipts remain supported.
7. Per-trajectory prefix checks initially allowed a rewritten prompt inside
   one fixed parent/record group when its other token fields were coherently
   rewritten. All eight samples now require identical original prompt IDs.
   Synthetic prompt-length variation was moved across groups, and a coherent
   rewrite rejection test plus group-consistent capacity tests were added.

## Independently executed checks

Interpreter: `.irisx/agent-factory3-proof/venv/bin/python`, Python 3.12.14,
PyTorch 2.9.0+cpu, NumPy 2.3.5, Pydantic 2.13.4. `torch.version.cuda` is `None`.
The install is confined to an ignored venv but inherits system-site packages;
it is not a hermetic environment. No framework/model dependencies were added
by this reviewer.

From repository root, with `PYTHONHASHSEED=0`:

```sh
.irisx/agent-factory3-proof/venv/bin/python -m unittest discover -s tools/arc2_agent_factory3_bridge_20261014/tests -v
.irisx/agent-factory3-proof/venv/bin/python -O -m unittest discover -s tools/arc2_agent_factory3_bridge_20261014/tests -v
.irisx/agent-factory3-proof/venv/bin/python -O -m tools.arc2_agent_factory3_bridge_20261014.proof
```

- Normal suite: **25 passed, zero skipped**.
- Optimized `-O` suite: **25 passed, zero skipped**.
- Proof: 64 actual upstream samples, 224 generated tokens, six mixed groups,
  and 16 upstream metric states.
- Upstream and frozen-local scalar loss: `0.0014256983995437622`.
- Loss absolute gap, raw-logit gradient maximum gap, and per-trajectory
  reduction gradient maximum gap: **0.0**.
- Raw-logit gradient norm: `0.017627257853746414`, finite and nonzero.
- Singleton-support raw-logit gradients are zero. Variable generated lengths,
  prompt masks, strict clipping boundaries, positive/negative/zero advantage,
  detached behavior/ratio, and unequal-shard metric merging are covered.
- Additional independent parameterization, rerun under `-O` after the final
  corrections: 16 synthetic batches covering all
  four batch indices and one, six, or eight mixed groups. Maximum scalar-loss
  and raw-logit-gradient gaps against frozen `rl_math` were both **0.0**.
- The proof also completed under a Python audit hook rejecting socket connect,
  bind, and DNS lookup events: **zero such network events**. No
  `agent_factory_3`, `transformers`, `peft`, `sglang`, `vllm`, or `accelerate`
  module was loaded. This supplements static source inspection; it is not a
  general network-sandbox certification.

The upstream DDIS source deliberately remains byte-identical, including its
`assert` statements. Those assertions disappear under `-O`. The bridge's
explicit validation and generated shapes do not rely on them, and the bridge
negative tests pass under `-O`; this does **not** certify arbitrary direct
calls to the upstream class as hardened against malformed input.

The README, Traditional Chinese integration report, validation report,
source manifest, and two dependency records were also reviewed. Their
distinction between source-component execution and future production wiring
is accurate. Dependency records explicitly avoid claiming a hermetic or
complete hash-locked environment. The research report's upstream dependency,
divisor-default, and example-hardware descriptions were cross-checked against
the pinned upstream files.

## Evidence limits and remaining gates

The proof uses fabricated non-ARC tensors and exercises gradients through
masked-logprob computation to synthetic logits. It does not exercise Qwen,
LoRA, real causal teacher forcing, model state, cached generation, or an
optimizer. A supplied leaf logprob can have a derivative even at value zero;
only the tested singleton-support raw-logit graph establishes zero underlying
gradient in that synthetic case.

`BatchContext`, input rewards, train/exclusion membership, policy identity,
DFA states, and support declarations remain untrusted caller declarations.
Hash consistency is not authenticated runtime evidence. Prepared Python
objects are not security capabilities, and callers can recompute digests.
No admission should consume this bridge result as proof of training lineage,
DFA correctness, actor ownership, unchanged-model replay, memory/time bounds,
or optimizer commit/rollback.

Future production use still needs an independently identified and reviewed
runtime successor, authentic train-only receipt provenance, original actor
and replay gates, real adapter-gradient/state checks, full cost accounting,
and unchanged scientific comparisons. Repository-wide validation/publication
is owned separately by the integrating lead; this report only records the
focused checks independently run here.

## Reviewed implementation identity

The following SHA256 values bind the implementation and tests used for the
25-test normal/optimized acceptance runs above:

| Path beneath `tools/arc2_agent_factory3_bridge_20261014/` | SHA256 |
| --- | --- |
| `bridge.py` | `68e09ed7c01bc51a32a7ddf31eaceb16d928dc3f20069d3f53967a9d70ab74a3` |
| `proof.py` | `8a126e2d4973c7f37a05a244dfd516f8d11617c1ceb1432381e0e4f1e2c303d6` |
| `provenance.py` | `434241a97958a39f904ccad9857e30e4dc3267ae87625aac3be548a75db1103e` |
| `fixtures.py` | `eeec2c88e85adaa0369b50fbc2bd29e42f711188bf4cd247d68ed9ee904851aa` |
| `tests/test_contract.py` | `c7e6e3a7e06a30eae88b6ef77974095f7c911a1ab08f856e445ad06d825c92ea` |
| `tests/test_torch_conformance.py` | `c24aa78c8401d5916b9fb8f663086bd966211ff3babd6405e474b7d5f746c266` |

Later implementation changes require renewed affected checks; documentation
alone does not extend this verdict to a different runtime or experiment.
