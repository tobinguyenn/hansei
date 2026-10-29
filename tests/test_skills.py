from __future__ import annotations

import unittest

from tests.helpers import ROOT, load_module

SKILLS = ROOT / "plugins/hansei/skills"
frontmatter = load_module("ensure_memory_pointer").read_frontmatter


class TestSkills(unittest.TestCase):
    def test_four_skills_with_matching_names(self):
        for name in ("retro", "setup", "sync", "check"):
            fm = frontmatter(SKILLS / name / "SKILL.md")
            self.assertEqual(fm["name"], name)
            self.assertTrue(fm["description"])

    def test_no_legacy_paths_or_plugin_root_in_bodies(self):
        for p in SKILLS.glob("*/SKILL.md"):
            text = p.read_text()
            self.assertNotIn("~/.claude/skills/hansei", text, p)
            self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text, p)
            self.assertIn("next to this SKILL.md's parent `skills/` folder", text, p)

    def test_setup_and_sync_name_their_flags(self):
        setup = (SKILLS / "setup/SKILL.md").read_text()
        self.assertIn("--scope default --create-dirs --remove-hooks --remove-legacy-skill --shim", setup)
        sync = (SKILLS / "sync/SKILL.md").read_text()
        self.assertIn("--sync-index --dry-run --scope default", sync)
        check = (SKILLS / "check/SKILL.md").read_text()
        self.assertIn("--check --scope default", check)

    def test_frontmatter_values_are_strict_yaml(self):
        for p in SKILLS.glob("*/SKILL.md"):
            lines = p.read_text().splitlines()
            self.assertEqual(lines[0], "---", p)
            for line in lines[1:lines.index("---", 1)]:
                if line[:1] in (" ", "\t", "#") or ":" not in line:
                    continue
                value = line.split(":", 1)[1].strip()
                quoted = len(value) >= 2 and value[0] == value[-1] and value[0] in "'\""
                if ": " in value and not quoted:
                    self.fail(f"{p}: unquoted ': ' in {line!r}")

    def test_no_claude_md_in_plugin(self):
        self.assertFalse((ROOT / "plugins/hansei/CLAUDE.md").exists())


if __name__ == "__main__":
    unittest.main()
