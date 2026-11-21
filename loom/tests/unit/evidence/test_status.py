"""A draft's result's status from the evidence and the texts now: attested with everything it uses, changed when any of it changes, one look for each notation, and a Lean record believed only while its Lean is unchanged."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from loom.evidence import log
from loom.evidence.log import replay, write
from loom.evidence.status import files_unchanged, status
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import Blank, DraftWeb, Here, Joined
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok

PERSON = Who("person", "A. Author")
LOOM = Who("loom")
MAIN = r"""\documentclass{article}
\usepackage{amsmath}
\newtheorem{lemma}{Lemma}
\newtheorem{definition}{Definition}
\newcommand{\Zcyc}{\mathcal{Z}}
\newcommand{\bd}{\partial}
\begin{document}
\begin{definition}\label{def:connected}
A quiver is connected if its underlying graph is connected.
\end{definition}
\begin{definition}\label{def:cycle}
For a connected quiver (Definition~\ref{def:connected}), $\Zcyc = \ker \bd$.
\end{definition}
\begin{lemma}\label{lem:balanced}
Every $w \in \Zcyc$ on a tree vanishes, as in Definition~\ref{def:cycle}.
\end{lemma}
\begin{lemma}
A lemma with no label.
\end{lemma}
\end{document}
"""
#: Blocks are keyed by their place (`drafting/main.tex#lemma:1`); a test finds one by its label and file.
LEMMA = ("lem:balanced", "drafting/main.tex")


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    root = tmp_path / "q"
    ok("init", str(root), "--demo", cwd=tmp_path)
    (root / "drafting" / "main.tex").write_text(MAIN, encoding="utf-8")
    (root / "lean").mkdir()
    (root / "lean" / "Balanced.lean").write_text("theorem balanced : True := trivial\n", encoding="utf-8")
    return root


def _web(root: Path, reviewer: str | None = None) -> DraftWeb:
    return DraftWeb(scan(load_quilt(root)), reviewer=reviewer)


def _key(web: DraftWeb, at: tuple[str, str] = LEMMA) -> str:
    label, file = at
    [node] = [n for n in web.bearing.get(label, []) if n.file == file]
    return node.key


def _edit(root: Path, old: str, new: str, file: str = "drafting/main.tex") -> None:
    path = root / file
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _file_hash(root: Path, rel: str) -> str:
    return "sha256:" + hashlib.sha256((root / rel).read_bytes()).hexdigest()


def _lean(
    root: Path, web: DraftWeb, *, statement: str = "sha256:" + "1" * 64, ok_: bool = True, assumed: list | None = None
) -> log.Record:
    subject = web.subject(Here("block", _key(web)))
    assert subject is not None
    return write(
        root,
        "lean",
        LOOM,
        on=subject,
        project={
            "root": "lean",
            "toolchain": "leanprover/lean4:v4.36.0",
            "mathlib": "9d58",
            "manifest": "sha256:" + "2" * 64,
        },
        files={"lean/Balanced.lean": _file_hash(root, "lean/Balanced.lean")},
        declarations=[
            {
                "name": "balanced",
                "kind": "theorem",
                "role": "states",
                "names": {"label": "lem:balanced"},
                "statement": statement,
                "axioms": ["propext"],
                "sorry": False,
            }
        ],
        assumed=assumed or [],
        uses=[],
        replay={"tool": "leanchecker", "exit": 0, "output": ""},
        ok=ok_,
    )


def _attest(root: Path, web: DraftWeb, lean: log.Record, here: tuple[str, str] = LEMMA) -> None:
    """What the attest act will write: the result, its closure as it reads now, and each notation row not yet attested."""
    at = Here("block", _key(web, here))
    subject = web.subject(at)
    assert subject is not None
    closure = [{k[0]: k[1], "hash": h} for k, h in sorted(web.closure(at).items())]
    write(
        root,
        "attested",
        PERSON,
        on=subject,
        lean=lean.id,
        statements={"balanced": lean.get("declarations")[0]["statement"]},
        closure=closure,
        rulings=[],
    )
    done = {r.on.key: r.on.hash for r in replay(root).of_kind("attested") if r.on and r.on.kind == "macro"}
    for name, digest in web.notation(at).items():
        if done.get(("macro", name)) != digest:
            write(root, "attested", PERSON, on=Subject("macro", name, digest))


def _status(root: Path, here: tuple[str, str] = LEMMA, reviewer: str | None = None):  # type: ignore[no-untyped-def]
    web = _web(root, reviewer)
    return status(replay(root), web, Here("block", _key(web, here)), lean_now=files_unchanged(root))


def test_a_result_is_named_by_its_label_and_a_block_with_none_has_no_lasting_name(root: Path) -> None:
    web = _web(root)
    subject = web.subject(Here("block", _key(web)))
    assert subject is not None and subject.key == ("label", "lem:balanced")
    unlabelled = [n.key for n in web.blocks if not n.labels]
    assert len(unlabelled) == 1 and web.subject(Here("block", unlabelled[0])) is None
    assert status(replay(root), web, Here("block", unlabelled[0]), lean_now=files_unchanged(root)).subject is None


def test_the_closure_is_what_the_statement_uses_in_turn_and_the_notation_its_own_commands(root: Path) -> None:
    web = _web(root)
    here = Here("block", _key(web))
    assert set(web.closure(here)) == {("label", "def:cycle"), ("label", "def:connected")}
    assert set(web.notation(here)) == {"Zcyc", "bd"}
    assert web.closure(Here("block", _key(web, ("def:connected", "drafting/main.tex")))) == {}


def test_nothing_done_reads_none_and_a_lean_record_reads_unattested(root: Path) -> None:
    assert _status(root).lean == "none"
    _lean(root, _web(root))
    found = _status(root)
    assert found.lean == "unattested" and found.role == "proved"
    assert set(found.unattested_notation) == {"Zcyc", "bd"}


def test_attested_with_its_closure_and_notation_reads_formalized(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    found = _status(root)
    assert found.lean == "formalized" and found.causes == () and found.unattested_notation == ()


def test_a_definition_under_it_changed_reads_changed_and_names_it(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    _edit(
        root,
        "if its underlying graph is connected.",
        "if its underlying graph is connected after its loops are removed.",
    )
    found = _status(root)
    assert found.lean == "changed"
    assert [c.key for c in found.causes] == [("label", "def:connected")]


def test_its_own_text_changed_reads_changed(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    found = _status(root)
    assert found.lean == "changed" and found.causes[0].key == ("label", "lem:balanced")


def test_a_result_whose_definition_changed_holds_again_once_attested_on_the_text_now(root: Path) -> None:
    web = _web(root)
    lean = _lean(root, web)
    _attest(root, web, lean)
    _edit(
        root,
        "if its underlying graph is connected.",
        "if its underlying graph is connected after its loops are removed.",
    )
    web = _web(root)
    assert _status(root).lean == "changed"
    _attest(root, web, lean)  # "still states it", on the text now
    found = _status(root)
    # the Lean record is on the lemma's text, which did not change, so it still stands
    assert found.lean == "formalized"


def test_a_notation_changed_is_one_look_for_every_result_that_uses_it(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    _edit(root, r"\newcommand{\Zcyc}{\mathcal{Z}}", r"\newcommand{\Zcyc}{\mathcal{Z}_1}")
    found = _status(root)
    assert found.lean == "changed" and [c.key for c in found.causes] == [("macro", "Zcyc")]
    web = _web(root)
    write(root, "attested", PERSON, on=Subject("macro", "Zcyc", web.notation(Here("block", _key(web)))["Zcyc"]))
    assert _status(root).lean == "formalized"


def test_a_comment_in_a_macro_or_on_a_line_of_its_own_changes_nothing(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    _edit(root, r"\newcommand{\bd}{\partial}", r"\newcommand{\bd}{\partial} % the boundary")
    _edit(root, "A quiver is connected", "% a note on its own line\nA quiver is connected")
    assert _status(root).lean == "formalized"


def test_a_lean_file_changed_is_run_again_and_never_reads_formalized(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    (root / "lean" / "Balanced.lean").write_text("theorem balanced : False := sorry\n", encoding="utf-8")
    assert _status(root).lean == "rerun"


def test_the_lean_restated_is_to_attest_and_a_failed_check_reads_failed(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    _lean(root, web, statement="sha256:" + "3" * 64)
    assert _status(root).lean == "unattested"
    _lean(root, web, statement="sha256:" + "3" * 64, ok_=False)
    assert _status(root).lean == "failed"


def test_a_text_changed_since_loom_ran_lean_waits_for_loom_once_reattested(root: Path) -> None:
    web = _web(root)
    lean = _lean(root, web)
    _attest(root, web, lean)
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    _attest(root, _web(root), lean)  # the person says the Lean still states it
    assert _status(root).lean == "rerun"
    _lean(root, _web(root))  # loom runs it again on the text now
    assert _status(root).lean == "formalized"


def test_a_label_renamed_under_it_is_a_cause_with_nothing_now(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    _edit(root, r"\label{def:connected}", r"\label{def:conn}")
    found = _status(root)
    assert found.lean == "changed" and any(c.key == ("label", "def:connected") and c.now is None for c in found.causes)


def test_a_draft_copied_keeps_what_was_said_and_a_copy_changed_does_not(root: Path) -> None:
    web = _web(root)
    _attest(root, web, _lean(root, web))
    (root / "drafting" / "copy.tex").write_text(MAIN, encoding="utf-8")
    copy = ("lem:balanced", "drafting/copy.tex")
    assert _status(root, copy).lean == "formalized"
    _edit(root, "on a tree vanishes", "on a forest vanishes", file="drafting/copy.tex")
    assert _status(root, copy).lean == "changed"
    assert _status(root).lean == "formalized"


def test_acceptance_is_read_from_the_ledger(root: Path) -> None:
    from loom.cli.review import write_acceptance

    write_acceptance(scan(load_quilt(root)), [_key(_web(root))], "A. Author")
    assert _status(root, reviewer="A. Author").accepted == "fresh"
    assert _status(root, reviewer="Someone else").accepted is None
    _edit(root, "on a tree vanishes", "on a forest vanishes")
    assert _status(root, reviewer="A. Author").accepted == "changed"


class _Library:
    """A web of one node, its text and whether its body is empty, as the node store will answer."""

    def __init__(self, digest: str, *, stub: bool = False) -> None:
        self.digest, self.is_stub = digest, stub

    def subject(self, here: Here) -> Subject | None:
        return Subject("node", here.name, self.digest) if here.kind == "node" else None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return None

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        return {}

    def notation(self, here: Here) -> dict[str, str]:
        return {}

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        return self.is_stub

    def holds(self, ref: str, want: str) -> bool | None:
        return None


H1 = "sha256:" + "1" * 64
H2 = "sha256:" + "2" * 64
PAPER = {"ref": "tq-00A1-ref", "pdf": "sha256:" + "9" * 64, "pages": "12"}
NODE_HERE = Here("node", "tq-00K3")


def _node_status(root: Path, digest: str, stub: bool = False):  # type: ignore[no-untyped-def]
    return status(replay(root), _Library(digest, stub=stub), NODE_HERE, lean_now=files_unchanged(root))


def test_a_node_reads_unchecked_until_a_person_compares_this_very_text(tmp_path: Path) -> None:
    on = Subject("node", "tq-00K3", H1)
    write(tmp_path, "digested", LOOM, on=on, how="extracted", **{"from": {"ref": "tq-00A1-ref", "tex": H2}})
    found = _node_status(tmp_path, H1)
    assert (found.reading, found.how, found.compared_before) == ("unchecked", "extracted", False)
    write(tmp_path, "compared", PERSON, on=on, **{"with": PAPER})
    assert _node_status(tmp_path, H1).reading == "matches"
    changed = _node_status(tmp_path, H2)
    assert (changed.reading, changed.compared_before, changed.how) == ("unchecked", True, None)


def test_a_stub_reads_as_one_and_says_when_its_source_lacked_it(tmp_path: Path) -> None:
    write(
        tmp_path,
        "sought",
        LOOM,
        on=Subject("node", "tq-00K3", H1),
        found=False,
        **{"from": {"ref": "tq-00A1-ref", "tex": H2}},
    )
    found = _node_status(tmp_path, H1, stub=True)
    assert found.reading == "stub" and found.sought


def test_an_open_correction_is_on_the_text_it_corrects_until_declined(tmp_path: Path) -> None:
    on = Subject("node", "tq-00K3", H1)
    made = write(
        tmp_path, "proposed", Who("agent", "Claude Code Agent"), on=on, bytes="+++\nschema = 1\n+++\n", why="page 12"
    )
    assert _node_status(tmp_path, H1).proposal == made.id
    assert _node_status(tmp_path, H2).proposal is None
    write(tmp_path, "declined", PERSON, proposal=made.id, why="")
    assert _node_status(tmp_path, H1).proposal is None


# ---- the gate: nothing reads formalized while a library result under it is unread, unchecked or, assumed, unattested


class _Nodes(Blank):
    """A library of a few nodes, each with its text's hash and whether its body is empty, as the node store will answer."""

    def __init__(self, nodes: dict[str, tuple[str, bool]]) -> None:
        self.nodes = nodes

    def subject(self, here: Here) -> Subject | None:
        held = self.nodes.get(here.name) if here.kind == "node" else None
        return Subject("node", here.name, held[0]) if held else None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        held = self.nodes.get(key[1]) if key[0] == "node" else None
        return held[0] if held else None

    def stub(self, here: Here) -> bool | None:
        held = self.nodes.get(here.name) if here.kind == "node" else None
        return held[1] if held else None


