# Decision 0001: Separate Imported Corpus By Preservation Boundary

- **Status:** Accepted for repository organization
- **Date:** 2026-08-24
- **Scope:** Filesystem organization only

## Decision

Imported predecessor trees live under `sources/predecessors/`, external reference trees under `sources/external/`, and paper artifacts under `references/papers/`. IRIS-X-authored work has separate `research/`, `experiments/`, `docs/`, and `tools/` boundaries.

## Reasons

Physical location now communicates preservation expectations before an agent opens any file. This reduces accidental edits, makes inventory/classification checks mechanical, and keeps research writing separate from immutable evidence.

## Boundaries

This decision does not choose an architecture, runtime, dependency, ontology, or research question. Imported leaf names are retained to avoid combining relocation with renaming. Original import paths and Git identities remain in the corpus registries.
