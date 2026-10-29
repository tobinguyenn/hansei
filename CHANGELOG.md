# Changelog

Each entry says what changed for users and whether an update needs more than
`claude plugin update hansei@hansei`. Releases that touch `hooks/hooks.json` are
marked **hooks changed**: Claude Code needs a restart (not just `/reload-plugins`),
and Codex users must re-trust the hooks under `/hooks`.

## 1.0.0 — 2026-10-30

First release as a plugin. Install id `hansei@hansei`.

- Four skills: `/hansei:retro` (the session retro; `/hansei` is an alias on Claude
  Code), `/hansei:setup` (one-time wiring), `/hansei:sync` (repair indexes after
  showing a diff), `/hansei:check` (read-only health check).
- The plugin ships the Claude Code and Codex context hooks. User-level hooks are
  now opt-in (`--hook`) and only needed for clone installs. `/hansei:setup` removes
  hooks left behind by an old clone install and moves an old
  `~/.claude/skills/hansei` clone aside as `hansei.bak-<date>`.
- `ensure_memory_pointer.py` gains `--remove-hooks`, `--shim`,
  `--remove-legacy-skill`, `--sync-index [--dry-run]`, and a richer `--check`.
- `hansei_context.py` nudges towards `/hansei:setup` when no lesson store exists.
- Python floor is 3.9 (was documented as 3.10). Standard library only.
- Lesson stores (`~/.hansei/`, `<repo>/.hansei/`) and the pointer-block text are
  unchanged; existing lessons need no migration.
