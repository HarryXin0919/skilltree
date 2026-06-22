from skilltree.tokenizer import parse_command, split_commands, tokenize


def only(line):
    parsed = tokenize(line)
    assert len(parsed) == 1
    return parsed[0]


def test_simple_subcommand_and_flag():
    cmd = only('git commit -m "hello world"')
    assert cmd.base == "git"
    assert cmd.subcommand == "commit"
    assert "-m" in cmd.flags
    assert cmd.flag_values["-m"] == "hello world"
    # The message is never mistaken for a flag.
    assert "hello world" not in cmd.flags


def test_quotes_protect_separators():
    # The pipe lives inside quotes, so it is NOT a command separator.
    commands = split_commands('echo "a | b && c"')
    assert len(commands) == 1


def test_pipe_split():
    parsed = tokenize("grep -i foo file | wc -l")
    assert len(parsed) == 2
    assert parsed[0].base == "grep"
    assert parsed[1].base == "wc"


def test_logical_and_split():
    parsed = tokenize('git add . && git commit -m "x"')
    assert [p.base for p in parsed] == ["git", "git"]
    assert parsed[1].subcommand == "commit"


def test_semicolon_split():
    parsed = tokenize("cd /tmp ; ls -la")
    assert [p.base for p in parsed] == ["cd", "ls"]


def test_value_flag_not_treated_as_subcommand():
    # -C takes a path value, so the real subcommand is `commit`.
    cmd = only("git -C /path/to/repo commit -m msg")
    assert cmd.subcommand == "commit"
    assert "-C" in cmd.flags
    assert cmd.flag_values["-C"] == "/path/to/repo"


def test_clustered_short_flags_expand():
    cmd = only("docker run -it --rm myimage")
    assert cmd.subcommand == "run"
    assert "-i" in cmd.flags
    assert "-t" in cmd.flags
    assert "--rm" in cmd.flags
    assert "myimage" in cmd.args


def test_tar_cluster_with_value_flag():
    cmd = only("tar -xzf archive.tar.gz")
    assert cmd.base == "tar"
    assert {"-x", "-z", "-f"} <= set(cmd.flags)
    # -f consumes the following archive name as its value.
    assert cmd.flag_values["-f"] == "archive.tar.gz"


def test_unknown_tool_has_no_subcommand():
    cmd = only("mytool do-something --flag")
    assert cmd.base == "mytool"
    assert cmd.subcommand is None
    assert "do-something" in cmd.args
    assert "--flag" in cmd.flags


def test_grep_has_no_subcommand():
    cmd = only("grep -rn TODO src/")
    assert cmd.subcommand is None
    assert {"-r", "-n"} <= set(cmd.flags)
    assert "TODO" in cmd.args


def test_find_single_dash_long_option_not_clustered():
    cmd = only('find . -name "*.py" -type f')
    assert cmd.base == "find"
    assert "-name" in cmd.flags
    assert "-type" in cmd.flags
    # It must NOT explode into -n -a -m -e.
    assert "-n" not in cmd.flags
    assert cmd.flag_values["-name"] == "*.py"
    assert cmd.flag_values["-type"] == "f"
    assert "." in cmd.args


def test_long_flag_with_equals():
    cmd = only("tar --exclude=node_modules -czf out.tar.gz src")
    assert "--exclude" in cmd.flags
    assert cmd.flag_values["--exclude"] == "node_modules"


def test_negative_number_is_argument():
    cmd = only("ssh -p 22 user@host")
    assert cmd.flag_values["-p"] == "22"
    assert "user@host" in cmd.args


def test_empty_command_returns_none():
    assert parse_command([]) is None
