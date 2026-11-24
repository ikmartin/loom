"""The Overleaf mirror, against local stand-ins for Overleaf: a bare repository, and a local git server behind a password for the token's paths."""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

import loom.overleaf as overleaf
from loom.overleaf import LinkRefused, MirrorError, address, run, store_token
from tests.unit._overleaf_server import TOKEN, Server, serving

ID = "5f1e0c2a9b3d4e6f7a8b9c0d"
MAIN = "\\documentclass{article}\n\\begin{document}\nHello.\n\\end{document}\n"
PAT = ("Pat Person", "pat@example.org")
CLEO = ("Cleo Coauthor", "cleo@example.org")


def git(cwd: Path, *args: str, who: tuple[str, str] = PAT) -> str:
    name, email = who
    env = {"GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email}
    import os

    return subprocess.check_output(["git", *args], cwd=cwd, text=True, env={**os.environ, **env}).strip()


def project(bare: Path, files: dict[str, str], who: tuple[str, str] = PAT) -> Path:
    """A bare repository on `main` standing in for an Overleaf project, its first commit holding `files`."""
    seed = bare.parent / f"{bare.name}.seed"
    git(bare.parent, "init", "-q", "--bare", "-b", "main", str(bare))
    git(bare.parent, "init", "-q", "-b", "main", str(seed))
    for rel, text in files.items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_text(text, encoding="utf-8")
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "new project", who=who)
    git(seed, "push", "-q", str(bare), "main")
    return bare


def stand_in(tmp_path: Path) -> str:
    """What the stand-in for the Keychain holds."""
    kept = tmp_path / "keychain-stand-in"
    return kept.read_text() if kept.exists() else ""


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    (tmp_path / "srv").mkdir()
    project(tmp_path / "srv" / ID, {"main.tex": MAIN})
    with serving(tmp_path / "srv") as served:
        yield served


# ---- the link --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "link",
    [
        f"https://www.overleaf.com/project/{ID}",
        f"https://www.overleaf.com/project/{ID}/",
        f"https://www.overleaf.com/project/{ID}?utm=x#section",
        f"www.overleaf.com/project/{ID}",
        f"overleaf.com/project/{ID.upper()}",
        f"https://git.overleaf.com/{ID}",
        f"https://git@git.overleaf.com/{ID}",
        f"https://git.overleaf.com/{ID}.git",
        f"  git clone https://git.overleaf.com/{ID}  ",
        f"git clone https://git.overleaf.com/{ID} my-paper",
    ],
)
def test_a_project_s_own_link_in_any_form_overleaf_gives_names_its_git_address(link: str) -> None:
    assert address(link) == f"https://git.overleaf.com/{ID}"


def test_an_old_project_s_numeric_id_is_its_git_address() -> None:
    assert address("https://www.overleaf.com/project/1234567") == "https://git.overleaf.com/1234567"


@pytest.mark.parametrize(
    "link",
    [
        "https://www.overleaf.com/read/abcdefghijkl",
        "https://www.overleaf.com/read/abcdefghijkl#3f2a1b",
        "https://www.overleaf.com/8429385762qwertyzxcvbn",
    ],
)
def test_a_sharing_link_is_refused_because_it_does_not_name_the_project(link: str) -> None:
    with pytest.raises(LinkRefused) as refused:
        address(link)
    assert refused.value.code == "sharing-link"


@pytest.mark.parametrize(
    "link",
    [
        "",
        "https://www.overleaf.com/project",
        "https://www.overleaf.com/project/not-an-id",
        f"https://github.com/someone/{ID}",
        f"https://overleaf.example.edu/project/{ID}",
        f"https://git.overleaf.com.evil.example/{ID}",
        f"https://www.overleaf.com.evil.example/project/{ID}",
        "git clone",
    ],
)
def test_anything_else_is_refused_as_not_a_project(link: str) -> None:
    with pytest.raises(LinkRefused) as refused:
        address(link)
    assert refused.value.code == "not-a-project"


# ---- git and the token -----------------------------------------------------------------------------------------------


def failure(*args: str) -> MirrorError:
    with pytest.raises(MirrorError) as failed:
        run(None, *args)
    return failed.value


def test_no_test_reaches_the_keychain() -> None:
    assert "osxkeychain" not in overleaf.HELPER


def test_with_no_token_kept_git_fails_at_once_asking_for_one(server: Server) -> None:
    assert failure("ls-remote", server.url(ID)).code == "no-token"


def test_the_person_s_own_git_config_never_answers_for_the_mirror(
    server: Server, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A helper the person's git config names, holding the token, is cleared: only `HELPER` answers."""
    theirs = tmp_path / "their-credentials"
    host = server.url(ID).split("/")[2]
    theirs.write_text(f"http://git:{TOKEN}@{host}\n")
    config = tmp_path / "their-gitconfig"
    config.write_text(f"[credential]\n\thelper = store --file={theirs}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    assert failure("ls-remote", server.url(ID)).code == "no-token"


def test_a_token_overleaf_accepts_is_kept_by_the_helper_alone_and_used(server: Server, tmp_path: Path) -> None:
    store_token(server.url(ID), TOKEN)
    assert "refs/heads/main" in run(None, "ls-remote", server.url(ID)).decode()
    assert TOKEN in stand_in(tmp_path)


def test_a_refused_token_is_said_and_forgotten_so_the_next_try_asks_again(server: Server, tmp_path: Path) -> None:
    store_token(server.url(ID), "olp_NotTheToken")
    refused = failure("ls-remote", server.url(ID))
    assert refused.code == "token-refused" and "olp_NotTheToken" not in str(refused)
    assert "olp_NotTheToken" not in stand_in(tmp_path)
    assert failure("ls-remote", server.url(ID)).code == "no-token"


def test_a_project_whose_owner_has_no_git_access_is_said(server: Server) -> None:
    store_token(server.url(ID), TOKEN)
    server.access = False
    refused = failure("ls-remote", server.url(ID))
    assert refused.code == "no-git-access" and TOKEN not in str(refused)


def test_overleaf_out_of_reach_is_said(tmp_path: Path) -> None:
    with serving(tmp_path) as gone:
        url = gone.url(ID)
    store_token(url, TOKEN)
    refused = failure("ls-remote", url)
    assert refused.code == "offline" and TOKEN not in str(refused)


@pytest.mark.parametrize("token", ["", "   ", "olp_a\nhost=elsewhere.example", "olp a", "olp_\x00"])
def test_a_token_of_more_than_one_printable_line_never_reaches_the_helper(
    server: Server, tmp_path: Path, token: str
) -> None:
    with pytest.raises(MirrorError) as refused:
        store_token(server.url(ID), token)
    assert refused.value.code == "bad-token"
    assert stand_in(tmp_path) == ""
