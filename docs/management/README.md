# Repository management

Start with [the document entry](../README.md), then the generated [BOARD](BOARD.md)
and a task in [tasks/](tasks/). The [development plan](../plan/2026-10-14-workstream-pr2-pr4-local-development.md)
defines the three provisional stacked stages. This system records engineering
work across core, ARC-AGI-2 and line-b; it does not grant execution authority.

## Sources of truth

| Fact | Canonical source |
| --- | --- |
| Document content | The referenced Markdown document |
| Document kind, lifecycle and relationships | [documents.json](documents.json) |
| Task state, dependencies and writable scope | One JSON record in tasks/ |
| Code identity | Git commit |
| Test observations | A named report under docs/verification/ or linked CI |
| Human independent acceptance | A separately sourced, commit-bound review |

BOARD is a generated view; never edit its states by hand. Workstream STATUS
documents describe scope, evidence and limitations, and link to the board rather
than copying task progress. The workstream registry stays a navigation index.

## Routine task loop

1. Read the applicable AGENTS, selected STATUS and canonical plan. Use the
   [task template](templates/task-record.md) to create one bounded task.
2. Register each new or changed active document in documents.json. Use a local
   repository path, or a GitHub blob URL pinned to a full 40-character commit.
   List explicit writable path globs; metadata never contains executable commands.
3. Move planned to in_progress, work within the recorded scope, then run the
   checks below and the selected engineering checks. Keep raw logs and temporary
   outputs in the ignored workstream output root.
4. Commit the implementation checkpoint before writing a handoff. Bind its
   report to that checkpoint; use the [developer handoff template](templates/developer-handoff.md).
   Register the handoff, set implementation_commit and handoff_ref, and move to
   review_ready. Commit handoff and metadata separately.
5. Record the resulting delivery SHA in the delivery summary. The next stacked
   stage's base_commit is this delivery SHA, so it includes the upstream handoff.
   Do not require a report to contain its own commit SHA.
6. Return the branch, code/delivery SHAs, Draft PR and handoff to the original
   ChatGPT conversation. Developer and implementing subagent checks are self-review.

The state vocabulary is planned, in_progress, review_ready, verified, blocked
and changes_requested. A blocked task names its blockers and may return to
in_progress. A reviewer can request changes. verified needs an independent
review of the implementation_commit and records any limitations visibly; it
does not mean merged, scientifically effective, deployed or GPU-validated.
Use the [independent review template](templates/independent-review.md) only when
an actual independently sourced review exists. Retain superseded reviews as
historical evidence after a new code, test, dependency or CI change.

## Local commands

Run from the repository root:

```sh
python tools/dev.py status
python tools/dev.py check
python tools/dev.py render --check
python tools/dev.py context --task WSF-02
```

check and render --check are read-only. After an intentional metadata edit,
`python tools/dev.py render` updates only the marked generated board. The
validator rejects duplicate keys/IDs, unsafe or linked paths, missing and
unregistered active documents, dangling references, unknown fields, invalid
states, dependency cycles, overlapping concurrently writable scopes, stale
board output and verified tasks without a valid independent review reference.
Structural validation does not attest that a human review's conclusions are
correct or that a remote URL is available; the independent conversation checks
those sources separately.

Controlled suite selection uses `python tools/dev.py verify --suite ...`;
its static inventory and named reports do not replace the full historical
`python tools/repository_check.py --all` entry or make existing failures pass.
Use [test guidance](../../tests/README.md) for the implemented suites.

## Research and historical material

The [ARC research entry](../workstreams/arc-agi-2/RESEARCH.md), R1â€“R5 and key
results are individually cataloged. Their lifecycle status describes document
use, not scientific validity. Distinct architecture and training A/B/C
comparisons, denominators, results, limitations and unanswered hypotheses retain
their own source identities. Dates or run008 engineering failures alone do not
supersede research direction. Supersedes is empty unless the original source
establishes an explicit replacement relationship.

Legacy indexes cover the retained large historical collections at fixed Git
commits. They avoid rewriting frozen documents or inventing missing inputs.
Following an index is a source-reading operation, never an instruction to resume
Kaggle, download models or evaluator inputs, or reuse consumed run authority.
