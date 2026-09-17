# Decision 0003: Record P2 Admission Block

Status: Accepted

Date: 2026-09-17

## Context

The owner authorized the start of P2 repository work against `origin/main` and
required an admission check before any real Engineering Trial. The current
authority set still does not identify an owner-approved real domain or
workload, data rights and provenance, baseline, specialization intervention,
evaluation thresholds, provider/model, budget, or deployment target.

The P1 qualification fixture is synthetic by design. It cannot be reclassified
as real P2 evidence, and its successful package is not evidence that the
near-term validation objective in `PRODUCT_THESIS.md` has been achieved.

## Decision

P2 is **admission-blocked**. The authorized implementation scope is limited to
an owner-decision-ready admission package, its deterministic offline validator
and CLI entry point, documentation, and positive and negative tests. No real
Engineering Trial is admitted or executed by this decision.

The admission package at [`../../trials/p2-admission/`](../../trials/p2-admission/)
records:

- the exact readiness gaps and their `Unknown` state;
- three mutually exclusive owner choices: a local/offline real-domain path, an
  explicitly authorized external-provider path, or deferral;
- a complete first-trial draft mapped to the existing provider-neutral P1
  contracts;
- acceptance criteria, falsifiers, stop conditions, and the intended real-trial
  directory;
- explicit ineligibility for execution, promotion, and Domain Package claims.

The admission artifact is a digest-bound decision snapshot, not an
authorization token. It deliberately cannot be changed from
`admission_blocked` to ready under schema version `1.0`. A later owner decision
must name the selected option and resolve the necessary gates in a new current
decision before trial inputs or execution can be admitted.

## Owner decisions required

The owner must either defer P2 or select one execution path and supply or
approve all information required by that path. At minimum, an admitted trial
requires the real domain and representative frozen workload, source provenance
and rights, a baseline, a candidate intervention, evaluator and acceptance
thresholds, stop conditions, and a deployment target. External execution also
requires the exact provider/model, permitted data classes, maximum budget,
retention behavior, and approval evidence required by the data and execution
policy.

## Consequences

- P0 archive identities and `PRODUCT_THESIS.md` bytes remain unchanged.
- The P1 contract, qualification, selection, and package guarantees remain in
  force and are not generalized into a real-domain runtime.
- No network/provider/paid/sensitive-data execution, P3/P4 work, production
  runtime, deployment, or real Domain Package is authorized.
- Files in `trials/p2-admission/` are planning and admission evidence only;
  they are not Engineering Trial results.
