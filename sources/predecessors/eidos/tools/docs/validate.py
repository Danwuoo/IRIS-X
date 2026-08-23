from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .system import validate_repository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the Eidos documentation system.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root; defaults to the root containing eidos.yaml",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    errors = validate_repository(args.repo_root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Documentation system validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

