"""The Overleaf mirror, against local stand-ins for Overleaf: a bare repository, and a local git server behind a password for the token's paths."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

import loom.overleaf as overleaf
from loom.history.ledger import load_history
from loom.overleaf import LinkRefused, MirrorError, here, pair, paired, prepare, project_of, run, store_token
from loom.scan.owntext import own_text
from loom.scan.quilt import Quilt, load_quilt
from loom.scan.scan import scan
from loom.sync import SyncState
from tests.helpers import json_of, ok
from tests.unit import _mirror as mirror
from tests.unit._mirror import renamed_pair
from tests.unit._overleaf_server import TOKEN, Server, serving

ID = "5f1e0c2a9b3d4e6f7a8b9c0d"
ID2 = "5f1e0c2a9b3d4e6f7a8b9c0e"
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
    bare.parent.mkdir(parents=True, exist_ok=True)
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


def at(pid: str) -> Path:
    """Where loom's address for the project `pid` leads in the test's stand-in for Overleaf (`overleaf.BASE`)."""
    return Path(overleaf.BASE) / pid


@pytest.fixture
def server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Server]:
    """The stand-in for Overleaf served over HTTP behind a password, where loom's addresses lead."""
    (tmp_path / "srv").mkdir()
    project(tmp_path / "srv" / ID, {"main.tex": MAIN})
    with serving(tmp_path / "srv") as served:
        monkeypatch.setattr(overleaf, "BASE", served.url("").rstrip("/"))
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
def test_a_project_s_own_link_in_any_form_overleaf_gives_names_the_project(link: str) -> None:
    assert project_of(link) == ID


def test_an_old_project_s_numeric_id_names_it() -> None:
    assert project_of("https://www.overleaf.com/project/1234567") == "1234567"


def test_the_address_is_built_from_the_id_alone_on_overleaf_s_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(overleaf, "BASE", "https://git.overleaf.com")
    assert overleaf.address(f"https://www.overleaf.com/project/{ID}") == f"https://git.overleaf.com/{ID}"
    for given in ("--upload-pack=touch x", "../elsewhere", f"{ID}/../x", ""):
        with pytest.raises(MirrorError) as refused:
            overleaf.git_address(given)
        assert refused.value.code == "bad-record"


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
        project_of(link)
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
        project_of(link)
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


def overleaf_project(tmp_path: Path, files: dict[str, str] | None = None, pid: str = ID) -> Path:
    """The stand-in project `pid`, where loom's address for it leads; with a figure when `files` is not given."""
    bare = project(at(pid), files or {"main.tex": PAPER, "sections/intro.tex": INTRO})
    if files is None:
        seed = bare.parent / f"{bare.name}.seed"
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
    pair(q, ID, "paper", "main.tex", [PAT[1]])
    return load_quilt(q.root), bare


