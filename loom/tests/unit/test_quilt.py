"""Quilt discovery, config validation and who the author is."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from loom.scan.quilt import (
    NO_AUTHOR_MESSAGE,
    NoAuthorError,
    NoQuiltError,
    QuiltConfig,
    find_quilt,
    load_quilt,
    resolve_author,
)


def _make(root: Path, body: str = '[quilt]\nmain = "drafting/main.tex"\n') -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.toml").write_text(body, encoding="utf-8")
    return root


def test_quilt_discovery_walks_up(tmp_path: Path) -> None:
    root = _make(tmp_path / "q")
    deep = root / "drafting" / "nodes" / "deeper"
    deep.mkdir(parents=True)
    assert find_quilt(deep).root == root.resolve()


def test_quilt_discovery_fails_outside(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text("[notaquilt]\nx = 1\n", encoding="utf-8")
    with pytest.raises(NoQuiltError):
        find_quilt(tmp_path)


def test_quilt_discovery_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make(tmp_path / "q")
    monkeypatch.setenv("LOOM_QUILT", str(root))
    monkeypatch.chdir(tmp_path)
    assert find_quilt().root == root.resolve()


def test_quilt_config_unknown_key_warns(tmp_path: Path) -> None:
    root = _make(tmp_path / "q", '[quilt]\nmain = "drafting/main.tex"\nbogus = 1\n[extra]\ny = 2\n')
    q = load_quilt(root)
    assert any("quilt.bogus" in w for w in q.config.warnings)
    assert any("[extra]" in w for w in q.config.warnings)
    assert q.config.main == "drafting/main.tex"
    assert q.config.prefix == "q"


def test_a_table_that_is_not_a_table_warns() -> None:
    cfg = QuiltConfig.from_dict({"quilt": {"name": "Q"}, "refs": "yes"})
    assert cfg.name == "Q"
    assert any("[refs] is not a table" in w for w in cfg.warnings)


def test_the_author_is_the_flag_then_local_config_then_git(home: Path, tmp_path: Path) -> None:
    """A tracked author never identifies the person working in a clone."""
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(NoAuthorError) as exc:
        resolve_author(None, cwd=repo)
    assert str(exc.value) == NO_AUTHOR_MESSAGE
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Git Person"], check=True)
    assert resolve_author(None, cwd=repo) == ("Git Person", "git config user.name")
    user = home / ".config" / "loom" / "config.toml"
    user.parent.mkdir(parents=True)
    user.write_text('[author]\nname = "Config Person"\n', encoding="utf-8")
    assert resolve_author(None, cwd=repo) == ("Config Person", str(user))
    assert resolve_author("Flag Person", cwd=repo) == ("Flag Person", "--as")

    cfg = repo / "config.toml"
    cfg.write_text('[quilt]\nprefix = "ab"\n', encoding="utf-8")
    assert resolve_author(None, repo) == ("Config Person", str(user))  # no [author] table: the user config answers
    cfg.write_text('[quilt]\nprefix = "ab"\n\n[author]\nname = "Markas Hecht"\n', encoding="utf-8")
    assert resolve_author(None, repo) == ("Config Person", str(user))
    assert resolve_author("Someone Else", repo) == ("Someone Else", "--as")  # the flag still wins

    cfg.write_text('[quilt]\nprefix = "ab"\n\n[author]\nname = ""\n', encoding="utf-8")
    assert resolve_author(None, repo) == ("Config Person", str(user))


def test_the_git_name_is_asked_of_git_once_until_a_file_it_comes_from_changes(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A build asks for the name once per annotation; git is asked again only when its configuration changes, an included file's among it."""
    import os

    from loom.scan.quilt import git_user_name

    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    globl, extra, later = home / ".gitconfig", home / "extra.gitconfig", home / "later.gitconfig"
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(globl))
    globl.write_text("[include]\n\tpath = extra.gitconfig\n\tpath = ~/later.gitconfig\n", encoding="utf-8")
    extra.write_text("[user]\n\tname = First\n", encoding="utf-8")
    asked = []
    run = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda argv, *a, **kw: asked.append(argv) or run(argv, *a, **kw))

    def changed(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1_000_000))

    assert [git_user_name(repo) for _ in range(3)] == ["First"] * 3
    assert len(asked) == 1
    changed(extra, "[user]\n\tname = Second\n")
    assert git_user_name(repo) == "Second"
    changed(later, "[user]\n\tname = Third\n")  # an included file that did not exist
    assert git_user_name(repo) == "Third"
    changed(globl, "[user]\n\tname = Fourth\n")
    assert [git_user_name(repo) for _ in range(3)] == ["Fourth"] * 3
    assert len(asked) == 4


def test_the_user_configs_name_is_read_once_until_its_file_changes(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A process resolves the person's name once: the user config is read again only when its file changes, as a name saved in Settings changes it."""
    from loom.scan import quilt as module
    from loom.scan.quilt import save_author

    read: list[int] = []
    real = module.load_user_config
    monkeypatch.setattr(module, "load_user_config", lambda: read.append(1) or real())
    save_author("First")
    assert [resolve_author(None, tmp_path)[0] for _ in range(3)] == ["First"] * 3
    assert len(read) == 1
    save_author("Second")
    assert [resolve_author(None, tmp_path)[0] for _ in range(3)] == ["Second"] * 3
    assert len(read) == 2


def test_status_says_whose_states_it_gives_and_when_git_gave_the_name(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A look and an acceptance are kept under the name, so a name git gives is said; one the person set is not."""
    from loom.scan.quilt import save_author
    from tests.helpers import json_of, ok
    from tests.unit._quilts import demo

    q = demo(tmp_path)
    globl = home / "status.gitconfig"
    globl.write_text("[user]\n\tname = Git Person\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(globl))
    said = json_of("status", "--json", cwd=q)
    assert said["reviewer"] == {"name": "Git Person", "source": "git config user.name"}
    assert [n for n in said["notes"] if "Git Person's, the name git gives" in n]
    assert "the name git gives" in ok("status", cwd=q).stderr
    save_author("Set Person")
    said = json_of("status", "--json", cwd=q)
    assert said["reviewer"] == {"name": "Set Person", "source": "local user configuration"}
    assert not [n for n in said["notes"] if "git gives" in n]


def test_with_apples_git_stub_there_is_no_name_and_git_is_never_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On a Mac with no developer tools `/usr/bin/git` opens an installer dialog: the name is none, kept as any answer is, and git is not started."""
    from loom import gitprog
    from loom.scan.quilt import git_user_name

    monkeypatch.setattr(gitprog, "usable", lambda: False)
    asked: list[object] = []
    monkeypatch.setattr(subprocess, "run", lambda argv, *a, **kw: asked.append(argv))
    assert [git_user_name(tmp_path) for _ in range(3)] == [None] * 3
    assert asked == []
