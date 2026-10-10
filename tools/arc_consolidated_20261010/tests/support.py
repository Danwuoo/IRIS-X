"""Workspace scratch with inherited Windows ACLs, separate from run artifacts."""
from pathlib import Path
import shutil
import uuid

# Keep portable notebook extraction below Windows MAX_PATH without changing
# OS policy. UUID uniqueness, inherited ACLs and checked cleanup are unchanged.
ROOT = Path(__file__).resolve().parents[3] / ".irisx" / "ct"


class TemporaryDirectory:
    def __init__(self, *args, **kwargs):
        ROOT.mkdir(parents=True, exist_ok=True)
        self.path = ROOT / uuid.uuid4().hex
        self.path.mkdir()
        self.name = str(self.path)

    def __enter__(self):
        return self.name

    def cleanup(self):
        target = self.path.resolve()
        if target.parent != ROOT.resolve() or self.path.is_symlink():
            raise ValueError("unsafe test cleanup")
        if self.path.exists():
            shutil.rmtree(self.path)

    def __exit__(self, *args):
        self.cleanup()
