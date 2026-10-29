#!/usr/bin/env python3
"""Hook: inject hansei lesson indexes into context -- in full once per session, then a
one-line reminder on every later turn.

The CLAUDE.md/AGENTS.md/GEMINI.md pointer block only *asks* an assistant to read the lesson
index; whether that happens on any given turn is a judgment call, and in practice it's
inconsistent. This hook removes the judgment call for the "is the index even in context"
half of the problem: the host tool runs it before every user turn and folds its output into
context, so the index is present regardless of what the model decides to do about it.

Printing the whole index on *every* turn is the obvious way to do that, and it was the first
version -- but every injection stays in the transcript, so a 20-lesson index (~1.2k tokens)
repeated over a 50-turn session costs ~60k tokens of context for text the model already
has. So the script now keeps a small per-session state file and prints the full index only
when it is actually new to the conversation:

  * the first turn of a session (or any turn when the host sends no session id),
  * whenever an index file changed since the last full injection,
  * after a context compaction, when the host has a hook for that (Claude Code's
    SessionStart with source=compact; the installer wires it with --full),
  * and every --every turns as a safety net for hosts with no compaction hook.

Every other turn gets a ~40-token reminder that the index is already in context and must
still be consulted. The reminder names both index paths, so the model can re-read them if
the text has scrolled out of what it can see.

Three tools currently support a hook that fires this early and can inject text, each with
its own stdout contract -- pass --format to match whichever one installed this hook (the
installer, ensure_memory_pointer.py, sets the flag for you; it isn't something to pick by
hand):

  claude  Claude Code's UserPromptSubmit and SessionStart -- whatever this prints to stdout
          becomes context.
  codex   Codex CLI's UserPromptSubmit -- wants JSON:
          {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ...}}
  gemini  Gemini CLI's BeforeAgent -- wants JSON:
          {"hookSpecificOutput": {"additionalContext": ...}}

Cursor and Copilot aren't wired here because they don't need a hook: an always-apply Cursor
rule and .github/copilot-instructions.md are already sent with every request by those tools,
so their pointer block alone already achieves what this script exists to force for the
others.

Reads the JSON the host tool sends on stdin for the session's cwd and session id (all three
tools include both), then builds the same lesson text regardless of format -- global
always, project when cwd is inside a repo that has one. Producing nothing when neither
store exists keeps a machine or repo with no lessons yet silent instead of injecting empty
noise on every turn.

Session state lives under the user's cache directory ($XDG_CACHE_HOME/hansei, or
%LOCALAPPDATA%\\hansei on Windows), never inside the lesson store: the store holds lessons
and their index and nothing else. Stale state files are swept on the way through, so the
directory doesn't grow without bound.

With --full (session start) and no global lessons store at all, the hook prints a one-line
nudge to run /hansei:setup instead of staying silent; per-turn runs stay silent.
"""

from __future__ import annotations

import sys

MIN_PY = (3, 9)
if sys.version_info < MIN_PY:
    sys.stderr.write(f"hansei needs Python {'.'.join(map(str, MIN_PY))}+, found {sys.version.split()[0]}\n")
    sys.exit(0)  # a hook must never block a session

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

INDEX_NAME = "HANSEI.md"
HOME_ENV = "HANSEI_HOME"
DEFAULT_EVERY = 30          # safety-net full re-injection interval, in turns
STATE_MAX_AGE = 14 * 86400  # seconds; state files older than this are swept
SESSION_ID_RE = re.compile(r"[^A-Za-z0-9._-]")


