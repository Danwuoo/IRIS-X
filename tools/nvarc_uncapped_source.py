# Original solver definitions: sorokin's Kaggle notebook Version10,
# arc2-qwen3-unsloth-flash-lora-batch4-queue, Apache-2.0.
# https://www.kaggle.com/code/sorokin/arc2-qwen3-unsloth-flash-lora-batch4-queue
# IRIS-X adaptation: explicitly remove only the original DFS wall-clock guard.
# See notices/NOTICE-native.txt and notices/LICENSE-Apache-2.0.txt.
"""A distinct, auditable in-memory derivative; never rewrite frozen source files.

The source's answer grammar/depth, cumulative p=.2 pruning, traversal and ranking
are scientific constraints. Its elapsed-time guard is a resource policy. The
latter alone is replaced. Unused start_time/end_time parameters remain for exact
call-interface preservation; end_time=None means no deadline, never infinity.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import hashlib
from pathlib import Path
import time
from types import SimpleNamespace

from tools.nvarc_native_solve_runtime import SOURCE_HASHES, load_sources, require
from tools.nvarc_native_multitask import digest
from tools.nvarc_original_ast_binding import portable_ast_dump

FUNCTIONS = {'turbo_dfs', 'inference_turbo_dfs', 'calc_scores'}
CONSTANTS = {'ARC_VOCAB', 'ARC_TOKENS', 'USER_TOKEN_ID', 'ASSISTANT_TOKEN_ID', 'PAD_ID', 'EOS_ID'}
GUARD = 'time.time() - start_time < 540 and time.time() < end_time'
FORMAT = 'irisx/native-uncapped-source-adaptation-v1'


def adapted_tree(directory):
    """Verify all original bytes and return the derivative AST plus exact receipt."""
    root = Path(directory)
    for name, expected in SOURCE_HASHES.items():
        require(hashlib.sha256((root/name).read_bytes()).hexdigest() == expected,
                'exact original code cell differs: ' + name)
    tree = ast.parse((root/'solver.py').read_bytes())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in FUNCTIONS
             or isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in CONSTANTS
                                                   for t in n.targets)]
    require({n.name for n in nodes if isinstance(n, ast.FunctionDef)} == FUNCTIONS,
            'all three original inference definitions required')
    original = ast.Module(body=nodes, type_ignores=[])
    adapted = deepcopy(original)
    dfs = next(n for n in adapted.body if isinstance(n, ast.FunctionDef) and n.name == 'turbo_dfs')
    loops = [n for n in ast.walk(dfs) if isinstance(n, ast.While)]
    expected = ast.parse(GUARD, mode='eval').body
    require(len(loops) == 1 and ast.dump(loops[0].test) == ast.dump(expected),
            'exact original dual DFS wall-clock guard required')
    loop = loops[0]
    before = portable_ast_dump(loop.test)
    loop.test = ast.copy_location(ast.Constant(value=True), loop.test)
    after = portable_ast_dump(loop.test)
    ast.fix_missing_locations(adapted)
    restored = deepcopy(adapted)
    restored_dfs = next(n for n in restored.body if isinstance(n, ast.FunctionDef) and n.name == 'turbo_dfs')
    next(n for n in ast.walk(restored_dfs) if isinstance(n, ast.While)).test = deepcopy(expected)
    require(portable_ast_dump(restored) == portable_ast_dump(original),
            'adaptation must change only the DFS wall-clock condition')
    receipt = {'format': FORMAT, 'original_source_sha256': dict(SOURCE_HASHES),
        'loaded_functions': sorted(FUNCTIONS),
        'original_inference_ast_digest': digest(portable_ast_dump(original)),
        'adapted_inference_ast_digest': digest(portable_ast_dump(adapted)),
        'changes': [{'function': 'turbo_dfs', 'line': loop.lineno,
            'operation': 'replace_while_condition', 'before_ast': before, 'after_ast': after,
            'removed_resource_guards': ['elapsed_seconds_less_than_540', 'epoch_before_end_time']}],
        'source_files_modified': False, 'end_time_policy': None,
        'remaining_start_time_read': 'original timestamp capture only; not a stop condition',
        'scientific_logic_changed': False, 'native_numerical_parity_claim': False}
    return adapted, receipt


def load_uncapped_sources(directory, torch, np):
    """Load reviewed definitions only; no notebook runner, model or external IO."""
    tree, receipt = adapted_tree(directory)
    loader, _original_solver, decoder = load_sources(directory, torch, np)
    namespace = {'np': np, 'torch': torch, 'time': time, 'defaultdict': defaultdict,
                 'AutoTokenizer': object}
    exec(compile(tree, str(Path(directory)/'solver.py') + ':uncapped-derivative', 'exec'), namespace)
    return loader, SimpleNamespace(**namespace), decoder, receipt


def prepare_solver(engine, root):
    loader, solver, decoder, receipt = load_uncapped_sources(root, engine.torch, engine.np)
    engine.loader, engine.solver, engine.decoder = loader, solver, decoder
    return receipt
