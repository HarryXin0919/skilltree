"""Render the skill tree and recommendations to the terminal with rich.

Glyphs degrade gracefully: on terminals whose encoding cannot represent the
emoji / block characters (e.g. a legacy Windows GBK console) an ASCII fallback
set is used instead, so output is never garbled and never crashes.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .analyze import Analysis, ToolStat
from .knowledge import TIERS
from .recommend import Recommendation

_TIER_STYLE = {
    "basic": "green",
    "intermediate": "yellow",
    "advanced": "magenta",
}


@dataclass(frozen=True)
class Glyphs:
    root: str
    check: str
    lock: str
    bar_full: str
    bar_empty: str
    growth_block: str
    tier_marks: tuple[str, str, str]


_EMOJI = Glyphs(
    root="🌳 ",
    check="✓",
    lock="🔒",
    bar_full="▰",
    bar_empty="▱",
    growth_block="█",
    tier_marks=("•", "••", "•••"),
)
_ASCII = Glyphs(
    root="",
    check="+",
    lock="-",
    bar_full="#",
    bar_empty=".",
    growth_block="#",
    tier_marks=("1", "2", "3"),
)


def _glyphs_for(console: Console) -> Glyphs:
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    sample = "".join(
        [_EMOJI.root, _EMOJI.check, _EMOJI.lock, _EMOJI.bar_full, _EMOJI.growth_block]
        + list(_EMOJI.tier_marks)
    )
    try:
        sample.encode(encoding)
        return _EMOJI
    except (UnicodeEncodeError, LookupError):
        return _ASCII


def _tier_mark(glyphs: Glyphs, tier: str) -> str:
    index = TIERS.index(tier) if tier in TIERS else 0
    return glyphs.tier_marks[index]


def _progress_bar(glyphs: Glyphs, ratio: float, width: int = 12) -> str:
    filled = round(ratio * width)
    return glyphs.bar_full * filled + glyphs.bar_empty * (width - filled)


def _tool_label(glyphs: Glyphs, tool: ToolStat) -> Text:
    bar = _progress_bar(glyphs, tool.ratio)
    pct = f"{tool.ratio * 100:4.0f}%"
    label = Text()
    label.append(f"{tool.tool}", style="bold cyan")
    label.append(f"  {bar} ", style="cyan")
    label.append(f"{tool.unlocked}/{tool.total} {pct}", style="dim")
    return label


def _node_label(glyphs: Glyphs, node_stat, *, locked_only: bool) -> Text | None:
    node = node_stat.node
    tier_style = _TIER_STYLE.get(node.tier, "white")
    mark = _tier_mark(glyphs, node.tier)
    if node_stat.used:
        if locked_only:
            return None
        label = Text()
        label.append(f"{glyphs.check} ", style="bold green")
        label.append(node.id, style="green")
        label.append(f" x{node_stat.count}", style="bold green")
        label.append(f"  [{node.tier} {mark}]", style=f"dim {tier_style}")
        return label
    label = Text()
    label.append(f"{glyphs.lock} ", style="dim")
    label.append(node.id, style="dim")
    label.append(f"  [{node.tier} {mark}]", style=f"dim {tier_style}")
    label.append(f"  {node.desc}", style="dim italic")
    return label


def build_tree(
    analysis: Analysis,
    glyphs: Glyphs,
    *,
    tool_filter: str | None = None,
    locked_only: bool = False,
) -> Tree:
    root = Tree(Text(f"{glyphs.root}{analysis.shell}", style="bold white"))
    for tool_name, tool_stat in analysis.tools.items():
        if tool_filter and tool_name != tool_filter:
            continue
        if locked_only and tool_stat.unlocked == tool_stat.total:
            continue
        branch = root.add(_tool_label(glyphs, tool_stat))
        for node_stat in tool_stat.nodes:
            label = _node_label(glyphs, node_stat, locked_only=locked_only)
            if label is not None:
                branch.add(label)
    return root


def render_tree(
    analysis: Analysis,
    console: Console,
    *,
    tool_filter: str | None = None,
    locked_only: bool = False,
) -> None:
    glyphs = _glyphs_for(console)
    console.print(
        build_tree(analysis, glyphs, tool_filter=tool_filter, locked_only=locked_only)
    )


def render_recommendations(recommendations: list[Recommendation], console: Console) -> None:
    if not recommendations:
        console.print(
            "[yellow]没有可推荐的下一步——你要么还没用过知识库里的工具，"
            "要么已经把它们点满了。先跑 `skilltree show` 看看。[/]"
        )
        return
    console.print("[bold]下一个值得解锁的技能：[/]\n")
    for index, rec in enumerate(recommendations, start=1):
        console.print(f"[bold cyan]{index}. {rec.node.invocation}[/]  [dim]({rec.node.tier})[/]")
        console.print(f"   {rec.reason}\n")


def render_stats(analysis: Analysis, console: Console) -> None:
    glyphs = _glyphs_for(console)
    table = Table(title="SkillTree 统计", show_edge=True, header_style="bold cyan")
    table.add_column("工具")
    table.add_column("已解锁", justify="right")
    table.add_column("总数", justify="right")
    table.add_column("进度")
    table.add_column("最高 tier")
    for tool_stat in analysis.tools.values():
        table.add_row(
            tool_stat.tool,
            str(tool_stat.unlocked),
            str(tool_stat.total),
            _progress_bar(glyphs, tool_stat.ratio),
            tool_stat.highest_tier or "—",
        )
    console.print(table)

    dist = analysis.tier_distribution()
    summary = Table(title="按 tier 分布（已解锁）", show_edge=True, header_style="bold magenta")
    for tier in TIERS:
        summary.add_column(tier, justify="center")
    summary.add_row(*[str(dist[tier]) for tier in TIERS])
    console.print(summary)
    console.print(
        f"\n[bold]总解锁：[/] {analysis.total_unlocked}/{analysis.total_nodes} "
        f"个节点，覆盖 {len(analysis.tools)} 个工具。"
    )