def test_pairing_says_what_it_asks_and_writes_nothing_of_the_person_s(tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    overleaf_project(tmp_path)
    asked = prepare(q, ID)
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
    assert (state.folder, state.project, state.master) == ("paper", ID, "paper/main.tex")
    assert state.integrated == git(bare, "rev-parse", "main")
    assert not (root / ".loom/local/overleaf/main.tex").exists(), "loom's clone has no checkout"


def test_settings_read_the_mirror_from_the_manifest_s_overleaf_alone(tmp_path: Path) -> None:
    """The viewer's Overleaf section draws the manifest's `overleaf`; the config Settings reads names no `sync`."""
    from loom.config_edit import published as settings

    q, _ = mirrored(tmp_path)
    assert "sync" not in settings(scan(q))
    assert overleaf.published(q.root)["folder"] == "paper"


def test_who_the_person_is_on_overleaf_stays_on_this_machine(tmp_path: Path) -> None:
    q, _ = mirrored(tmp_path)
    assert here(q.root)["me"] == [PAT[1]]
    assert PAT[1] not in (q.root / ".loom/records/source-sync.json").read_text()
    overleaf_project(tmp_path, pid=ID2)
    assert prepare(new_quilt(tmp_path / "again"), ID2)["me"] == []


def test_a_main_file_a_person_already_named_keeps_its_place(tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    (q.root / "notes.md").write_text("# Notes\n")
    (q.root / "config.toml").write_text('[quilt]\nname = "test"\nmain = "notes.md"\n')
    overleaf_project(tmp_path)
    pair(load_quilt(q.root), ID, "paper", "main.tex", [])
    assert load_quilt(q.root).config.main == "notes.md"


@pytest.mark.parametrize("folder", ["", "../outside", ".hidden", "a/.git", "/abs"])
def test_a_folder_name_loom_cannot_use_is_refused(tmp_path: Path, folder: str) -> None:
    q = new_quilt(tmp_path)
    with pytest.raises(MirrorError) as refused:
        pair(q, ID, folder, "main.tex", [])
    assert refused.value.code == "bad-folder" and paired(q.root) is None


def test_a_folder_that_exists_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    (q.root / "paper").mkdir()
    (q.root / "paper/mine.tex").write_text("mine\n")
    overleaf_project(tmp_path)
    with pytest.raises(MirrorError) as refused:
        pair(q, ID, "paper", "main.tex", [])
    assert refused.value.code == "folder-exists"
    assert sorted(p.name for p in (q.root / "paper").iterdir()) == ["mine.tex"] and journal(q.root) == []
    assert prepare(q, ID)["folder"] == "overleaf"


def test_a_quilt_mirrors_one_project(tmp_path: Path) -> None:
    q, bare = mirrored(tmp_path)
    with pytest.raises(MirrorError) as asked:
        prepare(q, ID)
    with pytest.raises(MirrorError) as paired_again:
        pair(q, ID, "other", "main.tex", [])
    assert asked.value.code == paired_again.value.code == "paired"
    assert not (q.root / "other").exists()


def test_of_several_main_files_main_tex_is_taken_else_the_person_chooses(tmp_path: Path) -> None:
    two = {"main.tex": PAPER, "talk.tex": PAPER, "macros.tex": "\\newcommand{\\R}{\\mathbb{R}}\n"}
    project(at("a" * 24), two)
    assert prepare(new_quilt(tmp_path / "a"), "a" * 24)["main"] == "main.tex"
    other = {"paper.tex": PAPER, "talk.tex": PAPER}
    project(at("b" * 24), other)
    asked = prepare(new_quilt(tmp_path / "b"), "b" * 24)
    assert (asked["mains"], asked["main"]) == (["paper.tex", "talk.tex"], "")
    with pytest.raises(MirrorError) as refused:
        pair(new_quilt(tmp_path / "c"), "b" * 24, "paper", "macros.tex", [])
    assert refused.value.code == "no-main"


def test_a_project_with_no_file_that_begins_a_document_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MirrorError) as refused:
        prepare(new_quilt(tmp_path), str(project(at("d" * 24), {"notes.tex": "Just notes.\n"}).name))
    assert refused.value.code == "no-main"


def test_pairing_through_overleaf_s_password_keeps_the_token_out_of_the_quilt(server: Server, tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    with pytest.raises(MirrorError) as refused:
        prepare(q, ID)
    assert refused.value.code == "no-token"
    store_token(server.url(ID), TOKEN)
    asked = prepare(q, ID)
    pair(q, ID, asked["folder"], asked["main"], [])
    assert (q.root / "paper/main.tex").read_text() == MAIN
    assert not [p for p in q.root.rglob("*") if p.is_file() and TOKEN.encode() in p.read_bytes()]


# ---- a pull ----------------------------------------------------------------------------------------------------------


def moves(root: Path) -> list[dict[str, Any]]:
    p = root / ".loom" / "records" / "history" / "ledger.jsonl"
    lines = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.is_file() else []
    return [x for x in lines if x["action"] == "move"]


def take_pull(root: Path) -> dict[str, Any]:
    return overleaf.update(load_quilt(root))


def test_a_colleague_s_exact_rename_is_recorded_when_the_pull_is_taken_in(tmp_path: Path) -> None:
    root, other = renamed_pair(tmp_path)
    mirror.run(other, "mv", "main.tex", "paper.tex")
    mirror.run(other, "commit", "-q", "-m", "rename")
    mirror.run(other, "push", "-q", "origin", "HEAD:main")
    overleaf.fetch(load_quilt(root))
    assert moves(root) == []  # never on fetch
    take_pull(root)
    assert [{k: m[k] for k in ("from", "to", "moved", "via")} for m in moves(root)] == [
        {"from": "drafting/main.tex", "to": "drafting/paper.tex", "moved": False, "via": "sync"}
    ]
    assert 'main = "drafting/paper.tex"' in (root / "config.toml").read_text()
    assert SyncState.read(root).main == "paper.tex"
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


def test_only_an_unambiguous_identical_pair_is_a_rename(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two identical files deleted and one added, or one deleted and two added, cannot say which went where."""
    from loom.sync import exact_renames

    monkeypatch.setattr(overleaf, "_sealed", lambda _clone: True)  # a repository of the test's, not loom's clone

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
    assert exact_renames(root / ".git", before, mirror.run(root, "rev-parse", "HEAD")) == [("c.tex", "f.tex")]


def test_the_quilt_s_own_repository_is_never_touched(tmp_path: Path) -> None:
    root = mirror.quilt_at(tmp_path)
    mirror.run(root, "init", "-q", "-b", "main")
    mirror.run(root, "add", ".")
    mirror.run(root, "commit", "-q", "-m", "the quilt")
    head, refs = mirror.run(root, "rev-parse", "HEAD"), mirror.run(root, "for-each-ref")
    bare = mirror.overleaf(tmp_path)
    pair(load_quilt(root), mirror.PROJECT, "drafting", "main.tex", [])
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


# ---- updating --------------------------------------------------------------------------------------------------------

TWO = (
    mirror.PREAMBLE
    + "\\begin{document}\n"
    + "\\begin{lemma}Every finite tree with two vertices has a leaf.\\end{lemma}\n"
    + "\\begin{lemma}The complete graph on five vertices is not planar.\\end{lemma}\n"
    + "\\end{document}\n"
)


def two_lemmas(tmp_path: Path) -> tuple[Path, Path]:
    """A mirroring quilt whose paper holds two lemmas keyed by their place, as a pilot's paper is; with the project."""
    return mirror.paired(tmp_path, {"main.tex": TWO, "loom.sty": "% local support\n"})


def listed(root: Path) -> dict[str, list[str]]:
    """The blocks a pull's review origins list, with who else's commits touched each."""
    from loom.review_origins import read

    return {key: row.get("by", []) for key, row in read(root).items() if row["source"].startswith("pull:")}


def acts(root: Path) -> list[str]:
    return [e["kind"] for e in journal(root) if "kind" in e]


def test_an_update_with_nothing_new_writes_nothing(tmp_path: Path) -> None:
    root, _ = two_lemmas(tmp_path)
    before = acts(root)
    assert overleaf.update(load_quilt(root)) == {"state": "up-to-date"}
    assert acts(root) == before


def test_a_colleague_s_edit_arrives_as_overleaf_holds_it_and_is_listed_by_name(tmp_path: Path) -> None:
    root, bare = two_lemmas(tmp_path)
    edited = TWO.replace("has a leaf", "has at least two leaves")
    mirror.edit(mirror.colleague(tmp_path, bare), "sharper", {"main.tex": edited})
    said = overleaf.update(load_quilt(root))
    assert said == {
        "state": "updated",
        "files": 1,
        "by": ["Colleague"],
        "own": 0,
        "places": [],
        "here": [],
        "overwritten": [],
    }
    assert (root / "drafting/main.tex").read_text() == edited
    assert list(listed(root).values()) == [["Colleague"]]
    assert acts(root).count("pull") == 2  # the pairing and the update, each one act


def test_the_person_s_own_commit_is_left_out_of_review_and_said(tmp_path: Path) -> None:
    root, bare = two_lemmas(tmp_path)
    mine = mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)
    mirror.edit(mine, "my edit", {"main.tex": TWO.replace("has a leaf", "has two leaves")}, who=mirror.PERSON)
    said = overleaf.update(load_quilt(root))
    assert (said["by"], said["own"]) == ([], 1)
    assert listed(root) == {}


def test_of_two_commits_only_the_colleague_s_blocks_are_listed(tmp_path: Path) -> None:
    root, bare = two_lemmas(tmp_path)
    mine = mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)
    first = TWO.replace("has a leaf", "has two leaves")
    mirror.edit(mine, "mine", {"main.tex": first}, who=mirror.PERSON)
    mirror.edit(mirror.colleague(tmp_path, bare), "theirs", {"main.tex": first.replace("not planar", "never planar")})
    said = overleaf.update(load_quilt(root))
    assert (said["by"], said["own"]) == (["Colleague"], 1)
    (key,) = listed(root)
    result = scan(load_quilt(root))
    assert "never planar" in own_text(result, result.nodes[key])


def test_a_block_both_touched_is_listed_and_a_change_that_only_removed_lines_is_too(tmp_path: Path) -> None:
    root, bare = mirror.paired(tmp_path, {"main.tex": TWO.replace("has a leaf.", "has a leaf.\nIt is easy.\nReally.")})
    q = load_quilt(root)
    mine = mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)
    text = (root / "drafting/main.tex").read_text()
    mirror.edit(mine, "mine", {"main.tex": text.replace("It is easy.", "It is quite easy.")}, who=mirror.PERSON)
    mirror.edit(
        mirror.colleague(tmp_path, bare),
        "cut",
        {"main.tex": text.replace("It is easy.", "It is quite easy.").replace("\nReally.", "")},
    )
    said = overleaf.update(q)
    assert (said["by"], said["own"]) == (["Colleague"], 0)
    assert list(listed(root).values()) == [["Colleague"]]


