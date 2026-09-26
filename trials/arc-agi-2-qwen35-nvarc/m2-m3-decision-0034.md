# Decision 0034 restart submission record

Status: local preparation complete; submission receipts pending.

The owner reported stopping both Decision 0033 sessions and requested two
restarts without monitoring. [Decision 0034](../../docs/decisions/0034-restart-nvarc-without-monitoring.md)
authorizes one private submission each, with no Dataset mutation or result
retrieval. The existing heartbeat remains PAUSED.

| Binding | M2 source-cont-002 | M3 teacher-small-005 |
| --- | --- | --- |
| Plan SHA-256 | `c1e9ac165a83783b1ba916fb39a170a58f9550b60b9d99c55951e1d06b544dda` | `f9a405423a955e35350f83cb898caeaafcb67a8b5ccdca77ed7f890459393234` |
| Notebook SHA-256 | `1b30af202b4f4908caad86d6a91668ed1c07ac84eedce7a53e172258c8524604` | `b51a21580f440f49b8f12f84f1450516f7e84bb061597fe464a9675025255073` |
| Metadata SHA-256 | `37b6b6b2a8094b351dca3f0f412c9f7ec55d1efa1918aec5f747c98984f36530` | `697699533e36d13b2730e9ecd6083d482ca4883ed72187b1ee7764ed36f05e54` |

Both packages use runtime wheel SHA-256
`639b0c866371ef843adcac7fcc3288a46bb35ec496d7592e91ace53b512c11d9`.
Comparison with the retained approved packages verified identical source
configuration, visible task, training lineage, pinned source bundle, teacher
seed, prompts and dependency/model manifests. The only changed wheel members
are the two runtime identity guards and the wheel RECORD. New plans change
identity/decision and set output retrieval allowance to zero; M2 also sets
Dataset mutation allowance to zero. Model work and token/step caps are unchanged.

Both offline package preflights passed. The restart regression rejects reuse
of the previous decision and confirms unchanged workload/template bodies.
No model or provider call was made by these checks.
Full repository validation passed 220 tests with four existing optional skips;
the final documentation/layout check also passed.

Generated packages, preflights, comparison report and the atomic execution
ledger are retained under `.irisx/arc-agi-2/qwen35-nvarc/m2-m3/`.
Submission is not evidence of runtime success, accepted SDG pairs or parity.
