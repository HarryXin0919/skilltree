"""Render SkillTree's output to SVG "terminal screenshots" for the README.

Run from the repo root:

    python tools/make_screenshots.py

Produces docs/show.svg, docs/next.svg and docs/stats.svg. Uses an in-memory
StringIO console so emoji glyphs are always used (independent of the host
terminal's encoding) and records the output for SVG export.
"""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from skilltree.analyze import Analysis, analyze
from skilltree.knowledge import load_knowledge_base
from skilltree.recommend import recommend
from skilltree.render import render_recommendations, render_stats, render_tree

DOCS = Path(__file__).resolve().parent.parent / "docs"


def _console(width: int) -> Console:
    # A StringIO file has no `.encoding`, so the renderer defaults to UTF-8 and
    # uses the emoji glyph set; force_terminal keeps colour styling on.
    return Console(
        record=True,
        file=io.StringIO(),
        width=width,
        force_terminal=True,
        color_system="truecolor",
    )


def _subset(analysis: Analysis, tools: list[str]) -> Analysis:
    return Analysis(tools={t: analysis.tools[t] for t in tools}, shell=analysis.shell)


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    kb = load_knowledge_base()
    sample = Path(__file__).resolve().parent.parent / "skilltree" / "data" / "sample_history.txt"
    commands = [line for line in sample.read_text(encoding="utf-8").splitlines() if line.strip()]
    analysis = analyze(commands, kb, shell="demo")

    # Hero: the skill tree for two representative tools.
    console = _console(112)
    render_tree(_subset(analysis, ["git", "docker"]), console)
    console.save_svg(str(DOCS / "show.svg"), title="skilltree show --demo")

    # Recommendation feature.
    console = _console(96)
    render_recommendations(recommend(analysis, kb, limit=3), console)
    console.save_svg(str(DOCS / "next.svg"), title="skilltree next --demo")

    # Stats overview across all tools.
    console = _console(72)
    render_stats(analysis, console)
    console.save_svg(str(DOCS / "stats.svg"), title="skilltree stats --demo")

    print(f"wrote SVGs to {DOCS}")


if __name__ == "__main__":
    main()