def test_a_block_whose_own_words_did_not_change_is_not_listed_when_what_it_uses_did(tmp_path: Path) -> None:
    uses = (
        mirror.PREAMBLE
        + "\\begin{document}\n"
        + "\\begin{lemma}\\label{lem:tree}Every finite tree with two vertices has a leaf.\\end{lemma}\n"
        + "\\begin{lemma}\\uses{lem:tree}By Lemma~\\ref{lem:tree}, a forest has a leaf.\\end{lemma}\n"
        + "\\end{document}\n"
    )
    root, bare = mirror.paired(tmp_path, {"main.tex": uses, "loom.sty": "% local support\n"})
    mirror.edit(
        mirror.colleague(tmp_path, bare),
        "sharper",
        {"main.tex": uses.replace("has a leaf.\\end", "has two leaves.\\end", 1)},
    )
    overleaf.update(load_quilt(root))
    assert list(listed(root)) == ["lem:tree"]


def test_with_no_address_of_the_person_s_every_change_is_listed(tmp_path: Path) -> None:
    root = mirror.quilt_at(tmp_path)
    bare = mirror.overleaf(tmp_path, {"main.tex": TWO, "loom.sty": "% local support\n"})
    pair(load_quilt(root), mirror.PROJECT, "drafting", "main.tex", [])
    mine = mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)
    mirror.edit(mine, "mine", {"main.tex": TWO.replace("has a leaf", "has two leaves")}, who=mirror.PERSON)
    assert overleaf.update(load_quilt(root))["by"] == [mirror.PERSON[0]]


def test_a_change_made_here_is_written_over_said_and_kept_in_the_version_before(tmp_path: Path) -> None:
    root, bare = two_lemmas(tmp_path)
    stray = TWO.replace("not planar", "not planar, typed here by mistake")
    (root / "drafting/main.tex").write_text(stray)
    (root / "drafting/mine.tex").write_text("only here\n")
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": TWO.replace("has a leaf", "has leaves")})
    said = overleaf.update(load_quilt(root))
    assert said["overwritten"] == ["drafting/main.tex"]
    assert (root / "drafting/main.tex").read_text() == TWO.replace("has a leaf", "has leaves")
    assert (root / "drafting/mine.tex").read_text() == "only here\n"
    history = load_history(load_quilt(root).history_dir)
    kept = [
        history.landmark_path(e).read_text() for e in history.landmarks() if "before-update" in str(e.get("landmark"))
    ]
    assert kept == [stray]


def test_a_file_overleaf_removes_is_removed_and_one_it_adds_arrives(tmp_path: Path) -> None:
    root, bare = mirror.paired(tmp_path, {"main.tex": mirror.SOURCE, "loom.sty": "% s\n", "old.tex": "old\n"})
    other = mirror.colleague(tmp_path, bare)
    mirror.run(other, "rm", "-q", "old.tex", who=mirror.COLLEAGUE)
    mirror.edit(other, "swap", {"new.tex": "new\n"})
    assert overleaf.update(load_quilt(root))["files"] == 2
    assert not (root / "drafting/old.tex").exists() and (root / "drafting/new.tex").read_text() == "new\n"


def test_a_note_keeps_its_words_when_a_colleague_puts_a_lemma_above_its_block(tmp_path: Path) -> None:
    from loom.records.store import Records

    root, bare = two_lemmas(tmp_path)
    result = scan(load_quilt(root))
    (key,) = [k for k, n in result.nodes.items() if n.kind == "environment" and "not planar" in own_text(result, n)]
    ok("annotate", key, "Which embedding?", "--quote", "not planar", "--as", "Pat", cwd=root)
    above = TWO.replace(
        "\\begin{lemma}Every", "\\begin{lemma}A new lemma a colleague added.\\end{lemma}\n\\begin{lemma}Every"
    )
    mirror.edit(mirror.colleague(tmp_path, bare), "a lemma above", {"main.tex": above})
    overleaf.update(load_quilt(root))
    result = scan(load_quilt(root))
    (note,) = Records(root, load_quilt(root).history_dir).resolved(result)
    assert not note.detached and "not planar" in own_text(result, result.nodes[note.target])


