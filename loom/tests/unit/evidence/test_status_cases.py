"""A draft's result attested as the act will attest it, then one change: a change that can alter what it means takes it off `formalized`, one that cannot leaves it there."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from loom.evidence.log import replay, write
from loom.evidence.status import files_unchanged, status
from loom.evidence.subjects import Subject, Who
from loom.evidence.web import DraftWeb, Here
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import ok, templated

PERSON = Who("person", "A. Author")
LOOM = Who("loom")
M, B = "drafting/main.tex", "drafting/b.tex"
PRE = r"""\documentclass{article}
\usepackage{amsmath}
\newtheorem{lemma}{Lemma}
\newtheorem{theorem}{Theorem}
\newtheorem{definition}{Definition}
%s
\begin{document}
%s
\end{document}
"""


def doc(macros: str, body: str) -> str:
    return PRE % (macros, body)


def h(c: str) -> str:
    return "sha256:" + c * 64


def _template(d: Path) -> None:
    ok("init", str(d / "q"), "--demo", cwd=d)
    (d / "q" / "drafting" / "outline.tex").unlink()
    (d / "q" / "lean").mkdir()
    (d / "q" / "lean" / "R.lean").write_text("theorem r : True := trivial\n", encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("LOOM_FIXED_TIME", "2026-11-21T10:00:00Z")
    templated("evidence-cases", tmp_path, _template)
    return tmp_path / "q"


def put(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")


def web(root: Path) -> DraftWeb:
    return DraftWeb(scan(load_quilt(root)))


def here_of(w: DraftWeb, label: str, file: str | None = None) -> Here:
    [node] = [n for n in w.bearing.get(label, []) if file is None or n.file == file][:1]
    return Here("block", node.key)


def lean(root: Path, on: Subject, **kw: object) -> object:
    """A `lean` record on `on` as loom will write one; `kw` overrides a declaration's fields or the record's."""
    decl = {
        "name": "r",
        "kind": "theorem",
        "role": "states",
        "names": {on.kind: on.name},
        "statement": kw.pop("statement", h("1")),
        "axioms": kw.pop("axioms", []),
        "sorry": kw.pop("sorry", False),
    }
    decl.update(kw.pop("decl", {}))  # type: ignore[call-overload]
    fields = {
        "project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")},
        "files": {"lean/R.lean": "sha256:" + hashlib.sha256((root / "lean/R.lean").read_bytes()).hexdigest()},
        "declarations": [decl],
        "assumed": [],
        "uses": [],
        "replay": {"tool": "leanchecker", "exit": 0, "output": ""},
        "ok": True,
    }
    fields.update(kw)
    return write(root, "lean", LOOM, on=on, **fields)


def lean_and_attest(root: Path, label: str, file: str | None = None, *, statement: str = "1") -> None:
    """Lean on the text now, then the person's attestation of it with the closure as it reads now and each notation row."""
    w = web(root)
    here = here_of(w, label, file)
    subject = w.subject(here)
    assert subject is not None
    record = lean(root, subject, statement=h(statement))
    closure = [{k[0]: k[1], "hash": v} for k, v in sorted(w.closure(here).items())]
    write(
        root,
        "attested",
        PERSON,
        on=subject,
        lean=record.id,  # type: ignore[attr-defined]
        statements={"r": h(statement)},
        closure=closure,
        rulings=[],
    )
    for name, digest in w.notation(here).items():
        write(root, "attested", PERSON, on=Subject("macro", name, digest))


def lean_of(root: Path, label: str, file: str | None = None) -> str:
    w = web(root)
    return status(replay(root), w, here_of(w, label, file), lean_now=files_unchanged(root)).lean


