# Decision 0010: Adopt a lightweight, risk-based development workflow

Date: 2026-09-21
Status: Accepted

## Context

The product direction in `PRODUCT_THESIS.md` remains correct. The development
process became harder than the product problem: routine implementation choices
were repeatedly copied into authority files, operational guides, repository
checks, and new decision records. This increased coordination cost without
improving trial evidence or safety.

The repository still needs strict controls around external execution, sensitive
data, paid resources, frozen evidence identities, and irreversible actions.
Those controls do not justify treating every local, reversible engineering
change as a governance event.

## Decision

IRIS-X keeps **Build–Measure–Select** and adopts two work lanes.

### Routine lane

Work proceeds without a new decision record when it is all of the following:

- within the adopted product and current trial boundaries;
- local, offline, reversible, and covered by proportionate tests;
- free of new providers, paid resources, credentials, or sensitive-data
  disclosure; and
- does not change a frozen artifact identity, public contract, acceptance
  threshold, or promotion claim.

The routine loop is:

1. state one outcome and its acceptance check;
2. build the smallest end-to-end increment;
3. measure it with the narrowest reliable validation;
4. keep, revise, or reject it from the evidence.

### Gated lane

Explicit owner direction is required before work crosses a product boundary,
uses an external provider or paid resource, exposes sensitive data, changes a
frozen identity or public contract, makes a promotion claim, or performs an
irreversible operation. A durable decision record is added only when the choice
will govern future work. Approval is requested at the boundary, not for every
preparatory local edit.

### One current status source

Each active Engineering Trial has one current status page. It states the goal,
current state, next action, acceptance condition, and blockers, and links to
detailed procedures or historical decisions only when needed. Accepted
decision records remain immutable rationale and provenance; README files no
longer need to restate the full decision chain.

For Trial 001, the current status source is
`trials/first-real-domain/README.md` until the Decision 0009 result-closure gate
permits its tracked path to move.

### One default validation entry point

The default repository validation command is:

```powershell
python tools\repository_check.py --all
```

Focused checks remain available during development, but handoff uses the single
entry point.

## Preserved boundaries

This decision changes development process, not product intent or trial
evidence. It preserves:

- the exact bytes of `PRODUCT_THESIS.md`;
- the provider-neutral contracts and package verification rules;
- the historical Decision 0003 admission snapshot;
- the Trial 001 data-isolation, offline-execution, zero-paid-spend, evaluation,
  and acceptance requirements;
- every frozen Decision 0009 `run-001` identity and path; and
- the requirement for a separate explicit owner authorization before a real
  ARC-AGI-2 model/solver run.

## Consequences

- Routine code, test, documentation, and refactoring work no longer needs a new
  decision record or repeated authorization prose.
- Safety and evidence invariants remain machine-checked where practical.
- New decisions are shorter and reserved for durable boundary changes.
- Current operational state is read from the active trial status page rather
  than reconstructed from the entire decision history.
