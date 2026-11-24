"""The Overleaf mirror, against local stand-ins for Overleaf: a bare repository, and a local git server behind a password for the token's paths."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import loom.overleaf as overleaf
from loom.overleaf import LinkRefused, MirrorError, address, here, pair, paired, prepare, run, store_token
from loom.scan.quilt import Quilt, load_quilt
from loom.sync import SyncState
from tests.helpers import json_of, ok
from tests.unit import _mirror as mirror
from tests.unit._mirror import renamed_pair
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


# ---- pairing ---------------------------------------------------------------------------------------------------------

INTRO = "\\section{Introduction}\nWe study things.\n"
PAPER = "\\documentclass{article}\n\\begin{document}\n\\input{sections/intro}\n\\end{document}\n"
FIGURE = bytes(range(256))


def new_quilt(tmp_path: Path) -> Quilt:
    """A quilt as `loom init` leaves a new one: no main document, nothing denied to agents."""
    from loom.layout import stamp

    root = tmp_path / "quilt"
    root.mkdir(parents=True)
    stamp(root)
    (root / "config.toml").write_text('[quilt]\nname = "test"\n', encoding="utf-8")
    return load_quilt(root)


def overleaf_project(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    bare = project(tmp_path / "overleaf.git", files or {"main.tex": PAPER, "sections/intro.tex": INTRO})
    if files is None:
        seed = tmp_path / "overleaf.git.seed"
        (seed / "figures").mkdir()
        (seed / "figures/plot.pdf").write_bytes(FIGURE)
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "a figure")
        git(seed, "push", "-q", str(bare), "main")
    return bare


def journal(root: Path) -> list[dict[str, Any]]:
    path = root / ".loom/local/writes.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def mirrored(tmp_path: Path) -> tuple[Quilt, Path]:
    """A new quilt paired with a project in `paper/`, the person known as Pat."""
    q = new_quilt(tmp_path)
    bare = overleaf_project(tmp_path)
    pair(q, str(bare), "paper", "main.tex", [PAT[1]])
    return load_quilt(q.root), bare


def test_pairing_says_what_it_asks_and_writes_nothing_of_the_person_s(tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    asked = prepare(q, str(overleaf_project(tmp_path)))
    assert asked == {
        "folder": "paper",
        "mains": ["main.tex"],
        "main": "main.tex",
        "authors": [{"name": PAT[0], "email": PAT[1]}],
        "me": [],
    }
    assert sorted(p.name for p in q.root.iterdir()) == [".loom", "config.toml"]
    assert journal(q.root) == []


def test_pairing_copies_the_project_into_a_new_folder_as_one_act(tmp_path: Path) -> None:
    q, bare = mirrored(tmp_path)
    root = q.root
    assert (root / "paper/main.tex").read_text() == PAPER
    assert (root / "paper/sections/intro.tex").read_text() == INTRO
    assert (root / "paper/figures/plot.pdf").read_bytes() == FIGURE
    (act,) = [e for e in journal(root) if e.get("event", "begin") == "begin" and e.get("kind") == "pull"]
    assert {"paper/main.tex", "paper/sections/intro.tex", "config.toml", ".loom/records/source-sync.json"} <= set(
        act["files"]
    )
    assert q.config.main == "paper/main.tex" and q.config.agents_deny == ["paper/"]
    state = SyncState.read(root)
    assert (state.folder, state.url, state.master, state.directory) == (
        "paper",
        str(bare),
        "paper/main.tex",
        ".loom/local/overleaf",
    )
    assert state.integrated == git(bare, "rev-parse", "main")
    assert not (root / ".loom/local/overleaf/main.tex").exists(), "loom's clone has no checkout"


def test_who_the_person_is_on_overleaf_stays_on_this_machine(tmp_path: Path) -> None:
    q, _ = mirrored(tmp_path)
    assert here(q.root)["me"] == [PAT[1]]
    assert PAT[1] not in (q.root / ".loom/records/source-sync.json").read_text()
    assert prepare(new_quilt(tmp_path / "again"), str(overleaf_project(tmp_path / "again")))["me"] == []


def test_a_main_file_a_person_already_named_keeps_its_place(tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    (q.root / "notes.md").write_text("# Notes\n")
    (q.root / "config.toml").write_text('[quilt]\nname = "test"\nmain = "notes.md"\n')
    pair(load_quilt(q.root), str(overleaf_project(tmp_path)), "paper", "main.tex", [])
    assert load_quilt(q.root).config.main == "notes.md"


@pytest.mark.parametrize("folder", ["", "../outside", ".hidden", "a/.git", "/abs"])
def test_a_folder_name_loom_cannot_use_is_refused(tmp_path: Path, folder: str) -> None:
    q = new_quilt(tmp_path)
    with pytest.raises(MirrorError) as refused:
        pair(q, str(overleaf_project(tmp_path)), folder, "main.tex", [])
    assert refused.value.code == "bad-folder" and paired(q.root) is None


def test_a_folder_that_exists_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    (q.root / "paper").mkdir()
    (q.root / "paper/mine.tex").write_text("mine\n")
    bare = overleaf_project(tmp_path)
    with pytest.raises(MirrorError) as refused:
        pair(q, str(bare), "paper", "main.tex", [])
    assert refused.value.code == "folder-exists"
    assert sorted(p.name for p in (q.root / "paper").iterdir()) == ["mine.tex"] and journal(q.root) == []
    assert prepare(q, str(bare))["folder"] == "overleaf"


def test_a_quilt_mirrors_one_project(tmp_path: Path) -> None:
    q, bare = mirrored(tmp_path)
    with pytest.raises(MirrorError) as asked:
        prepare(q, str(bare))
    with pytest.raises(MirrorError) as paired_again:
        pair(q, str(bare), "other", "main.tex", [])
    assert asked.value.code == paired_again.value.code == "paired"
    assert not (q.root / "other").exists()


def test_of_several_main_files_main_tex_is_taken_else_the_person_chooses(tmp_path: Path) -> None:
    two = {"main.tex": PAPER, "talk.tex": PAPER, "macros.tex": "\\newcommand{\\R}{\\mathbb{R}}\n"}
    assert prepare(new_quilt(tmp_path / "a"), str(project(tmp_path / "a.git", two)))["main"] == "main.tex"
    other = {"paper.tex": PAPER, "talk.tex": PAPER}
    asked = prepare(new_quilt(tmp_path / "b"), str(project(tmp_path / "b.git", other)))
    assert (asked["mains"], asked["main"]) == (["paper.tex", "talk.tex"], "")
    with pytest.raises(MirrorError) as refused:
        pair(new_quilt(tmp_path / "c"), str(project(tmp_path / "c.git", other)), "paper", "macros.tex", [])
    assert refused.value.code == "no-main"


def test_a_project_with_no_file_that_begins_a_document_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MirrorError) as refused:
        prepare(new_quilt(tmp_path), str(project(tmp_path / "p.git", {"notes.tex": "Just notes.\n"})))
    assert refused.value.code == "no-main"


def test_pairing_through_overleaf_s_password_keeps_the_token_out_of_the_quilt(server: Server, tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    with pytest.raises(MirrorError) as refused:
        prepare(q, server.url(ID))
    assert refused.value.code == "no-token"
    store_token(server.url(ID), TOKEN)
    asked = prepare(q, server.url(ID))
    pair(q, server.url(ID), asked["folder"], asked["main"], [])
    assert (q.root / "paper/main.tex").read_text() == MAIN
    assert not [p for p in q.root.rglob("*") if p.is_file() and TOKEN.encode() in p.read_bytes()]


# ---- a pull ----------------------------------------------------------------------------------------------------------


def moves(root: Path) -> list[dict[str, Any]]:
    p = root / ".loom" / "records" / "history" / "ledger.jsonl"
    lines = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
    return [x for x in lines if x["action"] == "move"]


def take_pull(root: Path) -> None:
    from loom import sync

    q = load_quilt(root)
    sync.incorporate(q, sync.fetch(q, SyncState.read(root)))


def test_a_colleague_s_exact_rename_is_recorded_when_the_pull_is_taken_in(tmp_path: Path) -> None:
    root, other = renamed_pair(tmp_path)
    mirror.run(other, "mv", "main.tex", "paper.tex")
    mirror.run(other, "commit", "-q", "-m", "rename")
    mirror.run(other, "push", "-q", "origin", "HEAD:main")
    from loom import sync

    sync.fetch(load_quilt(root), SyncState.read(root))
    assert moves(root) == []  # never on fetch
    take_pull(root)
    assert [{k: m[k] for k in ("from", "to", "moved", "via")} for m in moves(root)] == [
        {"from": "drafting/main.tex", "to": "drafting/paper.tex", "moved": False, "via": "sync"}
    ]
    assert 'main = "drafting/paper.tex"' in (root / "config.toml").read_text()
    assert SyncState.read(root).published_main == "paper.tex"
    assert json_of("status", "--json", cwd=root)["keys"]["zk-0001"]["acceptance"]["fresh"] is True
    assert "drafting/main.tex -> drafting/paper.tex (renamed in a pull)" in ok("history", cwd=root).stdout


def test_a_rename_with_an_edit_is_not_recorded_and_the_document_is_gone(tmp_path: Path) -> None:
    root, other = renamed_pair(tmp_path)
    text = (other / "main.tex").read_text(encoding="utf-8")
    mirror.run(other, "rm", "-q", "main.tex")
    mirror.edit(other, "rename and edit", {"paper.tex": text.replace("zk-0001}A", "zk-0001}B")})
    take_pull(root)
    assert moves(root) == []
    gone = [x for x in json_of("lint", "--json", cwd=root)["diagnostics"] if x["code"] == "loom:document-gone"]
    assert len(gone) == 1 and "drafting/main.tex" in json.dumps(gone[0])


def test_only_an_unambiguous_identical_pair_is_a_rename(tmp_path: Path) -> None:
    """Two identical files deleted and one added, or one deleted and two added, cannot say which went where."""
    from loom.sync import exact_renames

    root = tmp_path / "r"
    root.mkdir()
    mirror.run(root, "init", "-q", "-b", "main")
    for name, body in (("a.tex", "same\n"), ("b.tex", "same\n"), ("c.tex", "c\n"), ("d.tex", "d\n")):
        (root / name).write_text(body, encoding="utf-8")
    mirror.run(root, "add", ".")
    mirror.run(root, "commit", "-q", "-m", "before")
    before = mirror.run(root, "rev-parse", "HEAD")
    mirror.run(root, "rm", "-q", "a.tex", "b.tex", "c.tex", "d.tex")
    for name, body in (("e.tex", "same\n"), ("f.tex", "c\n"), ("g.tex", "d\n"), ("h.tex", "d\n")):
        (root / name).write_text(body, encoding="utf-8")
    mirror.run(root, "add", ".")
    mirror.run(root, "commit", "-q", "-m", "after")
    assert exact_renames(root, before, mirror.run(root, "rev-parse", "HEAD")) == [("c.tex", "f.tex")]


def test_the_quilt_s_own_repository_is_never_touched(tmp_path: Path) -> None:
    root = mirror.quilt_at(tmp_path)
    mirror.run(root, "init", "-q", "-b", "main")
    mirror.run(root, "add", ".")
    mirror.run(root, "commit", "-q", "-m", "the quilt")
    head, refs = mirror.run(root, "rev-parse", "HEAD"), mirror.run(root, "for-each-ref")
    bare = mirror.overleaf(tmp_path)
    pair(load_quilt(root), str(bare), "drafting", "main.tex", [])
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": mirror.SOURCE.replace("}A", "}B")})
    take_pull(root)
    assert (mirror.run(root, "rev-parse", "HEAD"), mirror.run(root, "for-each-ref")) == (head, refs)


# ---- nothing writes to Overleaf --------------------------------------------------------------------------------------


def test_no_command_reaches_overleaf_and_no_git_call_of_loom_s_pushes() -> None:
    import ast

    from loom.ai.layout import command_tree

    assert not [c for c in command_tree() if c == "sync" or c.startswith("sync ")]
    src = Path(overleaf.__file__).parent
    for module in ("sync.py", "overleaf.py"):
        for node in ast.walk(ast.parse((src / module).read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and node.value in ("push", "send-pack"):
                raise AssertionError(f"{module} names git's {node.value!r} at line {node.lineno}")
