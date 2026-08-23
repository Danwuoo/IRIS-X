# Evidence Base v1 README

## Purpose

Evidence Base v1 converts Deep Research Round 1 into a traceable, experiment-level research asset. It is designed to show what was observed, under which comparison, with which benchmark, and with which unresolved confounders. It does not select a causal explanation, architecture, roadmap, or winning hypothesis.

## Unit of evidence

One row in `Evidence_Records` is one experiment, comparison, evaluation result, or benchmark-validity result. A paper may generate multiple rows. v1 contains 55 evidence records from 44 source candidates.

## Schema

- `Evidence_Records`: atomic observations, comparison setup, observed result, interpretation layers, confounders, capability interpretation and provenance.
- `Sources`: one row per paper, report, benchmark document or methodological source, linked back to evidence IDs.
- `Benchmarks`: capability interpretation and validity limits for 39 benchmark or evaluation frameworks.
- `Specialization_Taxonomy`: empirical mechanisms observed in the DR corpus; it is not a proposed architecture.
- `Claims`: falsifiable claim registry with supporting, contradicting and context-dependent evidence.
- `Counterexamples`: visible registry of the strongest cases and exactly what each case refutes.
- `Evidence_Gaps`: normalized missing evidence and the resolution type most likely to close each gap.
- `Definitions`: provisional and unstable concepts that must remain distinguishable.

## Interpretation rules

1. Same-backbone gain does not equal contemporary frontier superiority.
2. Benchmark score does not equal demonstrated domain expertise.
3. Model-level specialization does not equal system-level specialization.
4. A cross-generation comparison does not establish superiority over the contemporary frontier.
5. Hybrid results must retain tool, retrieval, environment and inference-compute asymmetries.
6. `Observed_Result`, `Author_Interpretation`, `DR_Synthesis` and `Evidence_Base_Inference` are separate evidence layers.
7. `Unknown`, `Not reported` and `Not verifiable from current source` are preserved rather than imputed.

## Confidence and comparability

- **Evidence confidence** estimates how securely the observation can be reconstructed from the current DR corpus. It is not a paper-quality score.
- **Comparability** estimates whether the recorded comparison isolates a meaningful specialist/generalist contrast.
- A high-profile result may have medium or low comparability when tool access, retrieval, system design, generation or inference compute differ.
- `Frontier_Superiority_Demonstrated = Partial` means the result is relevant but restricted by scope, version or system-level confounding.

## Known limitations

- Primary papers and appendices were not directly re-extracted in this Work task.
- Proprietary model size, training data, post-training and inference details are usually unknown.
- Training and inference compute are frequently missing.
- DR citation handles are preserved, but most URLs/DOIs still require direct source verification.
- Benchmark contamination remains uncertain, especially for public static sets and SWE-bench Verified.
- Finance evidence often lacks verified point-in-time controls.
- Many comparator dates and exact versions remain unresolved.
- Some DR statements are qualitative and therefore retain unknown numeric fields.

## Update protocol

Future research rounds should add new evidence rows, create new source or benchmark IDs, or update provenance/confidence fields after primary-source verification. Existing observations should not be overwritten to fit a later narrative. If an observation is corrected, retain its stable ID, document the correction in the relevant notes/rationale fields, and update linked claims and counterexamples. Candidate explanations must remain hypotheses unless controlled evidence changes their status.
