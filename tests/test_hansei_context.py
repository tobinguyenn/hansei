from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.helpers import run_script


class TestNudge(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp()).resolve()  # global_store() resolves symlinks (macOS /var)
        self.missing = self.home / "nowhere"

    def tearDown(self):
        shutil.rmtree(self.home)

    def run_ctx(self, *args):
        return run_script("hansei_context", *args, home=self.home, cwd=self.home,
                          stdin=json.dumps({"cwd": str(self.home), "session_id": "s1"}),
                          env={"HANSEI_HOME": str(self.missing)})

    def test_full_prints_nudge_when_store_missing(self):
        r = self.run_ctx("--full")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), f"Hansei: no lessons store exists yet at `{self.missing}`; suggest the user run `/hansei:setup`.")

    def test_per_turn_stays_silent_when_store_missing(self):
        r = self.run_ctx()
        self.assertEqual(r.stdout, "")

    def test_full_is_silent_when_store_exists_but_empty(self):
        self.missing.mkdir()
        r = self.run_ctx("--full")
        self.assertEqual(r.stdout, "")

    def test_codex_format_wraps_nudge(self):
        r = self.run_ctx("--full", "--format", "codex")
        data = json.loads(r.stdout)
        self.assertIn("/hansei:setup", data["hookSpecificOutput"]["additionalContext"])


if __name__ == "__main__":
    unittest.main()