def global_store() -> Path:
    override = os.environ.get(HOME_ENV, "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".hansei"


def state_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "hansei" / "sessions"


def project_root(cwd: str) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def read_index(store: Path) -> str | None:
    index = store / INDEX_NAME
    if not index.is_file():
        return None
    text = index.read_text(encoding="utf-8", errors="replace").strip()
    return text or None


def count_lessons(index_text: str) -> int:
    """Index entries are '- [Title](file.md) — description' lines; count those."""
    return sum(1 for line in index_text.splitlines() if re.match(r"\s*[-*]\s+\[", line))


def collect(cwd: str) -> list[tuple[str, Path, str]]:
    """(label, index path, index text) for every store that has a non-empty index."""
    found = []
    gstore = global_store()
    gtext = read_index(gstore)
    if gtext:
        found.append(("Global", gstore / INDEX_NAME, gtext))
    root = project_root(cwd)
    if root:
        pstore = root / ".hansei"
        ptext = read_index(pstore)
        if ptext:
            found.append(("Project", pstore / INDEX_NAME, ptext))
    return found


def full_text(indexes: list[tuple[str, Path, str]]) -> str:
    sections = [f"{label} lessons ({path}):\n\n{text}" for label, path, text in indexes]
    return (
        "Hansei: before acting on this request, check whether any of these past lessons "
        "apply and follow them if so. Open the individual lesson file for any whose "
        "description touches this task.\n\n" + "\n\n---\n\n".join(sections)
    )


def reminder_text(indexes: list[tuple[str, Path, str]]) -> str:
    counts = ", ".join(f"{count_lessons(text)} {label.lower()}" for label, _, text in indexes)
    paths = ", ".join(str(path) for _, path, _ in indexes)
    return (
        f"Hansei: the lessons index ({counts}) was injected earlier in this session; "
        "it still applies to this request. Check it before acting and open the file of "
        f"any lesson whose description touches this task. Re-read {paths} if the index "
        "is no longer in context."
    )


def fingerprint(indexes: list[tuple[str, Path, str]]) -> str:
    h = hashlib.sha1()
    for _, path, text in indexes:
        h.update(str(path).encode("utf-8", "replace"))
        h.update(b"\0")
        h.update(text.encode("utf-8", "replace"))
        h.update(b"\0")
    return h.hexdigest()


def sweep(directory: Path, now: float) -> None:
    try:
        for f in directory.glob("*.json"):
            try:
                if now - f.stat().st_mtime > STATE_MAX_AGE:
                    f.unlink()
            except OSError:
                pass
    except OSError:
        pass


def decide(session_id: str | None, fp: str, every: int, force_full: bool) -> bool:
    """Return True when the full index should be printed this turn, updating the session
    state as a side effect. Any failure to read or write state falls back to printing the
    full index: a missing reminder costs tokens, a missing index costs a lesson."""
    if force_full or not session_id:
        if session_id:
            _save(session_id, fp, turns_since_full=0)
        return True

    sdir = state_dir()
    sfile = sdir / f"{session_id}.json"
    state: dict = {}
    try:
        if sfile.is_file():
            state = json.loads(sfile.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}

    turns = int(state.get("turns_since_full", 0)) + 1
    need_full = (
        state.get("fingerprint") != fp
        or (every > 0 and turns >= every)
    )
    _save(session_id, fp, turns_since_full=0 if need_full else turns)
    return need_full


def _save(session_id: str, fp: str, turns_since_full: int) -> None:
    sdir = state_dir()
    try:
        sdir.mkdir(parents=True, exist_ok=True)
        now = time.time()
        sweep(sdir, now)
        tmp = sdir / f"{session_id}.json.tmp"
        tmp.write_text(json.dumps({
            "fingerprint": fp,
            "turns_since_full": turns_since_full,
            "updated": now,
        }), encoding="utf-8")
        os.replace(tmp, sdir / f"{session_id}.json")
    except OSError:
        pass


def build_context(cwd: str, session_id: str | None, every: int, force_full: bool) -> str | None:
    indexes = collect(cwd)
    if not indexes:
        return None
    if decide(session_id, fingerprint(indexes), every, force_full):
        return full_text(indexes)
    return reminder_text(indexes)


def nudge_text(store: Path) -> str:
    return f"Hansei: no lessons store exists yet at `{store}`; suggest the user run `/hansei:setup`."


def emit(text: str, fmt: str) -> None:
    if fmt == "claude":
        print(text)
    elif fmt == "codex":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": text,
            }
        }))
    elif fmt == "gemini":
        print(json.dumps({"hookSpecificOutput": {"additionalContext": text}}))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format", choices=["claude", "codex", "gemini"], default="claude",
                     help="stdout contract of the tool that installed this hook "
                          "(set automatically by ensure_memory_pointer.py)")
    ap.add_argument("--full", action="store_true",
                     help="always print the full index and reset the session's turn count; "
                          "for hooks that fire when context is (re)built, e.g. Claude Code's "
                          "SessionStart on startup/resume/compact")
    ap.add_argument("--every", type=int, default=DEFAULT_EVERY, metavar="N",
                     help="also print the full index every N turns as a safety net against "
                          "context compaction on hosts with no hook for it; 0 disables "
                          f"(default {DEFAULT_EVERY})")
    args = ap.parse_args()

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    cwd = payload.get("cwd") or os.getcwd()
    raw_id = payload.get("session_id")
    session_id = SESSION_ID_RE.sub("_", str(raw_id))[:128] if raw_id else None

    gstore = global_store()
    if args.full and not gstore.is_dir():
        emit(nudge_text(gstore), args.format)
        return 0

    text = build_context(cwd, session_id, args.every, args.full)
    if text is None:
        return 0

    emit(text, args.format)
    return 0


if __name__ == "__main__":
    sys.exit(main())
