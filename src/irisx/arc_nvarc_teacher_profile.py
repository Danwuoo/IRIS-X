"""Explicit direct-response Qwen profile; not upstream teacher parity."""

LIMITS = {"summary": {"input": 4096, "output": 512},
          "mix": {"input": 4096, "output": 1024},
          "input-logic": {"input": 4096, "output": 3072},
          "output-logic": {"input": 8192, "output": 3072}}
TOTAL_TOKENS = 28160
PROFILE = "qwen-direct-complete-v1"
PROMPTS = {
    "summary": """Describe the transformation rule in these two public ARC demonstrations.
Return only a concise final rule description, at most 150 words. Do not include analysis, code, or thinking.
Example 1 input: {INPUT_IMAGE1}
Example 1 output: {OUTPUT_IMAGE1}
Example 2 input: {INPUT_IMAGE2}
Example 2 output: {OUTPUT_IMAGE2}
Source comments: {USER_COMMENTS}
""",
    "mix": """Design one simple, unambiguous grid puzzle combining these two descriptions.
Return only the final puzzle specification, at most 250 words. State how to construct varied inputs
and deterministically transform them. Use 1..30 rows and columns, integer colors 0..9.
Do not include analysis, code, or thinking. Avoid rules requiring external information.
Description 1: {PUZZLE1}
Description 2: {PUZZLE2}
""",
    "input-logic": """Write one complete Python code block implementing this puzzle's input generator.
Define generate_puzzle_input(seed: int), returning a 2D numpy integer array.
Use only Python and numpy; seed all randomness from seed. Vary inputs across seeds.
Grids must be 1..30 by 1..30, colors 0..9. Include every helper you call.
No prose, analysis, ellipses, main entry, filesystem, network, or external dependencies.
Puzzle: {PUZZLE}
""",
    "output-logic": """Write one complete Python code block implementing this puzzle's output rule.
Define generate_puzzle_output(input_grid), returning a 2D numpy integer array.
Use only Python and numpy. The transformation must be deterministic; no randomness.
Grids must be 1..30 by 1..30, colors 0..9. Include every helper you call.
No prose, analysis, ellipses, main entry, filesystem, network, or external dependencies.
Puzzle: {PUZZLE}
Input generator (reference only):
{INPUT_CODE}
"""}


def profile_prompts(profile):
    if profile == PROFILE:
        return PROMPTS
    from .arc_nvarc_teacher_spec import PROFILE as SPEC_PROFILE, PROMPTS as SPEC_PROMPTS
    if profile == SPEC_PROFILE:
        return SPEC_PROMPTS
    raise ValueError("unknown direct teacher profile")