def test_what_reaching_overleaf_could_not_do_stays_on_this_machine_until_a_fetch_succeeds(tmp_path: Path) -> None:
    root, bare = two_lemmas(tmp_path)
    hidden = bare.with_name("moved.git")
    bare.rename(hidden)
    with pytest.raises(MirrorError):
        overleaf.update(load_quilt(root))
    assert here(root)["problem"] in ("no-git-access", "failed", "offline")
    assert "problem" not in (root / ".loom/records/source-sync.json").read_text()
    hidden.rename(bare)
    assert overleaf.update(load_quilt(root)) == {"state": "up-to-date"} and here(root)["problem"] is None


def test_an_update_through_overleaf_s_password_keeps_the_token_out_of_the_quilt(server: Server, tmp_path: Path) -> None:
    q = new_quilt(tmp_path)
    store_token(server.url(ID), TOKEN)
    pair(q, ID, "paper", "main.tex", [])
    clone = tmp_path / "cleo"
    git(tmp_path, "clone", "-q", str(server.root / ID), str(clone))
    (clone / "main.tex").write_text(MAIN.replace("Hello.", "Hello, world."))
    git(clone, "commit", "-q", "-am", "edit", who=CLEO)
    git(clone, "push", "-q", "origin", "main", who=CLEO)
    assert overleaf.update(load_quilt(q.root))["files"] == 1
    assert not [p for p in q.root.rglob("*") if p.is_file() and TOKEN.encode() in p.read_bytes()]


# ---- a mirrored document to the rest of loom -------------------------------------------------------------------------


def suggested(root: Path) -> str:
    """A suggested edit on the second lemma, `not planar` to `never planar`; its id."""
    from loom.scan.quilt import save_author

    save_author("Pat")  # the person who keeps it; the test's home is its own
    said = json_of(
        "suggest",
        "drafting/main.tex#lemma:2",
        "--quote",
        "not planar",
        "--with",
        "never planar",
        "--as",
        "Claude Agent",
        "--json",
        cwd=root,
    )
    return str(said["edit"])


def test_keep_on_a_mirrored_document_is_refused_and_writes_nothing(tmp_path: Path) -> None:
    from tests.helpers import refused

    root, _ = two_lemmas(tmp_path)
    edit_id = suggested(root)
    before = (root / "drafting/main.tex").read_bytes()
    refused("changes", "--keep", edit_id, cwd=root, code=1, match="mirrors Overleaf")
    assert (root / "drafting/main.tex").read_bytes() == before


def test_done_in_overleaf_keeps_the_edit_once_an_update_brings_its_text_and_writes_nothing_more(tmp_path: Path) -> None:
    root, bare = two_lemmas(tmp_path)
    edit_id = suggested(root)
    mine = mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)
    mirror.edit(mine, "took the suggestion", {"main.tex": TWO.replace("not planar", "never planar")}, who=mirror.PERSON)
    overleaf.update(load_quilt(root))
    after = (root / "drafting/main.tex").read_bytes()
    written = acts(root)
    ok("changes", "--keep", edit_id, cwd=root)
    assert (root / "drafting/main.tex").read_bytes() == after
    assert acts(root) == written, "a Keep whose text Overleaf has already writes no file"
    assert [c["id"] for c in json_of("changes", "--json", cwd=root)["changes"]] == []


def test_no_act_but_an_update_moves_a_file_in_or_out_of_the_mirrored_folder(tmp_path: Path) -> None:
    """`Drafting/` is the mirrored folder where the file system ignores case, as a Mac's does, and is refused as it is; where case is told apart, as on Linux, it is another folder, and the move into it is the person's to make."""
    from tests.helpers import refused

    root, _ = two_lemmas(tmp_path)
    (root / "notes.tex").write_text("\\documentclass{article}\n\\begin{document}\nMine.\n\\end{document}\n")
    for old, new in (("drafting/main.tex", "elsewhere.tex"), ("notes.tex", "drafting/notes.tex")):
        refused("mv", old, new, cwd=root, code=1, match="mirrors Overleaf")
    assert (root / "drafting/main.tex").is_file() and (root / "notes.tex").is_file()
    if (root / "DRAFTING").exists():
        refused("mv", "notes.tex", "Drafting/notes.tex", cwd=root, code=1, match="mirrors Overleaf")
        assert (root / "notes.tex").is_file()
    else:
        ok("mv", "notes.tex", "Drafting/notes.tex", cwd=root)
        assert (root / "Drafting/notes.tex").is_file() and not (root / "drafting/notes.tex").exists()


def test_a_link_into_the_mirrored_folder_or_another_spelling_of_it_is_the_folder(tmp_path: Path) -> None:
    """The door judges the real file a path reaches: a link from an open place into the folder, and the folder named in another case where the file system ignores case, are refused as the folder is."""
    from loom import writes
    from loom.overleaf import mirrored

    root, _ = two_lemmas(tmp_path)
    (root / "notes").mkdir()
    (root / "notes/paper").symlink_to(root / "drafting", target_is_directory=True)
    (root / "notes/main.tex").symlink_to(root / "drafting/main.tex")
    spelled = ["Drafting/main.tex"] if (root / "DRAFTING").exists() else []
    for rel in ["notes/paper/main.tex", "notes/main.tex", "notes/paper/new.tex", *spelled]:
        assert mirrored(root, rel), rel
        with pytest.raises(writes.WriteRefused) as refused, writes.act(root, load_quilt(root).history_dir, "keep") as w:
            w.replace(rel, b"written past the mirror\n")
        assert refused.value.code == "mirrored", rel
    assert (root / "drafting/main.tex").read_text() == TWO and not (root / "drafting/new.tex").exists()
    assert not mirrored(root, "notes/elsewhere.tex") and not mirrored(root, "drafting-notes/main.tex")


def test_an_update_writes_the_mirrored_folder_and_nothing_else_is_judged_mirrored(tmp_path: Path) -> None:
    from loom import writes

    root, _ = two_lemmas(tmp_path)
    with writes.act(root, load_quilt(root).history_dir, "keep") as w:
        w.replace("notes.tex", b"mine\n")
    assert (root / "notes.tex").read_text() == "mine\n"