def _attest_over(root: Path, draft: DraftWeb, lean: log.Record, nodes: list[str]) -> None:
    """An attestation whatever wrote it, its closure the lemma's and these library nodes at the hashes the library gives now: the gate must hold against any record."""
    at = Here("block", _key(draft))
    subject = draft.subject(at)
    assert subject is not None
    closure = [{k[0]: k[1], "hash": h} for k, h in sorted(draft.closure(at).items())]
    closure += [{"node": n, "hash": H1} for n in nodes]
    write(
        root,
        "attested",
        PERSON,
        on=subject,
        lean=lean.id,
        statements={"balanced": lean.get("declarations")[0]["statement"]},
        closure=closure,
        rulings=[],
    )
    for name, digest in draft.notation(at).items():
        write(root, "attested", PERSON, on=Subject("macro", name, digest))


def _gated(root: Path, library: Blank):  # type: ignore[no-untyped-def]
    draft = _web(root)
    return status(replay(root), Joined(draft, library), Here("block", _key(draft)), lean_now=files_unchanged(root))


@pytest.mark.parametrize(("stub", "why"), [(True, "stub"), (False, "unchecked")])
def test_a_library_result_it_uses_unread_or_unchecked_keeps_it_from_reading_formalized(
    root: Path, stub: bool, why: str
) -> None:
    draft = _web(root)
    _attest_over(root, draft, _lean(root, draft), ["tq-00B7"])
    found = _gated(root, _Nodes({"tq-00B7": (H1, stub)}))
    assert found.lean == "waiting" and [(w.key, w.why) for w in found.waiting_on] == [(("node", "tq-00B7"), why)]
    if not stub:
        write(root, "compared", PERSON, on=Subject("node", "tq-00B7", H1), **{"with": PAPER})
        assert _gated(root, _Nodes({"tq-00B7": (H1, False)})).lean == "formalized"


