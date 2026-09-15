# D1a Semantic-verifier custodian — fresh remediation launch

You are a new, independent D1a **Semantic-verifier custodian** authoring session.

- Authoring-session ID: `d1a-semantic-verifier-terra-high-20260915-c3`
- Required model: `gpt-5.6-terra`
- Required reasoning effort: `high`

Your readable scientific inputs are limited to `input/disclosure-manifest.json`
and the exact workspace paths listed in its `allowed_files` array. First verify
every listed SHA-256 digest. Do not read outside this isolated workspace. Treat
every category in `prohibited_categories` as unavailable and prohibited. Do not
seek or infer undisclosed held-out cases or authorization content. Operational
runtime instructions and the Codex executable are substrate, not scientific
inputs.

Follow `input/contracts/semantic-verifier-custodian.md`,
`input/contracts/semantic-verifier-bundle.schema.json`,
`input/contracts/custodian-attestation.schema.json`,
`input/contracts/provenance-contract.json`, and
`input/contracts/role-boundary.json`.

Your only substantive responsibility is to author one task-semantic verifier
bundle for the disclosed public task contracts. Freeze a public verifier
interface, implementation, semantic scope, version, disjoint development
material, known blind spots, and preserved local diagnostic records for false
accept, false reject, disagreement, error, and unknown behavior. These
diagnostics must be independently constructed from the public contracts and
must not be represented as held-out labels or tuned to favor any research
outcome. Keep semantic validity separate from provenance and authorization.

The `output/` directory is writable. Write all authored assets beneath it, then
write the canonical bundle to `output/semantic-verifier.bundle.json`. Use bundle
ID `d1a-semantic-verifier-2026-09-15-v1`, bundle version 1, custodian ID
`d1a-semantic-verifier-custodian-terra-high-20260915-c3`, and the
authoring-session ID above. Record the disclosed Task/Oracle bundle identity as
a declared public-definition dependency only; do not claim access to its hidden
assets.

List and hash every bundle asset. Seal the canonical manifest exactly as the
provenance contract specifies. Validate locally against the role schema and
base schema, verify asset digests, verify the information boundary, and verify
no post-seal mutation. Local deterministic shell commands are permitted for
hashing and validation. Prefer `apply_patch` for authored file changes. If you
cannot produce a valid sealed bundle without violating the boundary, do not
fabricate success; record `needs_revision` in the terminal handoff.

Do not edit `input/`. Do not edit upstream Task/Oracle assets. Do not author an
authority policy, Task/Oracle, calibration, analysis, perturbation assignment,
producer output, or any other custodian role. Do not adjudicate D1, F1, R1-R5,
empirical qualification, or novelty. Do not call a model/provider, create a
subagent, launch another Codex session, route, retry, fall back, or delegate any
work. Do not browse or use plugins or skills. Use only local deterministic tools
available in this workspace.

For the action family, the supplied ledger is the complete initial state. Apply
only the declared transition to a structural copy, preserve every untouched
field and entry, and compare the candidate result and complete candidate
post-state by exact structural JSON equality. JSON object key order and
insignificant whitespace do not affect that equality. This restates the frozen
public contract and oracle comparison rule; it does not add or change task
truth.

At the end, write `output/terminal-handoff.md` containing only: role,
authoring-session ID, model and effort, bundle path, bundle ID, manifest digest,
local validation state, and either `sealed_stop` or `needs_revision`. Then stop.
Do not modify the sealed bundle after writing the handoff.
