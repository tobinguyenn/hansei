# hansei

**Hansei** (反省) — the practice of reflecting on what went wrong so it doesn't recur.

Turn the mistakes an AI assistant makes in a session into memory that survives it.

Ask for a retro at the end of a session. The assistant reviews what actually went wrong,
distills it into a few actionable lessons, shows you a draft, and — once you approve — writes
them to disk and wires up every assistant on your machine to read them next time.

The memory is shared. A mistake recorded while working in one tool is corrected in all of
them.

## Install

Claude Code:

```
claude plugin marketplace add tobinguyenn/hansei
claude plugin install hansei@hansei
```

then start a session and run `/hansei:setup` once. Update later with
`claude plugin marketplace update hansei && claude plugin update hansei@hansei`, or turn on
auto-update for the `hansei` marketplace in the `/plugin` Marketplaces tab. Check
[CHANGELOG.md](CHANGELOG.md) first: releases marked **hooks changed** need a restart.

Codex CLI:

```
codex plugin marketplace add tobinguyenn/hansei
```

then start `codex`, run `/plugins`, install `hansei`, run `/hooks` and trust the two hansei
hooks, then run the setup skill once. Update later with
`codex plugin marketplace upgrade hansei`, then re-trust the hooks, because Codex ties
trust to the hook's hash.

Both commands accept a local path or a full git URL instead of `owner/repo`. On machines
that reach the repo through the `github.tobi` SSH alias, use the URL form.

| Command | Does |
|---|---|
| `/hansei:retro [--scope ...]` | Session retro; `/hansei` is an alias on Claude Code |
| `/hansei:setup` | One-time wiring, idempotent |
| `/hansei:sync` | Repair indexes, shows a diff first |
| `/hansei:check` | Read-only health check |

### Without plugin support

Clone the repo somewhere stable, then wire the instructions files and user-level hooks:

```bash
python3 <clone>/plugins/hansei/scripts/ensure_memory_pointer.py --create-dirs --hook
```

and point the tool at `plugins/hansei/skills/retro/SKILL.md` as described in
`plugins/hansei/references/other-agents.md`.

With `--hook` wired at user level, run `--check --hook` (plain `--check` flags those
user-level hooks as `duplicate`, which only makes sense when the plugin supplies them).

Only Python 3.9+ and its standard library are required. The script is cross-platform
(Windows, macOS, Linux, and Windows-via-WSL).

**Known limitation:** plugin hooks call `python3`, which stock Windows Python lacks.

## Use

Just ask, at the end of a session:

> lessons learned
> what did you get wrong here?
> remember that so you don't do it again

It won't run unprompted. Two scoping options:

- `--scope global` — only lessons that transfer to other projects
- `--scope project` — only lessons about this codebase

## What it does

**Scans** the session for real mistakes — corrections, rework, failed assumptions, broken
conventions. Not your changes of mind, and not normal iteration.

**Classifies** each one. Would it still be useful in a different codebase next year? Global.
Does it depend on this project's specifics? Project.

**Scrubs** the global ones. Project names, paths, people, tickets, and internal service names
come out; technology names stay, because "Postgres returns X" is general knowledge and "the
database did something" is useless.

**Shows you a draft and stops.** Nothing is written until you approve. You can drop lessons,
move them between scopes, or reword them.

**Writes** the lesson files, updates the index, and re-verifies that the two agree.

## Where things go

```
~/.hansei/            global; shared by every assistant on the machine
<repo-root>/.hansei/  project; shared by every assistant in the repo
```

Neither path contains a vendor name. The store is the single source of truth: a lesson
recorded while using one assistant is read by all of them, and uninstalling any one tool
leaves the memory untouched. Set `$HANSEI_HOME` (absolute path) to move the global store.

Each store holds one file per lesson plus a `HANSEI.md` index. Assistants read the
index first — one small file per session — and open individual lessons only when a description
matches the task.

A lesson file:

```markdown
---
name: verify-live-code-path
description: "Confirm a file is on the live code path before editing it"
metadata:
  scope: project
  modified: 2026-08-25T07:45:38.248Z
---

About to edit a file whose name matches the feature being changed. In layered codebases the
file whose name matches is often legacy and no longer wired to anything.

**Why:** edits to an unrouted file change nothing, and nothing fails loudly.

**How to apply:** before editing, trace one real request or call chain to that file.
```

