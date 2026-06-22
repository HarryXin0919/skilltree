"""Recommend the next flag worth learning.

The heuristic: inside the tools you already use often, find unused nodes one
tier above your current level for that tool, and surface the ones attached to
your most-used tools first.
"""

from __future__ import annotations

from dataclasses import dataclass

from .analyze import Analysis, ToolStat
from .knowledge import TIERS, KnowledgeBase, SkillNode


@dataclass
class Recommendation:
    node: SkillNode
    tool_usage: int
    reason: str


def _target_tier(highest_tier: str | None) -> str:
    """The tier we want to nudge the user toward for a given tool."""
    if highest_tier is None:
        # Used the tool but only via bare invocations: start at basic.
        return TIERS[0]
    rank = TIERS.index(highest_tier)
    if rank + 1 < len(TIERS):
        return TIERS[rank + 1]
    return TIERS[-1]  # already advanced — keep mining remaining advanced nodes


def _reason(tool: str, usage: int, node: SkillNode) -> str:
    invocation = node.invocation
    return f"你已经常用 {tool}（命中 {usage} 次），但还没试过 `{invocation}`：{node.desc}"


def recommend(analysis: Analysis, kb: KnowledgeBase, limit: int = 3) -> list[Recommendation]:
    """Return up to ``limit`` recommendations, best first."""
    candidates: list[tuple[int, int, str, ToolStat, SkillNode]] = []
    for tool_stat in analysis.tools.values():
        usage = tool_stat.usage_count
        if usage <= 0:
            continue  # only recommend within tools the user actually uses
        target = _target_tier(tool_stat.highest_tier)
        target_rank = TIERS.index(target)
        for node_stat in tool_stat.nodes:
            if node_stat.used:
                continue
            if node_stat.node.tier != target:
                continue
            # Sort key: higher tool usage first, then higher-value tier, then
            # a stable id for determinism.
            candidates.append((usage, target_rank, node_stat.node.id, tool_stat, node_stat.node))

    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))

    recommendations: list[Recommendation] = []
    for usage, _rank, _id, tool_stat, node in candidates[:limit]:
        recommendations.append(
            Recommendation(node=node, tool_usage=usage, reason=_reason(tool_stat.tool, usage, node))
        )
    return recommendations
