# Domain Package Format

Status: minimal extensible P1 package layout.

```text
domain-package/
├── manifest.json
├── domain/specification.json
├── evaluation/
│   ├── workload.json
│   ├── requirements.json
│   ├── evaluator.json
│   ├── cases.json
│   └── results/
│       ├── <baseline-result-id>.json
│       └── <candidate-result-id>.json
├── specialization/
│   ├── configurations/
│   │   ├── <baseline-configuration-id>.json
│   │   └── <candidate-configuration-id>.json
│   └── components/
│       └── <component-id>.json
├── selection/decision.json
├── trial/trial.json
├── deployment/metadata.json
└── known-limitations.json
```

The manifest binds the Domain Specification, workload, requirements, evaluator,
selected configuration, measured result, selection decision, deployment
metadata placeholder, and limitations by exact identity and content digest.
Its artifact table separately records the SHA-256 of every complete file byte
sequence. The package also carries every EvaluationResult named by the
SelectionDecision's `baseline_result_ref`, `considered_result_refs`, and
`eligible_result_refs`, plus every trial configuration and referenced component
needed to interpret those results.

Verification is closed-world: every declared file must exist, every byte digest
and document digest must match, all cross-artifact references must agree, and no
undeclared file may be present. A package requires a `promote` decision whose
selected result satisfies the binding rules. The verifier proves that baseline
is considered, eligible results are a considered subset, each trial
configuration has exactly one considered result, and the selected result binds
the selected configuration. It then recomputes case/segment evidence,
requirements, eligibility, Pareto filtering, and deterministic selection from
the packaged evidence instead of trusting the decision declaration. Missing,
extra, malformed, substituted, or corrupt content is rejected.

Manifest paths use canonical relative POSIX syntax and are resolved beneath the
package root. Backslashes, absolute paths, traversal, and symbolic links are
rejected so verification has the same boundary on Windows and POSIX systems.

Identical canonical inputs produce identical directory contents. P1 packages
contain no model weights, customer data, external resources, secrets, or real
deployment configuration. The deployment document is an explicit non-deployable
placeholder; production packaging and archive/container formats are deferred.
