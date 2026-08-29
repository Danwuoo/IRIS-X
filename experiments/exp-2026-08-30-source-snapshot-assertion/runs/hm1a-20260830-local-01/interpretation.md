# H-M1a Interpretation: `hm1a-20260830-local-01`

- **Status:** reviewed valid result
- **Support status:** `Supported — task-local`
- **Code revision executed:** `8188b2a8a6567a2c323617540bc6df56d4971b95`
- **Raw records:** `raw/terminal-records.jsonl`
- **Derived aggregate:** `results.json`

## Directly Observed Result

The run completed 30/30 valid terminal records: five frozen identity cases,
two arms, and three repetitions. The registry was parsed as its actual JSON
encoding rather than inferred from its `.yaml` extension.

| Arm | Valid accepted | Mismatches rejected | Mismatches accepted | False rejection of valid identity |
| --- | ---: | ---: | ---: | ---: |
| `record-only-v0` | 3/3 | 0/12 | 12/12 | 0/3 |
| `registry-assert-v0` | 3/3 | 12/12 | 0/12 | 0/3 |

The treatment rejected the four mismatch types on every repetition with the
expected resolver/assertion reasons: `unknown_source_id`,
`unknown_snapshot_id`, `tree_oid_mismatch`, and
`snapshot_source_relationship_mismatch`. All ten arm/case pairs agreed across
three repetitions. The valid VANTA identity resolved to registered and observed
tree OID `4e095233520418705168f40a556177477839b052` on each treatment repetition.

These observations satisfy every predeclared H-M1a support condition. The
record-only control missed mismatches because it deliberately records rather
than resolves or enforces the relationship.

## Cost and Preservation Observation

The control recorded 685.3701 ms wall and 62.5 ms process CPU across its 15
records; the treatment recorded 342.583 ms wall and 46.875 ms process CPU,
read 421,935 registry bytes, and performed six Git tree lookups. The arms take
different early-exit paths, and the sub-second single-host timings do not
establish a stable speed relationship. Assertion cost at broader workloads is
`Not established`.

The registry hash was unchanged before/after, `sources/` and
`references/papers/` were clean, and no network, model, token/API, credential,
or paid-service use occurred.

## Evidence Boundary

This is deterministic synthetic-challenge and local-registry evidence for a
narrow startup integrity assertion. It does not establish upstream provenance,
complete manifest validity, terminal-record completeness, resource-ledger
completeness, full H-M1, or an IRIS-X architecture invariant.

The supported narrow constraint is: future evidence-producing runs in this
batch should fail closed before measured episodes unless their registered
source ID, active snapshot relationship, and Git source tree at the code commit
resolve and match exactly.
