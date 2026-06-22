"""``skilltree`` command-line interface."""

from __future__ import annotations

import importlib.resources as resources
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from . import __version__
from .analyze import Analysis, analyze
from .growth import default_db_path, load_snapshots, render_growth, save_snapshot
from .history import default_history_path, detect_shell, parse_history
from .knowledge import KnowledgeBase, KnowledgeError, load_knowledge_base
from .practice import build_exercise, render_exercise
from .recommend import recommend
from .render import render_recommendations, render_stats, render_tree

app = typer.Typer(
    add_completion=False,
    help="把你的 shell history 变成一棵命令行技能树。所有分析只在本地进行。",
    no_args_is_help=True,
)


def _console(no_color: bool) -> Console:
    return Console(no_color=no_color, highlight=False)


def _load_demo_history() -> list[str]:
    sample = resources.files("skilltree") / "data" / "sample_history.txt"
    return parse_history(Path(str(sample)), shell="plain")


def _build_analysis(
    *,
    history: Optional[Path],
    shell: str,
    demo: bool,
    kb_dir: Optional[Path],
    console: Console,
) -> Analysis:
    try:
        kb: KnowledgeBase = load_knowledge_base(kb_dir)
    except KnowledgeError as exc:
        console.print(f"[red]知识库加载失败：{exc}[/]")
        raise typer.Exit(code=1)

    if demo:
        commands = _load_demo_history()
        shell_label = "demo"
    else:
        path = history or default_history_path(None if shell == "auto" else shell)
        try:
            commands = parse_history(path, shell=shell)
        except FileNotFoundError:
            console.print(
                f"[red]找不到 history 文件：{path}[/]\n"
                "[dim]用 --history 指定路径，或加 --demo 试用内置样例。[/]"
            )
            raise typer.Exit(code=1)
        shell_label = detect_shell() if shell == "auto" else shell

    return analyze(commands, kb, shell=shell_label)


# Shared options ------------------------------------------------------------

HistoryOpt = typer.Option(None, "--history", "-H", help="history 文件路径（默认自动探测）。")
ShellOpt = typer.Option("auto", "--shell", "-s", help="bash | zsh | plain | auto。")
DemoOpt = typer.Option(False, "--demo", help="使用内置脱敏样例历史，不读你的真实历史。")
KbOpt = typer.Option(None, "--kb", help="自定义知识库目录（默认用内置的）。")
NoColorOpt = typer.Option(False, "--no-color", help="关闭颜色输出。")


@app.command()
def show(
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="只看某个工具。"),
    locked: bool = typer.Option(False, "--locked", help="只看还没用过的节点。"),
    history: Optional[Path] = HistoryOpt,
    shell: str = ShellOpt,
    demo: bool = DemoOpt,
    kb: Optional[Path] = KbOpt,
    no_color: bool = NoColorOpt,
) -> None:
    """渲染技能树：绿色=已解锁，灰色🔒=未探索。"""
    console = _console(no_color)
    analysis = _build_analysis(history=history, shell=shell, demo=demo, kb_dir=kb, console=console)
    render_tree(analysis, console, tool_filter=tool, locked_only=locked)


@app.command(name="next")
def next_(
    count: int = typer.Option(3, "--count", "-n", min=1, help="推荐几个。"),
    history: Optional[Path] = HistoryOpt,
    shell: str = ShellOpt,
    demo: bool = DemoOpt,
    kb: Optional[Path] = KbOpt,
    no_color: bool = NoColorOpt,
) -> None:
    """推荐下一个值得学的 flag。"""
    console = _console(no_color)
    analysis = _build_analysis(history=history, shell=shell, demo=demo, kb_dir=kb, console=console)
    knowledge = load_knowledge_base(kb)
    render_recommendations(recommend(analysis, knowledge, limit=count), console)


@app.command()
def stats(
    history: Optional[Path] = HistoryOpt,
    shell: str = ShellOpt,
    demo: bool = DemoOpt,
    kb: Optional[Path] = KbOpt,
    no_color: bool = NoColorOpt,
) -> None:
    """汇总：总解锁数、各工具进度、tier 分布。"""
    console = _console(no_color)
    analysis = _build_analysis(history=history, shell=shell, demo=demo, kb_dir=kb, console=console)
    render_stats(analysis, console)


@app.command()
def snapshot(
    history: Optional[Path] = HistoryOpt,
    shell: str = ShellOpt,
    demo: bool = DemoOpt,
    kb: Optional[Path] = KbOpt,
    db: Optional[Path] = typer.Option(None, "--db", help="快照数据库路径。"),
    no_color: bool = NoColorOpt,
) -> None:
    """把当前解锁状态存进本地 SQLite，用于追踪成长。"""
    console = _console(no_color)
    analysis = _build_analysis(history=history, shell=shell, demo=demo, kb_dir=kb, console=console)
    taken_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    snap = save_snapshot(analysis, taken_at=taken_at, db_path=db)
    console.print(
        f"[green]已记录快照[/] {snap.taken_at}："
        f"{snap.unlocked}/{snap.total_nodes} 个节点 "
        f"(basic {snap.basic} / intermediate {snap.intermediate} / advanced {snap.advanced})。"
    )
    console.print(f"[dim]数据库：{db or default_db_path()}[/]")


@app.command()
def growth(
    db: Optional[Path] = typer.Option(None, "--db", help="快照数据库路径。"),
    no_color: bool = NoColorOpt,
) -> None:
    """画出解锁数量随时间的变化。"""
    console = _console(no_color)
    render_growth(load_snapshots(db), console)


@app.command()
def practice(
    tool: Optional[str] = typer.Option(None, "--tool", "-t", help="只在这个工具里挑练习。"),
    history: Optional[Path] = HistoryOpt,
    shell: str = ShellOpt,
    demo: bool = DemoOpt,
    kb: Optional[Path] = KbOpt,
    no_color: bool = NoColorOpt,
) -> None:
    """针对一个未探索的高价值 flag 生成安全的沙箱练习。"""
    console = _console(no_color)
    analysis = _build_analysis(history=history, shell=shell, demo=demo, kb_dir=kb, console=console)
    knowledge = load_knowledge_base(kb)
    recs = recommend(analysis, knowledge, limit=10)
    if tool:
        recs = [rec for rec in recs if rec.node.tool == tool]
    if not recs:
        console.print("[yellow]暂时没有合适的练习目标——先 `skilltree next` 看看推荐。[/]")
        raise typer.Exit(code=0)
    render_exercise(build_exercise(recs[0].node), console)


@app.callback(invoke_without_command=True)
def main(
    version: bool = typer.Option(False, "--version", "-V", help="打印版本并退出。"),
) -> None:
    if version:
        typer.echo(f"skilltree {__version__}")
        raise typer.Exit()


def run() -> None:  # console-script entry point
    # Safety net: never crash on a strict console encoding (e.g. legacy GBK on
    # Windows). Characters the terminal cannot represent are replaced rather
    # than raising UnicodeEncodeError mid-render.
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    app()


if __name__ == "__main__":
    run()