# ---- the token goes nowhere but the helper ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["no-token", "token-refused", "no-git-access", "offline", "accepted"])
def test_the_token_passes_through_loom_to_the_helper_and_nowhere_else(
    server: Server, tmp_path: Path, capfd: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    from loom.render.api import ApiError, handle
    from loom.render.build import build

    q = new_quilt(tmp_path)
    link = f"https://www.overleaf.com/project/{ID}"
    if path == "offline":
        with serving(tmp_path) as gone:
            monkeypatch.setattr(overleaf, "BASE", gone.url("").rstrip("/"))
    wrong = "olp_NotTheToken42"
    answers: list[Any] = []

    def ask(endpoint: str, body: dict[str, Any]) -> None:
        try:
            answers.append(handle(q.root, endpoint, body))
        except ApiError as exc:
            answers.append(exc.answer())

    if path != "no-token":
        ask("overleaf-token", {"link": link, "token": wrong if path == "token-refused" else TOKEN})
    server.access = path != "no-git-access"
    ask("overleaf-pair", {"link": link})
    if path == "accepted":
        ask("overleaf-pair", {"link": link, "folder": "paper", "main": "main.tex", "me": []})
        ask("overleaf-update", {})
    else:
        assert answers[-1]["error"]["code"] == path, answers
    manifest = build(load_quilt(q.root)).manifest
    said = capfd.readouterr()
    for secret in (TOKEN, wrong):
        assert secret not in json.dumps(answers) + json.dumps(manifest) + said.out + said.err
        for place in (q.root, tmp_path / "home"):
            assert not [p for p in place.rglob("*") if p.is_file() and secret.encode() in p.read_bytes()], place


# ---- what the review found ---------------------------------------------------------------------------------------------


def edit_record(root: Path, **fields: Any) -> None:
    """Change the record that travels with the quilt, as a quilt handed over could."""
    path = root / ".loom/records/source-sync.json"
    record = json.loads(path.read_text())
    record.update(fields)
    path.write_text(json.dumps(record))


@pytest.mark.parametrize(
    "fields",
    [
        {"branch": "--upload-pack=touch {marker}; true"},
        {"url": "--upload-pack=touch {marker}"},
        {"project": "--upload-pack=touch {marker}"},
        {"project": f"{ID}/../elsewhere"},
        {"main": "--output={marker}"},
        {"integrated": "--output={marker}"},
        {"folder": ".claude"},
        {"folder": "../outside"},
    ],
)
def test_a_record_that_came_with_the_quilt_decides_nothing_loom_did_not_check(
    tmp_path: Path, fields: dict[str, str]
) -> None:
    """O-1: the record's every field is checked as it is read, so no address, branch, option or folder it names reaches git or the door."""
    root, _ = two_lemmas(tmp_path)
    marker = tmp_path / "MARKER"
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text('{"mine": true}\n')
    edit_record(root, **{k: v.format(marker=marker) for k, v in fields.items()})
    with pytest.raises(MirrorError) as refused:
        overleaf.update(load_quilt(root))
    assert refused.value.code == "bad-record"
    assert not marker.exists() and (root / ".claude/settings.json").read_text() == '{"mine": true}\n'
    assert overleaf.published(root)["problem"] == "bad-record"


def test_a_folder_that_really_lies_in_a_dot_named_place_is_never_written(tmp_path: Path) -> None:
    """O-1: the folder is judged at every use by the door's place rule, on the real folder: one swapped for a link into `.claude` is refused."""
    root, bare = two_lemmas(tmp_path)
    (root / ".claude").mkdir()
    shutil.rmtree(root / "drafting")
    (root / "drafting").symlink_to(root / ".claude", target_is_directory=True)
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": TWO.replace("has a leaf", "has leaves")})
    with pytest.raises(MirrorError) as refused:
        overleaf.update(load_quilt(root))
    assert refused.value.code == "bad-record" and not (root / ".claude/main.tex").exists()


def plant_hook(clone: Path, marker: Path) -> None:
    for name in ("reference-transaction", "post-checkout", "pre-auto-gc"):
        hook = clone / "hooks" / name
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(f"#!/bin/sh\ntouch {marker}\ncat >/dev/null\n")
        hook.chmod(0o755)


def test_no_hook_runs_in_loom_s_clone_and_a_clone_a_quilt_brought_is_made_again(tmp_path: Path) -> None:
    """O-1: every mirror git call runs with hooks off, and a clone this machine did not make for this quilt and project is removed and made again, nothing in it read."""
    root, bare = two_lemmas(tmp_path)
    marker = tmp_path / "MARKER"
    plant_hook(root / ".loom/local/overleaf", marker)
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": TWO.replace("has a leaf", "has leaves")})
    overleaf.fetch(load_quilt(root))
    assert not marker.exists()
    handed = tmp_path / "handed"
    shutil.copytree(root, handed, symlinks=True)
    (handed / ".loom/local/overleaf/config").write_text(
        '[remote "origin"]\n\turl = /elsewhere\n[core]\n\tfsmonitor = touch ' + str(marker) + "\n"
    )
    plant_hook(handed / ".loom/local/overleaf", marker)
    overleaf.update(load_quilt(handed))
    assert not marker.exists() and not (handed / ".loom/local/overleaf/hooks").exists()
    assert (handed / "drafting/main.tex").read_text() == TWO.replace("has a leaf", "has leaves")


THREE = (
    mirror.PREAMBLE
    + "\\newcommand{\\R}{\\mathbb{R}}\n"
    + "\\begin{document}\n"
    + "Some words before.\n"
    + "\\begin{lemma}Alpha one.\nAlpha caveat: only for n > 2.\nAlpha end.\\end{lemma}\n"
    + "\\begin{lemma}Beta two.\\end{lemma}\n"
    + "\\begin{lemma}Gamma three.\\end{lemma}\n"
    + "\\end{document}\n"
)


def three(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """A mirroring quilt of three lemmas, a macro and words between, with a bibliography; the project, and a clone each for the colleague and the person."""
    root, bare = mirror.paired(tmp_path, {"main.tex": THREE, "loom.sty": "% s\n", "refs.bib": "@book{a, title={A}}\n"})
    return root, bare, mirror.colleague(tmp_path, bare), mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)


def test_a_colleague_s_removed_line_is_seen_though_the_person_later_edited_the_block(tmp_path: Path) -> None:
    """O-2: who changed a block is read over every commit that touched its lines, not from the lines that survive."""
    root, _, cleo, pat = three(tmp_path)
    cut = THREE.replace("Alpha caveat: only for n > 2.\n", "")
    mirror.edit(cleo, "cut the caveat", {"main.tex": cut})
    mirror.edit(pat, "my words", {"main.tex": cut.replace("Alpha one.", "Alpha one, Pat.")}, who=mirror.PERSON)
    said = overleaf.update(load_quilt(root))
    assert (said["by"], said["own"]) == (["Colleague"], 0)
    assert list(listed(root).values()) == [["Colleague"]]


def test_a_colleague_s_line_the_person_rewrote_is_still_the_colleague_s_change(tmp_path: Path) -> None:
    root, _, cleo, pat = three(tmp_path)
    mirror.edit(cleo, "theirs", {"main.tex": THREE.replace("Beta two.", "Beta two, Cleo.")})
    mirror.edit(pat, "mine", {"main.tex": THREE.replace("Beta two.", "Beta two, Pat.")}, who=mirror.PERSON)
    said = overleaf.update(load_quilt(root))
    assert (said["by"], said["own"]) == (["Colleague"], 0)


@pytest.mark.parametrize(
    "change, place, file",
    [
        (lambda t: t.replace("\\begin{lemma}Gamma three.\\end{lemma}\n", ""), "removed", "drafting/main.tex"),
        (lambda t: t.replace("\\mathbb{R}", "\\mathbb{Q}"), "preamble", "drafting/main.tex"),
        (lambda t: t.replace("Some words before.", "Some other words before."), "between", "drafting/main.tex"),
    ],
)
def test_a_colleague_s_change_outside_any_block_is_listed_by_its_place_and_name(
    tmp_path: Path, change: Callable[[str], str], place: str, file: str
) -> None:
    """O-3: a result removed, the preamble and the text between results are each a row for the file, named."""
    root, _, cleo, _ = three(tmp_path)
    mirror.edit(cleo, "outside", {"main.tex": change(THREE)})
    said = overleaf.update(load_quilt(root))
    assert said["places"] == [{"file": file, "place": place, "by": ["Colleague"]}] and said["by"] == ["Colleague"]


def test_a_colleague_s_bibliography_is_listed_and_the_person_s_own_preamble_change_is_left_out(tmp_path: Path) -> None:
    root, _, cleo, pat = three(tmp_path)
    mirror.edit(cleo, "a reference", {"refs.bib": "@book{a, title={A}}\n@book{b, title={B}}\n"})
    mirror.edit(pat, "my macro", {"main.tex": THREE.replace("\\mathbb{R}", "\\mathbb{C}")}, who=mirror.PERSON)
    said = overleaf.update(load_quilt(root))
    assert said["places"] == [{"file": "drafting/refs.bib", "place": "not-a-document", "by": ["Colleague"]}]
    assert said["own"] == 1


def test_a_change_made_here_and_written_over_is_listed_as_made_here_under_no_name(tmp_path: Path) -> None:
    """O-9: a block Overleaf did not change whose words here differed is listed as written over, by no one; the colleague's block by name."""
    root, _, cleo, _ = three(tmp_path)
    here_text = THREE.replace("Gamma three.", "Gamma three, typed here.")
    (root / "drafting/main.tex").write_text(here_text)
    mirror.edit(cleo, "theirs", {"main.tex": THREE.replace("Beta two.", "Beta two, Cleo.")})
    said = overleaf.update(load_quilt(root))
    assert said["by"] == ["Colleague"] and len(said["here"]) == 1
    from loom.review_origins import read

    rows = {k: (r["by"], r["here"]) for k, r in read(root).items()}
    assert sorted(rows.values()) == [([], True), (["Colleague"], False)]


def test_what_an_update_cut_short_had_already_written_still_reaches_review(tmp_path: Path) -> None:
    """O-4: the blocks an update cut short had written are listed by the next, which reads who changed what from the commits, not from what it writes."""
    root, _, cleo, _ = three(tmp_path)
    theirs = THREE.replace("Beta two.", "Beta two, Cleo.")
    mirror.edit(cleo, "theirs", {"main.tex": theirs})
    (root / "drafting/main.tex").write_text(theirs)  # as a cut-short update leaves it, the record still before it
    said = overleaf.update(load_quilt(root))
    assert said["by"] == ["Colleague"] and list(listed(root).values()) == [["Colleague"]]


def test_a_colleague_s_duplicate_label_never_stops_an_update(tmp_path: Path) -> None:
    """O-5: what a co-author wrote arrives; the two definitions are a problem in the document, and their fix arrives too."""
    labelled = THREE.replace("\\begin{lemma}Beta two.", "\\begin{lemma}\\label{lem:beta}Beta two.")
    root, bare = mirror.paired(tmp_path, {"main.tex": labelled, "loom.sty": "% s\n"})
    cleo = mirror.colleague(tmp_path, bare)
    twice = labelled.replace(
        "\\end{document}", "\\begin{lemma}\\label{lem:beta}Beta again.\\end{lemma}\n\\end{document}"
    )
    mirror.edit(cleo, "pasted twice", {"main.tex": twice})
    assert overleaf.update(load_quilt(root))["state"] == "updated"
    assert (root / "drafting/main.tex").read_text() == twice
    mirror.edit(cleo, "fixed", {"main.tex": labelled})
    assert overleaf.update(load_quilt(root))["state"] == "updated"
    assert (root / "drafting/main.tex").read_text() == labelled


def test_every_refusal_an_update_knows_answers_with_its_code(tmp_path: Path) -> None:
    """O-6: two updates at once, and a PDF saved into the mirrored folder, answer with their codes, not a 500."""
    import base64

    from loom import sync
    from loom.render.api import ApiError, handle

    root, bare = two_lemmas(tmp_path)
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": TWO.replace("has a leaf", "has leaves")})
    q = load_quilt(root)
    stale = overleaf.fetch(q)
    overleaf.update(q)
    with pytest.raises(MirrorError) as raced:
        sync.incorporate(q, stale, [])
    assert raced.value.code == "taken-in"
    pdf = base64.b64encode(b"%PDF-1.4\n%%EOF\n").decode()
    with pytest.raises(ApiError) as saved:
        handle(root, "pdf-save", {"path": "drafting/scan.pdf", "data": pdf})
    assert (saved.value.code, saved.value.status) == ("mirrored", 409)


def test_a_reviewer_name_an_agent_goes_by_is_refused_every_overleaf_act(tmp_path: Path) -> None:
    """The quilt's reviewer name decides as the request's `author` does: an agent's name never updates, pairs or unpairs, and nothing is written."""
    from loom.render.api import ApiError, handle
    from loom.scan.quilt import save_author

    root, bare = two_lemmas(tmp_path)
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": TWO.replace("has a leaf", "has leaves")})
    save_author("Referee Agent")
    for endpoint, body in (
        ("overleaf-update", {}),
        ("overleaf-unpair", {}),
        ("overleaf-pair", {"link": f"https://www.overleaf.com/project/{ID}"}),
    ):
        with pytest.raises(ApiError) as refused:
            handle(root, endpoint, body)
        assert (refused.value.code, refused.value.status) == ("author-only", 403), endpoint
    assert (root / "drafting/main.tex").read_text() == TWO and paired(root) is not None


def test_none_yet_is_asked_again_once_the_history_names_someone_new(tmp_path: Path) -> None:
    """O-7: a person who said "none yet" is asked again after their first change in Overleaf."""
    root = mirror.quilt_at(tmp_path)
    bare = project(at(ID), {"main.tex": TWO, "loom.sty": "% s\n"}, who=mirror.COLLEAGUE)
    pair(load_quilt(root), ID, "drafting", "main.tex", [])
    assert here(root)["ask"] is False
    pat = mirror.colleague(tmp_path, bare, "mine", who=mirror.PERSON)
    mirror.edit(pat, "mine", {"main.tex": TWO.replace("has a leaf", "has two leaves")}, who=mirror.PERSON)
    overleaf.fetch(load_quilt(root))
    assert here(root)["ask"] is True and overleaf.published(root)["ask_me"] is True
    overleaf.set_me(load_quilt(root), [mirror.PERSON[1]])
    assert here(root)["ask"] is False


def test_no_word_a_new_quilt_or_the_design_carries_names_loom_sync() -> None:
    """O-10."""
    repo = Path(__file__).resolve().parents[3]
    for rel in ("loom/src/loom/assets/init/readme.md", "docs/design/principles.md", "docs/specs/write-api.md"):
        text = (repo / rel).read_text(encoding="utf-8")
        assert "loom sync" not in text and "sync-incorporate" not in text and "sync-preview" not in text, rel


# ---- the confirming look -----------------------------------------------------------------------------------------------


def evil_project(tmp_path: Path) -> Path:
    """Another repository, whose text must never reach the folder."""
    return project(tmp_path / "evil.git", {"main.tex": TWO.replace("has a leaf", "EVIL")})


@pytest.mark.parametrize(
    "name, text",
    [
        ("config", '[url "{evil}"]\n\tinsteadOf = {base}\n'),
        ("config", '[core]\n\tattributesFile = {attrs}\n[diff "evil"]\n\ttextconv = {script}\n'),
        ("config.worktree", '[url "{evil}"]\n\tinsteadOf = {base}\n'),
        ("info/attributes", "*.tex diff=evil\n"),
        ("info/grafts", "{tip}\n"),
        ("commondir", "{evil}\n"),
        ("objects/info/alternates", "{evil}/objects\n"),
        ("objects/info/http-alternates", "http://127.0.0.1:9/objects\n"),
    ],
)
def test_a_key_written_into_loom_s_clone_after_loom_made_it_is_never_obeyed(
    tmp_path: Path, name: str, text: str
) -> None:
    """O-1: the mark holds a seal of what in the clone can name a program or an address, checked before every git call; a clone that no longer matches is made again, never repaired, and nothing written into it runs or reaches the folder."""
    root, bare = two_lemmas(tmp_path)
    clone = root / ".loom/local/overleaf"
    marker, evil = tmp_path / "MARKER", evil_project(tmp_path)
    script = tmp_path / "textconv.sh"
    script.write_text(f'#!/bin/sh\ntouch {marker}\ncat "$1"\n')
    script.chmod(0o755)
    (tmp_path / "attrs").write_text("*.tex diff=evil\n")
    planted = clone / name
    planted.parent.mkdir(parents=True, exist_ok=True)
    tip = git(bare, "rev-parse", "main")
    written = text.format(evil=evil, base=overleaf.BASE, attrs=tmp_path / "attrs", script=script, tip=tip)
    with planted.open("a") as f:
        f.write(written)
    theirs = TWO.replace("not planar", "never planar")
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": theirs})
    overleaf.update(load_quilt(root))
    assert not marker.exists()
    assert (root / "drafting/main.tex").read_text() == theirs
    assert not planted.exists() or written not in planted.read_text(), "made again, not repaired"


def test_a_proxy_written_into_loom_s_clone_never_hears_the_token(server: Server, tmp_path: Path) -> None:
    """O-1: `http.proxy` written into loom's clone after it was made is never used: the clone is made again before Overleaf is reached."""
    import socket
    import threading

    heard: list[bytes] = []
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)

    def listen() -> None:
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            heard.append(conn.recv(65536))
            conn.close()

    threading.Thread(target=listen, daemon=True).start()
    q = new_quilt(tmp_path)
    store_token(server.url(ID), TOKEN)
    pair(q, ID, "paper", "main.tex", [])
    with (q.root / ".loom/local/overleaf/config").open("a") as f:
        f.write(f"[http]\n\tproxy = http://127.0.0.1:{listener.getsockname()[1]}\n")
    overleaf.update(load_quilt(q.root))
    listener.close()
    assert heard == []


