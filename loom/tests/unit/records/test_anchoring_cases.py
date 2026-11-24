"""Where a record goes when blocks compete for it (`records.locate.follow`): the independent review's smallest cases (`safe-anchoring-review.md`, A-2 to A-8 and A-12), each a tiny quilt changed once. A record goes to a block other than its own key's only when nothing else could be meant; otherwise it is on none."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

from loom import layout

PRE = "\\documentclass{article}\n\\usepackage{amsthm}\n\\newtheorem{lemma}{Lemma}\n\\newtheorem{proposition}{Proposition}\n\\newtheorem{theorem}{Theorem}\n\\newtheorem{remark}{Remark}\n\\begin{document}\n%s\\end{document}\n"


def env(name: str, body: str, label: str = "") -> str:
    lab = f"\\label{{{label}}}" if label else ""
    return f"\\begin{{{name}}}{lab}\n{body}\n\\end{{{name}}}\n\n"


def proof(body: str = "") -> str:
    return "\\begin{proof}\n" + (body + "\n" if body else "") + "\\end{proof}\n\n"


def sec(title: str, body: str, label: str = "") -> str:
    lab = f"\\label{{{label}}}" if label else ""
    return f"\\section{{{title}}}{lab}\n{body}\n\n"


def main_with(*inputs: str) -> str:
    return PRE % "".join(f"\\input{{{i}}}\n" for i in inputs)


@pytest.fixture
def out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for m in ("AI_AGENT", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SANDBOX", "CURSOR_AGENT", "GEMINI_CLI"):
        monkeypatch.delenv(m, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    root = tmp_path / "q"
    (root / ".loom").mkdir(parents=True)
    (root / ".loom" / "format").write_text(f"{layout.NUMBER}\n")
    (root / "config.toml").write_text('[quilt]\nname = "t"\nmain = "drafting/main.tex"\nprefix = "tq"\n')
    return root


def write(out: Path, files: dict[str, str]) -> None:
    """Make the quilt's `.tex` files exactly `files`: any other under `drafting/` goes."""
    for p in list((out / "drafting").rglob("*.tex")) if (out / "drafting").exists() else []:
        if str(p.relative_to(out)) not in files:
            p.unlink()
    for p, t in files.items():
        (out / p).parent.mkdir(parents=True, exist_ok=True)
        (out / p).write_text(t)


def scanned(out: Path):  # type: ignore[no-untyped-def]
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    return scan(load_quilt(out))


def note(out: Path, key: str, body: str, quote: str | None = None) -> str:
    from loom.cli.review import _one_comment

    return _one_comment(scanned(out), ("human", "Tester"), key, body, quote, None, None, None).split()[0]


def suggest(out: Path, monkeypatch: pytest.MonkeyPatch, key: str, with_text: str, quote: str | None = None) -> str:
    import loom.cli.suggest as S
    from loom.records import edits as E

    r = scanned(out)
    monkeypatch.setattr(S, "open_scan", lambda q: r)
    before = {e.id for e in E.replay(out)[0]}
    with contextlib.redirect_stdout(io.StringIO()):
        S.suggest_command.callback(  # type: ignore[misc]
            key=key,
            with_text=with_text,
            quote=quote,
            before=False,
            after=False,
            answers=None,
            comment=None,
            author="Agent Tester",
            withdraw=None,
            why=None,
            dry_run=False,
            as_json=True,
            quilt_path=str(out),
        )
    return next(e.id for e in E.replay(out)[0] if e.id not in before)


def text_of(out: Path, key: str | None) -> str | None:
    """The text of the block `key` names now; None for none."""
    if not key:
        return None
    r = scanned(out)
    n = r.nodes.get(key)
    if n is None and key in r.assembly.regions:
        n = r.nodes.get(r.assembly.regions[key].container)
    return None if n is None else (out / n.file).read_text()[n.start : n.end]


def shown(out: Path, ann: str) -> str | None:
    """The text of the block an annotation is shown on, attached; None when it is detached."""
    from loom.records.store import Records

    res = next(x for x in Records(out).resolved(scanned(out)) if x.annotation.id == ann)
    return None if res.detached else text_of(out, res.target)


def detached_on(out: Path, ann: str) -> str | None:
    """The text of the block a detached annotation still names: none, since a detached record names no block."""
    from loom.records.store import Records

    res = next(x for x in Records(out).resolved(scanned(out)) if x.annotation.id == ann)
    assert res.detached
    return text_of(out, res.target) if res.target else None


def keeps_into(out: Path, eid: str) -> str | None:
    """The text of the block Keep would write an edit into; None when it is unplaced."""
    from loom.records import edits as E

    e = next(x for x in E.replay(out)[0] if x.id == eid)
    try:
        return text_of(out, E.place(scanned(out), e).key)
    except E.Unplaced:
        return None


