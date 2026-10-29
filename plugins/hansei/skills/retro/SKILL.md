---
name: retro
description: Reviews the current session for mistakes the assistant made, distills them into actionable lessons, and saves them as memory files in one vendor-neutral global store at `~/.hansei/` (project-agnostic) and `<repo-root>/.hansei/` (project-specific), shared by every assistant, wiring them into whichever instructions files the assistants in use read (CLAUDE.md, AGENTS.md, Cursor rules, Copilot instructions, GEMINI.md) so future sessions pick them up. Use this whenever the user asks to run hansei, or asks for lessons learned, a session retro or post-mortem, "what did you get wrong", "what did you learn", "remember your mistakes", "don't make that mistake again", "save this to memory so you don't repeat it", or otherwise asks to turn this conversation's errors and corrections into durable memory. Trigger on explicit requests only — do not run it unprompted.
---

# Lessons Learned

Turn the mistakes made in this session into memory that survives it.

The value of this skill is entirely in the quality of the lessons. Three sharp, specific
lessons beat fifteen vague ones — a memory file full of "be more careful" is worse than no
memory file at all, because it burns context in every future session and teaches nothing.

## When this runs

Only on explicit request. The user asks for a retro, or lessons learned, or tells you to
remember something you got wrong. Never volunteer this mid-task and never run it "just in
case" at the end of a session.

## Arguments

`--scope default | project | global` — which memory store to write to. Accept it as a flag or
in plain language ("only global ones", "just for this repo"); they mean the same thing.

- **`default`** (assumed when nothing is given) — classify each lesson on its merits and write
  it wherever it belongs. Some sessions produce only global lessons, some only project ones,
  some both.
- **`global`** — write only to the global store (see below).
- **`project`** — write only to `<repo-root>/.hansei/`.

The flag filters the output; it does not change the classification. Classify every lesson
honestly in step 2, then drop the ones outside the requested scope. This matters most for
`--scope global`: a lesson that only makes sense with a filename or service name in it is
still a project lesson, and rewriting it to fit global memory would smuggle project identity
into a store that must not contain any. Drop it instead and say so.

Don't silently discard. When the flag filters lessons out, list them in the draft by title
with their real scope, so the user can re-run without the flag if they want them after all.

If `--scope project` is requested but there's no project context (no repo, no project
directory, the work was purely conversational), say so and stop rather than falling back to
global — the user asked for something that doesn't exist here.

`--agent <key>` — restricts the run to one assistant's instructions files. It does **not**
affect where lessons are stored: the global store is always `~/.hansei/` and the project store
is always `<repo-root>/.hansei/`, regardless of which assistants get wired.

Optional. By default the script wires **every assistant it detects in use** — checking
`~/.claude`, `~/.codex`, `~/.gemini` for global scope and `CLAUDE.md`, `AGENTS.md`,
`.cursor`, `.github` in the repo for project scope — falling back to `claude` if it finds
none. Since they all point at the same store, wiring several cannot split the memory; it
just means more tools read the same lessons.

Pass `--agent` only when the user asks to limit it to one tool. The script prints the set it
chose and why on its `agents` lines — watch those rather than assuming.

Two assistants can never be wired globally: Cursor keeps user-level rules in app settings
and Copilot has no user-level file at all. Both still get project pointers. This is a limit
of those tools, not something to work around.

## One store, many assistants

The memory is deliberately not Claude-specific. Neither store path contains a vendor name —
`~/.hansei/` and `<repo-root>/.hansei/` — so uninstalling any one tool leaves the lessons
intact. Every assistant is pointed at the same files through whatever instructions file it
happens to read —
`CLAUDE.md`, `AGENTS.md`, `.cursor/rules/`, `.github/copilot-instructions.md`, `GEMINI.md`.
A mistake recorded while working in one tool is therefore corrected in all of them, which is
most of the point.

The global store sits under one agent's home directory (`--agent`) and the project store under
`<repo-root>/.hansei/`, but both are single stores that every assistant reads. Hosting the
global one inside a vendor directory is an addressing decision, not an ownership one — never
write a second copy for a second tool.

Two consequences for how lessons get written:

- **Write for an unknown reader.** A lesson may be read by an assistant with different tools
  and a different interface. "Use the Edit tool rather than rewriting the file" assumes a
  specific toolset; "make targeted edits rather than rewriting whole files" doesn't. Prefer
  the behaviour over the mechanism.
- **Don't name the assistant that made the mistake** unless the lesson genuinely only applies
  to that one. Lessons are about the work, not about who was at the keyboard.

If the user is running this skill under a non-Claude assistant, see
`references/other-agents.md` — such tools don't auto-load `SKILL.md`, so the workflow has to
be reachable another way.

## The workflow

Five steps: scan → classify → draft → confirm → write. Step 4 is a hard stop — never write
memory files before the user has approved the draft.

