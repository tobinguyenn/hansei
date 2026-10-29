#!/usr/bin/env python3
"""Point every coding assistant on this machine at the shared hansei memory.

The lessons live in one vendor-neutral store; each assistant just gets a pointer block
in whatever instructions file it happens to read. A mistake learned in one tool then
improves all of them.

    ~/.hansei/            global, shared by every assistant on the machine
    <repo-root>/.hansei/  project, shared by every assistant in the repository

Neither path contains a vendor name: the store outlives any one tool being uninstalled,
and every wired assistant reads the same lessons. Set $HANSEI_HOME to move the global one.

Usage:

    python ensure_memory_pointer.py                       # wire every detected assistant
    python ensure_memory_pointer.py --agent gemini        # wire Gemini only
    python ensure_memory_pointer.py --hook                # also wire the user-level context hooks
                                                          # (--no-hook is accepted; hooks are off by default)
    python ensure_memory_pointer.py --remove-hooks        # strip legacy user-level hansei hooks
    python ensure_memory_pointer.py --check               # report only, never write
    python ensure_memory_pointer.py --scope global
    python ensure_memory_pointer.py --list                # show the registry and exit

Exit codes: 0 = in order (or changes applied), 1 = changes needed but --check was set,
2 = refused (malformed markers, bad arguments). The codes make it usable as a pre-commit
or CI guard against an instructions file that drifted out of sync.
"""

from __future__ import annotations

import sys

MIN_PY = (3, 9)
if sys.version_info < MIN_PY:
    sys.stderr.write(f"hansei needs Python {'.'.join(map(str, MIN_PY))}+, found {sys.version.split()[0]}\n")
    sys.exit(2)

import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

BEGIN = "<!-- BEGIN hansei -->"
END = "<!-- END hansei -->"

INDEX_NAME = "HANSEI.md"       # index at the root of each store
PROJECT_STORE = ".hansei"      # <repo-root>/.hansei/
GLOBAL_STORE = ".hansei"       # ~/.hansei/ -- same leaf name at both scopes
HOME_ENV = "HANSEI_HOME"       # escape hatch: absolute path overriding ~/.hansei

# HTML comments are the marker style because every target below is either Markdown or
# tolerant of them as literal text, so one convention works across all agents.

def global_body(store: str) -> str:
    """Names the project store as well, hedged, because this block is read in every
    repository -- including ones whose own instructions file was never wired. Without the
    second bullet a repo-local `.hansei/` is only ever found when the project pointer
    happens to exist, which makes discovery depend on setup order."""
    return f"""## Hansei

Two stores record mistakes made in past sessions and the corrected behaviour, both shared by
every assistant:

- `{store}/` — lessons that hold anywhere, read in every project.
- `<repo-root>/.hansei/` — lessons specific to the current repository, when it has one.

Before starting a task, read `{store}/{INDEX_NAME}`, and `.hansei/{INDEX_NAME}` as well when
the repository has one — each indexes its own lessons with a one-line description. Open the
individual files whose descriptions touch the work at hand, plus any about how to work
generally. Treat what you read as standing instructions.

**Delegating to a subagent.** A subagent inherits none of this — it gets no hook, and in
practice it does not act on a pointer to a file. So before delegating, pick the lessons that
touch what it will do and paste their `Why` and `How to apply` text into its prompt as hard
constraints; never hand it a path to read. Include the whole index when the subagent can write
files or run commands: a lesson only looks irrelevant until the subagent does the thing it
warns about."""


def project_body(store: str) -> str:
    """Names *both* stores, not just the project one.

    Cursor and Copilot have no user-level instructions file, so this block is the only
    pointer they ever get -- if it omitted the global store, the machine-wide lessons would
    be unreachable for them. Naming both here also means a project file read without its
    global counterpart still leads to everything.
    """
    return f"""## Hansei

Two stores record mistakes made in past sessions and the corrected behaviour, both shared by
every assistant:

- `.hansei/` — lessons specific to this repository.
- `{store}/` — lessons that hold anywhere, shared across every project on this machine.

Before starting work, read `.hansei/{INDEX_NAME}` and `{store}/{INDEX_NAME}` — each indexes
its own lessons with a one-line description. Open the individual files whose descriptions
touch the work at hand, plus any about how to work generally. Treat what you read as
standing instructions.

**Delegating to a subagent.** A subagent inherits none of this — it gets no hook, and in
practice it does not act on a pointer to a file. So before delegating, pick the lessons that
touch what it will do and paste their `Why` and `How to apply` text into its prompt as hard
constraints; never hand it a path to read. Include the whole index when the subagent can write
files or run commands: a lesson only looks irrelevant until the subagent does the thing it
warns about."""