def test_a_deleted_statements_empty_proof_takes_no_other_empty_proof(
    out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A-5, `empty_proofs`."""
    L = env("lemma", "Every finite group of odd order is solvable.")
    P = env("proposition", "Every planar graph is four colourable.")
    Rm = env("remark", "The constants above are not sharp.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L + proof() + P + proof() + Rm})
    key = "drafting/s1.tex#proposition:1/proof"
    a = note(out, key, "prove this by discharging")
    e = suggest(out, monkeypatch, key, "By discharging, as in Appel and Haken.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L + proof() + Rm})
    assert shown(out, a) is None and keeps_into(out, e) is None


def test_a_renamed_file_sends_nothing_to_an_obvious_proof_elsewhere(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A-2, `renamed_file_twin_elsewhere`."""
    s1 = env("lemma", "Every compact metric space is separable.") + proof("Obvious.")
    s2 = env("theorem", "Every bounded harmonic function on the plane is constant.") + proof("Obvious.")
    write(out, {"drafting/main.tex": main_with("s1", "s2"), "drafting/s1.tex": s1, "drafting/s2.tex": s2})
    key = "drafting/s2.tex#theorem:1/proof"
    a = note(out, key, "not obvious: cite Liouville")
    e = suggest(out, monkeypatch, key, "By Liouville's theorem.")
    s2b = env("theorem", "Every bounded harmonic function on the plane is constant.") + proof(
        "Obvious. Indeed, apply the mean value property on large discs."
    )
    write(
        out, {"drafting/main.tex": main_with("s1", "liouville"), "drafting/s1.tex": s1, "drafting/liouville.tex": s2b}
    )
    assert shown(out, a) is None and keeps_into(out, e) is None


def test_a_backup_in_no_document_takes_no_record(out: Path) -> None:
    """A-2, `renamed_file_backup_copy`: the live file renamed and the lemma edited; the notes follow it, never into the backup."""
    A = env("remark", "We fix notation.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    X2 = env("lemma", "Every finite graph with minimum degree at least three contains an even cycle.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X, "drafting/old/s1-backup.tex": A + X})
    (out / ".gitignore").write_text("drafting/old/\n")
    a = note(out, "drafting/s1.tex#lemma:1", "why even?")
    q = note(out, "drafting/s1.tex#lemma:1", "say which cycle", "contains an even cycle")
    write(
        out,
        {"drafting/main.tex": main_with("graphs"), "drafting/graphs.tex": A + X2, "drafting/old/s1-backup.tex": A + X},
    )
    assert shown(out, a) == shown(out, q) == X2.strip()


def test_a_block_moved_into_a_notes_slot_does_not_take_it(out: Path) -> None:
    """A-3, `swap_and_edit`: Z moved up into X's slot and X, touched, to the end; the notes follow X."""
    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    B = env("remark", "The bound in the lemma above is attained.")
    Z = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    C = env("remark", "This closes the section.")
    X2 = env("lemma", "Every finite graph with minimum degree at least three contains an even cycle.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B + C + Z})
    a = note(out, "drafting/s1.tex#lemma:2", "this needs 2-connectivity")
    q = note(out, "drafting/s1.tex#lemma:2", "why even?", "contains an even cycle")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Z + B + C + X2})
    assert shown(out, a) == shown(out, q) == X2.strip()


def test_a_block_moved_into_a_deleted_ones_slot_does_not_take_its_note(out: Path) -> None:
    """A-3, `delete_and_move_in`."""
    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    B = env("remark", "The bound in the lemma above is attained.")
    C = env("remark", "This closes the section.")
    Z = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B + C + Z})
    a = note(out, "drafting/s1.tex#lemma:2", "this lemma is false for K4")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Z + B + C})
    assert shown(out, a) is None


def test_an_edited_original_keeps_its_records_from_a_verbatim_copy(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A-4, `copy_then_edit_original`: and Keep writes into the original, the copy untouched."""
    A = env("remark", "We fix notation.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    B = env("remark", "The bound is sharp.")
    X2 = env(
        "lemma", "Every finite graph with minimum degree at least three contains an even cycle through a given vertex."
    )
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B})
    a = note(out, "drafting/s1.tex#lemma:1", "why even?")
    q = note(out, "drafting/s1.tex#lemma:1", "say which cycle", "contains an even cycle")
    e = suggest(out, monkeypatch, "drafting/s1.tex#lemma:1", "a cycle of even length", "an even cycle")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X2 + B + X})
    assert shown(out, a) == shown(out, q) == keeps_into(out, e) == X2.strip()


def test_an_equation_in_an_edited_original_keeps_its_note_from_a_verbatim_copy(out: Path) -> None:
    """A-4, `copy_then_edit_original_region`."""
    A = env("remark", "We fix notation.")
    X = env(
        "lemma",
        "For every n we have\n\\begin{equation}\\label{eq:sum}\n  \\sum_{k=1}^{n} (2k-1) = n^2\n\\end{equation}\nby induction.",
    )
    B = env("remark", "The bound is sharp.")
    X2 = env("lemma", "For every positive integer n we have\n\\begin{equation}\\label{eq:sum}\n  \\sum_{k=1}^{n} (2k-1) = n^2\n\\end{equation}\nby induction on n.")  # fmt: skip
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B})
    a = note(out, "drafting/s1.tex#lemma:1#eq:sum", "say it is a telescoping sum")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X2 + B + X})
    assert shown(out, a) == X2.strip()


def test_a_deleted_lemmas_note_goes_to_no_parallel_sibling(out: Path) -> None:
    """A-6, `parallel_statements`."""
    A = env("remark", "We fix a field k throughout.")
    X = env("lemma", "Let f be a morphism of finite dimensional vector spaces over k of equal dimension. If f is injective then f is an isomorphism.")  # fmt: skip
    Y = env("lemma", "Let f be a morphism of finite dimensional vector spaces over k of equal dimension. If f is surjective then f is an isomorphism.")  # fmt: skip
    B = env("remark", "Both fail in infinite dimension.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + Y + B})
    a = note(out, "drafting/s1.tex#lemma:1", "the injective case needs rank-nullity; cite it")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Y + B})
    assert shown(out, a) is None


def test_a_quoted_edit_on_a_deleted_proof_is_written_into_no_other(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A-7, `quoted_edit_fallback`."""
    L1 = env("lemma", "The sum of the first n odd numbers is a square.")
    P1 = proof("By induction on n, adding the next odd number.")
    L2 = env("lemma", "Every tree on n vertices has n-1 edges.")
    P2 = proof("By induction on n, removing a leaf.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L1 + P1 + L2 + P2})
    e = suggest(out, monkeypatch, "drafting/s1.tex#lemma:1/proof", "By strong induction on n", "By induction on n")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L2 + P2})
    assert keeps_into(out, e) is None


