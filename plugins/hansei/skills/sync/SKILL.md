---
name: sync
description: Repair the hansei lesson indexes so every lesson file is listed and every link resolves. Shows the change and waits for approval. Does not scan the session or write lessons; use `/hansei:retro` for that.
---

# Hansei index sync

`<scripts-dir>` is the `scripts/` directory next to this SKILL.md's parent `skills/` folder.

1. Preview the change without writing anything:

   ```bash
   python3 <scripts-dir>/ensure_memory_pointer.py --sync-index --dry-run --scope default
   ```

2. If it exited 2 (a lesson has no frontmatter description; the error names the file), show the error, tell the user to add the description to that file, and stop.

   If it exited 0, report that both indexes are in sync and stop.

3. Show the diff per store and ask for approval. The user may drop individual entries or edit a description; apply such edits by hand after the script run if needed.

4. Wait. Write nothing until the user approves.

5. Apply, then re-check, and report:

   ```bash
   python3 <scripts-dir>/ensure_memory_pointer.py --sync-index --scope default
   python3 <scripts-dir>/ensure_memory_pointer.py --check --scope default
   ```

6. Anything outside the index that the check reports (missing pointer block, duplicated hook, missing shim) is reported with "run `/hansei:setup`", not fixed here.
