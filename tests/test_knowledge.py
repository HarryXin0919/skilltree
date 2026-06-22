import pytest

from skilltree.knowledge import KnowledgeError, load_knowledge_base


def test_load_bundled_knowledge_base():
    kb = load_knowledge_base()
    for tool in ("git", "docker", "tar", "grep", "find", "ssh"):
        assert tool in kb.tools
        assert len(kb.tools[tool]) >= 8


def test_flag_nodes_have_a_flag():
    kb = load_knowledge_base()
    for node in kb.all_nodes():
        if node.type == "flag":
            assert node.flag, f"{node.id} has no derived flag"


def test_match_index_resolves_known_nodes():
    kb = load_knowledge_base()
    assert kb.subcommand_node("git", "commit") is not None
    amend = kb.flag_nodes("git", "--amend")
    assert amend and amend[0].subcommand == "commit"
    # grep's recursive flag is not scoped to a subcommand.
    recursive = kb.flag_nodes("grep", "-r")
    assert recursive and recursive[0].subcommand is None


def test_missing_field_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "tool: demo\nnodes:\n  - id: demo.x\n    type: flag\n    tier: basic\n"
        '    invocation: "demo -x"\n',  # missing desc
        encoding="utf-8",
    )
    with pytest.raises(KnowledgeError):
        load_knowledge_base(tmp_path)


def test_invalid_tier_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "tool: demo\nnodes:\n  - id: demo.x\n    type: subcommand\n    tier: wizard\n"
        '    invocation: "demo go"\n    desc: nope\n',
        encoding="utf-8",
    )
    with pytest.raises(KnowledgeError):
        load_knowledge_base(tmp_path)


def test_empty_directory_raises(tmp_path):
    with pytest.raises(KnowledgeError):
        load_knowledge_base(tmp_path)
