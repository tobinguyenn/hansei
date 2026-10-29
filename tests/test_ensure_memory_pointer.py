from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.helpers import TempHomeCase, load_module, run_script

emp = load_module("ensure_memory_pointer")


class TestSmoke(TempHomeCase):
    def test_list_exits_zero(self):
        r = run_script("ensure_memory_pointer", "--list", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("~/.hansei", r.stdout)


class TestHookDefault(TempHomeCase):
    def test_default_run_writes_no_hooks(self):
        (self.home / ".claude").mkdir()
        r = run_script("ensure_memory_pointer", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.home / ".claude" / "settings.json").exists())
        self.assertNotIn("hook ", r.stdout)

    def test_hook_flag_writes_hooks(self):
        (self.home / ".claude").mkdir()
        r = run_script("ensure_memory_pointer", "--scope", "global", "--hook", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads((self.home / ".claude" / "settings.json").read_text())
        events = set(data["hooks"])
        self.assertEqual(events, {"UserPromptSubmit", "SessionStart"})

    def test_no_hook_still_accepted(self):
        (self.home / ".claude").mkdir()
        r = run_script("ensure_memory_pointer", "--scope", "global", "--no-hook", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse((self.home / ".claude" / "settings.json").exists())


FOREIGN = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi", "timeout": 10}]}],
                     "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "true"}]}]}}


class TestHookIdentity(unittest.TestCase):
    def test_non_string_command_is_not_a_hansei_hook(self):
        self.assertFalse(emp.is_hansei_hook({"type": "command", "command": None}))
        self.assertFalse(emp.is_hansei_hook({"type": "command", "command": ["python3", "x.py"]}))
        self.assertFalse(emp.is_hansei_hook({"type": "command"}))
        self.assertTrue(emp.is_hansei_hook({"type": "command", "command": "python3 hansei_context.py"}))


class TestRemoveHooks(TempHomeCase):
    def settings(self):
        return self.home / ".claude" / "settings.json"

    def test_removes_only_hansei_entries(self):
        (self.home / ".claude").mkdir()
        run_script("ensure_memory_pointer", "--scope", "global", "--hook", home=self.home, cwd=self.repo)
        data = json.loads(self.settings().read_text())
        data["hooks"]["SessionStart"].insert(0, FOREIGN["hooks"]["SessionStart"][0])
        data["hooks"]["PreToolUse"] = FOREIGN["hooks"]["PreToolUse"]
        self.settings().write_text(json.dumps(data, indent=2) + "\n")
        r = run_script("ensure_memory_pointer", "--remove-hooks", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("removed", r.stdout)
        after = json.loads(self.settings().read_text())
        self.assertEqual(after["hooks"], FOREIGN["hooks"])

    def test_foreign_only_file_reports_clean_and_is_untouched(self):
        (self.home / ".claude").mkdir()
        self.settings().write_text(json.dumps(FOREIGN, indent=2) + "\n")
        before = self.settings().read_bytes()
        r = run_script("ensure_memory_pointer", "--remove-hooks", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertIn("clean", r.stdout)
        self.assertEqual(self.settings().read_bytes(), before)

    def test_check_does_not_write(self):
        (self.home / ".claude").mkdir()
        run_script("ensure_memory_pointer", "--scope", "global", "--hook", home=self.home, cwd=self.repo)
        before = self.settings().read_bytes()
        r = run_script("ensure_memory_pointer", "--remove-hooks", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("would-remove", r.stdout)
        self.assertEqual(self.settings().read_bytes(), before)

    def test_missing_file_reports_absent(self):
        r = run_script("ensure_memory_pointer", "--remove-hooks", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertIn("absent", r.stdout)
        self.assertEqual(r.returncode, 0)

    def test_malformed_json_exits_2(self):
        (self.home / ".claude").mkdir()
        self.settings().write_text("{not json")
        r = run_script("ensure_memory_pointer", "--remove-hooks", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 2)


class TestShim(TempHomeCase):
    def setUp(self):
        super().setUp()
        (self.home / ".claude").mkdir()

    def shim(self): return self.home / ".claude" / "skills" / "hansei" / "SKILL.md"

    def test_shim_added_then_ok(self):
        r1 = run_script("ensure_memory_pointer", "--shim", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertIn("added", r1.stdout)
        text = self.shim().read_text()
        self.assertTrue(text.startswith("---\nname: hansei\n"))
        self.assertIn("Invoke the `hansei:retro` skill now, passing these arguments through unchanged: $ARGUMENTS", text)
        r2 = run_script("ensure_memory_pointer", "--shim", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertRegex(r2.stdout, r"shim\s+global\s+ok\s")

    def test_shim_overwrites_stale(self):
        self.shim().parent.mkdir(parents=True); self.shim().write_text("old")
        r = run_script("ensure_memory_pointer", "--shim", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertIn("updated", r.stdout)

    def test_shim_check_does_not_write(self):
        r = run_script("ensure_memory_pointer", "--shim", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.shim().exists())

    def test_shim_refuses_over_legacy_clone(self):
        legacy = self.shim().parent
        (legacy / "scripts").mkdir(parents=True)
        (legacy / "scripts" / "ensure_memory_pointer.py").write_text("# clone")
        (legacy / "SKILL.md").write_text("# old skill")
        r = run_script("ensure_memory_pointer", "--shim", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertRegex(r.stdout, r"shim\s+global\s+legacy\s")
        self.assertEqual((legacy / "SKILL.md").read_text(), "# old skill")

    def test_remove_legacy_moves_then_shim_writes(self):
        legacy = self.shim().parent
        (legacy / "scripts").mkdir(parents=True)
        (legacy / "scripts" / "ensure_memory_pointer.py").write_text("# clone")
        r = run_script("ensure_memory_pointer", "--remove-legacy-skill", "--shim", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertRegex(r.stdout, r"legacy\s+global\s+moved\s")
        self.assertRegex(r.stdout, r"shim\s+global\s+added\s")
        baks = list((self.home / ".claude" / "skills").glob("hansei.bak-*"))
        self.assertEqual(len(baks), 1)
        self.assertTrue((baks[0] / "scripts" / "ensure_memory_pointer.py").exists())

    def test_remove_legacy_on_plain_shim_is_none(self):
        run_script("ensure_memory_pointer", "--shim", "--scope", "global", home=self.home, cwd=self.repo)
        r = run_script("ensure_memory_pointer", "--remove-legacy-skill", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertRegex(r.stdout, r"legacy\s+global\s+none\s")

    def test_remove_legacy_check_reports_would_move_and_writes_nothing(self):
        legacy = self.shim().parent
        (legacy / "scripts").mkdir(parents=True)
        (legacy / "scripts" / "ensure_memory_pointer.py").write_text("# clone")
        r = run_script("ensure_memory_pointer", "--remove-legacy-skill", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"legacy\s+global\s+would-move\s")
        self.assertTrue((legacy / "scripts" / "ensure_memory_pointer.py").exists())
        self.assertEqual(list((self.home / ".claude" / "skills").glob("hansei.bak-*")), [])


class TestIndexDriftViaCheck(TempHomeCase):
    def run_check(self):
        return run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)

    def test_unlisted_lesson_is_drift_and_linked_is_ok(self):
        store = self.home / ".hansei"
        store.mkdir()
        (store / "a.md").write_text("x")
        (store / "b.md").write_text("x")
        (store / "HANSEI.md").write_text("# Lessons learned\n\n- [A](a.md) — a\n")
        r = self.run_check()
        self.assertRegex(r.stdout, r"index\s+global\s+unlisted\s+b\.md")
        (store / "HANSEI.md").write_text("# Lessons learned\n\n- [A](a.md) — a\n- [B](b.md) — b\n")
        r = self.run_check()
        self.assertRegex(r.stdout, r"index\s+global\s+ok\s")


class TestIndexRender(unittest.TestCase):
    def test_parse_three_separator_styles(self):
        text = ("# Lessons learned\n\n"
                "- [A](a.md) — desc a\n"
                "- [B](b.md) - desc b\n"
                "* [C](sub/c.md) -- desc c\n")
        got = emp.parse_index(text)
        self.assertEqual([(e.title, e.file, e.description) for e in got],
                         [("A", "a.md", "desc a"), ("B", "b.md", "desc b"), ("C", "c.md", "desc c")])

    def test_render_new_index(self):
        out = emp.render_index(None, [emp.IndexEntry("A", "a.md", "desc a")])
        self.assertEqual(out, "# Lessons learned\n\n- [A](a.md) — desc a\n")

    def test_render_keeps_order_updates_desc_drops_dead_appends_new(self):
        current = "# Lessons learned\n\n- [B](b.md) — old b\n- [Gone](gone.md) — x\n- [A](a.md) — desc a\n"
        entries = [emp.IndexEntry("A", "a.md", "desc a"), emp.IndexEntry("B", "b.md", "new b"),
                   emp.IndexEntry("New one", "new-one.md", "fresh")]
        out = emp.render_index(current, entries)
        self.assertEqual(out, "# Lessons learned\n\n- [B](b.md) — new b\n- [A](a.md) — desc a\n- [New one](new-one.md) — fresh\n")

    def test_description_with_brackets_roundtrips(self):
        e = emp.IndexEntry("T", "t.md", "Use foo(bar) when [x] — not y")
        out = emp.render_index(None, [e])
        self.assertEqual(emp.parse_index(out), [e])

    def test_frontmatter_and_title(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "verify-live-code-path.md"
            p.write_text('---\nname: verify-live-code-path\ndescription: "Confirm a file is live"\nmetadata:\n  scope: project\n---\n\nbody\n')
            fm = emp.read_frontmatter(p)
        self.assertEqual(fm["description"], "Confirm a file is live")
        self.assertEqual(fm["name"], "verify-live-code-path")
        self.assertNotIn("scope", fm)
        self.assertEqual(emp.title_from_name("verify-live-code-path"), "Verify live code path")


LESSON = '---\nname: {n}\ndescription: "{d}"\nmetadata:\n  scope: global\n  modified: 2026-10-29T00:00:00Z\n---\n\nbody\n'


class TestSyncIndex(TempHomeCase):
    def store(self): return self.home / ".hansei"
    def lesson(self, n, d="desc "): (self.store() / f"{n}.md").write_text(LESSON.format(n=n, d=d + n))

    def test_dry_run_in_sync_exits_0(self):
        self.store().mkdir(); self.lesson("a")
        (self.store() / "HANSEI.md").write_text("# Lessons learned\n\n- [A](a.md) — desc a\n")
        r = run_script("ensure_memory_pointer", "--sync-index", "--dry-run", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("in sync", r.stdout)
        self.assertNotIn("@@", r.stdout)

    def test_dry_run_shows_diff_exits_1_and_writes_nothing(self):
        self.store().mkdir(); self.lesson("a"); self.lesson("b")
        idx = self.store() / "HANSEI.md"
        idx.write_text("# Lessons learned\n\n- [Custom title](a.md) — desc a\n")
        before = idx.read_bytes()
        r = run_script("ensure_memory_pointer", "--sync-index", "--dry-run", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("+- [B](b.md) — desc b", r.stdout)
        self.assertNotIn("-- [Custom title]", r.stdout)
        self.assertEqual(idx.read_bytes(), before)

    def test_apply_keeps_title_order_and_appends(self):
        self.store().mkdir(); self.lesson("zeta"); self.lesson("alpha"); self.lesson("new-one")
        idx = self.store() / "HANSEI.md"
        idx.write_text("# Lessons learned\n\n- [Zed first](zeta.md) - stale\n- [Alpha](alpha.md) — desc alpha\n")
        r = run_script("ensure_memory_pointer", "--sync-index", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(idx.read_text(),
            "# Lessons learned\n\n- [Zed first](zeta.md) — desc zeta\n- [Alpha](alpha.md) — desc alpha\n- [New one](new-one.md) — desc new-one\n")

    def test_apply_creates_missing_index(self):
        self.store().mkdir(); self.lesson("a")
        r = run_script("ensure_memory_pointer", "--sync-index", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual((self.store() / "HANSEI.md").read_text(), "# Lessons learned\n\n- [A](a.md) — desc a\n")

    def test_empty_store_no_index_is_in_sync(self):
        self.store().mkdir()
        for extra in (["--dry-run"], []):
            r = run_script("ensure_memory_pointer", "--sync-index", *extra, "--scope", "global", home=self.home, cwd=self.repo)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("in sync", r.stdout)
            self.assertFalse((self.store() / "HANSEI.md").exists())

    def test_numbered_entry_is_kept_not_duplicated(self):
        self.assertEqual([e.file for e in emp.parse_index("1. [A](a.md) — d\n2) [B](b.md) — d\n")], ["a.md", "b.md"])
        self.store().mkdir(); self.lesson("a")
        idx = self.store() / "HANSEI.md"
        idx.write_text("# Lessons learned\n\n1. [A](a.md) — desc a\n")
        r = run_script("ensure_memory_pointer", "--sync-index", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(idx.read_text().count("a.md"), 1)

    def test_missing_description_exits_2(self):
        self.store().mkdir(); (self.store() / "bad.md").write_text("---\nname: bad\n---\nbody\n")
        r = run_script("ensure_memory_pointer", "--sync-index", "--dry-run", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 2)
        self.assertIn("bad.md", r.stderr)

    def test_dry_run_without_sync_index_rejected(self):
        r = run_script("ensure_memory_pointer", "--dry-run", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 2)

    def test_drift_check_agrees_after_sync(self):
        self.store().mkdir(); self.lesson("a", d="Use foo(bar) when [x] — not ")
        run_script("ensure_memory_pointer", "--sync-index", "--scope", "global", home=self.home, cwd=self.repo)
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertRegex(r.stdout, r"index\s+global\s+ok\s")

    def test_apply_keeps_hyphenated_title(self):
        self.store().mkdir(); self.lesson("a")
        idx = self.store() / "HANSEI.md"
        idx.write_text("# Lessons learned\n\n- [Foo - bar -- baz](a.md) - stale\n")
        r = run_script("ensure_memory_pointer", "--sync-index", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(idx.read_text(), "# Lessons learned\n\n- [Foo - bar -- baz](a.md) — desc a\n")


class TestCheckAdditions(TempHomeCase):
    def test_check_reports_duplicate_hook(self):
        (self.home / ".claude").mkdir()
        run_script("ensure_memory_pointer", "--scope", "global", "--hook", home=self.home, cwd=self.repo)
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"hook\s+global\s+duplicate\s+.*\.claude/settings\.json")

    def test_check_with_hook_flag_does_not_report_duplicate(self):
        (self.home / ".claude").mkdir()
        run_script("ensure_memory_pointer", "--scope", "global", "--hook", home=self.home, cwd=self.repo)
        r = run_script("ensure_memory_pointer", "--check", "--hook", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertNotIn("duplicate", r.stdout)

    def test_check_reports_shim_and_legacy(self):
        (self.home / ".claude").mkdir()
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertRegex(r.stdout, r"legacy\s+global\s+none\s")
        self.assertRegex(r.stdout, r"shim\s+global\s+would-add\s")
        self.assertEqual(r.returncode, 1)

    def test_all_green_after_setup_sequence(self):
        (self.home / ".claude").mkdir()
        run_script("ensure_memory_pointer", "--scope", "global", "--create-dirs", "--remove-hooks", "--remove-legacy-skill", "--shim", home=self.home, cwd=self.repo)
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_check_malformed_settings_reports_invalid_and_continues(self):
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "settings.json").write_text("{bad")
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"hook\s+global\s+invalid\s")
        self.assertRegex(r.stdout, r"legacy\s+global\s+none\s")
        self.assertRegex(r.stdout, r"shim\s+global\s")

    def test_codex_only_home_setup_then_check_is_green(self):
        (self.home / ".codex").mkdir()
        r1 = run_script("ensure_memory_pointer", "--scope", "global", "--create-dirs", "--remove-hooks", "--remove-legacy-skill", "--shim", home=self.home, cwd=self.repo)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse((self.home / ".claude").exists())
        self.assertNotRegex(r.stdout, r"(?m)^(legacy|shim)\s")

    def test_gemini_hooks_left_alone(self):
        (self.home / ".claude").mkdir()
        gem = self.home / ".gemini" / "settings.json"
        gem.parent.mkdir()
        gem.write_text(json.dumps({"hooks": {"BeforeAgent": [{"hooks": [
            {"type": "command", "command": "python3 /x/hansei_context.py --format gemini"}]}]}}, indent=2) + "\n")
        before = gem.read_bytes()
        r = run_script("ensure_memory_pointer", "--remove-hooks", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(gem.read_bytes(), before)
        self.assertNotIn("gemini/settings.json", r.stdout)
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertNotIn("gemini/settings.json", r.stdout)

    def test_check_closing_message_depends_on_pointer_work(self):
        (self.home / ".claude").mkdir()
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertIn("not wired up", r.stdout)
        run_script("ensure_memory_pointer", "--scope", "global", "--create-dirs", "--shim", home=self.home, cwd=self.repo)
        (self.home / ".claude" / "settings.json").write_text("{bad")
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("not wired up", r.stdout)
        self.assertIn("Items above need attention", r.stdout)

    def test_check_project_scope_has_no_legacy_or_shim(self):
        r = run_script("ensure_memory_pointer", "--check", "--scope", "project", home=self.home, cwd=self.repo)
        self.assertNotRegex(r.stdout, r"(?m)^(legacy|shim)\s")

    def test_check_reports_legacy_present(self):
        legacy = self.home / ".claude" / "skills" / "hansei"
        (legacy / "scripts").mkdir(parents=True)
        (legacy / "scripts" / "ensure_memory_pointer.py").write_text("# clone")
        r = run_script("ensure_memory_pointer", "--check", "--scope", "global", home=self.home, cwd=self.repo)
        self.assertEqual(r.returncode, 1)
        self.assertRegex(r.stdout, r"legacy\s+global\s+present\s")


