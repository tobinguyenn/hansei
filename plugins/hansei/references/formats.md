# Formats

## Layout

```
<store>/
├── HANSEI.md              index of every lesson in this store
├── <kebab-name>.md        one lesson per file
└── <kebab-name>.md
```

Stores:

- Global: `~/.hansei/` — one store, every assistant. `$HANSEI_HOME` overrides it.
- Project: `<repo-root>/.hansei/`.

Each store has its own index. One lesson per file, so the filename and the frontmatter `name`
identify a single lesson, and the index is what makes a folder of many small files readable.

## Lesson file

Filename `<kebab-name>.md`, where `<kebab-name>` matches the frontmatter
`name` minus the prefix.

```markdown
---
name: verify-live-code-path
description: "Confirm a file is on the live code path before editing it"
metadata:
  scope: project
  modified: 2026-08-25T07:45:38.248Z
---

About to edit a file whose name matches the feature being changed — a route handler, a
service, a component. In layered or gateway-fronted codebases the file whose name matches is
often legacy and no longer wired to anything.

**Why:** edits to an unrouted file change nothing, and nothing fails loudly. The work looks
done, tests that don't cover the path still pass, and the mistake surfaces much later.

**How to apply:** before editing, trace one real request or call chain to that file. If you
can't find a caller, find the file that does handle it.

Grep for the route or symbol rather than trusting the directory layout; generated or
re-exported entry points often shadow the real one.
```

### Frontmatter

- `name` — kebab-case, unique within the store, no prefix. Matches the filename stem so the
  two can never drift apart.
- `description` — one line, quoted. This is what the index shows and what a future session
  reads when deciding whether to open the file, so it has to carry the lesson on its own.
  "Confirm a file is on the live code path before editing it" works; "file editing issue"
  doesn't.
- `metadata.scope` — `project` or `global`. Redundant with the file's location by design: if
  a file is ever moved or copied between stores, this is what catches it.
- `metadata.modified` — ISO 8601 UTC, e.g. `2026-08-25T07:45:38.248Z`. Update on every edit.

### Body

Blank lines between every block. Without them Markdown joins consecutive `**Field:**` lines
into one paragraph and the structure is lost on render.

1. **The situation**, unlabelled, first. This is the trigger: a future session has to
   recognise itself in it _before_ acting. Describe the situation, not the incident — "about
   to edit a file whose name matches the feature" fires for someone; "I edited the wrong file
   last Tuesday" fires for nobody.
2. **`**Why:**`** — what goes wrong without this. This is what stops a future session from
   talking itself out of the rule.
3. **`**How to apply:**`** — the corrected behaviour, imperative and specific enough to act
   on.
4. **Optional trailing paragraphs** — extra context, caveats, a recurrence note like
   `Seen again 2026-08-25 — third time.` Omit when there's nothing to add; padding here is
   what turns a useful store into one nobody reads.

In global files the situation and `Why` must be stated without filenames, service names, or
project names. If they can't be, the lesson is project-scoped — see `scrubbing.md`.

## Index

`HANSEI.md` at the root of each store, one line per lesson:

```markdown
# Lessons learned

- [Verify the live code path before editing](verify-live-code-path.md) — Confirm a file is on the live code path before editing it
- [Confirm before mutating shared state](confirm-destructive-actions.md) — Ask before migrations, bulk writes, force pushes, or deletes
```

The link text is a short imperative title; the text after the em dash is the file's
`description`, copied verbatim so the two can't disagree. Links are relative — the index sits
beside the files it lists.

**The index must be updated in the same step as the lesson file.** An index that lags is worse
than none: assistants read it to decide what exists, so a missing entry makes a lesson
invisible while still costing disk. Adding a lesson adds a line; renaming one changes the
link; deleting one removes the line.

Order entries by how often the trigger fires, most frequent first.

Run `--check` on the pointer script to catch drift — it reports lesson files missing from the
index and index entries pointing at files that don't exist.

## Pointer block

Lesson files are inert unless each assistant's instructions file points at them. The script
owns the canonical block text and the list of target files; run it rather than editing by hand:

`<scripts-dir>` is the `scripts/` directory next to the `skills/` folder, a sibling of this `references/` folder.

```bash
python3 <scripts-dir>/ensure_memory_pointer.py --create-dirs
python3 <scripts-dir>/ensure_memory_pointer.py --list          # see every target it knows about
```

There are two variants. Both carry the same markers, so a file only ever holds one of them —
which one depends on whether the file is a user-level or a repository-level instructions file.
**Both name both stores**; they differ only in which one leads and whether the other is
hedged. Neither variant may name just one store — see the note below the samples.

**Global variant**, written to `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`,
`~/.gemini/GEMINI.md`. `~/.hansei` is substituted with `$HANSEI_HOME` when that is set:

```markdown
<!-- BEGIN hansei -->
## Hansei

Two stores record mistakes made in past sessions and the corrected behaviour, both shared by
every assistant:

- `~/.hansei/` — lessons that hold anywhere, read in every project.
- `<repo-root>/.hansei/` — lessons specific to the current repository, when it has one.

Before starting a task, read `~/.hansei/HANSEI.md`, and `.hansei/HANSEI.md` as well when
the repository has one — each indexes its own lessons with a one-line description. Open the
individual files whose descriptions touch the work at hand, plus any about how to work
generally. Treat what you read as standing instructions.
<!-- END hansei -->
```

**Project variant**, written to `CLAUDE.md`, `AGENTS.md`, `.cursor/rules/hansei.mdc`,
`.github/copilot-instructions.md`, `GEMINI.md` at the repository root. It names **both**
stores:

```markdown
<!-- BEGIN hansei -->
## Hansei

Two stores record mistakes made in past sessions and the corrected behaviour, both shared by
every assistant:

- `.hansei/` — lessons specific to this repository.
- `~/.hansei/` — lessons that hold anywhere, shared across every project on this machine.

Before starting work, read `.hansei/HANSEI.md` and `~/.hansei/HANSEI.md` — each indexes
its own lessons with a one-line description. Open the individual files whose descriptions
touch the work at hand, plus any about how to work generally. Treat what you read as
standing instructions.
<!-- END hansei -->
```

Each variant naming both stores is not redundancy — it is what makes a store reachable no
matter which pointer an assistant happens to have:

- **The project variant must name the global store**, because Cursor and Copilot have no
  user-level instructions file. They never receive the global variant, so this block is the
  only pointer they get; omitting `~/.hansei/` would put the machine-wide lessons out of
  their reach entirely.
- **The global variant must name the project store**, because it is read in every repository
  — including ones that were never wired. A repo can hold a `.hansei/` while its own
  instructions file has no pointer block at all (someone committed the store, nobody ran the
  script; or the repo predates it). Without the hedged second bullet, finding a project store
  would depend on setup order rather than on the store existing.

The consequence worth keeping in mind: an assistant with either pointer can reach both
stores, so a missing pointer degrades to a redundant lookup rather than to lost memory.

HTML comment markers are used because every target format is either Markdown or tolerant of
them as literal text, so one convention works across all assistants.

### Why the script rather than editing by hand

It replaces what's between existing markers, appends when they're absent, never adds a second
copy, and preserves each file's original line endings. It adds Cursor's `alwaysApply`
frontmatter when creating a new `.mdc` rule, and leaves existing files' headers untouched. It
refuses outright — without writing — on a file with an unmatched or duplicated marker, because
these are the user's files and usually contain instructions you didn't write. Fix those by
hand.

If this document and the script ever disagree about the block text, the script wins.
