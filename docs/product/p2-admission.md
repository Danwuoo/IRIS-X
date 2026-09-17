# P2 Admission Contract

Status: current, admission-blocked under
[`Decision 0003`](../decisions/0003-record-p2-admission-block.md).

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

The repository does not yet contain the owner approvals or real evidence needed
to run that slice. The tracked admission package makes those omissions explicit
without manufacturing trial results or changing the provider-neutral P1
contracts.

## Admission snapshot

[`trials/p2-admission/admission.json`](../../trials/p2-admission/admission.json)
uses the `irisx/p2-admission` schema version `1.0`. It is a strict,
digest-bound snapshot with exact local authority-file hashes. Its validator
checks:

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

A valid result confirms that the block is represented consistently. It does
not admit or run a trial.

## Admission rule

Schema version `1.0` accepts only `admission_blocked`. It also requires trial
execution, promotion, and Domain Package eligibility to remain false. This
prevents a re-signed edit from converting the current decision snapshot into
authorization.

After a later owner decision resolves the required inputs, record that scope
in a new decision, create the real artifacts under the reserved trial
directory, validate their exact P1 contract bindings, and only then implement a
deliberate real-trial execution path. Synthetic fixtures, missing provenance or
rights, stale references, an unnamed provider/model, or an absent budget can
never satisfy P2 admission.
