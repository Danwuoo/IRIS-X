# Contradiction Map v1

## 1. Executive Summary

Contradiction Map v1 identifies **14** evidence-linked contradiction or tension records across the current corpus. **0** qualify as established or probable direct empirical contradictions. **10** are best interpreted as scope-, measurement-, category-, temporal- or comparison-dependent rather than genuine contradictions. **4** remain unresolved because the available evidence is not comparable or verified enough to adjudicate them.

The absence of an established CT1 direct contradiction is itself informative, but it is not evidence of scientific consistency. It mainly reflects weak matched comparisons: 39 of 55 Evidence Base records are below High comparability, comparator versions are frequently unknown, and system-resource parity is usually absent.

## 2. Most Important Finding About the Original Puzzle

The original puzzle is not one empirical phenomenon. The strongest structural result is a required split between:

1. **model-level specialization** — changes to model parameters that often improve the adapted base but less often establish broad contemporary frontier superiority; and
2. **system-level specialization** — retrieval, tools, search, workflow control, environment design or verification that can produce strong bounded counterexamples even with a non-frontier base.

The same phrase, “specialized system,” currently covers both. Until they are separated, a model-level frontier gap can appear to contradict a system-level win even though the evidence units, resources and measured capabilities differ.

## 3. Major Contradictions and Tensions

### T0001 — Relative gain versus absolute frontier superiority

- **Position A:** domain adaptation frequently improves the same or closely related base (E0001, E0015–E0016, E0029, E0031).
- **Position B:** stronger or later frontier generalists often remain ahead (E0003, E0013–E0014, E0025, E0033–E0034).
- **Assessment:** not a genuine contradiction. Both can be true because they use different reference points.
- **Boundary:** same-backbone bounded evaluation versus strongest contemporary comparator.
- **Uncertainty:** how frequently matched specialization closes the frontier gap remains unresolved.

### T0002 — Model-level scarcity versus system-level success

- **Position A:** broad model-level specialist frontier dominance appears uncommon.
- **Position B:** PaperQA2, Aviary and formal mathematics systems provide strong bounded system-level counterexamples (E0041, E0044–E0047).
- **Assessment:** specialization-level divergence, not direct contradiction.
- **Boundary:** weights alone versus full capability system with tools, retrieval, environment and inference compute.
- **Uncertainty:** matched component ablations are missing.

### T0003 — Benchmark leadership versus workflow advantage

- **Position A:** generalists lead many domain-labeled benchmark comparisons.
- **Position B:** specialized systems appear stronger more often on workflow-heavy tasks.
- **Assessment:** primarily a measurement conflict. LegalBench, MCQ medicine and short code tasks do not measure the same capabilities as filing research, literature synthesis or repository execution.
- **Boundary:** benchmark proxy versus professional workflow fidelity.
- **Uncertainty:** there are almost no paired evaluations of the same systems across both constructs.

### T0004 — Narrow wins versus broad-domain weakness

- **Position A:** BERTimbau-LoRA, Legal-BERT/Contracts-BERT and Code Llama-Python show that narrow specialization can offset a large parameter disadvantage (E0018–E0019, E0029).
- **Position B:** broad legal, finance and coding comparisons more often favor generalists.
- **Assessment:** scope-conditioned divergence.
- **Boundary:** fixed-label or short synthesis task versus broad task family, workflow or OOD transfer.
- **Uncertainty:** cross-task durability is largely unmeasured.

### T0005 — Specialist success versus frontier drift

- **Position A:** specialists beat named comparator versions at particular snapshots.
- **Position B:** later frontier generations overtake those results.
- **Assessment:** temporal/frontier drift. A dated claim is not inconsistent with a later ranking.
- **Boundary:** explicit evaluation date, comparator version and persistence window.
- **Uncertainty:** many exact versions and dates are missing.

### T0006 — Binary category versus hybrid systems

- **Position A:** the literature often narrates specialist and generalist as mutually exclusive classes.
- **Position B:** many evaluated systems combine a general backbone with specialized components (E0006, E0022–E0023, E0031–E0032, E0041, E0044, E0047–E0048).
- **Assessment:** definition mismatch.
- **Boundary:** model identity versus deployable capability-system boundary.
- **Uncertainty:** component contribution remains unmeasured even after the category is repaired.

### T0007 — Author-linked wins versus broader evaluation

- **Position A:** MMedIns, SaulLM and FinTral report frontier-level wins in closely linked evaluation contexts (E0009, E0017, E0022–E0023).
- **Position B:** broader, newer or independent comparisons show weaker specialist dominance.
- **Assessment:** unresolved.
- **Boundary:** benchmark ownership, task sampling, prompt protocol, comparator date and independent replication.
- **Uncertainty:** none of these high-impact claims has independent replication in Evidence Base v1.

## 4. Contradictions That Disappear After Conditioning

The following apparent conflicts cease to be contradictions once the comparison is conditioned correctly:

