# Running this under a non-Claude assistant

The memory itself is already portable — one shared store, and the script wires up every
assistant's instructions file. What isn't portable is *this document*. `SKILL.md` with YAML
frontmatter is an Anthropic convention; Cursor, Copilot, Codex, and Gemini won't discover or
auto-load it. So the workflow has to be made reachable by hand, once, per tool.

Three ways, roughly in order of how well they work.

## 1. A slash command or prompt file

**Codex CLI with plugin support:** install via the marketplace (`codex plugin marketplace add
tobinguyenn/hansei`, then `/plugins`), trust the hooks under `/hooks`, and run the setup
skill. Nothing else is needed. The manual path below remains for Cursor, Copilot and Gemini.

Most tools support user-defined prompts. Point the prompt at this skill folder rather than
copying its contents, so there's one source of truth:

- **Codex / Gemini CLI / Zed** — a file in the tool's prompts or commands directory.
- **Cursor** — a rule with `alwaysApply: false`, invoked by name when wanted.
- **Copilot** — a prompt file under `.github/prompts/`.

The body only needs to be a pointer:

```markdown
Run the hansei workflow: read <clone>/plugins/hansei/skills/retro/SKILL.md and follow it exactly,
including the references it names. Do not skip the draft-and-confirm step.
```

The last sentence matters. Step 4 is a hard stop, and an assistant reading these instructions
second-hand is more likely to treat it as advisory and write files without asking.

## 2. Just ask, with the path

No setup at all — paste this when you want it:

> Read `<clone>/plugins/hansei/skills/retro/SKILL.md` and follow it to record lessons from this session.

Works everywhere. Fine if you run this occasionally rather than habitually.

## 3. A permanent line in the instructions file

Add to `AGENTS.md` (or the tool's equivalent), *outside* the `hansei` markers so the
script doesn't overwrite it:

```markdown
When asked for lessons learned, a retro, or to remember a mistake, read
`<clone>/plugins/hansei/skills/retro/SKILL.md` and follow that workflow.
```

The tradeoff: it costs context in every session to serve an occasional request. Option 1 is
better if the tool supports it.

## Where to put the skill folder

Anywhere stable and readable by all your tools. Somewhere like `~/.agents/skills/hansei/`
keeps it next to the memory it manages and out of any single vendor's directory — which also
avoids the failure mode where reinstalling one tool's skills wipes it.

Avoid putting it inside a directory that a tool manages and replaces on update.

## What to expect from other assistants

The workflow is plain prose and one Python script, so nothing depends on Claude-specific
tooling. The parts most likely to degrade:

- **The draft-and-confirm stop.** Assistants tuned to act rather than ask may write
  immediately. Reinforce it in whatever prompt you set up.
- **Scrubbing discipline.** Getting project identity out of global lessons takes care;
  `references/scrubbing.md` has to actually be read, not skimmed.
- **The honest-classification rule.** Under `--scope global`, the temptation is to rewrite
  project lessons to fit rather than dropping them.

If lessons written by another tool start showing project names in the global store, that's the
signal — tighten the prompt to name `references/scrubbing.md` explicitly.