DEF_W = r"""\begin{definition}\label{def:w}
A widget is a set $W$ with
\begin{equation}\label{eq:w}
x^2 = 1 \quad\text{for all } x \in W.
\end{equation}
\end{definition}
"""
R_EQ = "\\begin{lemma}\\label{lem:r}\nEvery $W$ satisfying \\eqref{eq:w} is finite.\n\\end{lemma}\n"
SHARED = r"\begin{lemma}\label{lem:r}Every $x \in \K$ is bounded.\end{lemma}" + "\n"
K_LEMMA = r"\begin{lemma}\label{lem:r}Every $x \in \K$ is bounded.\end{lemma}"
DEF_X = r"\begin{definition}\label{def:X}A widget is compact.\end{definition}" + "\n"
R_X = r"\begin{lemma}\label{lem:r}Every widget (Definition~\ref{def:x}) is bounded.\end{lemma}" + "\n"
TWO_DOWN = (
    r"\begin{definition}\label{def:a}A gadget is open.\end{definition}"
    + "\n"
    + r"\begin{definition}\label{def:b}A widget is a gadget (\ref{def:a}).\end{definition}"
    + "\n"
    + r"\begin{lemma}\label{lem:r}Every widget (\ref{def:b}) is bounded.\end{lemma}"
)
CYCLE = (
    r"\begin{definition}\label{def:a}An A is a B (\ref{def:b}).\end{definition}"
    + "\n"
    + r"\begin{definition}\label{def:b}A B is an A (\ref{def:a}) that is open.\end{definition}"
    + "\n"
    + r"\begin{lemma}\label{lem:r}Every A (\ref{def:a}) is bounded.\end{lemma}"
)
USES = (
    r"\begin{definition}\label{def:a}A gadget is open.\end{definition}"
    + "\n"
    + r"\begin{lemma}\label{lem:r}\uses{def:a}Every gadget is bounded.\end{lemma}"
)
ENV = r"\newenvironment{cond}{\begin{itemize}\item[(i)] $x>0$}{\end{itemize}}"
ENV_LEMMA = r"\begin{lemma}\label{lem:r}If \begin{cond}\item $y>0$\end{cond} then $xy>0$.\end{lemma}"
NESTED = (
    r"\begin{theorem}\label{thm:r}Suppose \begin{lemma}every $x$ is real.\end{lemma} Then $x^2 \ge 0$.\end{theorem}"
)
LINE_END = "\\begin{lemma}\\label{lem:r}\nEvery widget is finite. % first note\n\\end{lemma}"
ONLY_COMMENT = "\\begin{lemma}\\label{lem:r}\n% first note\nEvery widget is finite.\n\\end{lemma}"
COMMENTED_MACRO = "\\newcommand{\\K}{\\mathbb{R}% the reals\n}"

#: (what changes, the files before, the result's label and file, the files after, whether the change can alter what it means)
CASES = [
    ("a display the statement refers to", {M: doc("", DEF_W + R_EQ)}, ("lem:r", M), {M: doc("", DEF_W.replace("x^2 = 1", "x^3 = 1") + R_EQ)}, True),
    ("the definition around that display", {M: doc("", DEF_W + R_EQ)}, ("lem:r", M), {M: doc("", DEF_W.replace("a set $W$", "a finite group $W$") + R_EQ)}, True),
    ("a macro a used macro is built from", {M: doc(r"\newcommand{\B}{\mathbb{R}}" + "\n" + r"\newcommand{\A}{\B^n}", r"\begin{lemma}\label{lem:r}Every $x \in \A$ is bounded.\end{lemma}")}, ("lem:r", M), {M: doc(r"\newcommand{\B}{\mathbb{C}}" + "\n" + r"\newcommand{\A}{\B^n}", r"\begin{lemma}\label{lem:r}Every $x \in \A$ is bounded.\end{lemma}")}, True),
    ("the second of two documents' definitions of a shared file's macro", {M: doc(r"\newcommand{\K}{\mathbb{R}}", r"\input{shared}"), B: doc(r"\newcommand{\K}{\mathbb{Q}}", r"\input{shared}"), "drafting/shared.tex": SHARED}, ("lem:r", None), {B: doc(r"\newcommand{\K}{\mathbb{C}}", r"\input{shared}")}, True),
    ("the first of two documents' definitions of a shared file's macro", {M: doc(r"\newcommand{\K}{\mathbb{R}}", r"\input{shared}"), B: doc(r"\newcommand{\K}{\mathbb{Q}}", r"\input{shared}"), "drafting/shared.tex": SHARED}, ("lem:r", None), {M: doc(r"\newcommand{\K}{\mathbb{C}}", r"\input{shared}")}, True),
    ("a statement's words put in by \\input", {M: doc("", "\\begin{lemma}\\label{lem:r}\n\\input{body}\n\\end{lemma}"), "drafting/body.tex": "Every widget is finite.\n"}, ("lem:r", M), {"drafting/body.tex": "Every widget is infinite.\n"}, True),
    ("a comment at a line's end", {M: doc("", LINE_END)}, ("lem:r", M), {M: doc("", LINE_END.replace("first note", "second note"))}, False),
    ("a line that is only a comment", {M: doc("", ONLY_COMMENT)}, ("lem:r", M), {M: doc("", ONLY_COMMENT.replace("first note", "second note, longer"))}, False),
    ("a comment inside a used macro's definition", {M: doc(COMMENTED_MACRO, K_LEMMA)}, ("lem:r", M), {M: doc(COMMENTED_MACRO.replace("the reals", "the real numbers"), K_LEMMA)}, False),
    ("the spaces of a statement and a macro's body", {M: doc(r"\newcommand{\K}{\mathbb{R}}", K_LEMMA)}, ("lem:r", M), {M: doc(r"\newcommand{\K}{ \mathbb{R} }", K_LEMMA.replace("Every $x", "Every\n   $x"))}, False),
    ("a reference that named nothing when attested, put right", {M: doc("", DEF_X + R_X)}, ("lem:r", M), {M: doc("", DEF_X.replace("def:X", "def:x").replace("compact", "closed") + R_X)}, True),
    ("a definition two steps down", {M: doc("", TWO_DOWN)}, ("lem:r", M), {M: doc("", TWO_DOWN.replace("is open", "is closed"))}, True),
    ("one member of a cycle of uses", {M: doc("", CYCLE)}, ("lem:r", M), {M: doc("", CYCLE.replace("that is open", "that is closed"))}, True),
    ("the target of a \\uses", {M: doc("", USES)}, ("lem:r", M), {M: doc("", USES.replace("is open", "is closed"))}, True),
    ("a macro defined in the document's body", {M: doc("", r"\newcommand{\K}{\mathbb{R}}" + "\n" + K_LEMMA)}, ("lem:r", M), {M: doc("", r"\newcommand{\K}{\mathbb{C}}" + "\n" + K_LEMMA)}, True),
    ("a macro of a local package", {M: doc(r"\usepackage{mine}", K_LEMMA), "drafting/mine.sty": r"\newcommand{\K}{\mathbb{R}}" + "\n"}, ("lem:r", M), {"drafting/mine.sty": r"\newcommand{\K}{\mathbb{C}}" + "\n"}, True),
    ("an environment the person defined", {M: doc(ENV, ENV_LEMMA)}, ("lem:r", M), {M: doc(ENV.replace("x>0", "x<0"), ENV_LEMMA)}, True),
    ("a result nested in the statement", {M: doc("", NESTED)}, ("thm:r", M), {M: doc("", NESTED.replace("is real", "is complex"))}, True),
]  # fmt: skip


