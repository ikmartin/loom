"""What a served quilt remembers between builds names everything it is made from: after saves, notes, an acceptance and a compile, the server publishes the site a build from cold makes of the same files.

The cold build runs in a fresh process, so nothing the server's process remembers reaches it. A page's blank space may differ between two runs of TeX over one text (the queue, 44), so a page is read with each run of blank space as one, as `tests/tex/test_sweep_real.py` reads it.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from loom.history.ledger import load_history
from loom.history.steps import write_step
from loom.paths import BLOCKS, BUILD_INDEX, SITE
from loom.render import serve as serve_mod
from loom.render.serve import ServeSession
from loom.reshape.copy import plan_copy
from loom.scan.quilt import load_quilt, save_author
from loom.scan.scan import scan
from loom.section_drafts import capture_context
from tests.helpers import PATIENCE, edit, run
from tests.unit.render._serve import QuickServer, fake_bundle, post

DOC = "drafting/main.tex"
TEXT = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\begin{document}
\section{First}\label{zk-0100}
First prose.
\begin{lemma}\label{zk-0001}
First statement holds for every widget.
\end{lemma}
\begin{proof}
A first proof, by counting widgets twice.
\end{proof}
\section{Second}\label{zk-0200}
Second prose.
\begin{lemma}\label{zk-0002}
Second statement uses \ref{zk-0001}.
\end{lemma}
\begin{proof}
A second proof, by the first lemma.
\end{proof}
\end{document}
"""


def _copied(root: Path, name: str, key: str | None) -> str:
    """An agent's copy of the document, recorded as `loom draft` records it: the whole document, or the section `key` in its saved context."""
    q = load_quilt(root)
    result = scan(q)
    history = load_history(q.history_dir)
    target = f".loom/agents/copies/{name}.tex"
    plan = plan_copy(result, history, DOC, target, key) if key else plan_copy(result, history, DOC, target)
    (root / target).write_text(plan.text)
    extra = {"scope": plan.scope, "suffix": plan.suffix, "context": capture_context(result, DOC)} if key else {}
    write_step(
        history,
        "copy",
        "copy-" + name,
        plan.freeze,
        "Tester",
        {"from": DOC, "to": target, "bases": plan.bases, **extra},
        plan.source_text,
        "main.tex",
    )
    return target


def _site(root: Path) -> dict[str, bytes]:
    out = {}
    for p in sorted((root / SITE).rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            if p.name == "manifest.json":
                manifest = json.loads(data)
                manifest.pop("generated", None)
                data = json.dumps(manifest, sort_keys=True, indent=1).encode()
            elif p.suffix == ".html":
                data = re.sub(rb"\s+", b" ", data)
            out[p.relative_to(root / SITE).as_posix()] = data
    return out


def _settled(s: ServeSession) -> None:
    """Wait until the server has compiled what it was asked to and published nothing for a while."""
    deadline = time.monotonic() + 4 * PATIENCE
    while time.monotonic() < deadline:
        assert s.compiles is not None
        if s.compiles.idle(PATIENCE):
            seen = s.publications.counts()
            if s.publications.wait(seen, 1.5) == seen and s.compiles.idle(0):
                return
    raise AssertionError("the server never settled")


def test_a_server_after_saves_notes_an_acceptance_and_a_compile_publishes_what_a_cold_build_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.layout import stamp

    monkeypatch.setattr(serve_mod, "ThreadingHTTPServer", QuickServer)
    root = tmp_path / "q"
    (root / "drafting").mkdir(parents=True)
    stamp(root)
    (root / ".loom" / "agents" / "copies").mkdir(parents=True)
    (root / "config.toml").write_text('[quilt]\nname="cold"\nprefix="zk"\nmain="drafting/main.tex"\n')
    (root / DOC).write_text(TEXT)
    save_author("Tester")
    whole = _copied(root, "whole", None)
    section = _copied(root, "first", "zk-0100")
    # the first lemma as the section draft holds it, under the key the draft derived for it
    drafted = next(k for k, n in scan(load_quilt(root)).nodes.items() if n.file == section and k.startswith("zk-0001"))
    s = ServeSession(load_quilt(root), fake_bundle(tmp_path), port=0, compile_masters=True, interval=0.2)
    try:
        s.start()
        _settled(s)
        api = s.url.rstrip("/") + "/_api/"

        def note(target: str, quote: str) -> None:
            status, answer = post(
                api + "annotate", {"target": target, "message": "Which?", "quote": quote, "author": "Tester"}
            )
            assert status == 200, answer

        steps = [
            # a word in a proof
            lambda: edit(root / DOC, "by counting widgets twice", "by counting gadgets twice"),
            # a note, then the words it quotes changed, so it is drawn on the version it was written on
            lambda: note("zk-0002", "Second statement"),
            # the agent's copy of the whole document changes a result: a row to adopt
            lambda: edit(root / whole, "Second statement uses", "Second statement now uses"),
            # the section draft changes its prose, and a note is written on its own lemma
            lambda: edit(root / section, "First prose.", "First prose, drafted."),
            lambda: note(drafted, "First statement"),
            # an acceptance, then the accepted text changed: a comparison in Review
            lambda: run("accept", "zk-0001", "--as", "Tester", "--force", "--yes", cwd=root),
            lambda: edit(root / DOC, "First statement holds", "The first statement holds"),
            lambda: edit(root / DOC, "Second statement uses", "The second lemma uses"),
            # the person keeps every edit in place, so the text as kept is the file's and the note's words changed in it
            lambda: post(api + "change-keep", {"all": True, "author": "Tester"}),
        ]
        for step in steps:
            step()
            _settled(s)
    finally:
        s.stop()
    served = _site(root)
    manifest = json.loads(served["manifest.json"])
    assert [p for p in served if p.startswith("fragments/versions/")], "the note on words since changed has its version"
    adopted = [c for c in manifest["contributions"] if c.get("copy") == whole]
    assert adopted and adopted[0]["changes"], "the agent's copy offers a change"
    assert manifest["keys"]["zk-0001"]["acceptance"]["causes"], "the accepted text changed since"
    draft = next(m for m in manifest["masters"] if m["path"] == section)
    assert b'class="annotation' in served[draft["fragment"]], "the note on the draft is marked on it"
    for derived in (root / SITE, root / BLOCKS, root / BUILD_INDEX):
        shutil.rmtree(derived) if derived.is_dir() else derived.unlink(missing_ok=True)
    cold = subprocess.run(
        [sys.executable, "-m", "loom", "build"], cwd=root, capture_output=True, text=True, timeout=300
    )
    assert cold.returncode in (0, 1), cold.stdout + cold.stderr
    made = _site(root)
    assert sorted(made) == sorted(served)
    assert [rel for rel in made if made[rel] != served[rel]] == []
