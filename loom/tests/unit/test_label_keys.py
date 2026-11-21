"""A statement keyed by its label (`scan.nodes._keyable_labels`): the key and its place, the records on it when the label is added, renamed, deleted or given an id, a draft copied to a second document, and an acceptance whose dependency a label comes to key."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import edit, json_of, ok
from tests.unit._quilts import demo

WHO = "Tester"
NOTES = "drafting/notes.tex"
TEXT = r"""\section{Labelled}
\begin{lemma}\label{lem:first}
Every widget has a first part that is never empty.
\end{lemma}
\begin{proof}
By the definition of a widget, its first part holds a point.
\end{proof}

\begin{lemma}
An unlabelled lemma about gadgets which stays as it is.
\end{lemma}

\begin{theorem}\label{thm:second}
Each gadget meets every widget in a finite set by Lemma~\ref{lem:first}:
\begin{equation}\label{eq:finite}
|G \cap W| < \infty
\end{equation}
\end{theorem}
"""


@pytest.fixture
def q(tmp_path: Path) -> Path:
    from loom.scan.quilt import save_author

    save_author(WHO)
    root = demo(tmp_path)
    (root / NOTES).write_text(TEXT, encoding="utf-8")
    edit(root / "drafting/main.tex", "\\end{document}", "\\input{notes}\n\\end{document}")
    return root


def scanned(q: Path) -> Any:
    from loom.cli._quilt import open_scan

    return open_scan(str(q))


def note(q: Path, key: str, *more: str) -> str:
    return ok("annotate", key, "Which?", *more, "--type", "question", "--as", WHO, cwd=q).output.split()[0]


def row(q: Path, ann: str) -> dict[str, Any]:
    from loom.records.store import Records

    result = scanned(q)
    manifest: dict[str, Any] = {"nodes": {}, "keys": {}, "diagnostics": []}
    Records(q, result.quilt.history_dir).apply(result, manifest)
    return manifest["annotations"][ann]  # type: ignore[no-any-return]


def on(q: Path, ann: str) -> str:
    """The key of the block a note is on now; '' for none."""
    got = row(q, ann)
    return "" if got["detached"] else str(got["target"]["key"])


def test_a_statement_is_keyed_by_its_label_and_its_place_still_names_it(q: Path) -> None:
    from loom.cli._quilt import resolve_key

    r = scanned(q)
    assert {"lem:first", "lem:first/proof", f"{NOTES}#lemma:2", "thm:second"} <= set(r.nodes)
    assert "thm:second#eq:finite" in r.assembly.regions
    # the unlabelled lemma is still the second: a label renumbers nothing
    assert r.assembly.places[f"{NOTES}#lemma:1"] == "lem:first"
    assert r.named(f"{NOTES}#lemma:1/proof") == "lem:first/proof"
    assert r.named(f"{NOTES}#theorem:1#eq:finite") == "thm:second#eq:finite"
    assert resolve_key(r, f"{NOTES}#theorem:1") == "thm:second"
    # proofs and statements keyed by a label keep no versions of their own, as a place's do not
    from loom.history.steps import versionable

    assert not versionable(r.nodes["lem:first"]) and not versionable(r.nodes["lem:first/proof"])


@pytest.mark.parametrize(
    ("where", "text"),
    [
        ("a label defined again in another file", "\\begin{remark}\\label{lem:first} Again. \\end{remark}"),
        ("a label read as the same anchor", "\\begin{remark}\\label{Lem-First} Like it. \\end{remark}"),
    ],
)
def test_a_label_defined_twice_or_read_as_another_s_anchor_keys_nothing(q: Path, where: str, text: str) -> None:
    edit(
        q / "drafting/outline.tex",
        "\\section{What is being considered}",
        f"{text}\n\\section{{What is being considered}}",
    )
    r = scanned(q)
    assert "lem:first" not in r.nodes and f"{NOTES}#lemma:1" in r.nodes, where


def test_an_agent_s_copy_keeps_its_statements_by_place(q: Path) -> None:
    copy = q / ".loom/agents/copies/notes-copy.tex"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_text(TEXT.replace("lem:first", "lem:first-ai").replace("thm:second", "thm:second-ai"), encoding="utf-8")
    r = scanned(q)
    assert "lem:first-ai" not in r.nodes and "lem:first" in r.nodes


def test_a_note_on_a_statement_with_no_label_stays_on_it_when_a_label_is_added(q: Path) -> None:
    """A label added later to a statement that had none must not lose the notes already on it."""
    whole = note(q, f"{NOTES}#lemma:2")
    quoted = note(q, f"{NOTES}#lemma:2", "--quote", "stays as it is")
    edit(q / NOTES, "\\begin{lemma}\nAn unlabelled", "\\begin{lemma}\\label{lem:gadgets}\nAn unlabelled")
    assert on(q, whole) == "lem:gadgets" and on(q, quoted) == "lem:gadgets"


def test_a_note_on_a_label_s_key_follows_its_text_when_the_label_is_renamed_or_deleted(q: Path) -> None:
    first = note(q, "lem:first", "--quote", "never empty")
    second = note(q, "thm:second")
    region = note(q, "thm:second#eq:finite")
    edit(q / NOTES, "\\label{lem:first}", "\\label{lem:primary}")
    edit(q / NOTES, "Lemma~\\ref{lem:first}", "Lemma~\\ref{lem:primary}")
    edit(q / NOTES, "\\begin{theorem}\\label{thm:second}", "\\begin{theorem}")
    assert on(q, first) == "lem:primary"
    assert on(q, second) == f"{NOTES}#theorem:1"
    assert on(q, region) == f"{NOTES}#theorem:1#eq:finite"


def test_a_note_on_a_label_s_key_stays_off_a_new_result_the_label_is_given_to(q: Path) -> None:
    """An author may reuse a label, where loom never reuses an id: the note is not read on the new result."""
    ann = note(q, "lem:first", "--quote", "never empty")
    lemma = "\\begin{lemma}\\label{lem:first}\nEvery widget has a first part that is never empty.\n\\end{lemma}\n"
    edit(q / NOTES, lemma, "")
    edit(
        q / NOTES,
        "\\begin{theorem}",
        "\\begin{lemma}\\label{lem:first}\nA different result that took over the label.\n\\end{lemma}\n\n\\begin{theorem}",
    )
    assert on(q, ann) == ""


def test_a_note_on_a_label_s_proof_follows_it_moved_and_lightly_edited(q: Path) -> None:
    ann = note(q, "lem:first/proof", "--quote", "holds a point")
    text = (q / NOTES).read_text(encoding="utf-8")
    block = text[text.index("\\begin{lemma}\\label{lem:first}") : text.index("\\end{proof}") + len("\\end{proof}\n")]
    moved = text.replace(block, "") + "\n" + block.replace("holds a point.", "holds a point, at least.")
    (q / NOTES).write_text(moved, encoding="utf-8")
    assert on(q, ann) == "lem:first/proof"


def test_a_label_its_document_defines_twice_keeps_a_note_on_the_one_at_its_place(q: Path) -> None:
    ann = note(q, "lem:first")
    lemma = "\\begin{lemma}\\label{lem:first}\nEvery widget has a first part that is never empty.\n\\end{lemma}\n"
    (q / NOTES).write_text((q / NOTES).read_text(encoding="utf-8") + "\n" + lemma, encoding="utf-8")
    edit(q / NOTES, "is never empty.\n\\end{lemma}\n\\begin{proof}", "is not empty.\n\\end{lemma}\n\\begin{proof}")
    assert on(q, ann) == f"{NOTES}#lemma:1"


def test_a_note_on_a_label_s_key_stays_on_its_statement_when_an_id_is_added(q: Path) -> None:
    ann = note(q, "lem:first")
    edit(q / NOTES, "\\label{lem:first}", "\\label{dm-0099}\\label{lem:first}")
    assert "dm-0099" in scanned(q).nodes and on(q, ann) == "dm-0099"


def test_a_draft_copied_to_a_second_document_keeps_its_notes_in_its_own_and_its_acceptance_in_both(q: Path) -> None:
    """A note is about a place, in the document it was written in; an acceptance is about a text, and holds wherever that text stands under its label."""
    ann = note(q, "lem:first", "--quote", "never empty")
    ok("accept", "lem:first", "--as", WHO, "--force", "--yes", cwd=q)
    main = (q / "drafting/main.tex").read_text(encoding="utf-8")
    head = main.split("\\begin{document}", 1)[0]
    (q / "drafting/copy.tex").write_text(head + "\\begin{document}\n" + TEXT + "\\end{document}\n", encoding="utf-8")
    r = scanned(q)
    original, copied = f"{NOTES}#lemma:1", "drafting/copy.tex#lemma:1"
    assert "lem:first" not in r.nodes and {original, copied} <= set(r.nodes)
    assert on(q, ann) == original
    keys = json_of("status", "--json", cwd=q)["keys"]
    assert keys[original]["state"] == "accepted" and keys[copied]["state"] == "accepted"
    edit(q / "drafting/copy.tex", "is never empty", "is not empty")
    keys = json_of("status", "--json", cwd=q)["keys"]
    assert keys[original]["state"] == "accepted" and keys[copied]["state"] != "accepted"
    assert on(q, ann) == original


def test_a_dependency_a_label_comes_to_key_leaves_an_acceptance_fresh_and_its_section_unchanged(q: Path) -> None:
    """Records written while a statement was keyed by its place read it by the label that keys it now: no dependency removed or added, and the block holding it hashes as it did."""
    from loom.scan.owntext import key_hash

    outline = q / "drafting/outline.tex"
    blocker = "\\begin{remark}\\label{Lem-First} Like it. \\end{remark}\n"
    edit(outline, "\\section{What is being considered}", blocker + "\\section{What is being considered}")
    before = scanned(q)
    section = next(k for k, n in before.nodes.items() if n.kind == "section" and n.file == NOTES)
    hashed = key_hash(before, section)
    assert f"{NOTES}#lemma:1" in before.nodes
    ok("accept", "thm:second", "--as", WHO, "--force", "--yes", cwd=q)
    assert json_of("status", "--json", cwd=q)["keys"]["thm:second"]["acceptance"]["fresh"] is True
    edit(outline, blocker, "")
    after = scanned(q)
    assert "lem:first" in after.nodes and key_hash(after, section) == hashed
    got = json_of("status", "--json", cwd=q)["keys"]["thm:second"]
    assert got["acceptance"]["fresh"] is True, json.dumps(got)


def test_a_suggested_edit_on_a_statement_s_place_is_kept_on_it_once_a_label_keys_it(q: Path) -> None:
    edit_id = json_of(
        "suggest", f"{NOTES}#lemma:2", "--quote", "stays as it is", "--with", "stays put",
        "--as", "Referee Agent", "--json", cwd=q, env={"AI_AGENT": "1"},
    )["edit"]  # fmt: skip
    edit(q / NOTES, "\\begin{lemma}\nAn unlabelled", "\\begin{lemma}\\label{lem:gadgets}\nAn unlabelled")
    ok("changes", "--keep", edit_id, cwd=q)
    assert "which stays put." in (q / NOTES).read_text(encoding="utf-8")


# ---- after the review ------------------------------------------------------------------------------------------


def test_a_proof_s_note_stays_on_it_when_its_statement_s_label_moves_to_one_with_no_proof(q: Path) -> None:
    """The proof's text never changed; the label's new statement has no proof, so the note goes with its text (K-1)."""
    ann = note(q, "lem:first/proof", "--quote", "holds a point")
    edit(q / NOTES, "\\begin{lemma}\\label{lem:first}\n", "\\begin{lemma}\n")
    edit(q / NOTES, "\\begin{lemma}\nAn unlabelled", "\\begin{lemma}\\label{lem:first}\nAn unlabelled")
    assert on(q, ann) == f"{NOTES}#lemma:1/proof"


def test_a_label_repeated_just_above_keeps_the_note_on_the_statement_holding_its_text(q: Path) -> None:
    """Both copies sit between like neighbours; the one holding the note's very text decides (K-2)."""
    ann = note(q, "lem:first", "--quote", "never empty")
    edit(
        q / NOTES,
        "\\section{Labelled}\n",
        "\\section{Labelled}\n\\begin{lemma}\\label{lem:first}\nAnother lemma under the same label.\n\\end{lemma}\n",
    )
    assert on(q, ann) == f"{NOTES}#lemma:2"


def test_a_file_no_document_reads_changes_no_key_and_holds_no_acceptance(q: Path) -> None:
    """A backup holding a copy of the statements: the paper's labels still key them, and the acceptance stays off the backup (K-3)."""
    ok("accept", "lem:first", "--as", WHO, "--force", "--yes", cwd=q)
    (q / "drafting/scratch.tex").write_text(TEXT, encoding="utf-8")
    r = scanned(q)
    assert "lem:first" in r.nodes and "drafting/scratch.tex#lemma:1" in r.nodes
    keys = json_of("status", "--json", cwd=q)["keys"]
    assert keys["lem:first"]["state"] == "accepted"
    assert keys.get("drafting/scratch.tex#lemma:1", {}).get("state") != "accepted"


def test_accept_refuses_a_region_key(q: Path) -> None:
    from tests.helpers import refused

    refused(
        "accept",
        "thm:second#eq:finite",
        "--as",
        WHO,
        "--force",
        "--yes",
        cwd=q,
        code=2,
        match="is not a statement or proof key",
    )
