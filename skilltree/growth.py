"""Persist dated snapshots of unlock state and chart growth over time.

Snapshots live in a local SQLite database (by default under the user's config
directory). Nothing is ever sent off the machine.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from .analyze import Analysis
from .knowledge import TIERS


def default_db_path() -> Path:
    return Path.home() / ".config" / "skilltree" / "snapshots.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            taken_at TEXT NOT NULL,
            total_nodes INTEGER NOT NULL,
            unlocked INTEGER NOT NULL,
            basic INTEGER NOT NULL,
            intermediate INTEGER NOT NULL,
            advanced INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    return conn


@dataclass
class Snapshot:
    taken_at: str
    total_nodes: int
    unlocked: int
    basic: int
    intermediate: int
    advanced: int


def save_snapshot(analysis: Analysis, taken_at: str, db_path: Path | None = None) -> Snapshot:
    """Store the current unlock state stamped with ``taken_at`` (ISO string)."""
    db_path = db_path or default_db_path()
    dist = analysis.tier_distribution()
    snapshot = Snapshot(
        taken_at=taken_at,
        total_nodes=analysis.total_nodes,
        unlocked=analysis.total_unlocked,
        basic=dist["basic"],
        intermediate=dist["intermediate"],
        advanced=dist["advanced"],
    )
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO snapshots (taken_at, total_nodes, unlocked, basic, intermediate, advanced)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                snapshot.taken_at,
                snapshot.total_nodes,
                snapshot.unlocked,
                snapshot.basic,
                snapshot.intermediate,
                snapshot.advanced,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return snapshot


def load_snapshots(db_path: Path | None = None) -> list[Snapshot]:
    db_path = db_path or default_db_path()
    if not db_path.exists():
        return []
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT taken_at, total_nodes, unlocked, basic, intermediate, advanced"
            " FROM snapshots ORDER BY taken_at, id"
        ).fetchall()
    finally:
        conn.close()
    return [Snapshot(*row) for row in rows]


def _safe_block(console: Console) -> str:
    encoding = getattr(console.file, "encoding", None) or "utf-8"
    try:
        "█".encode(encoding)
        return "█"
    except (UnicodeEncodeError, LookupError):
        return "#"


def render_growth(snapshots: list[Snapshot], console: Console) -> None:
    if not snapshots:
        console.print(
            "[yellow]还没有快照。先跑 `skilltree snapshot` 记录一次当前进度。[/]"
        )
        return
    block = _safe_block(console)
    table = Table(title="解锁进度成长曲线", header_style="bold cyan")
    table.add_column("日期")
    table.add_column("已解锁", justify="right")
    table.add_column("Δ", justify="right")
    for tier in TIERS:
        table.add_column(tier, justify="right")
    table.add_column("趋势")

    max_unlocked = max(s.unlocked for s in snapshots) or 1
    previous: int | None = None
    for snap in snapshots:
        delta = "" if previous is None else f"{snap.unlocked - previous:+d}"
        bar_width = round(snap.unlocked / max_unlocked * 20)
        table.add_row(
            snap.taken_at,
            str(snap.unlocked),
            delta,
            str(snap.basic),
            str(snap.intermediate),
            str(snap.advanced),
            block * bar_width,
        )
        previous = snap.unlocked
    console.print(table)