@pytest.mark.parametrize(("what", "before", "at", "after", "alters"), CASES, ids=[c[0] for c in CASES])
def test_a_change_takes_a_result_off_formalized_exactly_when_it_can_alter_its_meaning(
    root: Path, what: str, before: dict[str, str], at: tuple[str, str | None], after: dict[str, str], alters: bool
) -> None:
    put(root, before)
    lean_and_attest(root, *at)
    assert lean_of(root, *at) == "formalized"
    put(root, after)
    assert (lean_of(root, *at) != "formalized") is alters


def test_a_statement_citing_one_result_of_a_work_waits_until_the_library_can_answer_for_it(root: Path) -> None:
    put(
        root,
        {
            M: doc(
                "", r"\begin{lemma}\label{lem:r}By \cite[Theorem 2.1]{Calloway14}, every widget is finite.\end{lemma}"
            )
        },
    )
    lean_and_attest(root, "lem:r", M)
    w = web(root)
    s = status(replay(root), w, here_of(w, "lem:r", M), lean_now=files_unchanged(root))
    assert s.lean == "waiting" and [(x.key, x.why) for x in s.waiting_on] == [
        (("cite", "Calloway14 Theorem 2.1"), "unknown")
    ]


@pytest.mark.parametrize("order", [(M, B), (B, M)])
def test_one_label_on_two_texts_stands_formalized_on_each_attested_whatever_the_order(
    root: Path, order: tuple[str, str]
) -> None:
    lemma = r"\begin{lemma}\label{lem:r}%s\end{lemma}"
    put(root, {M: doc("", lemma % "Every widget is finite."), B: doc("", lemma % "Every widget is countable.")})
    for file in order:
        lean_and_attest(root, "lem:r", file, statement="3" if file == M else "4")
    assert lean_of(root, "lem:r", M) == lean_of(root, "lem:r", B) == "formalized"


def test_a_copied_draft_keeps_what_was_said_until_the_copy_is_changed(root: Path) -> None:
    lemma = r"\begin{lemma}\label{lem:r}%s\end{lemma}"
    put(root, {M: doc("", lemma % "Every widget is finite.")})
    lean_and_attest(root, "lem:r", M)
    put(root, {B: doc("", lemma % "Every widget is finite.")})
    assert lean_of(root, "lem:r", M) == lean_of(root, "lem:r", B) == "formalized"
    put(root, {B: doc("", lemma % "Every widget is countable.")})
    assert lean_of(root, "lem:r", M) == "formalized" and lean_of(root, "lem:r", B) == "changed"


TWO_LEMMAS = r"\begin{lemma}\label{lem:r}Every widget is finite.\end{lemma}"


