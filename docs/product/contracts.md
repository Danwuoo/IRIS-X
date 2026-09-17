# P1 Product Contracts

Status: active P1 contract definition. The implementation is in
`src/irisx/contracts.py`; canonical JSON uses schema version `1.0`.

## Common envelope

Every contract has exactly six top-level fields:

| Field | Meaning |
| --- | --- |
| `schema` | Contract family, such as `irisx/domain-specification` |
| `schema_version` | Machine schema version; P1 accepts `1.0` |
| `artifact_id` | Stable logical identity, independent of bytes |
| `version` | Human semantic version of the artifact |
| `content_digest` | SHA-256 of the canonical envelope without this field |
| `payload` | Family-specific fields |

Canonical JSON is UTF-8, sorted by object key, compact, finite-number-only, and
newline-terminated when written. Unknown fields, unsupported schema versions,
malformed identifiers, non-finite numbers, and digest mismatches fail closed.
An artifact reference contains `kind`, `artifact_id`, `version`, and
`content_digest`; all four must match the target.

Source material is represented by an explicit `source_id`, media type, exact
content digest, and bounded logical locator. Contracts do not embed arbitrary
domain datasets. Source locators and package artifact paths are canonical,
relative POSIX logical paths: backslashes, drive/absolute paths, empty or dot
segments, repeated separators, and `..` traversal are invalid. Any locator used
for filesystem access is resolved and checked to remain inside its declared
root.

## Contract families

| Contract | Required payload boundary |
| --- | --- |
| `DomainSpecification` | Name, description, material references, exact workload and requirement references, operating constraints, known limitations |
| `WorkloadDefinition` | Frozen case identities, segments, criticality, input/expected source references, exact evaluator reference |
| `RequirementSet` | Requirements with metric, comparator, threshold, unit, hard/soft flag, and satisfy/minimize/maximize objective |
| `CandidateConfiguration` | Name, optional technique-neutral components, complexity, maintainability, limitations |
| `EngineeringTrial` | Goal, qualification flag, and exact specification/workload/requirements/evaluator/baseline/candidate references |
| `EvaluationResult` | Exact trial/workload/evaluator/configuration references, individual cases, metrics, resource use, limitations |
| `SelectionDecision` | Promote/no-promotion/infeasible outcome, all considered and eligible results, exact selected evidence when promoted, rationale and tie-break rule |
| `DomainPackageManifest` | Exact product/evaluation/selection/deployment references, limitations, and byte digests for every declared package artifact |

Configuration components may independently reference `model`,
`prompts_programs`, `context_retrieval`, `workflow_control`, `adaptation`, and
`validation` artifacts. No component is universally mandatory; the P1 fixture
uses only bounded workflow and validation artifacts.

## Evidence and selection semantics

Numeric evidence has one of three explicit states: `observed`, `unknown`, or
`not_evaluated`. Only `observed` carries a numeric value, so an observed zero
cannot be confused with missing evidence. A missing or non-observed hard metric
does not satisfy its requirement. Measurement units are part of the evidence:
an observation whose unit differs from the RequirementSet unit is not compared,
cannot satisfy a hard requirement, and cannot establish Pareto dominance.

For case evidence, `critical_failure` is derived from the frozen
`WorkloadDefinition` (`case.critical` and `outcome.passed`), never trusted as an
independent claim. Overall accuracy, critical-failure count, case score, and all
declared segment accuracy aggregates are recomputed from individual outcomes;
missing or forged derived evidence fails closed.

Hard requirements gate eligibility. Soft requirements and declared objectives
guide selection without collapsing quality, critical failures, latency,
monetary/resource cost, complexity, maintainability, and operating constraints
into one compulsory score. P1 compares declared scalar objectives by Pareto
dominance and uses lexical configuration identity as the deterministic final
tie-break. The contract can record a retained eligible set even when no
promotion occurs.

Results are comparable only when their exact trial, frozen workload, and
evaluator references agree. The selected result must be eligible and must bind
the selected configuration. Stale, substituted, cross-run, missing, or unknown
hard evidence fails closed.

## P2 extension rule

A future real domain should supply new artifacts and references using these
families. Fixture identifiers, lookup behavior, case count, and metrics are not
production defaults. If a real-domain need cannot be expressed, change the
schema deliberately through a versioned decision and migration tests; do not
silently add optional fields or reinterpret an existing field.