# Cursor only guarantees a rule stays in context when its frontmatter says so, so a newly
# created rule file needs this header. Existing files are left exactly as found.
MDC_HEADER = "---\ndescription: Hansei lessons-learned memory\nalwaysApply: true\n---\n\n"


@dataclass(frozen=True)
class Agent:
    key: str
    label: str
    project_file: str
    global_file: str | None  # None = this tool has no user-level instructions file
    detect: tuple[str, ...] = ()  # repo-relative paths indicating the tool is in use
    global_detect: tuple[str, ...] = ()  # home-relative equivalents
    header: str = ""  # prepended only when creating the file from scratch
    note: str = ""


REGISTRY: dict[str, Agent] = {
    a.key: a
    for a in [
        Agent(
            "claude", "Claude Code",
            project_file="CLAUDE.md",
            global_file=".claude/CLAUDE.md",
            detect=("CLAUDE.md", ".claude"),
            global_detect=(".claude",),
        ),
        Agent(
            "agents", "AGENTS.md (Codex, Zed, others)",
            project_file="AGENTS.md",
            global_file=".codex/AGENTS.md",
            detect=("AGENTS.md",),
            global_detect=(".codex",),
        ),
        Agent(
            "cursor", "Cursor",
            project_file=".cursor/rules/hansei.mdc",
            global_file=None,
            detect=(".cursor", ".cursorrules"),
            header=MDC_HEADER,
            note="Cursor keeps user-level rules in app settings, not a file; global scope skipped.",
        ),
        Agent(
            "copilot", "GitHub Copilot",
            project_file=".github/copilot-instructions.md",
            global_file=None,
            detect=(".github/copilot-instructions.md", ".github"),
            note="Copilot has no user-level instructions file; global scope skipped.",
        ),
        Agent(
            "gemini", "Gemini CLI",
            project_file="GEMINI.md",
            global_file=".gemini/GEMINI.md",
            detect=("GEMINI.md", ".gemini"),
            global_detect=(".gemini",),
        ),
    ]
}



class PointerError(Exception):
    """A file we refuse to touch, because editing it would risk mangling it."""


def render(body: str) -> str:
    return f"{BEGIN}\n{body}\n{END}"


