"""Render SkillTree's output to HTML "terminal screenshots" for the README.

Run from the repo root:

    python tools/make_screenshots.py        # writes docs/_html/*.html
    node ../_shot_build/shoot.mjs            # rasterises them to docs/*.png

We emit HTML (not SVG) on purpose. Rich's ``save_svg`` positions every run
with a ``textLength`` computed from the *character count*, while its tables are
laid out using East-Asian *cell* widths (CJK = 2). For Chinese text the two
disagree, so the browser squeezes wide glyphs with negative tracking and the
characters pile on top of each other. GitHub also strips the SVG's webfont, so
there is no reliable monospace metric to fall back on.

HTML sidesteps all of that: ``white-space: pre`` lays glyphs out at their
natural advance (never overlapping), and a duospaced CJK monospace font
(NSimSun, shipped with every Windows) keeps Han glyphs exactly twice the ASCII
width, so the box-drawing tables line up. A headless-Chrome screenshot then
bakes the result into a PNG that renders identically everywhere.
"""

from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

from skilltree.analyze import Analysis, analyze
from skilltree.knowledge import load_knowledge_base
from skilltree.recommend import recommend
from skilltree.render import render_recommendations, render_stats, render_tree

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
HTML_DIR = DOCS / "_html"

# A terminal-window chrome around Rich's recorded output. Braces are doubled so
# the string survives ``str.format`` inside Rich's HTML exporter; ``__TITLE__``
# is a plain sentinel we substitute ourselves (Rich only knows ``{code}`` etc.).
CODE_FORMAT = """<!doctype html><html><head><meta charset="utf-8"><style>
:root {{ color-scheme: dark; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: transparent; }}
.frame {{
    display: inline-block;
    background: #0d1117;
    border: 1px solid #222a35;
    border-radius: 14px;
    box-shadow: 0 18px 50px rgba(0, 0, 0, .45);
    overflow: hidden;
}}
.bar {{
    display: flex; align-items: center; gap: 9px;
    padding: 14px 18px;
    background: #161b22;
    border-bottom: 1px solid #222a35;
}}
.dot {{ width: 13px; height: 13px; border-radius: 50%; }}
.r {{ background: #ff5f56; }}
.y {{ background: #ffbd2e; }}
.g {{ background: #27c93f; }}
.cap {{
    margin-left: 10px; color: #8b949e; font-size: 18px;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
}}
.body {{ padding: 22px 26px 26px; }}
.body pre {{
    font-family: "Sarasa Mono SC", "NSimSun", "SimSun", "Cascadia Mono", monospace;
    font-size: 22px; line-height: 1.5; white-space: pre;
}}
{stylesheet}
</style></head><body>
  <div class="frame">
    <div class="bar">
      <span class="dot r"></span><span class="dot y"></span><span class="dot g"></span>
      <span class="cap">__TITLE__</span>
    </div>
    <div class="body"><pre><code>{code}</code></pre></div>
  </div>
</body></html>"""


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


def _save(console: Console, name: str, title: str) -> None:
    html = console.export_html(code_format=CODE_FORMAT, inline_styles=True)
    (HTML_DIR / f"{name}.html").write_text(html.replace("__TITLE__", title), encoding="utf-8")


def _subset(analysis: Analysis, tools: list[str]) -> Analysis:
    return Analysis(tools={t: analysis.tools[t] for t in tools}, shell=analysis.shell)


def main() -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    kb = load_knowledge_base()
    sample = ROOT / "skilltree" / "data" / "sample_history.txt"
    commands = [line for line in sample.read_text(encoding="utf-8").splitlines() if line.strip()]
    analysis = analyze(commands, kb, shell="demo")

    # Hero: the skill tree for two representative tools.
    console = _console(96)
    render_tree(_subset(analysis, ["git", "docker"]), console)
    _save(console, "show", "skilltree show --demo")

    # Recommendation feature.
    console = _console(84)
    render_recommendations(recommend(analysis, kb, limit=3), console)
    _save(console, "next", "skilltree next --demo")

    # Stats overview across all tools.
    console = _console(66)
    render_stats(analysis, console)
    _save(console, "stats", "skilltree stats --demo")

    print(f"wrote HTML to {HTML_DIR}")


if __name__ == "__main__":
    main()
