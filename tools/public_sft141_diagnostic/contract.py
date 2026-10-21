"""Small, independent codec for the publicly documented 16-token grid format.

This is an explicit format, not a generic model chat template. Spatial view
``4 * transpose_flag + rotations_ccw`` applies transpose first, then the stated
number of counterclockwise quarter turns. It works on rectangular grids.
"""

from collections.abc import Mapping, Sequence

NEWLINE_ID = 10
USER_ID = 11
ASSISTANT_ID = 12
PAD_ID = 13
IM_START_ID = 14
EOS_ID = 15
MAX_NEW_TOKENS = 931
VIEWS = tuple(range(8))
TOKEN_STRINGS = tuple(str(color) for color in range(10)) + (
    "\n", "user", "assistant", "<|endoftext|>", "<|im_start|>", "<|im_end|>",
)
Grid = list[list[int]]


def validate_grid(grid: object) -> Grid:
    """Validate and copy a 1..30 by 1..30 rectangular integer-color grid."""
    if not isinstance(grid, (list, tuple)) or not 1 <= len(grid) <= 30:
        raise ValueError("grid must have between 1 and 30 rows")
    width = None
    result = []
    for row in grid:
        if not isinstance(row, (list, tuple)) or not 1 <= len(row) <= 30:
            raise ValueError("grid rows must have between 1 and 30 cells")
        if width is None:
            width = len(row)
        if len(row) != width:
            raise ValueError("grid is not rectangular")
        if any(type(color) is not int or not 0 <= color <= 9 for color in row):
            raise ValueError("grid colors must be integers from 0 through 9")
        result.append(list(row))
    return result


def grid_text(grid: object) -> str:
    """Concatenated ASCII digits, LF-separated rows, and no final LF."""
    return "\n".join("".join(str(color) for color in row) for row in validate_grid(grid))


def _view(view: int) -> tuple[bool, int]:
    if type(view) is not int or not 0 <= view < 8:
        raise ValueError("view must be an integer from 0 through 7")
    return view >= 4, view % 4


def _transpose(grid: Grid) -> Grid:
    return [list(column) for column in zip(*grid)]


def _rotate_ccw(grid: Grid) -> Grid:
    return [list(column) for column in zip(*grid)][::-1]


def transform(grid: object, view: int) -> Grid:
    transpose, rotations = _view(view)
    result = validate_grid(grid)
    if transpose:
        result = _transpose(result)
    for _ in range(rotations):
        result = _rotate_ccw(result)
    return result


def inverse(grid: object, view: int) -> Grid:
    transpose, rotations = _view(view)
    result = validate_grid(grid)
    for _ in range((-rotations) % 4):
        result = _rotate_ccw(result)
    return _transpose(result) if transpose else result


def _grid_ids(grid: object) -> list[int]:
    result = []
    for index, row in enumerate(validate_grid(grid)):
        if index:
            result.append(NEWLINE_ID)
        result.extend(row)
    return result


def _support(train: Sequence[Mapping]) -> Sequence[Mapping]:
    if not isinstance(train, (list, tuple)) or not train:
        raise ValueError("at least one support demonstration is required")
    if any(not isinstance(pair, Mapping) or "input" not in pair or "output" not in pair
           for pair in train):
        raise ValueError("every demonstration requires input and output")
    return train


def prompt_ids(train: Sequence[Mapping], query: object, view: int = 0) -> list[int]:
    """Encode every support pair, then the query input and assistant prefix.

    ``query`` is an input grid, never a task/test dictionary with an answer.
    """
    _view(view)
    result = []
    for pair in _support(train):
        result.extend((IM_START_ID, USER_ID, NEWLINE_ID))
        result.extend(_grid_ids(transform(pair["input"], view)))
        result.extend((EOS_ID, IM_START_ID, ASSISTANT_ID, NEWLINE_ID))
        result.extend(_grid_ids(transform(pair["output"], view)))
        result.append(EOS_ID)
    result.extend((IM_START_ID, USER_ID, NEWLINE_ID))
    result.extend(_grid_ids(transform(query, view)))
    result.extend((EOS_ID, IM_START_ID, ASSISTANT_ID, NEWLINE_ID))
    return result


def prompt_text(train: Sequence[Mapping], query: object, view: int = 0) -> str:
    """Exact public spelling for checking a real tokenizer, with no BOS."""
    _view(view)
    result = []
    for pair in _support(train):
        result.extend(("<|im_start|>user\n", grid_text(transform(pair["input"], view)),
                       "<|im_end|><|im_start|>assistant\n",
                       grid_text(transform(pair["output"], view)), "<|im_end|>"))
    result.extend(("<|im_start|>user\n", grid_text(transform(query, view)),
                   "<|im_end|><|im_start|>assistant\n"))
    return "".join(result)


def answer_ids(grid: object) -> list[int]:
    return _grid_ids(grid) + [EOS_ID]


def parse_answer(ids: Sequence[int]) -> Grid:
    """Accept one complete EOS-terminated grid; never repair malformed text.

    Missing EOS, extra tokens (including PAD), non-grid tokens, blank rows,
    ragged shapes and dimensions outside 1..30 are failures.
    """
    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("answer is empty")
    if len(ids) > 930:
        raise ValueError("answer exceeds the largest supported grid plus EOS")
    if any(type(token) is not int for token in ids):
        raise ValueError("answer tokens must be integers")
    if ids[-1] != EOS_ID:
        raise ValueError("answer must end with EOS")
    rows: Grid = [[]]
    for token in ids[:-1]:
        if 0 <= token <= 9:
            rows[-1].append(token)
        elif token == NEWLINE_ID:
            rows.append([])
        else:
            raise ValueError("non-grid or premature EOS token in answer")
    return validate_grid(rows)
