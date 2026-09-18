# P2 Admission Contract

Status: historical blocked snapshot under
[`Decision 0003`](../decisions/0003-record-p2-admission-block.md), retained by
current
[`Decision 0004`](../decisions/0004-admit-first-p2-arc-agi-2-engineering-trial.md).

## Purpose

The first meaningful P2 result must be a real, bounded vertical slice:

```text
Domain Specification
→ Baseline
→ Specialization
→ Evaluation
→ Selection
→ versioned Domain Package
```

At the time of Decision 0003, the repository did not contain the owner approvals
or real evidence needed to run that slice. The tracked admission package makes
those historical omissions explicit without manufacturing trial results or
changing the provider-neutral P1 contracts. Decision 0004 later selected the
local/offline ARC-AGI-2 path and resolved the policy choices needed to begin its
bounded repository implementation, but did not rewrite this snapshot or
authorize a real model/solver run.

## Admission snapshot

[`trials/p2-admission/admission.json`](../../trials/p2-admission/admission.json)
uses the `irisx/p2-admission` schema version `1.0`. It is a strict,
digest-bound snapshot with exact captured authority-file hashes. Its validator
keeps Decisions 0001–0003 and `PRODUCT_THESIS.md` byte-bound while recognizing
that current `AGENTS.md` is superseded by Decision 0004. It checks:

- the current `admission_blocked` state and admission-only scope;
- the exact, mutually exclusive owner options;
- every required gate and explicit `Unknown` values;
- execution authorization completeness, including provider/model, permitted
  data, budget, retention, and stop conditions when external execution is
  proposed;
- the complete draft mapping to the existing `irisx/engineering-trial`
  contract;
- real-evidence requirements, acceptance criteria, falsifiers, and package
  eligibility; and
- stale or substituted authority references.

Validate it offline from the repository root:

```powershell
python -m irisx admission validate trials/p2-admission/admission.json
```

A valid result confirms that the historical block is represented consistently.
It does not supersede Decision 0004, admit a second trial, or authorize a run.

## Admission rule

Schema version `1.0` accepts only `admission_blocked`. It also requires trial
execution, promotion, and Domain Package eligibility to remain false. This
prevents a re-signed edit from converting the current decision snapshot into
authorization.

Decision 0004 is the later owner decision for the selected local/offline path.
It authorizes creation of real artifacts under the reserved trial directory and
a deliberate implementation and preflight path with exact P1 contract
bindings. Synthetic fixtures, missing provenance or rights, stale references,
an unbound local model/solver, or an absent execution envelope can never satisfy
its run preflight. Real execution remains separately authorization-gated.
