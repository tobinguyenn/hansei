---
name: setup
description: 'One-time wiring of hansei after installing the plugin: creates the lesson stores, writes the pointer blocks, removes old user-level hansei hooks, and installs the `/hansei` alias. Idempotent. Run only when the user asks for hansei setup.'
---

# Hansei setup

One-time wiring after installing the plugin. `<scripts-dir>` is the `scripts/` directory next to this SKILL.md's parent `skills/` folder.

There is no approval step: the user invoked this skill explicitly for exactly these writes, and every write is idempotent. Do not ask questions.

1. Run the check and show its output:

   ```bash
   python3 <scripts-dir>/ensure_memory_pointer.py --check --scope default
   ```

2. If the check exited 2 (malformed markers in an instructions file), stop here. Show the file named in the error and tell the user to fix it; do not run step 3.

3. Otherwise run the setup and show its output. If it exits 2 (for example a malformed settings file, named in the error message), show the error and the named file, tell the user to fix or remove that file, and stop:

   ```bash
   python3 <scripts-dir>/ensure_memory_pointer.py --scope default --create-dirs --remove-hooks --remove-legacy-skill --shim
   ```

4. Summarise every path touched, grouped as created, updated, removed, moved.

5. Remind the user: Codex requires trusting the two hansei hooks under `/hooks`, and Claude Code needs `/reload-plugins` or a restart for the new hooks to load.
