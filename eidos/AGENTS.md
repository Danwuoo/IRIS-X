# Eidos Agent Contract

This file applies to the entire repository.

## Start Here

1. Read `eidos.yaml` for the machine-readable project and documentation entry points.
2. Read `docs/index.json` to discover governed documents.
3. Load only the governed YAML records relevant to the task.
4. Treat files absent from the generated index as non-normative background unless this file says otherwise.

The existing Chinese ARC concept note is early background material. It is not an approved project charter, architecture, roadmap, specification, decision, or experiment record.

## Documentation Contract

- Governed documents are YAML files under the records directory configured in `eidos.yaml`.
- Every governed document MUST conform to `docs/schema/document.schema.json`.
- `docs/index.json` is generated output. Never edit it by hand.
- Stable document IDs and published record paths MUST NOT be reused for unrelated documents.
- Relationships MUST reference existing governed document IDs.
- A proposal, experiment, or note is non-normative regardless of its wording.
- Draft documents are not binding. Only statuses defined as normative by the validator may create current authority.
- Do not silently resolve conflicts between normative documents. Report the conflicting IDs and stop work affected by the conflict.
- Preserve provenance: an idea derived from a note or experiment MUST declare that relationship instead of presenting the idea as an established requirement.

## Change Workflow

When adding or changing governed documentation:

1. Create or edit the YAML record, using a new stable ID when it is a new document.
2. Keep requirements, objectives, decisions, questions, and metrics as structured fields with stable local IDs where applicable.
3. Run `python -m tools.docs.build_index`.
4. Run `python -m tools.docs.validate`.
5. Run `python -m unittest discover -s tests -v` when changing schemas or documentation tooling.
6. Include the record and regenerated index in the same change.

Do not create Markdown versions of governed RFCs, decisions, specifications, experiments, or project records. Markdown is reserved for this contract, the short human README, and exceptional narrative or archived source material.

## Repository Work

- Make the smallest change that satisfies the active task.
- Do not promote statements from background material into binding requirements without an explicit governed document and appropriate status.
- Verify current technical claims from primary sources before relying on them in research or design records.
- Keep generated artifacts deterministic and exclude timestamps unless they are semantically required.