def test_a_note_follows_the_section_its_label_left(out: Path) -> None:
    """A-8, `section_label_moved`: the label given to a new section; the note's text stands, labels aside, once in the section it was on."""
    S1 = sec("Main results", "We prove the classification of compact surfaces.", "sec:main")
    S2 = sec("Preliminaries", "Background on simplicial complexes.", "sec:prelim")
    S1b = sec("Main results", "We prove the classification of compact surfaces.")
    S3 = sec("The main theorem", "Here we state the new bound on the genus.", "sec:main")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": S2 + S1})
    a = note(out, "drafting/s1.tex#sec:main", "the classification is classical: cite it")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": S2 + S1b + S3})
    got = shown(out, a)
    assert got is not None and got.startswith("\\section{Main results}")


def test_a_block_moved_unchanged_to_another_file_is_followed(out: Path) -> None:
    """A-12, `block_moved_to_other_file`."""
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    A = env("remark", "We fix notation.")
    B = env("remark", "Further remarks.")
    write(out, {"drafting/main.tex": main_with("s1", "s2"), "drafting/s1.tex": A + X, "drafting/s2.tex": B})
    a = note(out, "drafting/s1.tex#lemma:1", "why even?")
    write(out, {"drafting/main.tex": main_with("s1", "s2"), "drafting/s1.tex": A, "drafting/s2.tex": B + X})
    assert shown(out, a) == X.strip()


def test_a_record_on_no_block_names_none_and_no_mark_is_drawn_in_another(out: Path) -> None:
    """A-9, `gone_mark`: the lemma a quoted and a whole-block note were on is deleted, and the next lemma takes its key; neither note is named on it, nor is a gone mark drawn inside it."""
    from loom.records.store import Records
    from loom.render.versions import gone_annotations

    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    C = env("lemma", "Every bounded sequence of reals with a finite limit is Cauchy.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + C})
    q = note(out, "drafting/s1.tex#lemma:2", "say which cycle", "contains an even cycle")
    w = note(out, "drafting/s1.tex#lemma:2", "why even?")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + C})
    assert detached_on(out, q) is None and detached_on(out, w) is None
    result = scanned(out)
    records = Records(out)
    gone = {g.annotation.id: g for g in gone_annotations(result, records)}
    assert gone[q].node is None and gone[q].entry is None
    manifest: dict = {"nodes": {}, "keys": {}, "diagnostics": []}  # type: ignore[type-arg]
    records.apply(result, manifest)
    assert manifest["annotations"][q]["target"]["key"] == ""
    assert {u["id"]: u["key"] for u in manifest["unplaced"]} == {
        q: "drafting/s1.tex#lemma:2",
        w: "drafting/s1.tex#lemma:2",
    }


def test_a_note_edited_or_answered_after_it_followed_its_block_stays_on_it(out: Path) -> None:
    """A-1, `edit_moves`: a note follows its lemma once one is put in above it; editing it, or replying to it, restates it on that lemma, never on the newcomer that took its key."""
    from loom.cli.review import _one_comment, edit_annotation

    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    N = env("lemma", "Every planar graph is five colourable, by a counting argument.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X})
    q = note(out, "drafting/s1.tex#lemma:2", "say which cycle", "contains an even cycle")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + N + X})
    assert shown(out, q) == X.strip()
    edit_annotation(scanned(out), q, ("human", "Tester"), body="say which cycle, and why it is even")
    assert shown(out, q) == X.strip()
    said = _one_comment(scanned(out), ("human", "Tester"), None, "a cycle through the root", None, None, q, None)
    reply = said.split()[0]
    assert shown(out, reply) == X.strip()


def test_the_listings_name_a_note_by_the_block_it_is_on_and_list_one_on_none_apart(out: Path) -> None:
    """A-10: `loom status`, the mailbox and `loom since` name a note that followed its block by that block, never the newcomer that took its key; a note on no block is listed apart, not dropped."""
    from loom.cli.review import status_payload
    from loom.mailbox import annotation_row
    from loom.records.store import Records

    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    Y = env("lemma", "Every bounded sequence of reals with a finite limit is Cauchy.")
    N = env("lemma", "Every planar graph is five colourable, by a counting argument.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + Y})
    q = note(out, "drafting/s1.tex#lemma:2", "say which cycle", "contains an even cycle")
    gone = note(out, "drafting/s1.tex#lemma:3", "cite Cauchy")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + N + X})
    result = scanned(out)
    records = Records(out)
    keys = status_payload(result, records)["keys"]
    assert [r["id"] for r in keys["drafting/s1.tex#lemma:3"]["reviews"]["annotations"]] == [q]
    assert not keys["drafting/s1.tex#lemma:2"]["reviews"]["annotations"]
    assert [(r["id"], r["written_on"]) for r in status_payload(result, records)["unplaced"]] == [
        (gone, "drafting/s1.tex#lemma:3")
    ]
    ann = next(r.annotation for r in records.resolved(result) if r.annotation.id == q)
    assert annotation_row(out, ann, result)["target"] == "drafting/s1.tex#lemma:3"


def _base_written_on(result, key, node, want):  # type: ignore[no-untyped-def]
    """`records.store.written_on` as on 08116105, the branch's base: the reference for unchanged text."""
    from loom.records.locate import block_hash

    if not want or "#" not in key or key in result.assembly.regions:
        return node
    if node is not None and block_hash(result, node.key) == want:
        return node
    path = node.file if node is not None else key.split("#", 1)[0]
    same = [n for n in result.nodes.values() if n.file == path and n is not node and block_hash(result, n.key) == want]
    return same[0] if len(same) == 1 else node


def _base_filed_on(result, key, node, want, near=""):  # type: ignore[no-untyped-def]
    """`records.store.filed_on` as on 08116105, for an edit that quotes nothing."""
    from loom.records.locate import block_hash, line_before, named_by_place

    if not want or not named_by_place(result, key, node):
        return node
    path = node.file if node is not None else key.split("#", 1)[0]
    same = [n for n in result.nodes.values() if n.file == path and block_hash(result, n.key) == want]
    if len(same) == 1:
        return same[0]
    if not near:
        return None
    under = [n for n in same if line_before(result, n) == near]
    return under[0] if len(under) == 1 else None