DEL = (
    mirror.PREAMBLE
    + "\\begin{document}\n"
    + "\\begin{lemma}Alpha one.\\end{lemma}\n"
    + "\\begin{lemma}Beta two.\\end{lemma}\n"
    + "\\begin{lemma}Gamma three.\\end{lemma}\n"
    + "\\end{document}\n"
)


@pytest.mark.parametrize("first, then", [("colleague", "person"), ("person", "colleague")])
def test_a_block_one_removed_and_the_other_wrote_again_is_listed(tmp_path: Path, first: str, then: str) -> None:
    """O-2: a block the colleague removed and the person then wrote again with new words, or the other way round, is the colleague's change too, since the colleague's commit touched that place."""
    root, bare = mirror.paired(tmp_path, {"main.tex": DEL, "loom.sty": "% s\n"})
    who = {"colleague": mirror.COLLEAGUE, "person": mirror.PERSON}
    clones = {k: mirror.colleague(tmp_path, bare, k, who=w) for k, w in who.items()}
    gone = DEL.replace("\\begin{lemma}Gamma three.\\end{lemma}\n", "")
    mirror.edit(clones[first], "removed", {"main.tex": gone}, who=who[first])
    mirror.edit(
        clones[then], "again", {"main.tex": DEL.replace("Gamma three.", "Gamma, written again.")}, who=who[then]
    )
    said = overleaf.update(load_quilt(root))
    assert said["by"] == ["Colleague"] and said["own"] == 0


