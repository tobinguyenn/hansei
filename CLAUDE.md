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

**Delegating to a subagent.** A subagent inherits none of this — it gets no hook, and in
practice it does not act on a pointer to a file. So before delegating, pick the lessons that
touch what it will do and paste their `Why` and `How to apply` text into its prompt as hard
constraints; never hand it a path to read. Include the whole index when the subagent can write
files or run commands: a lesson only looks irrelevant until the subagent does the thing it
warns about.
<!-- END hansei -->
