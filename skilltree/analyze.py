"""Match parsed history against the knowledge base and light up nodes."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .knowledge import TIER_RANK, TIERS, KnowledgeBase, SkillNode
from .tokenizer import ParsedCommand, tokenize


@dataclass
class NodeStat:
    node: SkillNode
    count: int = 0

    @property
    def used(self) -> bool:
        return self.count > 0


@dataclass
class ToolStat:
    tool: str
    description: str
    nodes: list[NodeStat] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.nodes)

    @property
    def unlocked(self) -> int:
        return sum(1 for stat in self.nodes if stat.used)

    @property
    def ratio(self) -> float:
        return self.unlocked / self.total if self.total else 0.0

    @property
    def usage_count(self) -> int:
        """Total number of matched invocations across this tool's nodes."""
        return sum(stat.count for stat in self.nodes)

    @property
    def highest_tier(self) -> str | None:
        used_tiers = [stat.node.tier for stat in self.nodes if stat.used]
        if not used_tiers:
            return None
        return max(used_tiers, key=lambda tier: TIER_RANK[tier])


@dataclass
class Analysis:
    tools: dict[str, ToolStat]
    shell: str = "shell"

    def node_stat(self, node_id: str) -> NodeStat | None:
        for tool in self.tools.values():
            for stat in tool.nodes:
                if stat.node.id == node_id:
                    return stat
        return None

    @property
    def total_nodes(self) -> int:
        return sum(tool.total for tool in self.tools.values())

    @property
    def total_unlocked(self) -> int:
        return sum(tool.unlocked for tool in self.tools.values())

    def tier_distribution(self) -> dict[str, int]:
        """Count of *unlocked* nodes per tier."""
        dist = {tier: 0 for tier in TIERS}
        for tool in self.tools.values():
            for stat in tool.nodes:
                if stat.used:
                    dist[stat.node.tier] += 1
        return dist


def _match_command(command: ParsedCommand, kb: KnowledgeBase, hits: Counter[str]) -> None:
    tool = command.base
    if tool not in kb.tools:
        return

    # Light the subcommand node (also lights the bare-tool node when the tool
    # has no subcommand, since that node's subcommand is None).
    sub_node = kb.subcommand_node(tool, command.subcommand)
    if sub_node is not None:
        hits[sub_node.id] += 1

    for flag in command.flags:
        for node in kb.flag_nodes(tool, flag):
            # A flag node scoped to a subcommand only matches under that
            # subcommand; an unscoped flag node matches anywhere.
            if node.subcommand in (None, command.subcommand):
                hits[node.id] += 1


def analyze(commands: list[str], kb: KnowledgeBase, shell: str = "shell") -> Analysis:
    """Build an :class:`Analysis` from raw history command strings."""
    hits: Counter[str] = Counter()
    for line in commands:
        for command in tokenize(line):
            _match_command(command, kb, hits)

    tools: dict[str, ToolStat] = {}
    for tool, nodes in kb.tools.items():
        stat = ToolStat(tool=tool, description=kb.descriptions.get(tool, ""))
        stat.nodes = [NodeStat(node=node, count=hits.get(node.id, 0)) for node in nodes]
        tools[tool] = stat
    return Analysis(tools=tools, shell=shell)