def project_root() -> Path:
    """Git root if there is one, else cwd -- so files land at the top of the repo rather
    than in whatever subdirectory the session happened to be in."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip()).resolve()
    except (OSError, subprocess.SubprocessError):
        pass
    return Path.cwd().resolve()


def newline_style(raw: str) -> str:
    """Match existing line endings. Takes the *untranslated* text -- Path.read_text()
    normalises CRLF to LF, which would make this always answer LF and quietly rewrite
    Windows files."""
    crlf = raw.count("\r\n")
    return "\r\n" if crlf and crlf >= raw.count("\n") - crlf else "\n"


def read_untranslated(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write_verbatim(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def ensure_ignored(root: Path, check: bool) -> str:
    """Make sure <repo-root>/.gitignore lists the project store. Returns ok / added /
    would-add. Existing lines and line endings are left as they were."""
    path = root / ".gitignore"
    raw = read_untranslated(path) if path.is_file() else ""
    entries = {line.strip() for line in raw.splitlines()}
    if entries & {PROJECT_STORE, PROJECT_STORE + "/", "/" + PROJECT_STORE, "/" + PROJECT_STORE + "/"}:
        return "ok"
    if check:
        return "would-add"
    nl = newline_style(raw)
    sep = "" if not raw or raw.endswith("\n") else nl
    write_verbatim(path, raw + sep + PROJECT_STORE + "/" + nl)
    return "added"


def ensure(path: Path, body: str, check: bool, header: str = "") -> str:
    """Return: ok, added, updated, missing, would-add, would-update."""
    block = render(body)

    if not path.exists():
        if check:
            return "missing"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_verbatim(path, header + block + "\n")
        return "added"

    original = read_untranslated(path)
    nl = newline_style(original)
    text = original.replace("\r\n", "\n")

    has_begin, has_end = BEGIN in text, END in text
    if has_begin != has_end:
        raise PointerError(
            f"{path} has an unmatched hansei marker. Fix it by hand -- "
            "refusing to guess where the block ends."
        )

    if has_begin:
        if text.count(BEGIN) > 1:
            raise PointerError(
                f"{path} contains more than one hansei block. "
                "Remove the duplicates by hand."
            )
        start, stop = text.index(BEGIN), text.index(END) + len(END)
        if text[start:stop] == block:
            return "ok"
        if check:
            return "would-update"
        updated = text[:start] + block + text[stop:]
        status = "updated"
    else:
        if check:
            return "would-add"
        sep = "" if text.endswith("\n\n") or not text.strip() else ("\n" if text.endswith("\n") else "\n\n")
        updated = text + sep + block + "\n"
        status = "added"

    if nl != "\n":
        updated = updated.replace("\n", nl)
    write_verbatim(path, updated)
    return status


# Three tools currently support a hook that fires early enough per turn to inject context,
# each under its own event name and settings file, but all three use the same shape of JSON
# once you're inside the event's hook list ({"hooks": [{"type": "command", "command": ...}]})
# -- so one ensure_hook() below serves all of them. Cursor and Copilot are absent on purpose:
# an always-apply Cursor rule and .github/copilot-instructions.md are already sent with every
# request by those tools, so there is nothing a hook would add for them.
HOOK_SPECS: dict[str, list[dict]] = {
    # Claude Code gets two hooks. UserPromptSubmit runs hansei_context.py every turn and
    # lets the script decide between the full index and a one-line reminder; SessionStart
    # (startup, resume, clear, compact) runs it with --full, because each of those events
    # builds a context window the index is not yet in -- compaction in particular would
    # otherwise silently drop it until the script's periodic safety net fires.
    "claude": [
        dict(event="UserPromptSubmit", fmt="claude", matcher=True, extra="",
             settings=".claude/settings.json"),
        dict(event="SessionStart", fmt="claude", matcher=False, extra="--full",
             settings=".claude/settings.json"),
    ],
    # "agents" also covers Zed and other AGENTS.md readers, but this hook config format
    # (hooks.json, no matcher key) is specifically Codex CLI's -- harmless for the others,
    # since they simply never read ~/.codex/hooks.json or <repo>/.codex/hooks.json.
    "agents": [
        dict(event="UserPromptSubmit", fmt="codex", matcher=False, extra="",
             settings=".codex/hooks.json"),
    ],
    "gemini": [
        dict(event="BeforeAgent", fmt="gemini", matcher=True, extra="",
             settings=".gemini/settings.json"),
    ],
}


SHIM_REL = ".claude/skills/hansei"
SHIM_TEXT = (
    "---\n"
    "name: hansei\n"
    "description: Alias for the hansei:retro plugin skill (session retro, lessons learned). "
    "Prefer hansei:retro when choosing a skill on your own; this alias exists so the user "
    "can type /hansei.\n"
    "---\n"
    "\n"
    "Invoke the `hansei:retro` skill now, passing these arguments through unchanged: "
    "$ARGUMENTS\n"
)


def is_legacy_clone(skill_dir: Path) -> bool:
    """A git clone of this repo used as the skill folder (pre-plugin install)."""
    return (skill_dir / "scripts" / "ensure_memory_pointer.py").is_file()


def move_legacy_skill(skill_dir: Path, check: bool, today: str) -> str:
    """Return: none, would-move, moved. Never deletes; renames to hansei.bak-<date>[-n]."""
    if not is_legacy_clone(skill_dir):
        return "none"
    if check:
        return "would-move"
    target = skill_dir.with_name(f"hansei.bak-{today}")
    n = 0
    while target.exists():
        n += 1
        target = skill_dir.with_name(f"hansei.bak-{today}-{n}")
    skill_dir.rename(target)
    return "moved"


def ensure_shim(skill_dir: Path, check: bool) -> str:
    """Return: legacy, ok, would-add, would-update, added, updated."""
    if is_legacy_clone(skill_dir):
        return "legacy"
    path = skill_dir / "SKILL.md"
    exists = path.is_file()
    if exists and read_untranslated(path) == SHIM_TEXT:
        return "ok"
    if check:
        return "would-update" if exists else "would-add"
    skill_dir.mkdir(parents=True, exist_ok=True)
    write_verbatim(path, SHIM_TEXT)
    return "updated" if exists else "added"


def is_hansei_hook(h: dict) -> bool:
    """The script path is the identity of a hansei hook (see ensure_hook)."""
    if not isinstance(h, dict) or h.get("type") != "command":
        return False
    command = h.get("command")
    return isinstance(command, str) and "hansei_context.py" in command


# Settings files the hooks above are written to, relative to the home or repo root.
HOOK_FILES: tuple[str, ...] = (".claude/settings.json", ".codex/hooks.json")


def remove_hooks(settings_file: Path, check: bool) -> str:
    """Strip hansei hooks from one settings file, leaving everything else as found.
    Return: absent, clean, would-remove, removed. A file with no hansei hook is never
    rewritten, so foreign entries (with or without a `matcher` key) keep their bytes."""
    if not settings_file.exists():
        return "absent"
    raw = settings_file.read_text(encoding="utf-8")
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as exc:
        raise PointerError(f"{settings_file} is not valid JSON: {exc}")

    hooks = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(hooks, dict):
        return "clean"

    changed = False
    for event in list(hooks):
        bucket = hooks[event]
        if not isinstance(bucket, list):
            continue
        kept = []
        for entry in bucket:
            inner = entry.get("hooks") if isinstance(entry, dict) else None
            if not isinstance(inner, list):
                kept.append(entry)
                continue
            remaining = [h for h in inner if not is_hansei_hook(h)]
            if len(remaining) == len(inner):
                kept.append(entry)
                continue
            changed = True
            if remaining:
                entry["hooks"] = remaining
                kept.append(entry)
        if len(kept) != len(bucket):
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]

    if not changed:
        return "clean"
    if check:
        return "would-remove"
    settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return "removed"


def hansei_hook_files(home: Path, root: Path, scope: str) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    if scope in ("global", "both"):
        files += [("global", home / f) for f in HOOK_FILES]
    if scope in ("project", "both"):
        files += [("project", root / f) for f in HOOK_FILES]
    return files


def hook_command(script: Path, fmt: str, extra: str = "") -> str:
    """sys.executable, not a hardcoded 'python3' -- that name doesn't exist on a stock
    Windows Python install (which gives you 'python' and the 'py' launcher instead), so a
    literal 'python3' here would register a hook that silently never fires. sys.executable
    is whatever interpreter is running *this* installer, which is guaranteed to exist on
    this machine. Both paths are quoted because Windows install paths routinely contain
    spaces (e.g. 'C:\\Program Files\\...' or a Users directory with a space in the name)."""
    python = sys.executable or ("python" if os.name == "nt" else "python3")
    cmd = f'"{python}" "{script}" --format {fmt}'
    return f"{cmd} {extra}" if extra else cmd


def ensure_hook(settings_file: Path, script: Path, check: bool, event: str, fmt: str,
                 matcher: bool, extra: str = "") -> str:
    """Register a context-injection hook for one event in a tool's settings file, merging
    with whatever else already lives there. Matched by 'hansei_context.py' appearing in a
    hook's command under that event -- settings.json/hooks.json has no comment syntax to
    carry a marker the way the Markdown pointer blocks do, so the script path is the
    identity instead. One event, one hansei hook: a second event (SessionStart next to
    UserPromptSubmit) is a separate call and a separate bucket."""
    cmd = hook_command(script, fmt, extra)
    existed = settings_file.exists()
    if not existed:
        if check:
            return "missing"
        data: dict = {}
    else:
        raw = settings_file.read_text(encoding="utf-8")
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise PointerError(f"{settings_file} is not valid JSON: {exc}")

    hooks = data.setdefault("hooks", {})
    bucket = hooks.setdefault(event, [])

    found = None
    for matcher_entry in bucket:
        for h in matcher_entry.get("hooks", []):
            if is_hansei_hook(h):
                found = h
                break
        if found:
            break

    if found is not None:
        if found.get("command") == cmd:
            return "ok"
        if check:
            return "would-update"
        found["command"] = cmd
        status = "updated"
    else:
        if check:
            return "would-add"
        entry = {"matcher": "*"} if matcher else {}
        entry["hooks"] = [{"type": "command", "command": cmd}]
        bucket.append(entry)
        status = "added"

    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return status


def global_store(home: Path) -> Path:
    """One fixed location, owned by no vendor. $HANSEI_HOME overrides it for anyone who
    wants the store elsewhere; otherwise the path is a constant, which is what lets the
    pointer text and the docs name it literally instead of globbing for it."""
    override = os.environ.get(HOME_ENV, "").strip()
    if override:
        p = Path(override).expanduser()
        if not p.is_absolute():
            raise PointerError(f"{HOME_ENV} must be an absolute path, got '{override}'")
        return p.resolve()
    return home / GLOBAL_STORE


def display(path: Path) -> str:
    """`~/.hansei` rather than `/home/you/.hansei`, so the pointer text stays portable
    across machines. Falls back to the absolute path when $HANSEI_HOME points outside the
    home directory -- relative_to() raises there rather than returning something useful."""
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


DEFAULT_AGENT = "claude"


def detected(home: Path, root: Path, scope: str) -> list[str]:
    """Agent keys showing evidence of being in use, in registry order.

    Global and project scope look at different evidence: a tool can be installed on the
    machine without this repo using it, and vice versa. An agent with no user-level
    instructions file can never be wired globally, so it is not reported for that scope.
    """
    keys = []
    for key, ag in REGISTRY.items():
        if scope == "global":
            if ag.global_file and any((home / p).exists() for p in ag.global_detect):
                keys.append(key)
        elif any((root / p).exists() for p in ag.detect):
            keys.append(key)
    return keys


def resolve_agents(explicit: str | None, home: Path, root: Path, scope: str) -> tuple[list[str], str]:
    """Which assistants to wire. All of them point at the same store, so wiring several in
    one run cannot split the memory -- it just means more tools read the same lessons.

    Returns (keys, why) so the caller can report how the set was chosen; silently wiring
    a file the user did not expect is worse than wiring none.
    """
    if explicit is not None:
        if explicit not in REGISTRY:
            raise PointerError(f"unknown agent '{explicit}'. Known: {', '.join(REGISTRY)}")
        return [explicit], "requested"

    found = detected(home, root, scope)
    if found:
        return found, "detected"
    # Nothing detected: wire the default rather than doing nothing, so a first run on a
    # fresh machine still leaves the memory reachable.
    return [DEFAULT_AGENT], "default; nothing detected"


@dataclass(frozen=True)
class IndexEntry:
    title: str
    file: str
    description: str


ENTRY_RE = re.compile(r"^(\s*(?:[-*]|\d+[.)])\s+)\[(?P<title>[^\]]*)\]\((?P<file>[^)]+\.md)\)\s*(?:—|–|--|-)?\s*(?P<desc>.*?)\s*$")
INDEX_HEADER = "# Lessons learned\n\n"


def parse_index(text: str) -> list[IndexEntry]:
    """One entry per index line that looks like a list item linking a .md file."""
    out = []
    for line in text.splitlines():
        m = ENTRY_RE.match(line)
        if m:
            out.append(IndexEntry(m["title"], Path(m["file"]).name, m["desc"]))
    return out


def render_entry(e: IndexEntry) -> str:
    return f"- [{e.title}]({e.file}) — {e.description}"


def render_index(current: str | None, entries: list[IndexEntry]) -> str:
    """Rebuild the index, keeping the existing order and any hand-written lines."""
    if current is None:
        return INDEX_HEADER + "\n".join(render_entry(e) for e in entries) + "\n"
    by_file = {e.file: e for e in entries}
    seen = set()
    kept = []
    for line in current.splitlines():
        m = ENTRY_RE.match(line)
        if m:
            name = Path(m["file"]).name
            if name not in by_file:
                continue
            kept.append(render_entry(by_file[name]))
            seen.add(name)
        else:
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    new = [render_entry(e) for e in entries if e.file not in seen]
    if new:
        if kept and not ENTRY_RE.match(kept[-1]):
            kept.append("")
        kept.extend(new)
    return "\n".join(kept) + "\n"


def read_frontmatter(path: Path) -> dict[str, str]:
    """Top-level `key: value` pairs of a leading --- block; nested keys are ignored."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        if m:
            v = m.group(2)
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[m.group(1)] = v
    return {}  # never closed: not frontmatter