@pytest.mark.parametrize("context", [False, True])
def test_on_unchanged_text_every_record_is_placed_as_the_base_placed_it(out: Path, context: bool) -> None:
    """A-11: whatever its kind of key (an id, a key named by place, a label, a region, a region whose label is defined twice, a section, an attached or a lone proof, an empty proof among twins, the document's own text), a note and an edit on text nobody changed are placed exactly where the base placed them, with context and without."""
    from loom.records import edits as E
    from loom.records.locate import block_hash, context_of, line_before, named_by_place
    from loom.records.log import append_new
    from loom.records.store import Records

    eq = "\\begin{equation}\\label{eq:twice}\n  a = b\n\\end{equation}\n"
    s1 = (
        sec("Setup", "We fix notation here.", "sec:setup")
        + env("lemma", "Every compact group admits a Haar measure.", "tq-0001")
        + proof("By Weil.")
        + env("lemma", "Every finite graph with minimum degree three contains an even cycle.\n" + eq)
        + proof()
        + env("remark", "The bound is sharp.\n" + eq)
        + proof()
        + sec("More", "Further words.")
        + proof("A lone proof, attached to nothing.")
    )
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": s1})
    result = scanned(out)
    keys = [k for k, n in result.nodes.items() if n.kind not in ("file",)] + list(result.assembly.regions)
    filed: list[tuple[str, str, str]] = []
    for key in keys:
        node = result.nodes.get(result.assembly.regions[key].container if key in result.assembly.regions else key)
        assert node is not None
        want = block_hash(result, node.key)
        extra = {"context": context_of(result, node)} if context and context_of(result, node) else {}
        ann = append_new(out, {"event": "created", "when": "2026-11-20T00:00:00Z", "author": "Tester", "kind": "human", "target": key, "against": want, "anchor": None, "body": "a note", **extra}, "2026-11-20")  # fmt: skip
        near = {"near": line_before(result, node)} if named_by_place(result, key, node) else {}
        ed = E.append_new(out, {"event": "created", "when": "2026-11-20T00:00:00Z", "author": "Agent", "kind": "agent", "target": key, "against": want, "anchor": None, "with": "New words.", "placement": "after", **near, **extra}, "2026-11-20")  # fmt: skip
        filed.append((key, ann, ed))
    result = scanned(out)
    shown = {r.annotation.id: r for r in Records(out).resolved(result)}
    edits = {e.id: e for e in E.replay(out)[0]}
    for key, ann, ed in filed:
        node = result.nodes.get(result.assembly.regions[key].container if key in result.assembly.regions else key)
        want = block_hash(result, node.key) if node is not None else ""
        base = _base_written_on(result, key, node, want)
        res = shown[ann]
        got = None if res.unplaced else result.nodes.get(res.target) or result.nodes.get(result.assembly.regions[res.target].container) if res.target in result.assembly.regions else result.nodes.get(res.target)  # fmt: skip
        assert (got.key if got else None) == (base.key if base else None), (key, "note")
        home = E.home(result, edits[ed])
        base_edit = _base_filed_on(result, key, node, want, edits[ed].near)
        assert (home.key if home else None) == (base_edit.key if base_edit else None), (key, "edit")


