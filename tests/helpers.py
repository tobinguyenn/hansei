from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "hansei" / "scripts"


def load_module(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass under `from __future__ import annotations`
    # looks the module up in sys.modules at class creation (breaks on Python 3.9).
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def run_script(name: str, *args: str, home: Path, cwd: Path, stdin: str = "", env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = {
        **os.environ,
        "HOME": str(home),
        "XDG_CACHE_HOME": str(home / ".cache"),
        **(env or {}),
    }
    if not env or "HANSEI_HOME" not in env:
        full_env.pop("HANSEI_HOME", None)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / f"{name}.py"), *args],
        env=full_env,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        input=stdin,
    )


class TempHomeCase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.repo = self.home / "repo"
        self.repo.mkdir()

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)
