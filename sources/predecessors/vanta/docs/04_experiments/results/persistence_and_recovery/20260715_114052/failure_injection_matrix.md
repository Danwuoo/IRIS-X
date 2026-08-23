# Failure-Injection Matrix

Deterministic injection points model durable protocol boundaries. They do
not claim an operating-system process kill was executed.

| Case | Window | Passed | Failed checks | Duration ms |
| --- | --- | ---: | --- | ---: |
| `P006-01` | normal commit then restart | `true` | none | `4154` |
| `P006-02` | crash before Evidence Packet persistence | `true` | none | `2813` |
| `P006-03` | prepared complete before file effect | `true` | none | `2029` |
| `P006-04` | file effect complete before DB commit | `true` | none | `1338` |
| `P006-05` | DB commit complete before client response | `true` | none | `1733` |
| `P006-06` | crash before rollback starts | `true` | none | `1105` |
| `P006-07` | crash during rollback | `true` | none | `1023` |
| `P006-08` | same idempotency key resend | `true` | none | `648` |
| `P006-09` | same key conflicting request | `true` | none | `692` |
| `P006-10` | artifact content corruption | `true` | none | `646` |
| `P006-11` | artifact reference missing | `true` | none | `825` |
| `P006-12` | schema version incompatible | `false` | case_completed | `826` |
| `P006-13` | database busy or locked | `true` | none | `545` |
| `P006-14` | write failure transaction rollback | `true` | none | `94` |
| `P006-15` | incomplete episode discovery | `true` | none | `405` |
| `P006-16` | clean workspace replay | `true` | none | `2120` |
| `P006-17` | structured reversible restart replay | `true` | none | `881` |
| `P006-18` | rejected action not accepted | `true` | none | `1786` |
| `P006-19` | non-accept verifier cannot commit | `true` | none | `427` |
| `P006-20` | unsupported and memory effects remain zero | `true` | none | `527` |