def title_from_name(name: str) -> str:
    t = name.replace("-", " ")
    return t[:1].upper() + t[1:]


def index_drift(store: Path) -> tuple[list[str], list[str], bool]:
    """Compare the store's index against the lesson files actually present.

    Returns (missing_from_index, orphaned_entries, index_exists). An index that lags is
    worse than none -- assistants read it to decide what exists, so an unlisted lesson is
    invisible while still costing disk.
    """
    if not store.is_dir():
        return [], [], False
    # Everything in the store except the index is a lesson. No prefix to rely on, which
    # also means a file added by hand can't be silently ignored.
    files = {f.name for f in store.glob("*.md") if f.name != INDEX_NAME}
    index = store / INDEX_NAME
    if not index.exists():
        return sorted(files), [], False
    text = index.read_text(encoding="utf-8", errors="replace")
    linked = {e.file for e in parse_index(text)}
    return sorted(files - linked), sorted(linked - files), True


def report_index(label: str, store: Path, check: bool) -> bool:
    """Print index state. Returns True if something needs the assistant's attention."""
    if store is None or not store.is_dir():
        return False
    missing, orphaned, exists = index_drift(store)
    if not exists:
        if missing:
            print(f"{'index':10} {label:8} {'MISSING':13} {store / INDEX_NAME} "
                  f"({len(missing)} lesson(s) unlisted)")
            return True
        return False
    for f in missing:
        print(f"{'index':10} {label:8} {'unlisted':13} {f}")
    for f in orphaned:
        print(f"{'index':10} {label:8} {'dead link':13} {f}")
    if not missing and not orphaned:
        print(f"{'index':10} {label:8} {'ok':13} {store / INDEX_NAME}")
    return bool(missing or orphaned)


