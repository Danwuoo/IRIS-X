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
│   └── result.json
├── specialization/
│   ├── configuration.json
│   └── component.json
├── selection/decision.json
├── trial/trial.json
├── deployment/metadata.json
└── known-limitations.json
```

The manifest binds the Domain Specification, workload, requirements, evaluator,
selected configuration, measured result, selection decision, deployment
metadata placeholder, and limitations by exact identity and content digest.
Its artifact table separately records the SHA-256 of every complete file byte
sequence.

Verification is closed-world: every declared file must exist, every byte digest
and document digest must match, all cross-artifact references must agree, and no
undeclared file may be present. A package requires a `promote` decision whose
selected result satisfies the binding rules. Missing, extra, malformed,
substituted, or corrupt content is rejected.

Identical canonical inputs produce identical directory contents. P1 packages
contain no model weights, customer data, external resources, secrets, or real
deployment configuration. The deployment document is an explicit non-deployable
placeholder; production packaging and archive/container formats are deferred.
