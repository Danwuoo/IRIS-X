# Calibration Custodian Packet

Supply either a fair exact-configuration calibration bundle or an explicit
`P0_unavailable` determination using `calibration-bundle.schema.json`. The
latter is preferable to a straw baseline.

For an available P0, bind the exact producer configuration and score
construction. The score may use only permitted producer/task features and must
exclude D1 warrant, evidence, authority, verifier, and policy labels. Provide
disjoint calibration and held-out split identities, sample size, empirical
diagnostics, and thresholds/loss/coverage rules frozen before held-out
analysis. Self-reported confidence without empirical calibration is
inadmissible.

Do not reuse held-out D1 outcomes. Hash all configuration, score, split,
diagnostic, and threshold assets; declare observed/prohibited information and
dependencies; provide independently reviewable provenance; and seal the
canonical manifest. If fairness or sample adequacy cannot be defended, set
`calibration_status` to `P0_unavailable` and explain why.
