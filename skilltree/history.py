"""Parse shell history files into a list of raw command strings.

Three formats are supported:

* ``bash``  — one command per line (``~/.bash_history``). Lines beginning with
  ``#`` are timestamp comments written when ``HISTTIMEFORMAT`` is set and are
  skipped.
* ``zsh``   — extended history (``~/.zsh_history``) of the form
  ``: 1700000000:0;git status``. Multi-line commands stored with a trailing
  backslash continuation are re-joined.
* ``plain`` — a bare text file with one command per line. Handy for tests and
  for feeding in a curated, de-identified history.

The parser never raises on malformed input: blank lines and undecodable bytes
are tolerated and dropped rather than crashing the run.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# ``: <epoch>:<elapsed>;<command>``
_ZSH_EXTENDED_RE = re.compile(r"^:\s+\d+:\d+;(.*)$")
# A bash timestamp comment line, e.g. ``#1700000000``.
_BASH_TS_RE = re.compile(r"^#\d+\s*$")

Shell = str  # one of: "bash", "zsh", "plain", "auto"


def detect_shell() -> Shell:
    """Best-effort guess of the current user's shell from ``$SHELL``."""
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return "zsh"
    if "bash" in shell:
        return "bash"
    # On Windows there is rarely a POSIX history file; default to bash format.
    return "bash"


def default_history_path(shell: Shell | None = None) -> Path:
    """Return the conventional history file path for ``shell``."""
    shell = shell or detect_shell()
    home = Path.home()
    if shell == "zsh":
        return home / ".zsh_history"
    return home / ".bash_history"


def _sniff_format(raw: str) -> Shell:
    """Decide whether raw text looks like zsh-extended or plain/bash."""
    for line in raw.splitlines():
        if _ZSH_EXTENDED_RE.match(line):
            return "zsh"
    return "bash"


def _clean(commands: list[str]) -> list[str]:
    out: list[str] = []
    for cmd in commands:
        cmd = cmd.strip()
        if cmd:
            out.append(cmd)
    return out


def _parse_bash(raw: str) -> list[str]:
    out: list[str] = []
    for line in raw.splitlines():
        if _BASH_TS_RE.match(line):
            continue
        out.append(line)
    return _clean(out)


def _parse_plain(raw: str) -> list[str]:
    return _clean(raw.splitlines())


def _parse_zsh(raw: str) -> list[str]:
    entries: list[str] = []
    current: str | None = None
    for line in raw.splitlines():
        match = _ZSH_EXTENDED_RE.match(line)
        if match:
            if current is not None:
                entries.append(current)
            current = match.group(1)
        elif current is not None and current.endswith("\\"):
            # Continuation of a multi-line command.
            current = current[:-1] + "\n" + line
        elif current is not None:
            entries.append(current)
            current = None
            # A stray, non-marker line in an extended file: keep it if it
            # still looks like a command (tolerates lightly corrupted files).
            if line.strip():
                entries.append(line)
        elif line.strip():
            # File opened with a non-marker line (mixed / non-extended zsh).
            entries.append(line)
    if current is not None:
        entries.append(current)
    return _clean(entries)


def parse_history(path: str | os.PathLike[str], shell: Shell = "auto") -> list[str]:
    """Parse ``path`` and return a list of de-timestamped command strings.

    Parameters
    ----------
    path:
        Path to the history file.
    shell:
        ``"bash"``, ``"zsh"``, ``"plain"`` or ``"auto"`` (the default, which
        sniffs the file contents).

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"history file not found: {path}")

    raw = path.read_text(encoding="utf-8", errors="replace")

    if shell == "auto":
        shell = _sniff_format(raw)

    if shell == "zsh":
        return _parse_zsh(raw)
    if shell == "plain":
        return _parse_plain(raw)
    return _parse_bash(raw)
