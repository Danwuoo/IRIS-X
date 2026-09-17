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
- [`p2-admission.md`](p2-admission.md) defines the blocked first-real-domain
  admission snapshot, owner decision gates, and offline validator.

P1 contracts remain provider- and technique-neutral. P2 has started only at
the admission layer and remains blocked under Decision 0003. A later authorized
real domain must adapt to these contracts without treating fixture details as
architecture.