def test_the_words_beside_an_insertion_hold_no_comment(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A-13: what an insertion records of its file beside its place leaves comments out, which the viewer hides and the person may delete."""
    import loom.cli.suggest as S
    from loom.records import edits as E

    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    write(
        out,
        {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": X + "% private: referee 2 thinks this is false\n"},
    )
    r = scanned(out)
    monkeypatch.setattr(S, "open_scan", lambda q: r)
    with contextlib.redirect_stdout(io.StringIO()):
        S.suggest_command.callback(  # type: ignore[misc]
            key="drafting/s1.tex#lemma:1", with_text=" Indeed.", quote="contains an even cycle.", before=False, after=True,
            answers=None, comment=None, author="Agent Tester", withdraw=None, why=None, dry_run=False, as_json=True, quilt_path=str(out),
        )  # fmt: skip
    (e,) = E.replay(out)[0]
    assert e.context is not None and "referee" not in e.context["beside"] and "private" not in e.context["beside"]


def _unrecorded(out: Path) -> None:
    """Take `context` off every record in both logs: what a record written before it was recorded is."""
    import json

    for log in (out / ".loom/records/annotations/log.jsonl", out / ".loom/records/edits/log.jsonl"):
        if log.exists():
            lines = [json.loads(line) for line in log.read_text().splitlines() if line]
            log.write_text("".join(json.dumps({k: v for k, v in e.items() if k != "context"}) + "\n" for e in lines))


def test_an_ids_empty_answer_being_filled_in_keeps_its_records(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B-1, `id_empty_answers`: the author begins tq-0003's empty answer; its note stays on it, and the agent's whole answer is written into no other empty answer."""
    E1 = env("lemma", "Exercise: show that every tree is bipartite.", "tq-0001")
    E3 = env("lemma", "Exercise: show that K5 is not planar.", "tq-0003")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": E1 + proof() + E3 + proof()})
    a = note(out, "tq-0003/proof", "use Euler's formula")
    e = suggest(out, monkeypatch, "tq-0003/proof", "By Euler's formula, e <= 3v - 6 fails for K5.")
    write(
        out,
        {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": E1 + proof() + E3 + proof("Suppose K5 were planar.")},
    )
    assert shown(out, a) == proof("Suppose K5 were planar.").strip()
    assert keeps_into(out, e) in (None, proof("Suppose K5 were planar.").strip())


@pytest.mark.parametrize("restated", ["before", "after"])
def test_a_note_on_an_id_stays_with_it_when_rewritten_beside_a_restatement(out: Path, restated: str) -> None:
    """B-2, `id_rewritten_copy_elsewhere`: the id never moved, so its note stays on it, rewritten under it, and never goes to a verbatim restatement."""
    intro = sec("Introduction", "We state our main theorem.")
    Tr = env("theorem", "Every compact orientable surface is a sphere with handles.")
    T = env("theorem", "Every compact orientable surface is a sphere with handles.", "tq-0007")
    T2 = env("theorem", "A closed orientable two-manifold of Euler characteristic chi is homeomorphic to the connected sum of 1 - chi/2 tori.", "tq-0007")  # fmt: skip
    S = sec("Proofs", "We prove the main theorem.")
    write(
        out,
        {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": intro + (Tr if restated == "before" else "") + S + T},
    )
    a = note(out, "tq-0007", "cite the classification")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": intro + Tr + S + T2})
    assert shown(out, a) == T2.strip()


@pytest.mark.parametrize("second", ["alike", "different"])
def test_a_deleted_first_proofs_note_goes_to_no_second_proof(out: Path, second: str) -> None:
    """B-3, `id_second_proof_takes_key`: an id's proofs are numbered by place, and the second takes `ID/proof` once the first is deleted; the note goes to none."""
    T = env("theorem", "Every planar graph is five colourable.", "tq-0007")
    P1 = proof("Induct on vertices: a vertex of degree at most five exists, remove it, colour the rest, and recolour along a Kempe chain.")  # fmt: skip
    P2 = {
        "alike": proof(
            "Induct on vertices: a vertex of degree at most five exists, delete it, colour the rest, and swap colours along a Kempe chain."
        ),  # fmt: skip
        "different": proof("Use the discharging method with charges six minus degree on every vertex."),
    }[second]
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": T + P1 + P2})
    a = note(out, "tq-0007/proof", "which Kempe chain?")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": T + P2})
    assert shown(out, a) is None


def test_a_label_given_to_a_look_alike_put_in_beside_its_block_keeps_the_note_with_the_label(out: Path) -> None:
    """B-4 against D-2: a look-alike put in right after the section, and the label moved onto it, leaves the very file that a copy of the section put in above it, the section then edited, would leave. A record stays with its label's block while that block reads like it, so the note stays on the look-alike."""
    S0 = sec("Preliminaries", "Background on simplicial complexes and their homology.", "sec:pre")
    S1 = sec("Main results", "We prove the classification of compact surfaces by cutting along curves.", "sec:main")
    S1b = sec("Main results", "We prove the classification of compact surfaces by cutting along curves.")
    S2 = sec(
        "Main results, revisited", "We prove the classification of compact surfaces by cutting along arcs.", "sec:main"
    )
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": S0 + S1})
    a = note(out, "drafting/s1.tex#sec:main", "cite Zeeman's proof")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": S0 + S1b + S2})
    got = shown(out, a)
    assert got is not None and got.startswith("\\section{Main results, revisited}")


@pytest.mark.parametrize("words", ["By induction on n.", "By induction, clearly."])
def test_a_short_proofs_note_follows_its_words_to_no_unrelated_proof(out: Path, words: str) -> None:
    """B-5, `four_words_elsewhere`: L1 deleted with its proof, and an unrelated proof shortened to the same words; a recorded neighbour says it is not the note's block."""
    L1 = env("lemma", "The sum of the first n odd numbers is a square.")
    L2 = env("lemma", "Every tree on n vertices has n-1 edges.")
    L5 = env("lemma", "Every connected graph has a spanning tree.")
    L6 = env("lemma", "A graph is bipartite iff it has no odd cycle.")
    P2 = proof("Remove a leaf and use induction on the number of vertices.")
    P6 = proof("Two-colour by parity of distance.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L1 + proof(words) + L2 + P2 + L5 + proof("Take a minimal connected spanning subgraph; it has no cycle.") + L6 + P6})  # fmt: skip
    a = note(out, "drafting/s1.tex#lemma:1/proof", "which induction?")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L2 + P2 + L5 + proof(words) + L6 + P6})
    assert shown(out, a) is None


def test_an_old_note_in_a_renamed_file_follows_no_copy_while_its_edited_block_reads_like_it(out: Path) -> None:
    """B-6, `old_rename`: a note written before `context` on the second of two identical theorems; the file renamed and that theorem edited. The copy holds its very text, the edited one reads like it: either could be meant."""
    T = env("theorem", "Every compact orientable surface is a sphere with handles.")
    T2 = env("theorem", "Every compact orientable surface is a sphere with some handles attached.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": T + T})
    a = note(out, "drafting/s1.tex#theorem:2", "cite the classification")
    _unrecorded(out)
    write(out, {"drafting/main.tex": main_with("graphs"), "drafting/graphs.tex": T + T2})
    assert shown(out, a) is None


def test_a_replacement_is_written_only_where_its_quote_stands_among_the_words_it_was_suggested_among(
    out: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second review's replacement edit: its quote now stands once in its block, but among other words; the words recorded either side say it is not the place."""
    X = env("lemma", "First we take the closure of A in the plane. Later we take its interior in the line.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": X})
    e = suggest(out, monkeypatch, "drafting/s1.tex#lemma:1", "form the closure", "take the closure")
    X2 = env("lemma", "First we compute the closure of A in the plane. Later we take the closure of B in the line.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": X2})
    assert keeps_into(out, e) is None


