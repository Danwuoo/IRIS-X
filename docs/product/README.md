# Product Documentation

`PRODUCT_THESIS.md` is the current product authority. The active product
documentation is:

- [`product-scope.md`](product-scope.md) defines what the product is intended to
  accomplish and which choices remain open;
- [`non-goals.md`](non-goals.md) defines what IRIS-X is not and prevents
  mechanism-led scope drift;
- [`contracts.md`](contracts.md) defines the P1 contract families and binding
  semantics;
- [`domain-package.md`](domain-package.md) defines the P1 package layout and
  independent verification boundary.
- [`p2-admission.md`](p2-admission.md) defines the historical blocked
  first-real-domain snapshot, its offline validator, and its relationship to
  current Decisions 0004, 0005, 0006, and 0007.

P1 contracts remain provider- and technique-neutral. Decision 0004 admits the
bounded ARC-AGI-2 Trial 001 implementation, Decision 0005 narrowly selects
the frozen Qwen revision and manual network-disabled Kaggle venue, and Decision
0006 binds the unpacked model source directly, and Decision 0007 binds the
Kaggle-extracted trial tree, without treating
fixture details as architecture. Real model/solver execution remains separately
authorization-gated.
