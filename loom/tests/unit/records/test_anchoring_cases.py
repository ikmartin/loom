"""Where a record goes when blocks compete for it (`records.locate.follow`): the independent review's smallest cases (`safe-anchoring-review.md`, A-2 to A-8 and A-12), each a tiny quilt changed once. A record goes to a block other than its own key's only when nothing else could be meant; otherwise it is on none."""

from __future__ import annotations

import contextlib
import io
from pathlib import Path

import pytest

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
    (root / ".loom" / "format").write_text("1\n")
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
    assert manifest["annotations"][q]["target"]["key"] is None
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
