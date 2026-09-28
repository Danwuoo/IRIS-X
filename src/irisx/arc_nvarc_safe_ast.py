"""Trusted interpretation of two small SDG program templates; no generated exec.

This is deliberately narrower than Python. A teacher reply with any extra
statement, import, call or changed control flow is rejected before probing.
The matched AST is interpreted by trusted code; teacher bytes never run.
"""

import ast

from .arc_nvarc_data import grid
from .canonical import digest_value
from .errors import ValidationError

_INPUT_TEMPLATE = """import numpy as np

def generate_puzzle_input(seed: int) -> np.ndarray:
    np.random.seed(seed)
    shape = [3, 3]
    rows, cols = shape
    grid = np.zeros((rows, cols), dtype=np.int64)
    for i in range(rows * cols):
        grid[i // cols, i % cols] = i
    permutation = np.random.permutation(rows * cols)
    for idx, new_pos in enumerate(permutation):
        grid[new_pos // cols, new_pos % cols] = idx
    return grid
"""

_OUTPUT_TEMPLATE = """import numpy as np

def generate_puzzle_output(input_grid):
    flat = np.asarray(input_grid, dtype=np.int64).reshape(-1)
    return flat[np.asarray({order}, dtype=np.int64)].reshape({shape})
"""


def _tree(code):
    if not isinstance(code, str) or not code or len(code.encode("utf-8")) > 65536:
        raise ValidationError("safe AST program bounds differ")
    try:
        return ast.parse(code)
    except SyntaxError as error:
        raise ValidationError("safe AST program syntax differs") from error


def _fingerprint(tree):
    return ast.dump(tree, include_attributes=False)


def _input_contract(code):
    if _fingerprint(_tree(code)) != _fingerprint(_tree(_INPUT_TEMPLATE)):
        raise ValidationError("safe AST input template differs")


def _output_contract(code):
    tree = _tree(code)
    try:
        function = tree.body[1]
        returned = function.body[-1].value
        shape = ast.literal_eval(returned.args[0])
        order = ast.literal_eval(returned.func.value.slice.args[0])
    except (AttributeError, IndexError, TypeError, ValueError) as error:
        raise ValidationError("safe AST output constants differ") from error
    if (type(shape) is not list or shape != [3, 3] or type(order) is not list or
            any(type(index) is not int for index in order) or
            sorted(order) != list(range(9))):
        raise ValidationError("safe AST output permutation differs")
    expected = _tree(_OUTPUT_TEMPLATE.format(order=repr(order), shape=repr(shape)))
    if _fingerprint(tree) != _fingerprint(expected):
        raise ValidationError("safe AST output template differs")
    return order, shape


class SafeASTProgramExecutor:
    """One exact syntax family, interpreted by trusted NumPy operations."""

    def __init__(self):
        self.material_digest = digest_value({"format": "irisx/nvarc-safe-ast-program-v1",
            "input_ast": _fingerprint(_tree(_INPUT_TEMPLATE)),
            "output_template": _OUTPUT_TEMPLATE})

    def probe(self, code, entry, *, seed=None, input_grid=None):
        import numpy as np

        if entry == "generate_puzzle_input":
            if type(seed) is not int or not 0 <= seed <= 1000000 or input_grid is not None:
                raise ValidationError("safe AST input arguments differ")
            _input_contract(code)
            permutation = np.random.RandomState(seed).permutation(9)
            value = np.zeros((3, 3), dtype=np.int64)
            for index, position in enumerate(permutation):
                value[int(position) // 3, int(position) % 3] = index
        elif entry == "generate_puzzle_output":
            if seed is not None:
                raise ValidationError("safe AST output arguments differ")
            order, shape = _output_contract(code)
            value = np.asarray(grid(input_grid), dtype=np.int64).reshape(-1)
            if value.size != 9:
                raise ValidationError("safe AST input grid shape differs")
            value = value[np.asarray(order, dtype=np.int64)].reshape(shape)
        else:
            raise ValidationError("safe AST entry differs")
        return {"kind": "ndarray", "dtype_kind": value.dtype.kind,
                "shape": list(value.shape), "value": value.tolist()}