def proposed_index(store: Path) -> tuple[str | None, str]:
    """Return (current index text or None, the text --sync-index would write)."""
    index = store / INDEX_NAME
    current = index.read_text(encoding="utf-8", errors="replace") if index.exists() else None
    existing = {e.file: e for e in parse_index(current)} if current is not None else {}
    entries = []
    for lesson in sorted(store.glob("*.md"), key=lambda f: f.name):
        if lesson.name == INDEX_NAME:
            continue
        fm = read_frontmatter(lesson)
        desc = fm.get("description")
        if not desc:
            raise PointerError(f"{lesson} has no frontmatter description; "
                               "add one before syncing the index")
        old = existing.get(lesson.name)
        title = old.title if old else title_from_name(fm.get("name") or lesson.stem)
        entries.append(IndexEntry(title, lesson.name, desc))
    return current, render_index(current, entries)


def sync_index(label: str, store: Path, dry_run: bool) -> bool:
    """Rewrite (or, with dry_run, diff) the store's index. True when a change is needed."""
    if not store.is_dir():
        return False
    index = store / INDEX_NAME
    current, proposed = proposed_index(store)
    if current is None and not any(f.name != INDEX_NAME for f in store.glob("*.md")):
        print(f"{'index':10} {label:8} {'in sync':13} {index}")
        return False
    if current == proposed:
        print(f"{'index':10} {label:8} {'in sync':13} {index}")
        return False
    if dry_run:
        sys.stdout.write("".join(difflib.unified_diff(
            (current or "").splitlines(True), proposed.splitlines(True),
            fromfile=str(index) if current is not None else "/dev/null",
            tofile=str(index) + " (proposed)")))
    else:
        write_verbatim(index, proposed)
        print(f"{'index':10} {label:8} {'written':13} {index}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--scope", choices=["default", "both", "global", "project"], default="default",
                    help="default/both = whichever applies; global or project = that one only")
    ap.add_argument("--agent", default=None,
                    help="wire only this assistant. Default: every assistant detected as "
                         f"being in use, falling back to {DEFAULT_AGENT} if none are. "
                         "All of them point at the same store. "
                         "Choices: " + ", ".join(REGISTRY))
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if changes are needed")
    ap.add_argument("--create-dirs", action="store_true", help="also mkdir the memory folders")
    ap.add_argument("--hook", action="store_true",
                    help="also wire the user-level context hooks (legacy clone installs; "
                         "the plugin ships its own)")
    ap.add_argument("--no-hook", action="store_true",
                    help="accepted for compatibility; hooks are off by default")
    ap.add_argument("--remove-hooks", action="store_true",
                    help="strip hansei hooks from the user-level settings files (honours --check)")
    ap.add_argument("--shim", action="store_true",
                    help="write ~/.claude/skills/hansei/SKILL.md, the /hansei alias (honours --check)")
    ap.add_argument("--remove-legacy-skill", action="store_true",
                    help="move a legacy clone at ~/.claude/skills/hansei to hansei.bak-<date> "
                         "(honours --check)")
    ap.add_argument("--sync-index", action="store_true",
                    help="rebuild the store index from the lesson files' frontmatter")
    ap.add_argument("--dry-run", action="store_true",
                    help="with --sync-index: show the diff, write nothing; exit 1 if it differs")
    ap.add_argument("--ignored", action="store_true",
                    help="add the project store (.hansei/) to the repo's .gitignore "
                         "(project scope; honours --check)")
    ap.add_argument("--list", action="store_true", help="print the agent registry and exit")
    args = ap.parse_args()
    if args.dry_run and not args.sync_index:
        ap.error("--dry-run only applies to --sync-index")

    if args.list:
        print(f"{'key':10} {'assistant':30} {'project file':36} global instructions")
        for ag in REGISTRY.values():
            gi = "~/" + ag.global_file if ag.global_file else "-"
            print(f"{ag.key:10} {ag.label:30} {ag.project_file:36} {gi}")
            if ag.note:
                print(f"{'':10} {ag.note}")
        print(f"\nAll of them point at one global store: {display(global_store(Path.home()))}"
              f"  (override with ${HOME_ENV})")
        return 0

    scope = "both" if args.scope == "default" else args.scope
    home = Path.home()
    root = project_root()
    gstore = global_store(home)
    # Every wired assistant points at this one directory, so wiring several in a single run
    # cannot split the memory. --agent narrows it to one. Reported for either scope, since
    # the project block names the global store too.
    if args.sync_index:
        changed = False
        if scope in ("global", "both"):
            changed |= sync_index("global", gstore, args.dry_run)
        if scope in ("project", "both"):
            changed |= sync_index("project", root / PROJECT_STORE, args.dry_run)
        return 1 if (args.dry_run and changed) else 0
    print(f"{'store':10} {'global':8} {'shared':13} {gstore}")
    if scope in ("project", "both"):
        print(f"{'store':10} {'project':8} {'repo':13} {root / PROJECT_STORE}")

    needs_work = False
    pointer_work = False
    pairs = []
    global_keys: list[str] = []
    project_keys: list[str] = []
    if scope in ("global", "both"):
        global_keys, why = resolve_agents(args.agent, home, root, "global")
        print(f"{'agents':10} {'global':8} {why:13} {', '.join(global_keys)}")
        for key in global_keys:
            ag = REGISTRY[key]
            if ag.global_file:
                pairs.append((ag, "global", home / ag.global_file, global_body(display(gstore))))
            else:
                print(f"{ag.key:10} {'global':8} {'n/a':13} {ag.note}")
    if scope in ("project", "both"):
        project_keys, why = resolve_agents(args.agent, home, root, "project")
        print(f"{'agents':10} {'project':8} {why:13} {', '.join(project_keys)}")
        for key in project_keys:
            ag = REGISTRY[key]
            pairs.append((ag, "project", root / ag.project_file, project_body(display(gstore))))

    for ag, label, path, body in pairs:
        status = ensure(path, body, args.check, ag.header)
        if status in ("missing", "would-add", "would-update"):
            needs_work = pointer_work = True
        print(f"{ag.key:10} {label:8} {status:13} {path}")

    if args.remove_hooks:
        for label, settings_file in hansei_hook_files(home, root, scope):
            status = remove_hooks(settings_file, args.check)
            if status == "would-remove":
                needs_work = True
            print(f"{'hook':10} {label:8} {status:13} {settings_file}")

    # The shim and legacy clone live under ~/.claude; without it (Codex-only machine) they
    # are not applicable, and creating it would make --check red later.
    claude_home = (home / ".claude").is_dir()
    if (args.remove_legacy_skill or args.shim) and scope in ("global", "both") and claude_home:
        skill_dir = home / SHIM_REL
        if args.remove_legacy_skill:
            status = move_legacy_skill(skill_dir, args.check,
                                       datetime.date.today().isoformat())
            if status == "would-move":
                needs_work = True
            print(f"{'legacy':10} {'global':8} {status:13} {skill_dir}")
        if args.shim:
            status = ensure_shim(skill_dir, args.check)
            if status in ("legacy", "would-add", "would-update"):
                needs_work = True
            print(f"{'shim':10} {'global':8} {status:13} {skill_dir / 'SKILL.md'}")

    if args.check and not args.hook and not args.remove_hooks:
        for label, settings_file in hansei_hook_files(home, root, scope):
            try:
                status = ("duplicate" if remove_hooks(settings_file, True) == "would-remove"
                          else "clean")
            except PointerError:
                status = "invalid"
            if status != "clean":
                needs_work = True
            print(f"{'hook':10} {label:8} {status:13} {settings_file}")

    if (args.check and scope in ("global", "both") and claude_home
            and not args.shim and not args.remove_legacy_skill):
        skill_dir = home / SHIM_REL
        present = is_legacy_clone(skill_dir)
        print(f"{'legacy':10} {'global':8} {'present' if present else 'none':13} {skill_dir}")
        status = ensure_shim(skill_dir, True)
        if present or status != "ok":
            needs_work = True
        print(f"{'shim':10} {'global':8} {status:13} {skill_dir / 'SKILL.md'}")

    # A hook is only wired for a key when that key was itself resolved for the scope --
    # same gating that decides whether the pointer block gets written, kept consistent
    # with --agent filtering. Cursor and Copilot have no entry in HOOK_SPECS at all.
    if args.hook:
        hook_script = Path(__file__).resolve().parent / "hansei_context.py"
        for key, specs in HOOK_SPECS.items():
            for spec in specs:
                hook_targets = []
                if key in global_keys:
                    hook_targets.append(("global", home / spec["settings"]))
                if key in project_keys:
                    hook_targets.append(("project", root / spec["settings"]))
                for label, settings_file in hook_targets:
                    status = ensure_hook(settings_file, hook_script, args.check,
                                          spec["event"], spec["fmt"], spec["matcher"],
                                          spec["extra"])
                    if status in ("missing", "would-add", "would-update"):
                        needs_work = True
                    print(f"{'hook':10} {label:8} {status:13} {settings_file}  "
                          f"[{key} {spec['event']}]")

    if args.ignored and scope in ("project", "both"):
        status = ensure_ignored(root, args.check)
        if status == "would-add":
            needs_work = True
        print(f"{'gitignore':10} {'project':8} {status:13} {root / '.gitignore'}")

    if args.create_dirs and not args.check:
        for label, d in (("global", gstore),
                         ("project", root / PROJECT_STORE)):
            if d is None:
                continue
            if scope in (label, "both"):
                d.mkdir(parents=True, exist_ok=True)
                print(f"{'memory':10} {label:8} {'dir ready':13} {d}")

    drift = False
    if scope in ("global", "both"):
        drift |= report_index("global", gstore, args.check)
    if scope in ("project", "both"):
        drift |= report_index("project", root / PROJECT_STORE, args.check)
    if drift:
        print("\nIndex is out of sync with the lesson files. "
              f"Update {INDEX_NAME} so every lesson is listed and every link resolves.")
        if args.check:
            needs_work = True

    if args.check and needs_work:
        if pointer_work:
            print("\nInstructions files are not wired up to read hansei memory. "
                  "Re-run without --check to fix.")
        else:
            print("\nItems above need attention. "
                  "Run /hansei:setup (or re-run without --check) to fix.")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except PointerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
