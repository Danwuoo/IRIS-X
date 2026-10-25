# Offline grid16 post-SFT contracts

`objectives.py` and `query_spans.py` are byte-identical reviewed first-party
source from the K1 engineering package. Source SHA values are retained in
`research/irisx-status-20261025/SOURCE-PROVENANCE.json`.

They expose pure tensor losses and strict query-response indexing, not a model
loader, dataset, tokenizer, training runner, optimizer scheduler or cloud tool.
The optional tensor tests require an already installed Torch/NumPy environment;
they never install dependencies or download data. Without Torch, those tests
are explicitly skipped, not reported as numerical acceptance.

- Query supervision covers the final answer plus EOS15, shifted exactly once;
  PAD13/support/prompt positions are not query targets.
- DPO uses whole-response log-probability sums and a pair denominator.
- Winner NLL uses a global chosen-token denominator.
- The G4 reference GRPO-style helper uses population-standardized group rewards,
  clipped ratios and reference KL. This is not the old asymmetric DDIS formula
  or a claim that the K1 inline G2 loop is an unchanged G4 implementation.
- Full denominator contributions must be summed across ranks correctly. Uniform
  reward returns no update; missing infrastructure evidence is not reward zero.

Synthetic CPU parity is not CUDA/TPU parity, a native restore or model benefit.

```sh
python -m unittest discover -s tests -p 'test_postsft_loss_contracts_20261025.py' -v
```
