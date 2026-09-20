# Decision 0006: use the unpacked model source for ARC-AGI-2 Trial 001

Date: 2026-09-20  
Status: Accepted

## Decision

The owner authorizes IRIS-X to use the unpacked files of
`Qwen/Qwen3.8-27B` at revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` directly throughout the active
Trial 001 flow. This decision supersedes Decision 0005 only where Decision
0005 required `model-package.zip` as the model transport or deployment form.

The private immutable Kaggle model Dataset is a raw model tree. Its root must
contain exactly the files declared by the locally generated
`irisx/model-source-provenance` artifact. The outbound `trial-input.zip`
contains that provenance artifact and its binding, but no model bytes.

The network-disabled Kaggle notebook must:

1. derive `/kaggle/input/datasets/{owner}/{slug}` from the bound Dataset;
2. reject symbolic links, missing files, extra files, size mismatches, and
   SHA-256 mismatches against the bound provenance;
3. pass that read-only directory directly to the runner; and
4. never copy or extract the model into `/kaggle/working`.

Preflight, returned result identity, quarantine import, and the final Domain
Package bind `model_source_provenance_digest`. An eligible self-contained
Domain Package stores the unpacked model under
`deployment/model-source/source/` with `provenance.json` beside it.

The active CLI accepts `--model-source` for outbound build, preflight, and ARC
Domain Package build. Model ZIP build and verification commands are removed
from the active surface.

## Bound Kaggle Dataset

The currently selected model Dataset binding is:

- owner: `danielwuu`;
- slug: `qwen38-27b`;
- notebook mount: `/kaggle/input/datasets/danielwuu/qwen38-27b`;
- access: private;
- transport: manual; and
- content: the unpacked raw model files, not a ZIP archive.

The immutable Kaggle Dataset version remains an explicit positive integer in
the binding and must match the version displayed by Kaggle.

## Unchanged gates

This decision does not authorize the real model/solver run. One later,
separate explicit owner execution authorization is still required after all
Decision 0004, 0005, and 0006 preflight gates pass. Internet remains disabled,
credentials are absent from the notebook, paid external spend remains USD 0,
weights remain frozen, evaluator truth remains local, and Kaggle transport
remains manual.