def test_a_record_naming_the_folder_in_another_case_is_refused_with_its_code(tmp_path: Path) -> None:
    """O-15: the record's folder must be the folder's own spelling."""
    root, bare = two_lemmas(tmp_path)
    edit_record(root, folder="DRAFTING")
    mirror.edit(mirror.colleague(tmp_path, bare), "edit", {"main.tex": TWO.replace("has a leaf", "has leaves")})
    with pytest.raises(MirrorError) as refused:
        overleaf.update(load_quilt(root))
    assert refused.value.code == "bad-record" and (root / "drafting/main.tex").read_text() == TWO


def test_a_record_switched_to_another_project_is_refused_with_its_code(tmp_path: Path) -> None:
    """O-16: a project whose history does not hold what was last taken in is not this quilt's."""
    root, _ = two_lemmas(tmp_path)
    project(at(ID2), {"main.tex": TWO.replace("has a leaf", "is another project")})
    edit_record(root, project=ID2)
    with pytest.raises(MirrorError) as refused:
        overleaf.update(load_quilt(root))
    assert refused.value.code == "bad-record" and (root / "drafting/main.tex").read_text() == TWO


def test_a_path_the_file_system_cannot_resolve_is_not_trusted_to_lie_outside_the_mirror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As recovery's place rule takes such a path on trust no more than one that leads out (`writes._real`), the door refuses a write to one in a mirroring quilt."""
    from loom import writes
    from loom.overleaf import mirrored

    root, _ = two_lemmas(tmp_path)
    real = writes._real
    monkeypatch.setattr(writes, "_real", lambda p: None if "renaming" in str(p) else real(p))
    assert mirrored(root, "renaming/notes.tex") and not mirrored(root, "notes.tex")
    with pytest.raises(writes.WriteRefused) as refused, writes.act(root, load_quilt(root).history_dir, "keep") as w:
        w.replace("renaming/notes.tex", b"x\n")
    assert refused.value.code == "mirrored" and not (root / "renaming").exists()


