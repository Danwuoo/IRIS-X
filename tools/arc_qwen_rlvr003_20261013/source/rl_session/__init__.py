"""Local, unreleased RLVR successor. No provider or submission entry point."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'baseline'))
