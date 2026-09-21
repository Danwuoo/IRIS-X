# Development Operating Model

Status: current under
[`Decision 0010`](../decisions/0010-adopt-lightweight-risk-based-development.md).
The product direction remains defined by the
[`Product Scope`](../product/product-scope.md); safety boundaries remain in the
[`Data and Execution Policy`](data-and-execution-policy.md).

## Default loop

Product engineering is the default IRIS-X track. Work follows
**Build–Measure–Select**:

1. state one outcome and the check that will prove it;
2. build the smallest reversible end-to-end increment;
3. measure it with the narrowest reliable test or workload;
4. keep, revise, or reject it from the evidence.

An **Engineering Trial** is used when the question requires empirical product
evidence. It identifies the goal, baseline, intervention, workload, measures,
costs, stop conditions, result, and selection. The active trial's README is its
current status source; detailed procedures and decision records are supporting
references rather than parallel status pages.

## Routine work

Local, offline, reversible work inside the current product and trial boundaries
does not require a new decision record or separate owner authorization. This
includes ordinary implementation, tests, documentation, refactoring, fixture
work, and validation improvements.

Routine work should leave only the evidence its risk warrants: focused tests
during development and the repository-wide check before handoff. P1 contracts
and historical evidence are preserved, but they do not need to be restated in
every current document.

## Gated work

An owner-authorized scope is required at the point where work would:

- change the product goal, public contract, acceptance threshold, or promotion
  claim;
- use an external provider, paid resource, credentials, or sensitive data;
- execute a real model workload covered by an explicit run gate;
- change a frozen artifact identity; or
- perform an irreversible deletion or migration.

Record a decision only when the answer will govern later work. A one-time
execution approval can remain an explicit owner instruction plus its generated
evidence; it does not need to create a new policy layer unless it changes a
durable boundary.

## Current status and validation

For Trial 001, use
[`trials/first-real-domain/README.md`](../../trials/first-real-domain/README.md)
for the current state, next action, and blockers. Use the Kaggle handoff guide
for the detailed procedure and Decisions 0004–0009 only when their rationale or
frozen identities are needed.

The default handoff check is:

```powershell
python tools\repository_check.py --all
```

Focused commands remain available for faster iteration.

## Research track

Research is conditional. It opens only when repeated engineering evidence
exposes a concrete unresolved question and the owner authorizes that question.
It should return a usable rule, method, or negative result to product
engineering rather than becoming a permanent parallel program.