# ---- O-4's settling, and a record naming the quilt itself ------------------------------------------------------------


def test_an_update_cut_short_after_a_dot_named_file_is_settled_by_the_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O-4: an update killed after writing `.latexmkrc` is left, since recovery writes no dot-named file; the next update, finding `.latexmkrc` as Overleaf holds it already, confirms it (`Act.confirm`) and the left one is settled."""
    from loom import writes
    from tests.unit.test_write_safety import Died, dying_before_the_rename

    root, bare = mirror.paired(tmp_path, {"main.tex": TWO, "loom.sty": "% s\n", ".latexmkrc": "$pdf_mode = 1;\n"})
    theirs = TWO.replace("not planar", "never planar")
    mirror.edit(mirror.colleague(tmp_path, bare), "both", {"main.tex": theirs, ".latexmkrc": "$pdf_mode = 4;\n"})
    overleaf.fetch(load_quilt(root))
    settled = 0
    for k in range(12):
        q = tmp_path / f"cut-{k}"
        shutil.copytree(root, q, symlinks=True)
        overleaf.fetch(load_quilt(q))  # a copy's clone is not one this machine made for it, so it is made again
        restore = dying_before_the_rename(monkeypatch, after=k)
        try:
            overleaf.update(load_quilt(q))
        except Died:
            pass
        else:
            restore()
            break
        restore()
        history = load_quilt(q).history_dir
        writes.recover(q, history)
        left = writes.left(q, history)
        if not left or (q / "drafting/.latexmkrc").read_text() != "$pdf_mode = 4;\n":
            continue
        assert [kind for kind, *_ in left] == ["a pull"]
        assert overleaf.update(load_quilt(q))["state"] == "updated"
        assert (q / "drafting/main.tex").read_text() == theirs
        writes.recover(q, history)
        assert writes.left(q, history) == [], k
        settled += 1
    assert settled >= 1


@pytest.mark.parametrize("folder", [".", "./", "", "x/..", "./drafting", "drafting/."])
def test_a_record_naming_the_quilt_itself_mirrors_nothing_and_stops_no_write(tmp_path: Path, folder: str) -> None:
    """Safe's reading: a record whose folder spells the quilt itself is not one loom reads, so it neither stops a write nor is written by an update."""
    from loom import writes
    from loom.overleaf import mirrored

    root, _ = two_lemmas(tmp_path)
    edit_record(root, folder=folder)
    assert not mirrored(root, "notes.tex") and not mirrored(root, "drafting/main.tex")
    with writes.act(root, load_quilt(root).history_dir, "keep") as w:
        w.replace("notes.tex", b"mine\n")
    assert (root / "notes.tex").read_text() == "mine\n"
    with pytest.raises(MirrorError) as refused:
        overleaf.update(load_quilt(root))
    assert refused.value.code == "bad-record"
