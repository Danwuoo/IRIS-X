# Pre-Product Cold Archive

The complete repository immediately before the product transition is preserved
at its original paths by the annotated local tag:

`archive/pre-product-transition-2026-09-17`

Identities:

- source commit: `83207e48cc44ce26d0bcb0c98006facfc4f01844`
- root tree: `623066ca75243af5e68f53d8674508d4470ce2cd`
- annotated tag object: `658cdd6ccc33ffd32ced70e0834726c8e30d0a7d`

[`manifest.json`](manifest.json) records the archived roots, representative
recovery objects, and recovery commands. [`path-index.tsv`](path-index.tsv)
records every original tracked path with its Git mode, type, and object ID.

The payload was not deep-moved under this directory. That avoids Windows
path-length failures and preserves the original paths used by historical
manifests, hashes, tests, and evidence records.

## Recovery

Inspect one historical text file without changing the worktree:

```powershell
git show archive/pre-product-transition-2026-09-17:research/foundational-research-synthesis.md
```

Create an isolated checkout of the complete historical tree:

```powershell
git worktree add --detach ..\IRIS-X-pre-product-transition archive/pre-product-transition-2026-09-17
```

Export exact archived blobs without checking them out into the active tree:

```powershell
git archive --format=zip --output=..\IRIS-X-pre-product-transition.zip archive/pre-product-transition-2026-09-17
```

Restore a deliberately selected historical path to the active index/worktree
only when a future owner-authorized task requires it:

```powershell
git restore --source=archive/pre-product-transition-2026-09-17 --staged --worktree -- <path>
```

The tag is local and was not pushed by P0. Do not run recovered tests, tools,
plans, launch helpers, prototype code, or experiments as part of current
validation.
