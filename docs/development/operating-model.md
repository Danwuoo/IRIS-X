# Development Operating Model

Status: current repository policy through the first P2 trial admission. See the current
[`Product Scope`](../product/product-scope.md) and
[`Data and Execution Policy`](data-and-execution-policy.md).

## Default track

Product engineering is the default IRIS-X track. Work follows
**Build–Measure–Select**: build the smallest justified candidate, measure it on
the declared workload and constraints, then select, revise, or reject it using
recorded evidence.

The **Engineering Trial** is the empirical unit for product changes. A future
authorized trial must identify its goal, baseline, intervention, workload,
measures, relevant costs, stop conditions, result, and engineering decision.
Creating this policy does not authorize a trial.

## Work authorization and gates

Before work begins, the owner-authorized scope must say what phase or question
is being addressed. Material choices are recorded under `docs/decisions/`.
Provider/model execution, paid services, sensitive data use, and budgeted work
also require the approvals in `data-and-execution-policy.md`.

A normal product cycle is:

1. establish an authorized scope and its undecided boundaries;
2. define the product question and acceptance evidence;
3. prepare the smallest reversible implementation or trial;
4. obtain any data, execution, and budget approvals before external activity;
5. measure against the same declared workload and constraints;
6. record the result, costs, limitations, and selection decision;
7. promote only the artifacts and rules justified by that decision.

## Research track

Research is conditional. It opens only through explicit owner authorization
when repeated engineering failures expose a concrete unresolved question.
Research should preserve uncertainty and return a usable rule, method, or
negative result to product engineering; it does not create an indefinite
parallel program by default.

P1 implements the contract and offline qualification foundation described in
Decision 0002. Decision 0003 and its admission package remain historical
blocked-state evidence. Decision 0004 selects a bounded local/offline
ARC-AGI-2 trial and authorizes its repository implementation, official-source
materialization, offline validation, and preflight work. The concrete local
model/solver and execution envelope remain unbound, and production runtime and
detailed architecture remain undecided. A real P2 model/solver run is not
authorized by the presence of P1 contracts, fixture artifacts, the historical
admission package, or the implementation alone; it requires the separate
explicit authorization and passed preflight specified in Decision 0004.
