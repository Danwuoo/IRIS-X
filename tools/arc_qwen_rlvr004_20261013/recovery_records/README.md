# Recovery provenance

The original rescue manifest and 32 final files/records were size/digest-checked
against the supplied archive. `LOCAL-INTEGRATION.json` maps exact recovered bytes
to their initial repository destinations. The five frozen references also match
the new branch's base. Older modules and incomplete transport/test fragments
remain in the original ZIP and ignored extraction directory; they are not
installed as complete production modules.

`historical-operator-evidence/` and `reviews/` contain original records only.
They are historical, not current approval, new test passes or live provider
state. The original package READMEs likewise retain historical scope and old
executor observations. Decision 0072 governs this new local attempt.

`publication_run006/config.py` and its dependent common source were adapted to
official local credential stores only. The missing transport and launcher test,
new local final assembly/acceptance and current release/handoff package are local
reconstructions. Their hashes cannot be claimed as recovered original hashes.
The source rescue ZIP and original contents remain preserved locally; current
validation and review records are separately bound to final bytes.
