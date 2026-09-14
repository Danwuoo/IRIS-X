# Semantic-Verifier Custodian Packet

Supply a task-semantic verifier using `semantic-verifier-bundle.schema.json`.
Its authoring identity/session must be distinct from the task/oracle custodian
for any intended F1-C claim. Code-process separation, a new prompt, or a new
function name is insufficient.

Freeze the public semantic interface, implementation, version, digest,
development material, and known blind spots. Development material must be
disjoint from held-out cases. Before freeze, do not observe held-out oracle
labels, authority maps, evidence/authority perturbation labels, or comparator
outputs. Provenance or authorization may not be silently absorbed into
"semantics" unless the task contract truly makes it semantic; such tasks cannot
identify R2 versus R4 and must be quarantined.

Include preserved examples or records for false accept, false reject,
disagreement, error, and unknown. These are competence diagnostics, not labels
stipulated to favor F1. Hash all assets, declare dependencies and forbidden
information, provide independently reviewable authorship/access evidence, and
seal without post-seal mutation.