## Supported assistants

The plugin installs into Claude Code and Codex CLI. The installer wires lesson pointers for
every assistant below, so a lesson recorded in one tool reaches all of them — the others just
get it through a clone install instead of a plugin.

| Key | Assistant | Install | Status | Project instructions | Global instructions |
|---|---|---|---|---|---|
| `claude` | Claude Code | plugin | verified | `CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `agents` | Codex CLI (also Zed, others via `AGENTS.md`) | plugin | untested | `AGENTS.md` | `~/.codex/AGENTS.md` |
| `gemini` | Gemini CLI | clone + `--hook` | untested | `GEMINI.md` | `~/.gemini/GEMINI.md` |
| `cursor` | Cursor | clone, pointer only | untested | `.cursor/rules/hansei.mdc` | — |
| `copilot` | GitHub Copilot | clone, pointer only | untested | `.github/copilot-instructions.md` | — |

*verified* means the full install → `/hansei:setup` → `/hansei:check` path has been run end to
end on a real machine; *untested* means the wiring is implemented and unit-tested but has not
been exercised against that tool. See `plugins/hansei/references/other-agents.md` for the
clone-install steps.

Cursor and Copilot have no user-level instructions file, so their global pointer is skipped.
Their project rules still reference the shared global store, so the lessons reach them anyway.

### Beyond the pointer: three tools also get an automatic hook

A pointer block only *asks* an assistant to read the index; whether that happens on any
given turn is a judgment call. Claude Code, Codex CLI, and Gemini CLI each expose a hook
that fires early enough in a turn to force the issue, so the plugin (or `--hook`) wires one there too
— it runs `hansei_context.py` before the model sees the prompt and injects whichever
lesson indexes exist directly into context, no judgment call required.

| Key | Assistant | Hook event | Registered in |
|---|---|---|---|
| `claude` | Claude Code | `UserPromptSubmit`, `SessionStart` | `~/.claude/settings.json` / `.claude/settings.json` |
| `agents` | Codex CLI | `UserPromptSubmit` | `~/.codex/hooks.json` / `.codex/hooks.json` |
| `gemini` | Gemini CLI | `BeforeAgent` | `~/.gemini/settings.json` / `.gemini/settings.json` |

Every injection stays in the transcript, so the script does not repeat the whole index on
every turn. It keeps a small per-session state file (under `~/.cache/hansei/sessions/`, or
`%LOCALAPPDATA%\hansei` on Windows) and prints the full index only when the conversation
doesn't have it yet: the first turn of a session, whenever an index file changed, after a
context compaction, and every 30 turns as a safety net (`--every N`, `0` disables). Every
other turn gets a one-line reminder that the index is already in context and must still be
consulted. On Claude Code the compaction case is handled by the `SessionStart` hook, which
runs the script with `--full` on startup, resume, clear and compact; Codex gets the same
`SessionStart` hook from the plugin, and Gemini relies on the safety net.

Cursor and Copilot don't need a hook: an always-apply Cursor rule and
`.github/copilot-instructions.md` are already sent with *every* request by those tools, so
the pointer block alone already does what the hook exists to force for the other three.

The plugin ships the Claude Code and Codex hooks only. Gemini and other tools keep using
`ensure_memory_pointer.py --hook` at user level, and clone installs wire all of them that way.
The plugin never edits or removes Gemini hooks.

## The script

`ensure_memory_pointer.py` keeps the instructions files pointing at the memory. It is
idempotent — run it as often as you like.

```bash
ensure_memory_pointer.py                    # wire every detected assistant, both scopes
ensure_memory_pointer.py --agent gemini     # wire Gemini only
ensure_memory_pointer.py --check            # report only, never write
ensure_memory_pointer.py --list             # show every supported assistant
```

The four skills are thin wrappers over a few more flags, which you can also run by hand:

| Flag | Does |
|---|---|
| `--create-dirs` | also create the memory folders |
| `--hook` | wire the user-level context hooks (clone installs only; the plugin ships its own) |
| `--remove-hooks` | strip user-level hansei hooks left by an old clone install |
| `--remove-legacy-skill` | move an old clone at `~/.claude/skills/hansei` aside to `hansei.bak-<date>` |
| `--shim` | write the `/hansei` alias skill (Claude Code only; skipped when `~/.claude` is absent) |
| `--ignored` | add `.hansei/` to the repo's `.gitignore` (project scope; `/hansei:setup --ignored`) |
| `--sync-index [--dry-run]` | rebuild each store's `HANSEI.md` from the lesson files; `--dry-run` shows the diff and writes nothing |

`/hansei:setup` runs `--create-dirs --remove-hooks --remove-legacy-skill --shim`; `/hansei:sync`
runs `--sync-index --dry-run`, waits for approval, then `--sync-index`; `/hansei:check` runs
`--check`. Under `--check` the hook, shim and legacy items are reported too.

By default it wires **every assistant it finds evidence of** — `~/.claude`, `~/.codex`,
`~/.gemini` for global scope; `CLAUDE.md`, `AGENTS.md`, `.cursor`, `.github` in the repo for
project scope — and falls back to Claude Code if it finds none. It prints the set it chose
and why. Since every pointer names the same store, wiring several cannot split the memory.

`--agent` narrows a run to one assistant. It does not change where lessons are stored.

Exit codes: `0` in order, `1` changes needed (`--check` only), `2` refused. That makes
`--check` usable as a pre-commit or CI guard:

```bash
python3 <clone>/plugins/hansei/scripts/ensure_memory_pointer.py --check --hook --scope project || exit 1
```

It refuses to touch a file whose markers are unmatched or duplicated, rather than guessing
where the block ends — these are your files and usually contain instructions it didn't write.

## Notes

**The index is load-bearing.** A lesson missing from `HANSEI.md` is invisible to
future sessions. `--check` reports unlisted files and dead links, and the workflow re-runs it
after writing.

**Project memory lives in the repo**, so it's likely to be committed and read by teammates.
Lessons are written accordingly — no credentials, no remarks about individuals. On first
creation the workflow asks whether you'd rather gitignore it.

**Global memory is not inside any vendor directory.** It lives at `~/.hansei/`, so
uninstalling or cleaning out `~/.claude/`, `~/.codex/` or any other tool's directory leaves
the lessons untouched. `$HANSEI_HOME` moves it if you want it somewhere else — a synced
directory, for instance.

**Two assistants can't be reached globally.** Cursor keeps user-level rules in app settings
and Copilot has no user-level instructions file, so neither gets a global pointer. Their
project rules still name the global store, so the lessons reach them in any wired repo.

**Finding none is a valid outcome.** If the session went well, it says so rather than
inventing lessons to have something to show.

## Contributing

- Work on a short-lived branch (`feat/…`, `fix/…`, `docs/…`) and merge by pull request.
- Prefix commit messages with `feat:`, `fix:`, `docs:` or `chore:`.
- Releases: bump `version` in both `plugin.json` files, add a `CHANGELOG.md` entry, tag
  `vX.Y.Z` (annotated), then `gh release create vX.Y.Z --title vX.Y.Z --notes-file <changelog section>`.
  The tag and the release title are both exactly `vX.Y.Z`, nothing else.
- `python3 -m unittest` must pass.

## Layout

```
hansei/
├── .claude-plugin/marketplace.json     Claude Code marketplace
├── .agents/plugins/marketplace.json    Codex marketplace
├── README.md
├── CHANGELOG.md
├── plugins/hansei/
│   ├── .claude-plugin/                 Claude Code plugin manifest
│   ├── .codex-plugin/                  Codex plugin manifest
│   ├── hooks/                          hook registration
│   ├── skills/
│   │   ├── retro/                      the workflow
│   │   ├── setup/                      one-time wiring
│   │   ├── sync/                       repair indexes
│   │   └── check/                      read-only health check
│   ├── scripts/
│   │   ├── ensure_memory_pointer.py    wires instructions files to the memory
│   │   └── hansei_context.py           hook: injects the lesson index
│   └── references/
│       ├── formats.md                  file format, index format, quality bar
│       ├── scrubbing.md                what to strip from global lessons
│       └── other-agents.md             running this outside Claude Code
└── tests/
```
