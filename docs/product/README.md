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

P1 contracts are intentionally provider- and technique-neutral. P2 must adapt a
real authorized domain to these contracts without treating fixture details as
architecture.
