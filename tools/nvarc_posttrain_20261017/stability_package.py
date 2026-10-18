"""Build a private save-only stability notebook locally; never publish or run.

Caller supplies the newly reviewed source/version and notebook identity. No old
notebook is overwritten and no current provider identity is embedded as default.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import re
import time

from tools.arc2_goal_sprint_20261017 import package as predecessor
from tools.arc2_goal_sprint_20261017.bootstrap import REFERENCES
from tools.arc2_goal_sprint_20261017.launch import require, write_new
from . import manual, package
from .materials import model_pin
from .stability_controller import WORKFLOW


def build_notebook(destination, *, run_id, session_id, notebook_ref, source_dataset, solver_dataset,
                   source_manifest_sha256, source_payload_sha256, started_epoch):
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{3,95}', run_id or ''), 'fresh portable source identity required')
    require(re.fullmatch(r'danielwuu/[a-z0-9][a-z0-9-]+', notebook_ref or ''), 'explicit owned private destination required')
    require(notebook_ref != 'danielwuu/iris-x-nvarc-dual-posttrain-20261017', 'independent diagnostic notebook required')
    require(re.fullmatch(r'danielwuu/[a-z0-9][a-z0-9-]+/[1-9][0-9]*', source_dataset or ''), 'pinned new private source required')
    require(re.fullmatch(r'danielwuu/[a-z0-9][a-z0-9-]+/[1-9][0-9]*', solver_dataset or '')
            and solver_dataset != REFERENCES['public'], 'evaluator-free solver projection required')
    require(all(re.fullmatch(r'[a-f0-9]{64}', value or '') for value in (source_manifest_sha256, source_payload_sha256)),
            'exact immutable capsule pins required')
    require(type(started_epoch) in (int, float) and math.isfinite(started_epoch)
            and 0 < started_epoch <= time.time(), 'historical source clock required')
    destination = Path(destination); destination.mkdir(parents=True, exist_ok=False)
    request = {'run_id': run_id, 'source_dataset': source_dataset, 'solver_dataset': solver_dataset,
        'source_manifest_sha256': source_manifest_sha256, 'source_payload_sha256': source_payload_sha256,
        'workflow': WORKFLOW, 'evaluation_mode': 'external-cpu', 'input_root': '/kaggle/input',
        'working_root': '/kaggle/working/' + run_id, 'runtime_root': '/kaggle/temp/' + run_id,
        'started_epoch': started_epoch, 'session_deadline_epoch': started_epoch + 43200, 'parameters': {}}
    notebook = manual.build_manual_notebook(predecessor.notebook([package.loader(request)], run_id), session_id)
    notebook['cells'][0]['source'] = (
        'Manual-run diagnostic only. Quick Save does not execute a GPU.\n\n'
        'Compares official2B and4B specialists serially on32 fixed training-derived development parents, '
        'excluding the prior24-parent selection panel and its known transformation groups. Each parent uses identical two-view decoding '
        'before and after32 demo-only updates, with an exact anchor reset. No PUBLIC predictions or '
        'competition submission are produced. Inherited checkpoint exposure is not erased.\n\n'
        'The first execution claims a write-once session using the Linux kernel process birth. '
        'A used start/output identity cannot be rerun to reset the deadline. Provider allocation time '
        'is not independently measured. The unchanged recipe requires one actual GPU with32GiB free; '
        'it does not combine device memory or modify hardware/security/billing settings. '
        'RTX PRO6000 is only the requested setting, not an allocation or eligibility claim.')
    name = 'iris-x-nvarc-ttt-stability.ipynb'
    write_new(destination / name, notebook)
    # Provider save routes can derive a slug from the title. Bind the two rather
    # than silently redirecting a dated destination to a differently named one.
    title = notebook_ref.split('/', 1)[1].replace('-', ' ')
    metadata = {'id': notebook_ref, 'title': title, 'code_file': name,
        'language': 'python', 'kernel_type': 'notebook', 'is_private': True, 'enable_gpu': True,
        'enable_tpu': False, 'enable_internet': False, 'machine_shape': 'NvidiaRtxPro6000',
        'dataset_sources': [REFERENCES[key] for key in ('wheels', 'interpreter', 'training')] + [solver_dataset, source_dataset],
        'model_sources': [model_pin(v)['model_source'] for v in ('2b', '4b')],
        'competition_sources': [], 'kernel_sources': []}
    write_new(destination / 'kernel-metadata.json', metadata)
    write_new(destination / 'frozen-source-request.json', request)
    result = {'format': 'irisx/nvarc-local-stability-delivery-v1', 'notebook_ref': notebook_ref,
        'source_identity': run_id, 'manual_session_id': session_id, 'workflow': WORKFLOW,
        'source_manifest_sha256': source_manifest_sha256, 'source_payload_sha256': source_payload_sha256,
        'save_mode_required': 'QUICK_SAVE', 'published': False, 'run_launched': False,
        'formal_competition_submission': False, 'private_source_upload_authorized_by_this_builder': False}
    write_new(destination / 'local-delivery.json', result)
    return result