- **Relative versus absolute comparison (K0001):** improving a base is compatible with remaining below a stronger frontier model.
- **Model versus system specialization (K0002):** PaperQA2 or Aviary does not show that domain-adapted weights alone beat generalists.
- **Benchmark versus workflow (K0003, K0011):** a model may lead on MCQ or short tasks and still fail on retrieval, evidence integration or procedure.
- **Narrow versus broad task scope (K0004, K0008):** a classifier or short-code specialist can win without demonstrating broad domain expertise.
- **Cross-generation ranking (K0005):** an older specialist win and a later generalist lead can both be correct.
- **Binary versus hybrid category (K0006):** a general backbone may be part of a specialized capability system.
- **Workflow tools versus model-only wins (K0012):** tools can be central for workflows without being necessary for bounded benchmark wins.
- **Ranking versus validity warning (K0014):** contamination or temporal leakage qualifies the ranking; it is not an opposite capability result.

## 5. Genuine or Potentially Genuine Contradictions

No evidence pair currently meets the standard for a High- or Medium-confidence **CT1 direct empirical contradiction** under substantially similar conditions.

Four conflicts remain potentially genuine but unresolved:

1. **K0007 — Medicine:** MMedIns frontier-win claims versus aggregate medical and newer clinical-tool/generalist comparisons.
2. **K0009 — Finance:** finance specialist gains versus newer generalist leadership and temporal-validity concerns.
3. **K0010 — Coding:** SWE-RL/code-specialist gains versus later frontier leadership on an increasingly contaminated benchmark.
4. **K0013 — Replication:** specialist wins in author-linked evaluations versus weaker dominance in broader or independent settings.

These are not classified as genuine because benchmark, generation, system boundary, access and protocol differences remain too large.

## 6. Boundary Conditions Emerging from the Evidence

The strongest descriptive boundaries are:

- **Model versus system specialization:** the most consequential split.
- **Narrow versus broad task distribution:** narrow classification and short synthesis produce the clearest model-level wins.
- **Benchmark proxy versus workflow capability:** rankings differ as retrieval, procedure and execution become central.
- **Older versus contemporary frontier:** superiority is time-indexed.
- **Weak versus strong backbone:** adaptation gains do not imply frontier-gap closure.
- **Matched versus unmatched tools/retrieval/inference compute:** the matched condition is largely missing.
- **Author-built versus independently replicated evaluation:** several high-impact counterexamples remain provisional.
- **In-distribution versus OOD:** durable transfer is not established.
- **Public/static versus exposure-controlled benchmark:** contamination and temporal leakage alter interpretability.

These are descriptive patterns or hypotheses about moderators, not causal laws.

## 7. Problem Definition Stress Test

### Remains stable

- Same-backbone specialization gains are a recurring observation.
- Leaderboard dominance alone cannot establish intrinsic superiority of general-purpose learning.
- The prevalence of specialist frontier dominance is still uncertain.
- Benchmark validity and comparison asymmetry are central research questions.

### Needs narrowing

- “Rarely forms absolute superiority” is most defensible for **model-level specialization on broad contemporary comparisons**, not for every capability system.
- “Stable” and “contemporary” need explicit time windows and comparator-version rules.
- “Generalizable” needs an OOD or held-out task-family criterion.

### Requires terminology separation

- Relative gain versus absolute frontier superiority.
- Benchmark proxy versus professional workflow capability.
- Narrow task solver versus broad domain specialist.
- General-purpose model versus general-purpose system configuration.

### Requires unit-of-analysis separation

- Model-level, system-level, hybrid and formal/narrow solver specialization.

### Remains unresolved

- Whether specialization is an independent scaling axis.
- Whether high-resource model-level specialization can reliably close the contemporary frontier gap.
- Whether the strongest counterexamples replicate independently and persist over time.

The current Problem Definition should not yet be replaced. The **Problem_Definition_Impact** sheet records revision directions without drafting a new definition.

## 8. Highest-Priority Unresolved Conflicts

1. **Medical frontier counterexample (K0007):** independently reproduce MMedIns under current comparators and shared clinical workflow tasks.
2. **Finance temporal validity (K0009):** run point-in-time, matched-access comparisons.
3. **Coding benchmark validity (K0010):** use fresh private or time-split repository tasks with a matched scaffold and rollout budget.
4. **Independent replication of author-linked wins (K0013):** verify MMedIns, SaulLM and FinTral with exact versions, prompts and task-level results.

These four conflicts should directly shape Deep Research Round 2. The **DR2_Question_Candidates** sheet contains discriminating questions, not answers or a finished DR2 prompt.

## 9. Primary-Source Verification Warning

Evidence Base v1 normalized Deep Research Round 1; it did **not** directly re-extract the experimental corpus from primary papers and appendices. Contradiction Map v1 therefore maps the structure of the current evidence, not final scientific truth.

The conclusions most sensitive to this limitation are:

- MMedIns-Llama 3 versus GPT-4/Claude-3.5 (E0009);
- the unidentified clinical specialist-tools comparison (E0012);
- SaulLM versus GPT-4/Llama 3-70B (E0017);
- FinTral versus GPT-4 (E0023);
- SWE-RL versus GPT-4o and later frontier systems (E0032–E0035);
- PaperQA2 and Aviary system-level advantages (E0041–E0046);
- AlphaProof/AlphaGeometry 2 and Gemini Deep Think inference budgets (E0047–E0048).

Until those records are re-extracted and key comparisons are independently reproduced, the map should be used to prioritize verification and design discriminating research—not to declare why specialization succeeds or fails.