def test_an_unplaced_edit_is_listed_on_no_block(out: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B-8, `places.py`: an edit on a deleted lemma is unplaced, and listed on no block, never on the lemma that took its key (`drafting/s1.tex#lemma:1`, Y now)."""
    from loom.pending import suggested

    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    Y = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": X + Y})
    e = suggest(out, monkeypatch, "drafting/s1.tex#lemma:1", "an even cycle, by Erdos", "an even cycle")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": Y})
    (p,) = [c for c in suggested(scanned(out)) if c.id == e]
    assert p.state == "unplaced" and p.key is None


def test_where_a_listing_names_a_note_is_read_again_after_a_write_to_the_log(out: Path) -> None:
    """B-12: a placement remembered for a scan is read again once the annotation log changes, as a served quilt's does when a note is restated with no new scan."""
    from loom.cli.review import edit_annotation
    from loom.records.store import Records, placed_key

    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    N = env("lemma", "Every planar graph is five colourable, by a counting argument.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X})
    q = note(out, "drafting/s1.tex#lemma:2", "say which cycle", "contains an even cycle")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + N + X})
    result = scanned(out)
    ann = next(r.annotation for r in Records(out).resolved(result) if r.annotation.id == q)
    assert placed_key(result, ann) == "drafting/s1.tex#lemma:3"
    edit_annotation(result, q, ("human", "Tester"), body="another word")
    ann = next(r.annotation for r in Records(out).resolved(result) if r.annotation.id == q)
    assert placed_key(result, ann) == "drafting/s1.tex#lemma:3"


def test_a_deleted_blocks_note_goes_to_no_copy_that_takes_its_key(out: Path) -> None:
    """C-1, `twin_inherits_key`: a lemma stated twice, two remarks between; the first, with the note, is deleted and the restatement takes its key. Its context recorded two copies, and its neighbours stand against the restatement."""
    L = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    R = env("remark", "This is used in Section 4.")
    S = env("remark", "We now turn to colourings.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L + R + S + L})
    a = note(out, "drafting/s1.tex#lemma:1", "the first statement needs 2-connectivity")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": R + S + L})
    assert shown(out, a) is None


def test_a_lemma_deleted_with_its_proof_leaves_its_note_on_no_sibling(out: Path) -> None:
    """C-1, `parallel_with_proof`: the injective lemma, recorded with a twin, is deleted with its proof; its surjective sibling takes its key and reads alike, without both its neighbours."""
    A = env("remark", "We fix a field k throughout.")
    X = env("lemma", "Let f be a morphism of finite dimensional vector spaces over k of equal dimension. If f is injective then f is an isomorphism.")  # fmt: skip
    Y = env("lemma", "Let f be a morphism of finite dimensional vector spaces over k of equal dimension. If f is surjective then f is an isomorphism.")  # fmt: skip
    B = env("remark", "Both fail in infinite dimension.")
    P = proof("By rank-nullity the image has full dimension.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + P + Y + B})
    a = note(out, "drafting/s1.tex#lemma:1", "the injective case needs rank-nullity; cite it")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Y + B})
    assert shown(out, a) is None


def test_a_four_word_text_follows_no_moved_id_to_a_block_elsewhere(out: Path) -> None:
    """C-3, `id_moved_short_text`: the remark deleted, its id given to another, and a remark reading the same four words written since at the end. The id never followed its text there: the note stays on the id's block, rewritten under it."""
    from loom.records.locate import rewritten

    A = env("lemma", "Every compact group admits a Haar measure.")
    R = env("remark", "This is well known.", "tq-0005")
    B = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    C = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    R2 = env("remark", "This is well known.")
    N = env("remark", "A different remark that took the id.", "tq-0005")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + R + B + C})
    a = note(out, "tq-0005", "give a reference")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + B + N + C + R2})
    assert shown(out, a) == N.strip()
    from loom.records.store import Records

    result = scanned(out)
    ann = next(r.annotation for r in Records(out).resolved(result) if r.annotation.id == a)
    assert rewritten(result, result.nodes["tq-0005"], ann.target_hash)


@pytest.mark.parametrize("put_in_above", [False, True])
def test_a_note_stays_with_its_rewritten_id_when_its_old_words_are_pasted_elsewhere(
    out: Path, put_in_above: bool
) -> None:
    """C-4, `id_rewritten_old_text_pasted`: in one edit tq-0007 is rewritten and its old words pasted, unlabelled, in the introduction, with or without a remark put in above it; the pasted copy stands between none of the note's neighbours."""
    intro = sec("Introduction", "We state our main theorem.")
    T = env("theorem", "Every compact orientable surface is a sphere with handles.", "tq-0007")
    T2 = env("theorem", "A closed orientable two-manifold of Euler characteristic chi is homeomorphic to the connected sum of 1 - chi/2 tori.", "tq-0007")  # fmt: skip
    Tr = env("theorem", "Every compact orientable surface is a sphere with handles.")
    S = sec("Proofs", "We prove the main theorem.")
    Z = env("remark", "The next theorem is classical.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": intro + S + T})
    a = note(out, "tq-0007", "cite the classification")
    write(
        out,
        {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": intro + Tr + S + (Z if put_in_above else "") + T2},
    )
    assert shown(out, a) == T2.strip()


@pytest.mark.parametrize("key", ["tq-0007", "drafting/appendix.tex#theorem:1"])
def test_a_note_is_on_no_block_while_its_file_is_read_by_no_document(out: Path, key: str) -> None:
    """C-5, `input_commented_out`: `\\input{appendix}` commented out; the note on the theorem, by its id or by its place, is on no block, never on the restatement in the introduction, and is on the theorem again once the appendix is read again."""
    Tr = env("theorem", "Every compact orientable surface is a sphere with handles.")
    intro = sec("Introduction", "We state our main theorem.")
    T = env(
        "theorem", "Every compact orientable surface is a sphere with handles.", "tq-0007" if "#" not in key else ""
    )
    app = sec("Appendix", "The proof of the main theorem.") + T + proof("Triangulate and cut along curves.")
    on = main_with("intro", "appendix")
    files = {"drafting/main.tex": on, "drafting/intro.tex": intro + Tr, "drafting/appendix.tex": app}
    write(out, files)
    a = note(out, key, "cite the classification")
    write(out, {**files, "drafting/main.tex": on.replace("\\input{appendix}", "% \\input{appendix}")})
    assert shown(out, a) is None
    write(out, files)
    assert shown(out, a) == T.strip()


def test_a_statement_changed_in_kind_keeps_its_note_from_a_copy_that_takes_its_key(out: Path) -> None:
    """C-1, the generator's kind-change: a proposition stated twice becomes a remark where it stands, and the copy further down takes `proposition:1` with both recorded neighbours against it; the remark, between both, reads like the note's text."""
    A = env("lemma", "Every compact group admits a Haar measure.")
    X = env("proposition", "Every planar graph has a vertex of degree at most five.")
    Xr = env("remark", "Every planar graph has a vertex of degree at most five.")
    B = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    C = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    D = env("lemma", "Every tree on n vertices has n-1 edges.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B + C + X + D})
    a = note(out, "drafting/s1.tex#proposition:1", "cite Euler's formula")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Xr + B + C + X + D})
    assert shown(out, a) == Xr.strip()


