"""Load and validate the skill-tree knowledge base.

The knowledge base is a directory of YAML files, one per tool. Each file
declares the tool and a list of nodes; every node is either a ``subcommand``
or a ``flag`` and carries a learning ``tier``. The match key for each node
(which tool / subcommand / flag it represents) is derived by tokenising its
``invocation`` string with the same tokenizer used for real history, so the
two can never drift apart.
"""

from __future__ import annotations

import importlib.resources as resources
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from .tokenizer import parse_command, split_commands

TIERS: tuple[str, ...] = ("basic", "intermediate", "advanced")
TIER_RANK: dict[str, int] = {tier: rank for rank, tier in enumerate(TIERS)}
NODE_TYPES: frozenset[str] = frozenset({"subcommand", "flag"})

_REQUIRED_FIELDS: tuple[str, ...] = ("id", "type", "tier", "invocation", "desc")


class KnowledgeError(ValueError):
    """Raised when a knowledge-base file is malformed."""


@dataclass(frozen=True)
class SkillNode:
    id: str
    type: str  # "subcommand" | "flag"
    tier: str  # "basic" | "intermediate" | "advanced"
    invocation: str
    desc: str
    tool: str
    subcommand: str | None
    flag: str | None

    @property
    def tier_rank(self) -> int:
        return TIER_RANK[self.tier]


def _derive_match(tool: str, node_type: str, invocation: str) -> tuple[str | None, str | None]:
    """Derive ``(subcommand, flag)`` for a node from its invocation string."""
    commands = split_commands(invocation)
    if not commands:
        return None, None
    parsed = parse_command(commands[0], raw=invocation)
    if parsed is None:
        return None, None
    if node_type == "subcommand":
        return parsed.subcommand, None
    # flag node: the canonical flag is the most specific (longest) flag named.
    flag = max(parsed.flags, key=len) if parsed.flags else None
    return parsed.subcommand, flag


def _build_node(tool: str, raw: dict, *, source: str) -> SkillNode:
    for key in _REQUIRED_FIELDS:
        if key not in raw or raw[key] in (None, ""):
            node_id = raw.get("id", "<unknown>")
            raise KnowledgeError(f"{source}: node '{node_id}' is missing required field '{key}'")

    node_type = str(raw["type"])
    if node_type not in NODE_TYPES:
        raise KnowledgeError(
            f"{source}: node '{raw['id']}' has invalid type '{node_type}' "
            f"(expected one of {sorted(NODE_TYPES)})"
        )

    tier = str(raw["tier"])
    if tier not in TIER_RANK:
        raise KnowledgeError(
            f"{source}: node '{raw['id']}' has invalid tier '{tier}' "
            f"(expected one of {list(TIERS)})"
        )

    invocation = str(raw["invocation"])
    subcommand, flag = _derive_match(tool, node_type, invocation)
    # Allow explicit overrides for awkward invocations.
    subcommand = raw.get("subcommand", subcommand)
    flag = raw.get("flag", flag)

    if node_type == "flag" and not flag:
        raise KnowledgeError(
            f"{source}: flag node '{raw['id']}' has no detectable flag in "
            f"invocation '{invocation}' (add an explicit 'flag:' field)"
        )

    return SkillNode(
        id=str(raw["id"]),
        type=node_type,
        tier=tier,
        invocation=invocation,
        desc=str(raw["desc"]),
        tool=tool,
        subcommand=subcommand,
        flag=flag,
    )


class KnowledgeBase:
    """All loaded tools and a lookup index over their nodes."""

    def __init__(self, tools: dict[str, list[SkillNode]], descriptions: dict[str, str]):
        self.tools = tools
        self.descriptions = descriptions
        # (tool, subcommand) -> subcommand node
        self._subcommand_index: dict[tuple[str, str | None], SkillNode] = {}
        # (tool, flag) -> list of flag nodes (a flag may be scoped to a subcommand)
        self._flag_index: dict[tuple[str, str], list[SkillNode]] = {}
        for nodes in tools.values():
            for node in nodes:
                if node.type == "subcommand":
                    self._subcommand_index[(node.tool, node.subcommand)] = node
                elif node.flag is not None:
                    self._flag_index.setdefault((node.tool, node.flag), []).append(node)

    def all_nodes(self) -> Iterable[SkillNode]:
        for nodes in self.tools.values():
            yield from nodes

    def subcommand_node(self, tool: str, subcommand: str | None) -> SkillNode | None:
        return self._subcommand_index.get((tool, subcommand))

    def flag_nodes(self, tool: str, flag: str) -> list[SkillNode]:
        return self._flag_index.get((tool, flag), [])


def _load_file(path: Path) -> tuple[str, str, list[SkillNode]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not data:
        raise KnowledgeError(f"{path.name}: file is empty")
    if "tool" not in data:
        raise KnowledgeError(f"{path.name}: missing top-level 'tool' field")
    tool = str(data["tool"])
    description = str(data.get("description", ""))
    raw_nodes = data.get("nodes") or []
    if not isinstance(raw_nodes, list):
        raise KnowledgeError(f"{path.name}: 'nodes' must be a list")
    nodes = [_build_node(tool, raw, source=path.name) for raw in raw_nodes]
    return tool, description, nodes


def _yaml_paths(directory: Path) -> list[Path]:
    return sorted(p for p in directory.iterdir() if p.suffix in {".yaml", ".yml"})


def load_knowledge_base(directory: str | Path | None = None) -> KnowledgeBase:
    """Load every YAML file in ``directory``.

    When ``directory`` is ``None`` the knowledge base bundled with the package
    is used, so the tool works after a plain ``pip install``.
    """
    if directory is None:
        packaged = resources.files("skilltree") / "knowledge_base"
        directory = Path(str(packaged))
    directory = Path(directory)
    if not directory.exists():
        raise KnowledgeError(f"knowledge base directory not found: {directory}")

    tools: dict[str, list[SkillNode]] = {}
    descriptions: dict[str, str] = {}
    for path in _yaml_paths(directory):
        tool, description, nodes = _load_file(path)
        tools[tool] = nodes
        descriptions[tool] = description
    if not tools:
        raise KnowledgeError(f"no knowledge-base YAML files found in {directory}")
    return KnowledgeBase(tools, descriptions)
