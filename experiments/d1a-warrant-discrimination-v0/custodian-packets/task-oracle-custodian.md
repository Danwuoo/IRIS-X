# Task/Oracle Custodian Packet

You are supplying an independently authored D1a task/oracle bundle, not an F1
policy or verifier. Use `task-oracle-bundle.schema.json` and produce a new,
sealed bundle outside `meta-fixtures/`.

Supply at least two bounded task families with stable family and instance IDs,
task contracts, permitted initial/post-state observations, and semantic or
post-state oracle rules. Freeze those rules before the perturbation implementer
receives them. Neither tasks nor oracles may depend on evidence/authority
assignments, future comparator decisions, or held-out producer outputs.

Keep task truth, `actual_outcome`, consequential `action_outcome`, and
authorization state separate. If the future study is intended to address F1-D,
include at least one reversible but consequential action family with a
predeclared post-state/utility oracle. Otherwise declare
`not_intended_for_F1_D`; do not imply agency relevance.

List every asset path and SHA-256 digest. Record observed, unobserved, declared,
and prohibited dependencies; include an independently reviewable authoring or
access record; seal the canonical manifest; and make no post-seal mutation.
Secrets are neither required nor permitted in provenance identity.

Do not author the authority policy, semantic verifier, calibration thresholds,
or analysis interpretation. A different directory or process name is not
independent authorship.
