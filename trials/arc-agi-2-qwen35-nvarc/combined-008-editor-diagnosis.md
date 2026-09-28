# Combined 008 owner-Editor diagnosis

The owner supplied `結果.zip` from a manually started combined 008 Editor
session. The ZIP SHA-256 is
`abc039ed6e4f3c8b613988a53eaf634de26d7f1f19b65e3f34791f9ac36fdb52`.
Its CRC, all 40 listed member digests, the exact Decision 0042 plan digest
`sha256:f8644274acac94f860839b1c93c2ddf54e82dd1ccdbc906027bcc5d36b873b49`,
both worker result envelopes and branch ledgers verify locally. The original
ZIP and verification report are retained under the ignored
`.irisx/arc-agi-2/qwen35-nvarc/m2-m3/combined-008-editor-observation-001/`.
The aggregate completed in 294.8 seconds on two distinct BF16 L4 UUIDs.

M2 completed one task-local TTT step, four grammar-completion generation
calls, eight candidate verifications and 400 explicit model forwards. Eight
6×6 model candidates satisfied shape and palette, but the top two were
dominated by a single color. An independent answer-free positional mapping
derived uniquely from every public train pair specifies a 6×6 test candidate.
The eight model candidates agree with it on only 8–12 of 36 cells. This is
public-demonstration agreement, **not** hidden-answer scoring or a claim that
the mapping must generalize.

M3 returned four EOS replies. Summary, exact public-rule mix, input program
and one-argument output program all passed their stage gates. The attempted
isolated program suite then stopped before a pair was accepted because the
Kaggle provider denied the `unshare` syscall (`Operation not permitted`).
The failure is in the namespace transport, not in a demonstrated program
semantic mismatch. Local WSL replay from the prior turn was a different
environment and does not establish provider namespace support. No SDG pair
or method promotion follows from this run.
