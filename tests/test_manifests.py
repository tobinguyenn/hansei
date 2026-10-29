from __future__ import annotations

import json
import re
import unittest

from tests.helpers import ROOT


class TestManifests(unittest.TestCase):
    def test_plugin_manifests_identical(self):
        a = json.loads((ROOT / "plugins/hansei/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT / "plugins/hansei/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(a, b)
        self.assertEqual(set(a), {"name", "version", "description", "author"})

    def test_changelog_top_entry_matches_version(self):
        version = json.loads((ROOT / "plugins/hansei/.claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
        top = re.search(r"^## (\S+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M).group(1)
        self.assertEqual(top, version)

    def test_hooks_reference_context_script(self):
        h = json.loads((ROOT / "plugins/hansei/hooks/hooks.json").read_text(encoding="utf-8"))["hooks"]
        self.assertEqual(set(h), {"UserPromptSubmit", "SessionStart"})
        for entries in h.values():
            cmd = entries[0]["hooks"][0]["command"]
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/hansei_context.py"', cmd)
        self.assertTrue(h["SessionStart"][0]["hooks"][0]["command"].endswith("--full"))
        self.assertNotIn("matcher", h["SessionStart"][0])
        self.assertEqual(h["UserPromptSubmit"][0]["matcher"], "*")


if __name__ == "__main__":
    unittest.main()
