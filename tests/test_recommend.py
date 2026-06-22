from skilltree.analyze import analyze
from skilltree.knowledge import load_knowledge_base
from skilltree.recommend import recommend


def build(commands):
    kb = load_knowledge_base()
    return analyze(commands, kb), kb


def test_recommends_next_tier_for_used_tool():
    # Heavy basic git use, no intermediate features yet.
    commands = ["git status"] * 5 + ["git add ."] * 3 + ["git commit"] * 4
    analysis, kb = build(commands)
    recs = recommend(analysis, kb, limit=3)
    assert recs
    # Current highest tier is basic, so recommendations should be intermediate.
    assert all(r.node.tier == "intermediate" for r in recs)
    assert all(r.node.tool == "git" for r in recs)


def test_no_recommendation_for_unused_tools():
    analysis, kb = build(["git status"])
    recs = recommend(analysis, kb, limit=5)
    # Only git was used, so nothing from docker/ssh/etc. should appear.
    assert all(r.node.tool == "git" for r in recs)


def test_recommendations_are_unused():
    analysis, kb = build(["git commit --amend"] * 3)
    recs = recommend(analysis, kb, limit=5)
    used_ids = {
        stat.node.id for tool in analysis.tools.values() for stat in tool.nodes if stat.used
    }
    assert all(r.node.id not in used_ids for r in recs)


def test_high_frequency_tool_ranked_first():
    commands = ["git status"] * 10 + ["grep foo bar"] * 1
    analysis, kb = build(commands)
    recs = recommend(analysis, kb, limit=1)
    assert recs[0].node.tool == "git"


def test_empty_history_no_recommendations():
    analysis, kb = build([])
    assert recommend(analysis, kb) == []