### 1. Scan the session for real mistakes

Re-read the conversation from the start and collect moments where things actually went wrong.
What counts:

- The user corrected you, pushed back, or said the output was wrong
- You had to redo or throw away work
- A command, test, or build failed because of an assumption you made
- You misread the requirements, edited the wrong thing, or solved a different problem
- You broke a convention the user had already stated
- You guessed at something you could have verified, and guessed wrong
- You were confidently wrong about a fact, API, or file's contents

What does **not** count — recording these dilutes the file:

- The user changing their mind or adding a new requirement. That is not your mistake.
- Normal exploration: reading files, trying an approach, finding a better one.
- One-off flakiness (network blip, transient tool error) with no generalizable takeaway.
- Typos you caught and fixed yourself in the same turn.
- Anything you'd have to stretch to call a mistake. If the session genuinely went well, say
  so and stop. Inventing lessons to have something to show is the main failure mode here.

Then merge: several symptoms often share one root cause. "Edited the wrong file", "assumed
the config was JSON", and "guessed at the function signature" may all be one lesson about
verifying before acting. Prefer the root cause. Aim for **1–7 lessons**; if you have more,
you are recording symptoms.

### 2. Classify each lesson: global or project

Ask of each lesson: *would this still be useful in a completely different codebase, for a
different client, next year?*

- **Yes → global.** Goes to the global store (`~/.hansei/`), stripped of every trace of
  this project. This is the strict one — read `references/scrubbing.md` before writing any
  global lesson.
- **No, it depends on this project's specifics → project.** Goes to
  `<repo-root>/.hansei/`, and may name files, paths, services, and
  conventions freely. Project memory is only useful *because* it is specific.

Project lessons live inside the repository, which means they are likely to be committed and
read by teammates. Write them as notes to the team, not as a private diary: no credentials, no
remarks about individuals, nothing you wouldn't put in a code comment. Never write to
`~/.claude/projects/<project>/memory/` — that path belongs to the automatic memory system and
anything placed there by hand may be rewritten or discarded.

A single mistake can legitimately produce both: a general lesson about verifying assumptions,
and a project lesson recording the specific fact you got wrong. Split it when both are
genuinely useful, but don't pad — one good lesson in one place is fine.

If there's no project context (no repo, no project directory, the work was purely
conversational), everything is global and you skip the project half entirely.

Classify on the merits regardless of `--scope` — the flag is applied after this step, not
during it. Deciding a lesson is "global" because the flag said global is how project names end
up in global memory.

### 3. Check what already exists

Resolve the project root first — the git root if there is one, otherwise the working
directory — so project lessons land at the top of the repo rather than in whatever
subdirectory the session happened to be in.

Then find out whether the assistants' instructions files are already wired up to read these
folders. Do this *now*,
before drafting, not at write time — the answer changes what you show the user, and a refusal
here is much cheaper to handle before any files exist than after. `<scripts-dir>` is the
`scripts/` directory next to this SKILL.md's parent `skills/` folder.

```bash
python3 <scripts-dir>/ensure_memory_pointer.py --check --scope <default|global|project> [--agent <key>]
```

Pass the same scope the user asked for — the script takes the same three words, so there's
nothing to translate. Checking a project instructions file you have no intention of writing to would
report work that isn't going to happen.

Read the exit code, not just the output. `0` means the instructions files in scope already point
at the memory folders. `1` means at least one needs the pointer added — normal on first run,
and it means step 5 will modify or create an instructions file, which belongs in the draft. `2` means a
an instructions file has an unmatched or duplicated marker and the script won't touch it; surface that in
the draft and ask the user to fix it or confirm they want the lessons written anyway with the
wiring left undone.

Then find out what's already recorded, so you can tell new from repeat. Each store has an
index, `HANSEI.md`, listing every lesson with a one-line description — read that
first and open only the individual files whose descriptions look close to what you're about
to write. The `--check` run above prints the resolved global store path on its `store` line:

```bash
cat "${HANSEI_HOME:-$HOME/.hansei}"/HANSEI.md 2>/dev/null
cat "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"/.hansei/HANSEI.md 2>/dev/null
```

If `--check` reported index drift — unlisted files or dead links — fix it as part of this run
even for lessons you didn't write. An index that lags makes existing lessons invisible.

Open any lesson file whose index description overlaps with what you're about to write.
Then, for each lesson:

- **Already recorded, same substance** → don't create a second file. Update the existing one:
  sharpen the wording, add a trailing recurrence note, bump `metadata.modified`. A lesson
  you've now violated twice is worth making more pointed, not worth writing twice.
- **New** → new file, new index entry.

One lesson per file. The filename, the frontmatter `name`, and the index entry all describe
the same single lesson, which is what lets the index stand in for reading the whole store.
Don't bundle two lessons into one file to keep the count down — split them and let the index
carry the weight.