def accept(out: Path, keys: list[str]) -> None:
    from loom.cli.review import write_acceptance

    write_acceptance(scanned(out), keys, "Tester")


def accepted(out: Path) -> dict[str, str]:
    """Each block that reads accepted now, by its text, with the text its row was given on."""
    from loom.records.store import Records

    result = scanned(out)
    states = Records(out, reviewer="Tester").key_states(result, observe=False)
    return {
        str(text_of(out, k)): str(text_of(out, s.row.key) if s.row.key in result.nodes else s.row.key)
        for k, s in states.items()
        if s.row is not None
    }


def test_an_acceptance_on_a_deleted_block_goes_to_no_copy_that_takes_its_key(out: Path) -> None:
    """C-6, `ledger_twin_inherits`: a lemma stated twice and only the first accepted; the first deleted, the restatement takes its key and reads accepted by nobody."""
    L = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    R = env("remark", "This is used in Section 4.")
    S = env("remark", "We now turn to colourings.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": L + R + S + L})
    accept(out, ["drafting/s1.tex#lemma:1"])
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": R + S + L})
    assert accepted(out) == {}


def test_an_ids_swapped_proofs_carry_no_acceptance_to_each_other(out: Path) -> None:
    """C-6, `id_proofs` (b): both proofs of tq-0007 accepted, then swapped; neither reads accepted with the other's row."""
    from loom.records.locate import block_hash
    from loom.records.store import Records

    T = env("theorem", "Every planar graph is five colourable.", "tq-0007")
    P1 = proof("Induct on vertices: a vertex of degree at most five exists, remove it, colour the rest, and recolour along a Kempe chain.")  # fmt: skip
    P2 = proof("Use the discharging method with charges six minus degree on every vertex, and reduce to unavoidable configurations.")  # fmt: skip
    X = env("remark", "Four colours suffice, but that is much harder.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": T + P1 + P2 + X})
    accept(out, ["tq-0007/proof", "tq-0007/proof/2"])
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": T + P2 + P1 + X})
    result = scanned(out)
    states = Records(out, reviewer="Tester").key_states(result, observe=False)
    for key in ("tq-0007/proof", "tq-0007/proof/2"):
        row = states[key].row
        assert row is None or row.text == block_hash(result, key)


def test_an_acceptance_follows_its_statement_when_its_label_moves_to_a_block_put_in_beside_it(out: Path) -> None:
    """C-6, the generator's label-move: the accepted lemma's id given to a lemma put in after it, which reads nothing like it; the row stays with the text it was given on, and the newcomer reads accepted by nobody."""
    A = env("remark", "We fix notation.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.", "tq-0009")
    Xb = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    N = env("lemma", "Every bounded sequence of reals has a convergent subsequence.", "tq-0009")
    B = env("remark", "The bound is sharp.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B})
    accept(out, ["tq-0009"])
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Xb + N + B})
    assert list(accepted(out)) == [Xb.strip()]


def test_a_note_follows_its_lemma_when_its_id_moves_onto_the_next_one(out: Path) -> None:
    """The harness's label-moved: tq-0009 moved off its lemma onto the lemma after it, which stood there already; that neighbour is recognised by its text, labels aside, and the note follows its lemma."""
    A = env("remark", "We fix notation throughout this section.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.", "tq-0009")
    Xb = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    Y = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    Yl = env("lemma", "Every bounded sequence of reals has a convergent subsequence.", "tq-0009")
    B = env("remark", "The bound is sharp.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + Y + B})
    a = note(out, "tq-0009", "cite Erdos")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + Xb + Yl + B})
    assert shown(out, a) == Xb.strip()


@pytest.mark.parametrize("deleted", ["twin", "statement"])
def test_a_statement_and_its_twin_beside_it_cannot_be_told_apart_once_one_is_deleted(out: Path, deleted: str) -> None:
    """A lemma restated right after itself, a note on the first; one of the two deleted. Either deletion leaves the very same text, so which block is the note's cannot be told, and it is on none."""
    A = env("remark", "We fix notation throughout this section.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    B = env("remark", "The bound is sharp.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + X + B})
    a = note(out, "drafting/s1.tex#lemma:1", "cite Erdos")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B})
    assert shown(out, a) is None


