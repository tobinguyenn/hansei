# Scrubbing global lessons

A global lesson is read in sessions that have nothing to do with the project it came from. If
it mentions that project, it's noise at best and a leak at worst — global memory follows the
user across clients, employers, and machines.

The test: **could a stranger read this file and learn anything about who you work for or what
you're building?** If yes, keep scrubbing.

## Remove

| Category | Examples |
|---|---|
| Project / repo / product names | `acme-billing`, `Project Hydra`, `the Nimbus dashboard` |
| Company, client, team names | `Acme Corp`, `the Sun\* team`, `the payments squad` |
| People's names and handles | `J. Doe asked for...`, `per @reviewer's comment` |
| Absolute or project-relative paths | `/Users/jdoe/work/acme/src/api/billing.ts`, `apps/web/lib/auth.ts` |
| Specific filenames unique to the project | `BillingReconciler.java`, `acme_config.yaml` |
| Internal service, table, env, and endpoint names | `svc-ledger-v2`, `users_legacy_tbl`, `PROD_EU_WEST` |
| Ticket / PR / issue IDs and URLs | `JIRA-4821`, `PR #338`, internal wiki links |
| Domains, hostnames, IPs, and anything credential-shaped | any of it, always |
| Business specifics | `the 3% partner fee`, `the Q4 migration deadline` |

## Keep

Scrubbing is about *identity*, not *technicality*. Strip everything that says whose project it
was; keep what makes the lesson actionable.

- **Public technology names** — React, Postgres, pytest, Docker, ripgrep. A lesson about a
  real API's real behavior is general knowledge and is most of what makes it useful. Reducing
  "Prisma's `findMany` returns `[]`, not `null`" to "the ORM behaves unexpectedly" destroys
  the lesson.
- **Generic role descriptions** — "a monorepo", "a CI pipeline", "a legacy migration script",
  "a config file in an unfamiliar format".
- **The behavioural pattern** — what you assumed, what you should have done first, what the
  cost of getting it wrong was.

## Rewriting

Replace identity with role. `acme-billing/src/reconcile.ts` becomes "a large module in an
unfamiliar codebase". A person's name becomes "the user". `JIRA-4821` disappears.

If a lesson survives scrubbing as nothing but "verify things before assuming", it was never a
global lesson — either it's project-specific, or the general version of it already exists in
your global memory. Don't force it.

## Which parts of a lesson leak

In the file format (`formats.md`), specifics get in through two blocks in particular:

- **The situation paragraph.** It describes where the lesson applies, so it reaches for the
  place it actually happened. "About to edit `packages/api/src/routes/invoices.ts`" has to
  become "about to edit a file whose name matches the feature being changed."
- **`**Why:**`.** It explains what broke, so it reaches for what specifically broke.

`**How to apply:**` is usually already clean, because corrected behaviour is naturally
general. `description` in the frontmatter is copied verbatim into the index — check it too;
a scrubbed body under a leaky description defeats the exercise.

## Examples

The pairs below show a raw observation split into its global and project versions. They are
illustrations of the rewrite, not file templates — see `formats.md` for the actual layout.

**Raw observation:** Edited `packages/api/src/routes/invoices.ts` assuming it was the live
handler, but Acme routes invoices through `packages/gateway` — wasted 20 minutes and the user
had to point it out.

- Global: *Before editing a file that looks like the right entry point, confirm it's actually
  on the live code path — in layered or gateway-fronted architectures, the file whose name
  matches the feature is often dead or superseded. Trace one real request end to end first.*
- Project: *Invoice requests are handled in `packages/gateway`, not
  `packages/api/src/routes/invoices.ts` — the latter is legacy and unrouted.*

**Raw observation:** Told the user the deploy script took an `--env` flag. It doesn't; it
reads `DEPLOY_TARGET`. The command failed in front of them.

- Global: *Don't state a CLI's flags from memory. Run `--help` or read the script before
  telling the user how to invoke it — a confidently wrong invocation costs more trust than a
  five-second check costs time.*
- Project: *The deploy script takes no `--env` flag; the target comes from the
  `DEPLOY_TARGET` environment variable.*

**Raw observation:** User said twice to stop adding explanatory comments to their code; kept
doing it.

- Global: *When the user states a style preference, treat it as standing policy for the rest
  of the session, not feedback on one file. Re-check it before each subsequent edit — repeat
  violations of an explicit instruction read as not listening.*
- Project: usually none. Preferences that follow the person belong in global memory.

**Raw observation:** Ran a migration against the shared staging database without asking.

- Global: *Before running anything that mutates shared or persistent state — migrations, bulk
  writes, force pushes, deletes — stop and confirm, even when the task seems to imply it.
  Reversibility, not difficulty, is what decides whether to ask.*
- Project: *Migrations must not be run without explicit approval; the staging database is
  shared.*
