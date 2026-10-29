---
name: check
description: 'Read-only health check of the hansei setup: stores, pointer blocks, hooks, `/hansei` alias, index drift, session state. Changes nothing.'
---

# Hansei check

Read-only. `<scripts-dir>` is the `scripts/` directory next to this SKILL.md's parent `skills/` folder.

1. Run:

   ```bash
   python3 <scripts-dir>/ensure_memory_pointer.py --check --scope default
   ```

   Exit 0 means healthy, 1 means something needs work, 2 means an instructions file has malformed markers.

2. Print a short table (item, state) built from the output lines. The first column of each line says what it is:
   - `store`, `agents`: where the lesson stores are and which assistants were detected.
   - an assistant key such as `claude` (pointer block): `ok`, or `missing` / `would-add` / `would-update` when the block needs writing.
   - `hook`: `clean`, or `duplicate` (an old user-level hansei hook still present) / `invalid` (settings file cannot be parsed; route to fixing the named settings file by hand, not to `/hansei:setup`).
   - `legacy`: `none`, or `present` (old clone at the legacy skill path).
   - `shim ... legacy`: the alias path is occupied by the old clone; route to `/hansei:setup`.
   - `agents` rows: `detected` is informational only; `missing` / `would-add` / `would-update` are real Codex-pointer findings.
   - `shim` (the `/hansei` alias): `ok`, or `would-add` / `would-update`.
   - `index`: `ok`, or `unlisted` / `dead link` / `MISSING`.

3. Finish with exactly one fix command:
   - `/hansei:setup` if any pointer, `duplicate` hook, shim or legacy line needs work (including exit 2: tell the user to fix the named file first). For an `invalid` hook row, instead tell the user to fix the named settings file by hand.
   - `/hansei:sync` if only index lines show drift.
   - If both kinds appear, name `/hansei:setup` first and mention `/hansei:sync` after it.
   - Nothing when everything is green.

Must not run anything else, and must not write or modify any file.
