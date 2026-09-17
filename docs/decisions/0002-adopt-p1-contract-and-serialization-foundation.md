# Decision 0002: Adopt the P1 Contract and Serialization Foundation

Status: Accepted

Date: 2026-09-17

## Context

P1 needs a minimal provider-neutral foundation that can prove exact evidence
binding, offline evaluation and selection, reproducible packaging, and
independent verification without choosing a real domain or backend.

## Decision

IRIS-X uses Python 3.11+, a standard `src/irisx` package, and a console entry
point declared by `pyproject.toml`. The P1 runtime has zero third-party
dependencies. A repository-local, standard-library PEP 517/660 backend builds
editable and regular pure-Python wheels without downloading a build tool. Local
and CI editable installs use `--no-build-isolation`. Because both runtime and
build dependency sets are empty, P1 carries no empty lock file. Adding any
third-party dependency requires a reviewed decision and one repository-wide
lock strategy before merge.

Contracts use strict canonical JSON with SHA-256 content identities. Each
contract separates logical identity, machine schema version, human artifact
version, and exact content digest. Supporting artifacts use the same envelope.
Python standard-library validation is explicit so P1 introduces no schema
framework before a concrete need exists.

The qualification path uses a bounded fixed-lookup adapter and synthetic cases.
It performs no network, provider/model, paid, training, retrieval, or real-domain
execution. Directory-based Domain Packages use a closed-world manifest and
byte-level artifact digests.

## Consequences

The surface is small, installable, cross-platform, deterministic, and directly
auditable. Validation code is intentionally more explicit than a framework-led
implementation. JSON Schema publication, signed manifests, uncertainty models,
multiple-candidate Pareto-front reporting, real adapters, production deployment,
and long-term package transport are deferred until authorized product pressure
justifies them.
