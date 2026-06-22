"""Generate a safe, sandboxed practice exercise for an unexplored skill.

Exercises only ever describe commands to run inside a throwaway temporary
directory — SkillTree never touches your real files and never runs anything
destructive on your behalf.
"""

from __future__ import annotations

from dataclasses import dataclass

from .knowledge import SkillNode


@dataclass
class Exercise:
    node: SkillNode
    scenario: str
    setup: list[str]
    commands: list[str]
    expected: str


def _generic(node: SkillNode) -> Exercise:
    return Exercise(
        node=node,
        scenario=(
            f"在一个临时目录里安全地试用 `{node.invocation}`：{node.desc}"
        ),
        setup=["mkdir skilltree-sandbox && cd skilltree-sandbox"],
        commands=[
            f"{node.tool} --help | less   # 先读懂 {node.invocation} 的作用",
            f"{node.invocation}   # 在沙箱里实际敲一遍",
        ],
        expected="观察输出，确认它和 desc 描述的行为一致，然后 `cd .. && rm -rf skilltree-sandbox`。",
    )


def build_exercise(node: SkillNode) -> Exercise:
    """Return a practice exercise for ``node`` (bespoke if available)."""
    drill_builder = _SPECIFIC.get(node.id)
    if drill_builder is not None:
        return drill_builder(node)
    return _generic(node)


def _git_amend(node: SkillNode) -> Exercise:
    return Exercise(
        node=node,
        scenario="练习修改上一次提交（不产生新的提交历史）。",
        setup=[
            "mkdir skilltree-sandbox && cd skilltree-sandbox",
            "git init -q && echo hello > a.txt && git add a.txt",
            'git commit -q -m "wip: tpyo in message"',
        ],
        commands=[
            'git commit --amend -m "fix: correct commit message"',
            "git log --oneline   # 只应看到一条提交，且 message 已更新",
        ],
        expected="git log 只有一条提交，message 变成 'fix: correct commit message'。完事后删掉沙箱目录。",
    )


def _git_stash(node: SkillNode) -> Exercise:
    return Exercise(
        node=node,
        scenario="练习把未提交的改动临时收起来，再恢复。",
        setup=[
            "mkdir skilltree-sandbox && cd skilltree-sandbox",
            "git init -q && echo v1 > a.txt && git add a.txt && git commit -q -m init",
            "echo v2 > a.txt   # 制造未提交改动",
        ],
        commands=[
            "git stash        # 改动被收起，工作区回到干净状态",
            "cat a.txt        # 应显示 v1",
            "git stash pop    # 改动回来了",
            "cat a.txt        # 应显示 v2",
        ],
        expected="stash 后文件回到 v1，pop 后恢复成 v2。完事后删掉沙箱目录。",
    )


def _find_exec(node: SkillNode) -> Exercise:
    return Exercise(
        node=node,
        scenario="练习用 find -exec 对匹配到的文件批量执行命令。",
        setup=[
            "mkdir skilltree-sandbox && cd skilltree-sandbox",
            "touch one.log two.log keep.txt",
        ],
        commands=[
            r'find . -name "*.log" -exec echo removing {} \;   # 先用 echo 预演，安全！',
            r'find . -name "*.log" -exec rm {} \;              # 确认无误后再真的删',
            "ls   # 只应剩下 keep.txt",
        ],
        expected="两个 .log 文件被删除，keep.txt 保留。永远先用 echo 预演 -exec。完事后删掉沙箱目录。",
    )


_SPECIFIC = {
    "git.commit.amend": _git_amend,
    "git.stash": _git_stash,
    "find.exec": _find_exec,
}


def render_exercise(exercise: Exercise, console) -> None:
    node = exercise.node
    console.print(f"[bold cyan]练习：{node.invocation}[/]  [dim]({node.tier})[/]\n")
    console.print(f"[bold]场景[/] {exercise.scenario}\n")
    console.print("[bold]准备（在临时沙箱里）[/]")
    for line in exercise.setup:
        console.print(f"  [green]$[/] {line}")
    console.print("\n[bold]要敲的命令[/]")
    for line in exercise.commands:
        console.print(f"  [green]$[/] {line}")
    console.print(f"\n[bold]预期效果[/] {exercise.expected}")
    console.print(
        "\n[dim italic]提醒：全程只在临时目录里操作，SkillTree 不会碰你的真实文件。[/]"
    )