def test_a_deleted_statements_note_goes_to_no_twin_where_its_neighbours_went_too(out: Path) -> None:
    """C-1, the harness's delete-statement with a twin standing at the end: the lemma and both its neighbours deleted, so no recorded neighbour stands anywhere; the restatement far below has nothing for it and is not taken."""
    A = env("remark", "We fix notation throughout this section.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    B = env("remark", "The bound is sharp.")
    C = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    D = env("remark", "This closes the section.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B + C + D + X})
    a = note(out, "drafting/s1.tex#lemma:1", "cite Erdos")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": C + D + X})
    assert shown(out, a) is None


INJ = "Let f be a morphism of finite dimensional vector spaces over k of equal dimension. If f is injective then f is an isomorphism."  # fmt: skip
SUR = "Let f be a morphism of finite dimensional vector spaces over k of equal dimension. If f is surjective then f is an isomorphism."  # fmt: skip


def test_an_id_moved_onto_a_look_alike_beside_it_leaves_note_and_acceptance_with_the_lemma_it_left(out: Path) -> None:
    """D-1, `label_between_lookalikes`: tq-0003 moved off the injective lemma onto its surjective look-alike after it. The injective lemma stands where it was, between both recorded neighbours, whatever twin was recorded: the note and the row follow it."""
    A = env("remark", "We fix a field k throughout.")
    B = env("remark", "Both fail in infinite dimension.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + env("lemma", INJ, "tq-0003") + env("lemma", SUR) + B})  # fmt: skip
    a = note(out, "tq-0003", "the injective case needs rank-nullity")
    accept(out, ["tq-0003"])
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + env("lemma", INJ) + env("lemma", SUR, "tq-0003") + B})  # fmt: skip
    assert shown(out, a) == env("lemma", INJ).strip()
    assert list(accepted(out)) == [env("lemma", INJ).strip()]


@pytest.mark.parametrize("copy", ["below", "above"])
def test_a_copy_put_beside_an_ids_block_then_edited_takes_none_of_its_records(out: Path, copy: str) -> None:
    """D-2, `id_copy_beside_then_edit`: the lemma copied, unlabelled, right below or above it, and the original edited, keeping the id. While the id's block reads like the record, the record stays with it."""
    A = env("remark", "We fix a field k throughout.")
    P = env("lemma", "Every planar graph is five colourable by an easy induction on vertices.")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.", "tq-0004")
    X0 = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    X2 = env("lemma", "Every finite graph with minimum degree at least three contains an even cycle through a given vertex.", "tq-0004")  # fmt: skip
    N = env("lemma", "Every bounded sequence of reals has a convergent subsequence by bisection.")
    B = env("remark", "Both fail in infinite dimension.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + P + X + N + B})
    a = note(out, "tq-0004", "say which cycle")
    accept(out, ["tq-0004"])
    pair = X2 + X0 if copy == "below" else X0 + X2
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + P + pair + N + B})
    assert shown(out, a) == X2.strip()
    assert list(accepted(out)) == [X2.strip()]


def test_a_deleted_propositions_note_goes_to_no_twin_that_stood_right_after_it(out: Path) -> None:
    """D-4: a proposition and its empty proof, its copy right after them; the proposition and its proof deleted, a block put in above. The copy keeps one recorded neighbour and none against, but with a copy recorded beside it one neighbour is no evidence: the note is on none."""
    A = env("remark", "We fix a field k throughout.")
    L = env("lemma", "Every planar graph is five colourable by an easy induction on vertices.")
    LP = proof("Remove a vertex of degree at most five and colour the rest.")
    T = env("proposition", "Every finite graph with minimum degree three contains an even cycle.")
    N = env("remark", "A remark a co-author put in above.")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + L + LP + T + proof() + T})
    a = note(out, "drafting/s1.tex#proposition:1", "say which cycle")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": N + A + L + LP + T})
    assert shown(out, a) is None


def test_a_moved_statement_with_a_look_alike_beside_it_keeps_its_note_at_its_own_key(out: Path) -> None:
    """C-1's shortcut with one copy recorded: the injective proposition, its surjective look-alike recorded as a twin, moved to the end; its very text stands once at its own key, which no look-alike could take without being rewritten into its words."""
    A = env("remark", "We fix a field k throughout.")
    B = env("remark", "Both fail in infinite dimension.")
    C = env("remark", "This closes the section.")
    X = env("proposition", INJ)
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + X + B + env("lemma", SUR) + C})
    a = note(out, "drafting/s1.tex#proposition:1", "cite rank-nullity")
    write(out, {"drafting/main.tex": main_with("s1"), "drafting/s1.tex": A + B + env("lemma", SUR) + C + X})
    assert shown(out, a) == X.strip()


def test_every_note_on_no_block_is_given_the_document_that_read_its_file_when_it_was_written(out: Path) -> None:
    """D-3: a note on an id whose file's `\\input` is commented out, and one on a lemma by its place in a section file whose block is deleted, each written while `drafting/talk.tex` read that file; both are on no block, their keys name nothing a document reads, and the manifest gives each `talk.tex`, never the key's file."""
    from loom.records.store import Records

    PRE2 = "\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\newtheorem{theorem}{Theorem}\n\\begin{document}\n%s\\end{document}\n"
    T = env("theorem", "Every compact orientable surface is a sphere with handles.", "tq-0007")
    X = env("lemma", "Every finite graph with minimum degree three contains an even cycle.")
    Y = env("lemma", "Every bounded sequence of reals has a convergent subsequence.")
    on = PRE2 % "\\input{app}\n\\input{sec}\n"
    files = {
        "drafting/main.tex": main_with(),
        "drafting/talk.tex": on,
        "drafting/app.tex": T,
        "drafting/sec.tex": X + Y,
    }
    write(out, files)
    a = note(out, "tq-0007", "cite the classification")
    b = note(out, "drafting/sec.tex#lemma:1", "say which cycle")
    write(out, {**files, "drafting/talk.tex": on.replace("\\input{app}", "% \\input{app}"), "drafting/sec.tex": Y})
    manifest: dict = {"nodes": {}, "keys": {}, "diagnostics": []}  # type: ignore[type-arg]
    Records(out).apply(scanned(out), manifest)
    assert {u["id"]: u["document"] for u in manifest["unplaced"]} == {a: "drafting/talk.tex", b: "drafting/talk.tex"}
    assert (
        next(u["why"] for u in manifest["unplaced"] if u["id"] == a)
        == "Its block is in a file no document reads now; it is back on that block once a document reads the file again."
    )
