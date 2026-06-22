from skilltree.analyze import analyze
from skilltree.knowledge import load_knowledge_base


def make_analysis(commands):
    return analyze(commands, load_knowledge_base())


def test_lights_subcommand_and_flag_nodes():
    analysis = make_analysis(
        [
            "git commit --amend",
            'git commit -m "msg"',
            "grep -i foo bar.txt",
        ]
    )
    # `commit` appears in two commands.
    assert analysis.node_stat("git.commit").count == 2
    assert analysis.node_stat("git.commit").used
    assert analysis.node_stat("git.commit.amend").count == 1
    assert analysis.node_stat("git.commit.message").count == 1
    # grep was used with -i and the base pattern node.
    assert analysis.node_stat("grep.ignore-case").used
    assert analysis.node_stat("grep.basic").used


def test_unused_nodes_stay_locked():
    analysis = make_analysis(["git status"])
    assert analysis.node_stat("git.status").used
    assert not analysis.node_stat("git.bisect").used
    assert analysis.node_stat("git.bisect").count == 0


def test_highest_tier_tracks_best_used_node():
    analysis = make_analysis(["git status", "git commit --amend"])
    git = analysis.tools["git"]
    # amend is intermediate, status is basic -> highest is intermediate.
    assert git.highest_tier == "intermediate"


def test_tool_ratio_and_totals():
    analysis = make_analysis(["git status", "git add ."])
    git = analysis.tools["git"]
    assert git.unlocked == 2
    assert git.total >= 8
    assert 0 < git.ratio < 1


def test_unknown_commands_are_ignored():
    analysis = make_analysis(["ls -la", "cd /tmp", "echo hi"])
    assert analysis.total_unlocked == 0


def test_tier_distribution():
    analysis = make_analysis(["git status", "git commit --amend", "git rebase -i"])
    dist = analysis.tier_distribution()
    assert dist["basic"] >= 1
    assert dist["intermediate"] >= 1
    assert dist["advanced"] >= 1


def test_clustered_tar_lights_multiple_nodes():
    analysis = make_analysis(["tar -xzf backup.tar.gz"])
    assert analysis.node_stat("tar.extract").used
    assert analysis.node_stat("tar.gzip").used
    assert analysis.node_stat("tar.file").used
