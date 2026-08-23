from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .system import DocumentSystemError, write_index


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the Eidos governed-document index.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="repository root; defaults to the root containing eidos.yaml",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        path = write_index(args.repo_root)
    except DocumentSystemError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