def test_a_library_result_nothing_can_say_of_keeps_it_from_reading_formalized(root: Path) -> None:
    """Before the node store, no web answers for a node: one under an attestation is a cause with nothing now, and one assumed in Lean waits."""
    draft = _web(root)
    _attest_over(root, draft, _lean(root, draft), ["tq-00B7"])
    for web in (Joined(draft, Blank()), draft):
        found = status(replay(root), web, Here("block", _key(draft)), lean_now=files_unchanged(root))
        assert found.lean == "changed" and [(c.key, c.now) for c in found.causes] == [(("node", "tq-00B7"), None)]
    assumed = Subject("node", "tq-00B8", H1)
    _attest_over(root, draft, _lean(root, draft, assumed=[assumed.to_dict()]), [])
    found = _gated(root, Blank())
    assert found.lean == "waiting" and [(w.key, w.why) for w in found.waiting_on] == [(("node", "tq-00B8"), "unknown")]


def test_a_result_assumed_in_lean_must_be_compared_and_its_own_lean_attested(root: Path) -> None:
    draft = _web(root)
    library = _Nodes({"tq-00B8": (H1, False)})
    node = Subject("node", "tq-00B8", H1)
    _attest_over(root, draft, _lean(root, draft, assumed=[node.to_dict()]), [])
    assert [(w.why) for w in _gated(root, library).waiting_on] == ["unchecked"]
    write(root, "compared", PERSON, on=node, **{"with": PAPER})
    found = _gated(root, library)
    assert found.lean == "waiting" and [w.why for w in found.waiting_on] == ["unattested"]
    axiom = write(
        root,
        "lean",
        LOOM,
        on=node,
        project={"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": "sha256:" + "2" * 64},
        files={"lean/Balanced.lean": _file_hash(root, "lean/Balanced.lean")},
        declarations=[
            {
                "name": "B8",
                "kind": "axiom",
                "role": "states",
                "names": {"node": "tq-00B8"},
                "statement": H2,
                "axioms": [],
                "sorry": False,
            }
        ],
        assumed=[],
        uses=[],
        replay={"tool": "leanchecker", "exit": 0, "output": ""},
        ok=True,
    )
    write(root, "attested", PERSON, on=node, lean=axiom.id, statements={"B8": H2}, closure=[], rulings=[])
    found = _gated(root, library)
    assert found.lean == "formalized" and found.relative_to == (node.key,)


def test_before_attesting_what_waits_is_said_beside_unattested(root: Path) -> None:
    draft = _web(root)
    _lean(root, draft, assumed=[{"node": "tq-00B8", "hash": H1}])
    found = _gated(root, _Nodes({"tq-00B8": (H1, True)}))
    assert found.lean == "unattested" and [w.why for w in found.waiting_on] == ["stub"]
