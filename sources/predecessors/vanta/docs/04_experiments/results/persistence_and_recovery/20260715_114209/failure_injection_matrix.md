# Failure-Injection Matrix

Deterministic injection points model durable protocol boundaries. They do
not claim an operating-system process kill was executed.

| Case | Window | Passed | Failed checks | Duration ms |
| --- | --- | ---: | --- | ---: |
| `P006-01` | normal commit then restart | `true` | none | `5613` |
| `P006-02` | crash before Evidence Packet persistence | `true` | none | `1098` |
| `P006-03` | prepared complete before file effect | `true` | none | `1869` |
| `P006-04` | file effect complete before DB commit | `true` | none | `2040` |
| `P006-05` | DB commit complete before client response | `true` | none | `822` |
| `P006-06` | crash before rollback starts | `true` | none | `4298` |
| `P006-07` | crash during rollback | `true` | none | `698` |
| `P006-08` | same idempotency key resend | `true` | none | `146` |
| `P006-09` | same key conflicting request | `true` | none | `246` |
| `P006-10` | artifact content corruption | `true` | none | `116` |
| `P006-11` | artifact reference missing | `true` | none | `161` |
| `P006-12` | schema version incompatible | `true` | none | `90` |
| `P006-13` | database busy or locked | `true` | none | `140` |
| `P006-14` | write failure transaction rollback | `true` | none | `108` |
| `P006-15` | incomplete episode discovery | `true` | none | `375` |
| `P006-16` | clean workspace replay | `true` | none | `511` |
| `P006-17` | structured reversible restart replay | `true` | none | `604` |
| `P006-18` | rejected action not accepted | `true` | none | `354` |
| `P006-19` | non-accept verifier cannot commit | `true` | none | `55` |
| `P006-20` | unsupported and memory effects remain zero | `true` | none | `58` |