### 4. Show the draft and stop

Present every proposed lesson before touching the filesystem, written in the file's own
format (Trigger / Do / Problem, blank-line separated — see `references/formats.md`) so what
the user approves is exactly what gets written. For each one show:

- The lesson text, exactly as it will be written
- Scope (global / project)
- Target file, and whether it's new, appended to, or an update of an existing entry
- One line of evidence: what happened in this session that produced it

Group by scope, global first. If `--scope` was anything other than `default`, say which scope
is active at the top of the draft, and list any lessons it filtered out — title and their real
scope, one line each. A user who asked for global lessons should still find out that the
session produced three project ones.

For global lessons, if scrubbing changed the wording substantially, it's worth showing what
was removed so the user can confirm nothing identifying leaked and nothing essential was lost.

Then state what will happen outside the lesson files themselves, based on the `--check` result
from step 3 — the user is approving a set of filesystem changes, so nothing should be a
surprise afterwards:

- Which instructions files will be created or modified, and for which assistants -- or that
  they are already wired up and won't be touched.
- If `--check` returned 2, that the wiring is blocked and why.
- If this would be the first time `.hansei/` is created in this repository, say so — it
  adds tracked files to someone's project, and they may prefer it gitignored. Ask; don't
  decide for them.

Then ask for approval, and make it easy to edit: the user should be able to say "drop 2, and
3 should be global not project" and have that just work.

Wait for a response. Do not write anything yet.

### 5. Write

After approval, run the script first — it creates the memory folders and wires up every
assistant's instructions file in one go, so the directories exist before you write into them:

```bash
python3 <scripts-dir>/ensure_memory_pointer.py --scope <default|global|project> --create-dirs
```

Use the same scope as step 3. Under `default`, narrow it to the scope you actually wrote to —
if every lesson turned out global, pass `--scope global` rather than creating an empty project
memory folder and adding a pointer block to a repository for lessons that don't exist.

If it exits 2 here despite step 3 looking clean, something changed underneath you — stop and
tell the user rather than writing lessons that nothing will read.

Then:

1. Write or update the lesson files using the format in `references/formats.md`: YAML
   frontmatter (`name`, `description`, `metadata.scope`, `metadata.modified`), then the
   situation, `**Why:**`, `**How to apply:**`, with blank lines between every block.
2. **Update `HANSEI.md` in each store you touched.** Add a line per new lesson,
   revise the line for any lesson you changed, and remove lines for anything deleted. This is
   not optional and not a follow-up task — a lesson missing from the index is invisible to
   every future session, so writing the file without the entry accomplishes nothing. Create
   the index if the store doesn't have one yet.
3. Re-run the script with `--check` to confirm the index and the files agree. It reports
   unlisted lessons and dead links; either means step 2 was done incompletely.
4. Report back concisely: which lesson files were created vs. updated, that the index was
   updated, and any instructions files the script touched.

Write the memory only. Never modify project source, config, or docs as part of "applying" a
lesson — if a lesson implies a code change, mention it and let the user decide.

## Naming

```
<store>/HANSEI.md            index, one line per lesson
<store>/<kebab-name>.md      one lesson per file
```

Where `<store>` is `~/.hansei/` (global) or `<repo-root>/.hansei/` (project).

`<kebab-name>` is short, lowercase, hyphenated, and describes the lesson rather than the
incident: `verify-live-code-path`, `confirm-destructive-actions`, `no-unrequested-comments`.
No prefix on the filenames — the dedicated store does the namespacing that a prefix used to,
so `verify-live-code-path.md` says everything a prefixed name would. The frontmatter `name` is
the filename stem, so the two can never drift. Everything in the store except `HANSEI.md` is a
lesson.

## References

Paths below are relative to the plugin root: the `scripts/` and `references/` directories next to this SKILL.md's parent `skills/` folder.

- `scripts/ensure_memory_pointer.py` — checks whether each assistant's instructions file points
  at the hansei stores and adds the pointer if not. `--list` shows every known agent,
  its instructions files, and where it would host the global store — useful when the user asks
  what's supported. Takes the same
  `--scope default|global|project` values the skill does (`both` is a synonym for `default`),
  plus `--agent` (which assistant this run is for, defaults to `claude`). Idempotent. Exit codes: `0`
  wired up, `1` needs the pointer (`--check` only), `2` refused because an instructions file has
  malformed markers. `--check` never writes, which also makes it usable as a pre-commit or CI
  guard against drift.
- `references/other-agents.md` — how to make this workflow reachable from Cursor, Copilot,
  Codex, or Gemini, which don't auto-load `SKILL.md`. Read when the user asks about using this
  outside Claude Code.
- `references/scrubbing.md` — how to strip project identity from global lessons, with
  before/after examples. Read this before writing any global lesson.
- `references/formats.md` — the memory file template, the lesson entry format, and the
  pointer block.
