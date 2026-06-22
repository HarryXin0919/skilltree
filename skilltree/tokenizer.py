"""Turn a raw command string into structured ``ParsedCommand`` records.

This is the most error-prone part of the project, so its behaviour is spelled
out explicitly and covered heavily by tests:

* Quoting is handled with :mod:`shlex`.
* A line is first split into independent commands on ``|``, ``&&``, ``||`` and
  ``;`` (quotes are respected, so ``echo "a | b"`` is *not* split).
* Within a command, redirections (``>``, ``>>``, ``<`` ...) and their targets
  are dropped.
* Clustered short flags follow getopt semantics: ``tar -xzf f`` expands to
  ``-x -z -f`` and the value-taking ``-f`` consumes ``f``.
* The value of a value-taking flag (``git commit -m "msg"``) is recorded
  separately and never mistaken for a flag or a subcommand.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

# Tools that use a subcommand as their first positional word. For every other
# tool the first positional token is treated as a plain argument and
# ``subcommand`` stays ``None`` (e.g. ``grep``, ``find``, ``ls``).
SUBCOMMAND_TOOLS: frozenset[str] = frozenset(
    {
        "git",
        "docker",
        "kubectl",
        "npm",
        "yarn",
        "pnpm",
        "pip",
        "cargo",
        "go",
        "apt",
        "apt-get",
        "brew",
        "systemctl",
        "gh",
        "terraform",
    }
)

# Flags that take a following value. Keyed by tool; used so the value is not
# misread as a subcommand or a separate flag (``git -C path commit`` ->
# subcommand is ``commit``, not ``path``). The empty-string key holds flags
# that commonly take a value regardless of tool.
VALUE_TAKING_FLAGS: dict[str, frozenset[str]] = {
    "": frozenset({"-m", "--message", "-o", "--output", "-C", "-f", "--file"}),
    "git": frozenset({"-C", "-c", "-m", "--message", "--git-dir", "--work-tree", "-b"}),
    "docker": frozenset(
        {
            "-p",
            "--publish",
            "-v",
            "--volume",
            "-e",
            "--env",
            "--name",
            "-w",
            "--workdir",
            "--network",
            "-u",
            "--user",
            "--entrypoint",
        }
    ),
    "ssh": frozenset({"-i", "-p", "-o", "-L", "-R", "-D", "-l", "-F", "-J", "-c"}),
    "tar": frozenset({"-f", "--file", "-C", "--directory"}),
    "grep": frozenset(
        {"-e", "--regexp", "-f", "--file", "-m", "--max-count", "-A", "-B", "-C"}
    ),
    "find": frozenset(
        {
            "-name",
            "-iname",
            "-type",
            "-path",
            "-maxdepth",
            "-mindepth",
            "-mtime",
            "-size",
            "-exec",
            "-user",
            "-group",
            "-perm",
            "-newer",
            "-regex",
        }
    ),
}

# Tools whose single-dash options are whole words rather than clusters of
# short flags (``find -name`` is one option, not ``-n -a -m -e``). For these we
# never expand a ``-xyz`` token into individual letters.
NO_CLUSTER_TOOLS: frozenset[str] = frozenset({"find"})

_SEPARATORS: frozenset[str] = frozenset({"|", "||", "&&", ";", "&"})
_REDIRECTIONS: frozenset[str] = frozenset({">", ">>", "<", "<<", "1>", "2>", "&>"})


@dataclass
class ParsedCommand:
    """Structured view of a single command."""

    base: str
    subcommand: str | None = None
    flags: list[str] = field(default_factory=list)
    args: list[str] = field(default_factory=list)
    flag_values: dict[str, str] = field(default_factory=dict)
    raw: str = ""


def _takes_value(tool: str, flag: str) -> bool:
    if flag in VALUE_TAKING_FLAGS.get(tool, frozenset()):
        return True
    return flag in VALUE_TAKING_FLAGS[""]


def _lex(text: str) -> list[str]:
    """Tokenise ``text`` respecting quotes and grouping shell punctuation."""
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        # Unbalanced quotes or similar — fall back to a naive split so we never
        # crash on a corrupted history line.
        return text.split()


def split_commands(line: str) -> list[list[str]]:
    """Split ``line`` into a list of token-lists, one per chained command."""
    commands: list[list[str]] = []
    current: list[str] = []
    for token in _lex(line):
        if token in _SEPARATORS:
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _expand_short_cluster(token: str, tool: str) -> tuple[list[str], bool]:
    """Expand a clustered short flag like ``-xzf`` into ``[-x, -z, -f]``.

    Returns the expanded flags and whether the final flag expects a value from
    the *next* token. If a value-taking flag appears mid-cluster, the remainder
    of the cluster is its inline value (getopt style) and no further token is
    consumed.
    """
    chars = token[1:]
    flags: list[str] = []
    for index, char in enumerate(chars):
        flag = f"-{char}"
        flags.append(flag)
        if _takes_value(tool, flag):
            remainder = chars[index + 1 :]
            # Inline value (``-fname``) -> no following token consumed.
            return flags, not remainder
    return flags, False


def parse_command(tokens: list[str], raw: str = "") -> ParsedCommand | None:
    """Parse a single command's token list into a :class:`ParsedCommand`."""
    tokens = [token for token in tokens if token]
    if not tokens:
        return None

    base = tokens[0]
    rest = tokens[1:]
    result = ParsedCommand(base=base, raw=raw or " ".join(tokens))

    index = 0
    pending_value_flag: str | None = None
    while index < len(rest):
        token = rest[index]

        if pending_value_flag is not None:
            result.flag_values[pending_value_flag] = token
            pending_value_flag = None
            index += 1
            continue

        if token in _REDIRECTIONS:
            index += 2  # skip the operator and its target
            continue

        if token.startswith("--") and len(token) > 2:
            name, _, value = token.partition("=")
            result.flags.append(name)
            if value:
                result.flag_values[name] = value
            elif _takes_value(base, name):
                pending_value_flag = name
            index += 1
            continue

        if token.startswith("-") and len(token) > 1 and not _is_negative_number(token):
            if base in NO_CLUSTER_TOOLS:
                # Single-dash long option (e.g. ``find -name``): one whole flag.
                result.flags.append(token)
                if _takes_value(base, token):
                    pending_value_flag = token
            else:
                expanded, expects_following = _expand_short_cluster(token, base)
                result.flags.extend(expanded)
                if expects_following:
                    pending_value_flag = expanded[-1]
            index += 1
            continue

        # Positional token: the first one is the subcommand for tools that use
        # subcommands, everything else is an argument.
        if result.subcommand is None and base in SUBCOMMAND_TOOLS:
            result.subcommand = token
        else:
            result.args.append(token)
        index += 1

    # De-duplicate flags while preserving order.
    seen: set[str] = set()
    deduped: list[str] = []
    for flag in result.flags:
        if flag not in seen:
            seen.add(flag)
            deduped.append(flag)
    result.flags = deduped
    return result


def _is_negative_number(token: str) -> bool:
    """``-5`` / ``-1.5`` are arguments, not flags."""
    try:
        float(token)
        return True
    except ValueError:
        return False


def tokenize(line: str) -> list[ParsedCommand]:
    """Parse a whole history line into one or more :class:`ParsedCommand`."""
    parsed: list[ParsedCommand] = []
    for tokens in split_commands(line):
        command = parse_command(tokens, raw=" ".join(tokens))
        if command is not None:
            parsed.append(command)
    return parsed
