# Provenance Recovery Queue

Status: Phase 1 working queue. Order is not a commitment; owner decisions are called out explicitly.

## Queue

| Priority | Scope | Missing information | Current status | Suggested next step |
|---|---|---|---|---|
| High | All 13 sources | Exact upstream revision | `Unknown` | Recover from original acquisition logs, download archives, provider metadata, or content matching against candidate repositories/tags. |
| High | `iris/`, `eidos/`, `spex/`, `vanta/` | Originating author/repository and public/private status | `Not established` | Ask the corpus owner or locate original transfer notes before attempting external attribution. |
| High | `frugalgpt/` | Authoritative license | `Conflicting evidence`: Apache-2.0 `LICENSE` versus MIT classifier in `setup.py` | Owner/upstream decision needed; preserve both facts until resolved. |
| High | `iris/`, `eidos/`, `spex/`, `vanta/` | License and redistribution terms | `Unknown`; no root license found | Determine whether these are internal predecessor snapshots and whether license records can be recovered. |
| Medium | Whole import | Acquisition method and transformation log | Import commit subject says assets were imported without unavailable LFS assets; commands/tools are `Unknown`. Phase 2 relocation is recorded separately and preserves the original Git identities. | Recover shell history, transfer notes, archive metadata, or importer output. |
| Medium | `NeMo-Agent-Toolkit-develop/` | Exact omitted Git LFS asset inventory | Known `.gitattributes` LFS classes; exact missing asset list `Not established` | Compare against a complete upstream snapshot after its revision is known. Other sources have no established LFS-omission finding. |
| Medium | All PDFs | Byte equality with cited primary copy | Title identities checked remotely; exact PDF versions `Not established` | Download cited-version copies independently and compare SHA-256 without replacing originals until reviewed. |
| Low | Standalone NVIDIA papers | Relationship to IRIS-X corpus themes | Registered only; no imported implementation source | Let comparative research decide whether they remain contextual references. |

## Owner Decisions Needed

1. Resolve whether FrugalGPT should follow its Apache-2.0 license file, the MIT classifier in packaging metadata, or require upstream clarification.
2. Decide whether the four unlabeled predecessor directories should be treated as frozen internal snapshots even if their licenses cannot be recovered.
3. Decide whether future provenance recovery should prioritize exact revisions for all external references or only those selected for direct experimentation.

Resolution should be recorded by updating the affected stable-ID row, preserving prior uncertainty labels in unresolved-question history where useful, and rerunning the validator.