@pytest.mark.parametrize(
    ("record", "reads"),
    [
        ({"sorry": True, "axioms": ["sorryAx"]}, "failed"),
        ({"axioms": ["Widget.finite_ax"]}, "failed"),
        ({"replay": {"tool": "leanchecker", "exit": 1, "output": "kernel rejected"}}, "failed"),
        ({"decl": {"names": {"label": "lem:other"}}}, "none"),
    ],
    ids=["a sorry", "an axiom it does not account for", "the kernel's replay failed", "it states another result"],
)
def test_lean_that_does_not_prove_the_result_never_reads_formalized(root: Path, record: dict, reads: str) -> None:
    put(root, {M: doc("", TWO_LEMMAS)})
    w = web(root)
    subject = w.subject(here_of(w, "lem:r", M))
    assert subject is not None
    made = lean(root, subject, **record)
    write(root, "attested", PERSON, on=subject, lean=made.id, statements={"r": h("1")}, closure=[], rulings=[])  # type: ignore[attr-defined]
    assert lean_of(root, "lem:r", M) == reads


def test_an_axiom_the_record_itself_states_for_a_library_result_keeps_it_proved(root: Path) -> None:
    put(root, {M: doc("", TWO_LEMMAS)})
    w = web(root)
    subject = w.subject(here_of(w, "lem:r", M))
    assert subject is not None
    stating = {"name": "r", "kind": "theorem", "role": "states", "names": {"label": "lem:r"}, "statement": h("1"), "axioms": ["lib_ax", "propext"], "sorry": False}  # fmt: skip
    assumed = {"name": "lib_ax", "kind": "axiom", "role": "states", "names": {"node": "tq-00B2"}, "statement": h("5"), "axioms": [], "sorry": False}  # fmt: skip
    made = lean(root, subject, declarations=[stating, assumed], assumed=[{"node": "tq-00B2", "hash": h("b")}])
    write(
        root,
        "attested",
        PERSON,
        on=subject,
        lean=made.id,
        statements={"r": h("1"), "lib_ax": h("5")},
        closure=[],
        rulings=[],
    )  # type: ignore[attr-defined]
    # not failed: the library result it assumes waits, as one no web can say of yet
    assert lean_of(root, "lem:r", M) == "waiting"


def test_a_later_lean_record_using_more_brings_what_it_uses_into_the_closure(root: Path) -> None:
    put(root, {M: doc("", r"\begin{definition}\label{def:x}A gadget is open.\end{definition}" + "\n" + TWO_LEMMAS)})
    w = web(root)
    subject, dx = w.subject(here_of(w, "lem:r", M)), w.subject(here_of(w, "def:x", M))
    assert subject is not None and dx is not None
    first = lean(root, subject)
    write(root, "attested", PERSON, on=subject, lean=first.id, statements={"r": h("1")}, closure=[], rulings=[])  # type: ignore[attr-defined]
    assert lean_of(root, "lem:r", M) == "formalized"
    lean(root, subject, uses=[dx.to_dict()])  # loom ran again: the same statement, now resting on def:x
    assert lean_of(root, "lem:r", M) == "changed"


def test_a_repeated_older_line_does_not_move_which_record_is_latest(root: Path) -> None:
    put(root, {M: doc("", TWO_LEMMAS)})
    lean_and_attest(root, "lem:r", M)
    w = web(root)
    subject = w.subject(here_of(w, "lem:r", M))
    assert subject is not None
    lean(root, subject, statement=h("5"))  # loom ran again; a statement the person has not attested
    assert lean_of(root, "lem:r", M) == "unattested"
    path = root / ".loom/records/evidence/log.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = next(line for line in lines if '"kind":"lean"' in line)
    path.write_text("\n".join([*lines, first]) + "\n", encoding="utf-8")
    assert lean_of(root, "lem:r", M) == "unattested"


class Library:
    """Two library nodes with bodies: tq-00A1 uses tq-00B2."""

    texts = {"tq-00A1": h("a"), "tq-00B2": h("b")}

    def subject(self, here: Here) -> Subject | None:
        return Subject("node", here.name, self.texts[here.name]) if here.name in self.texts else None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return self.texts.get(key[1]) if key[0] == "node" else None

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        return {("node", "tq-00B2"): self.texts["tq-00B2"]} if here.name == "tq-00A1" else {}

    def notation(self, here: Here) -> dict[str, str]:
        return {}

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        return False if here.kind == "node" else None

    def holds(self, ref: str, want: str) -> bool | None:
        return None


def test_an_attestation_that_leaves_out_a_member_of_the_closure_now_does_not_hold(root: Path) -> None:
    a = Subject("node", "tq-00A1", h("a"))
    write(root, "compared", PERSON, on=a, **{"with": {"ref": "tq-00A1-ref", "pdf": h("9")}})
    record = lean(root, a)
    write(root, "attested", PERSON, on=a, lean=record.id, statements={"r": h("1")}, closure=[], rulings=[])  # type: ignore[attr-defined]
    s = status(replay(root), Library(), Here("node", "tq-00A1"), lean_now=files_unchanged(root))
    assert s.lean == "changed" and [(c.key, c.then) for c in s.causes] == [(("node", "tq-00B2"), None)]
