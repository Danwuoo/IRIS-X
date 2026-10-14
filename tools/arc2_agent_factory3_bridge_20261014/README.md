# Agent Factory 3: actual offline component integration

This new research-line module executes upstream code. It does not rewire the
frozen producer, launch a model, run an optimizer, or claim ARC accuracy.

## Implemented delta

- `vendor/types.py`: exact upstream `TrainingSample` and its real validator.
- `vendor/losses/ddis_loss.py`: exact upstream `DDISLoss.compute_unpacked`.
- `vendor/losses/metric_state.py`: exact upstream mergeable `(sum, count)` metrics.
- `bridge.prepare_batch`: converts a complete native 64-slot training receipt
  into 64 actual upstream samples, preserving original token IDs, masks,
  behavior probabilities, group-relative advantages and local normalization.
- `bridge.compute_loss`: executes the upstream loss on supplied CPU replay
  tensors after declared-contract checks. It returns the real upstream loss
  object and metric states. It never calls `backward` or an optimizer.
- `proof.run_proof`: executes fabricated raw-logits → singleton/non-singleton
  masked log-probabilities → upstream loss → autograd; compares scalar losses
  and underlying-logit gradients to the hash-pinned frozen local math and a
  per-trajectory reduction. This is not model-gradient or model-replay evidence.

Previous IRIS-X code independently expressed the DDIS formula and did not run
upstream source. This component-level integration is new. Full Agent Factory 3
framework adoption and production wiring are not claimed.

## Reproduce the offline proof

From repository root with Python 3.12, NumPy, Pydantic 2 and CPU PyTorch:

```sh
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 python -m unittest discover -s tools/arc2_agent_factory3_bridge_20261014/tests -v
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 python -O -m unittest discover -s tools/arc2_agent_factory3_bridge_20261014/tests -v
PYTHONHASHSEED=0 OMP_NUM_THREADS=1 python -m tools.arc2_agent_factory3_bridge_20261014.proof
```

The implementation was tested with Python 3.12.14, `torch==2.9.0+cpu`,
`numpy==2.3.5`, `pydantic==2.13.4`. The existing proof interpreter is
`.irisx/agent-factory3-proof/venv/bin/python`. Package installation is isolated
to that ignored venv; it inherits the existing system-site NumPy/Pydantic and
is not a hermetic environment. No global environment was modified. Tensor tests
explicitly skip when torch is absent, which is **not** complete integration
acceptance; the proof command itself requires torch.

The only new installation used the official PyTorch CPU index, not the upstream
project's installation scripts, custom kernels or framework dependencies.
Full dependency versions and exact wheel identity are in the research report.
The two requirements files record the direct contract dependencies and the
observed CPU torch installation separately. They are dependency records, not
an automatic installer. The default repository dependency set is unchanged.

## API and unchanged semantics

1. Construct `BatchContext` with the expected 32 training parents/record IDs,
   complete declared PUBLIC/ancestor/alias exclusions, fixed batch index,
   policy UUID/identity, generation epoch, panel and sampling-policy hashes.
2. Call `prepare_batch(native_batch, context)` on an already available in-memory
   receipt. It does not load data, score answers, or authenticate the caller.
3. Supply a mapping from each trajectory ID to its differentiable CPU vector of
   original generated-token, DFA-conditioned log-probabilities. Call
   `compute_loss(prepared, replay_log_probs)`; no text retokenization occurs.
4. Consume the returned upstream loss/metric objects in an explicitly scoped
   offline analysis. Merely possessing them never authorizes an update.

The contract fixes 8 parents × 8 samples per batch; 32 disjoint parents over at
most four batches; rewards 0/1; group-centering without std; strict ratio bounds
`(0.8, 1.28)`; detached behavior and ratio; per-sequence divisor
`max(1, mixed_groups) × 8 × original_generated_length`. Prompt loss is zero.
Zero-signal groups remain in the reporting denominator and have zero advantage.
An entirely zero-signal batch is rejected by `compute_loss` before upstream
replay/loss execution, preserving the existing no-replay/no-update path.

All 64 original slots are required; infrastructure errors cannot become reward
zero or be dropped to make a partial group. Original prefix positions and hashes,
support membership, three-integer DFA-state declarations, exact forced-token
log-probability zero, fixed source pins, identity/version consistency, fatal/stop
state, finite values, raw-token lengths and native capacities are checked.
`BatchContext`/receipt hashes are declarations and consistency checks, not
cryptographic provenance authentication. Actual DFA transitions/support,
train-only lineage, original actor ownership, model weights/backend/cache and
actual replay still require the existing producer's independent admission.

The complete input receipt digest includes support/DFA and other original
declarations. Prepared samples and metadata are also digest-bound against later
mutation. These checks do not turn an in-process Python object into a security
capability or defend against a caller replacing trusted code or recomputing
every declaration.

Upstream integer weight version `0` is explicitly a **batch-local symbol** for
the declared native `policy_version`; the mapping is in `PreparedBatch.summary`.
Native generation epoch is preserved separately. Neither batch index nor epoch
is misrepresented as a globally ordered committed-weight version. No staleness
filter or asynchronous flow consumes this symbol.

The scalar replay checks mirror the existing nonforced `max|gap| ≤ .20`,
`p95|gap| ≤ .05`, unclipped fraction 1 contract. They do not verify original
model replay, GPU memory, wall time, process ownership, release gates or
commit/rollback. CPU inputs are explicit. No dispatch API exists.
Upstream `compute_unpacked` pads all supplied sequences. These small CPU fixtures
do not establish that 64 real Qwen replay graphs fit on one GPU. Future wiring
must preserve existing per-trajectory gradient accumulation and the original
full-batch divisor, or independently measure/admit a new memory/cost strategy.

## Scope and licensing

Copied upstream commit: `a1836decb836cd52cf2b27f5022f6838cee75df3`.
`source-manifest.json` records original paths, exact Git blob IDs, SHA256 and
byte sizes. `provenance.py` verifies copied bytes and five frozen local sources.
The three copied Python files and LICENSE are unmodified. Local glue, fixtures,
tests and NOTICE are additions. Preserve `vendor/LICENSE` and `vendor/NOTICE`
when redistributing these components; the parent project's license does not
replace their Apache-2.0 terms.
The exact upstream loss retains upstream assertions. Hardened normal/optimized
validation applies to bridge-generated inputs; it does not make the generic
direct upstream API safe against arbitrary invalid inputs under Python `-O`.

No RLFlow, SampleProcessor, ModelTrainer, FSDP2, SGLang, Harmony, GPT-OSS MXFP4,
R3/routing replay, DFlash, W&B, MCP server, custom fork, async queue, stale-policy
filter, OPSM or entropy-mask runtime is imported or executed. Upstream defaults
are not adopted: notably its default sequence-token-sum aggregation would change
the frozen local sequence-token-mean objective.

The scientific comparison remains A=SFT256, B≤4 disjoint 64-slot batches,
C=full-B-extra-wall-time-matched continued SFT, no TTT, train-derived selection,
and full PUBLIC120/167. A future runtime successor needs separate source identity,
review and unchanged-control model/replay/gradient/cost evidence before any
local-side training. See the implementation report and independent review in
[the Agent Factory 3 RL-method research section](../../research/arc2-sft-rl-continuation-20261014/agent-factory3/integration.zh-TW.md)
and its [independent review](../../research/arc2-sft-rl-continuation-20261014/agent-factory3/independent-review.md).
