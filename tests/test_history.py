import pytest

from skilltree.history import parse_history


def test_plain_format(fixtures):
    commands = parse_history(fixtures / "sample_history.txt", shell="plain")
    assert commands[0] == "git status"
    assert 'git commit -m "first commit"' in commands
    # Blank lines are dropped.
    assert "" not in commands


def test_bash_format_strips_timestamps(fixtures):
    commands = parse_history(fixtures / "sample.bash_history", shell="bash")
    # Timestamp comment lines (#1700000000) are removed.
    assert all(not c.startswith("#17") for c in commands)
    assert commands[0] == "git status"
    assert 'git commit -m "first"' in commands
    assert "docker ps" in commands
    # The blank line between entries is dropped.
    assert "" not in commands


def test_zsh_extended_format(fixtures):
    commands = parse_history(fixtures / "sample.zsh_history", shell="zsh")
    assert commands[0] == "git status"
    assert 'git commit -m "first commit"' in commands
    assert "docker run -it --rm ubuntu" in commands
    # The multi-line command is re-joined across the backslash continuation.
    assert any("echo line1" in c and "line2" in c for c in commands)
    # A corrupted, marker-less line is tolerated (kept, not a crash).
    assert any("corrupted line" in c for c in commands)
    assert "tar -xzf archive.tar.gz" in commands


def test_auto_detects_zsh(fixtures):
    auto = parse_history(fixtures / "sample.zsh_history", shell="auto")
    explicit = parse_history(fixtures / "sample.zsh_history", shell="zsh")
    assert auto == explicit


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_history(tmp_path / "does_not_exist", shell="plain")


def test_empty_file(tmp_path):
    empty = tmp_path / "empty"
    empty.write_text("\n\n   \n")
    assert parse_history(empty, shell="auto") == []
