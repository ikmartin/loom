"""A quilt mirroring a stand-in for an Overleaf project: a local bare repository on `main`, a colleague's clone that edits and pushes, and the quilt paired with it in `drafting/`."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from loom.overleaf import pair
from loom.scan.quilt import load_quilt

CONFIG = '[quilt]\nname = "test"\nmain = "drafting/main.tex"\nprefix = "zk"\nengine = "pdflatex"\n'
PREAMBLE = "\\documentclass{article}\n\\usepackage{loom}\n\\newtheorem{lemma}{Lemma}\n"
SOURCE = PREAMBLE + "\\begin{document}\n\\begin{lemma}\\label{zk-0001}A\\end{lemma}\n\\end{document}\n"
#: The person, as the project's history names them.
PERSON = ("Pat Person", "pat@example.org")
#: A colleague who edits the project in Overleaf.
COLLEAGUE = ("Colleague", "colleague@example.org")


def run(root: Path, *args: str, who: tuple[str, str] = PERSON) -> str:
    name, email = who
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }
    return subprocess.check_output(["git", *args], cwd=root, text=True, env=env, stderr=subprocess.DEVNULL).strip()


def quilt_at(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """A quilt that is no repository, holding `files` and nothing in `drafting/`, where the project goes."""
    from loom.layout import stamp

    root = tmp_path / "quilt"
    root.mkdir(parents=True)
    stamp(root)
    (root / "config.toml").write_text(CONFIG, encoding="utf-8")
    for rel, text in (files or {}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    return root


def overleaf(tmp_path: Path, files: dict[str, str] | None = None) -> Path:
    """A bare repository on `main` standing in for an Overleaf project, its first commit the person's."""
    bare = tmp_path / "overleaf.git"
    run(tmp_path, "init", "-q", "--bare", "-b", "main", str(bare))
    seed = tmp_path / "seed"
    run(tmp_path, "init", "-q", "-b", "main", str(seed))
    for rel, text in (files or {"main.tex": SOURCE, "loom.sty": "% local support\n"}).items():
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_text(text, encoding="utf-8")
    run(seed, "add", ".")
    run(seed, "commit", "-q", "-m", "new project")
    run(seed, "push", "-q", str(bare), "main")
    return bare


def colleague(tmp_path: Path, bare: Path, name: str = "collaborator", who: tuple[str, str] = COLLEAGUE) -> Path:
    """A clone of the project that `edit` commits to as `who`."""
    clone = tmp_path / name
    run(tmp_path, "clone", "-q", str(bare), str(clone))
    run(clone, "config", "user.name", who[0])
    run(clone, "config", "user.email", who[1])
    return clone


def edit(clone: Path, message: str, files: dict[str, str], who: tuple[str, str] = COLLEAGUE) -> None:
    """Commit `files` in `clone` as `who` and push, as Overleaf records an edit made there."""
    run(clone, "pull", "-q", "--ff-only", who=who)
    for rel, text in files.items():
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(text, encoding="utf-8")
    run(clone, "add", ".", who=who)
    run(clone, "commit", "-q", "-m", message, who=who)
    run(clone, "push", "-q", "origin", "HEAD:main", who=who)


def paired(tmp_path: Path, files: dict[str, str] | None = None) -> tuple[Path, Path]:
    """A quilt mirroring a new project in `drafting/`, its main `drafting/main.tex`, the person known by their address; with the project's bare repository."""
    root = quilt_at(tmp_path)
    bare = overleaf(tmp_path, files)
    pair(load_quilt(root), str(bare), "drafting", "main.tex", [PERSON[1]])
    return root, bare


def renamed_pair(tmp_path: Path) -> tuple[Path, Path]:
    """A mirroring quilt with `zk-0001` accepted in it, and a colleague's clone of its project."""
    from loom.scan.quilt import save_author
    from tests.helpers import ok

    save_author("Tester")  # status shows the local reviewer's acceptance, and this quilt has no git user to name one
    root, bare = paired(tmp_path)
    ok("accept", "zk-0001", "--force", "--as", "Tester", cwd=root)
    return root, colleague(tmp_path, bare)
