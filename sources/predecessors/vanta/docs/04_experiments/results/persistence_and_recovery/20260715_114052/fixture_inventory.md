# Fixture Inventory

The measured frame contains 20 deterministic persistence/recovery cases over
fixture-local Document Ops workspaces. Scratch SQLite databases and copied
workspaces are temporary; compact result artifacts in this directory are the
retained evidence.

| Case | Fixture / injection | Passed |
| --- | --- | ---: |
| `P006-01` | normal commit then restart | `true` |
| `P006-02` | crash before Evidence Packet persistence | `true` |
| `P006-03` | prepared complete before file effect | `true` |
| `P006-04` | file effect complete before DB commit | `true` |
| `P006-05` | DB commit complete before client response | `true` |
| `P006-06` | crash before rollback starts | `true` |
| `P006-07` | crash during rollback | `true` |
| `P006-08` | same idempotency key resend | `true` |
| `P006-09` | same key conflicting request | `true` |
| `P006-10` | artifact content corruption | `true` |
| `P006-11` | artifact reference missing | `true` |
| `P006-12` | schema version incompatible | `false` |
| `P006-13` | database busy or locked | `true` |
| `P006-14` | write failure transaction rollback | `true` |
| `P006-15` | incomplete episode discovery | `true` |
| `P006-16` | clean workspace replay | `true` |
| `P006-17` | structured reversible restart replay | `true` |
| `P006-18` | rejected action not accepted | `true` |
| `P006-19` | non-accept verifier cannot commit | `true` |
| `P006-20` | unsupported and memory effects remain zero | `true` |
