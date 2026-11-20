"""Section drafts isolate source edits without hiding shared-source consequences."""

import re
from pathlib import Path

import pytest

from loom.adopt import comparison, incorporate, prepare, refresh
from loom.history.ledger import load_history
from loom.history.steps import write_step
from loom.reshape.copy import plan_copy
from loom.scan.quilt import load_quilt, save_author
from loom.scan.scan import scan
from loom.section_drafts import _PICTURE, capture_context, check_overlap
from loom.sync import SyncError

DOC = "drafting/main.tex"
TEXT = r"""\documentclass{article}
\newtheorem{lemma}{Lemma}
\begin{document}
\section{First}\label{zk-0100}
First prose.
\begin{lemma}\label{zk-0001}
First statement.
\end{lemma}
\subsection{Details}\label{zk-0101}
Detail prose.
\section{Second}\label{zk-0200}
Second prose.
\begin{lemma}\label{zk-0002}
Second statement uses \ref{zk-0001}.
\end{lemma}
\end{document}
"""


@pytest.fixture
def quilt(tmp_path: Path):
    from loom.layout import stamp

    save_author("Tester")
    (tmp_path / "drafting").mkdir()
    stamp(tmp_path)
    (tmp_path / ".loom" / "agents" / "copies").mkdir(parents=True)
    (tmp_path / "config.toml").write_text('[quilt]\nname="sections"\nprefix="zk"\nmain="drafting/main.tex"\n')
    (tmp_path / DOC).write_text(TEXT)
    return load_quilt(tmp_path)


def copy(q, key="zk-0100", name="first"):
    result = scan(q)
    h = load_history(q.history_dir)
    target = f".loom/agents/copies/{name}.tex"
    p = plan_copy(result, h, DOC, target, key)
    check_overlap(result, DOC, p.scope)
    context = capture_context(result, DOC)
    (q.root / target).write_text(p.text)
    write_step(
        h,
        "copy",
        "copy-" + name,
        p.freeze,
        "Tester",
        {"from": DOC, "to": target, "bases": p.bases, "scope": p.scope, "suffix": p.suffix, "context": context},
        p.source_text,
        "main.tex",
    )
    return target


def edit(q, path, old, new):
    p = q.root / path
    p.write_text(p.read_text().replace(old, new))


def test_two_scopes_and_qualified_identity(quilt):
    a = copy(quilt)
    b = copy(quilt, "zk-0200", "second")
    assert "zk-0001-ai-01" in (quilt.root / a).read_text()
    assert "zk-0002-ai-02" in (quilt.root / b).read_text()
    assert "Second prose" not in (quilt.root / a).read_text()
    assert "zk-0001}" in (quilt.root / b).read_text()
    assert scan(quilt).nodes["zk-0001-ai-01"].derived_of == "zk-0001"
    with pytest.raises(SyncError, match="overlaps"):
        copy(quilt, "zk-0101", "details")


def test_section_adoption_preserves_outside_and_partial_proposals(quilt):
    a = copy(quilt)
    edit(quilt, a, "First statement.", "Improved statement.")
    edit(quilt, a, "First prose.", "Improved prose.")
    edit(quilt, DOC, "Second prose.", "Author's new second prose.")
    result = scan(quilt)
    data = comparison(result, a)
    assert {r["key"] for r in data["changes"]} == {"zk-0001"}
    p = prepare(result, a, ["zk-0001"])
    incorporate(scan(quilt), a, p["token"])
    assert (quilt.root / DOC).read_text() == TEXT.replace("First statement.", "Improved statement.").replace(
        "Second prose.", "Author's new second prose."
    )
    assert comparison(scan(quilt), a)["document_changed"]
    p = prepare(scan(quilt), a, [], True)
    incorporate(scan(quilt), a, p["token"])
    assert "Improved prose." in (quilt.root / DOC).read_text()
    assert not prepare(scan(quilt), a, [], True)["patch"]


def test_preamble_is_independent(quilt):
    a = copy(quilt)
    edit(quilt, a, "\\begin{document}", "\\newcommand{\\foo}{x}\n\\begin{document}")
    edit(quilt, a, "First prose.", "New prose.")
    p = prepare(scan(quilt), a, [], True)
    assert "newcommand" not in p["patch"]
    incorporate(scan(quilt), a, p["token"])
    p = prepare(scan(quilt), a, [], preamble=True)
    assert "newcommand" in p["patch"]
    incorporate(scan(quilt), a, p["token"])
    assert not comparison(scan(quilt), a)["preamble_changed"]


def test_refresh_retains_scope_namespace_and_proposals(quilt):
    a = copy(quilt)
    edit(quilt, a, "First statement.", "Proposal.")
    edit(quilt, DOC, "Detail prose.", "New author detail.")
    edit(quilt, DOC, "Second prose.", "Unrelated change.")
    refresh(scan(quilt), a)
    text = (quilt.root / a).read_text()
    assert "Proposal." in text and "New author detail." in text
    assert "Unrelated change." not in text and "zk-0001-ai-01" in text
    assert not refresh(scan(quilt), a)["updated"]


def test_root_removal_or_escape_refused(quilt):
    a = copy(quilt)
    edit(quilt, a, "\\end{document}", "\\section{Escaped}Outside.\n\\end{document}")
    with pytest.raises(SyncError, match="outside"):
        comparison(scan(quilt), a)
    assert (quilt.root / DOC).read_text() == TEXT


def test_included_section_preserves_inclusion_and_other_file(quilt):
    (quilt.root / "drafting" / "parts").mkdir()
    start = TEXT.index("\\section{First}")
    end = TEXT.index("\\section{Second}")
    (quilt.root / "drafting/parts/first.tex").write_text(TEXT[start:end])
    (quilt.root / DOC).write_text(TEXT[:start] + "\\input{parts/first}\n" + TEXT[end:])
    before = (quilt.root / DOC).read_text()
    a = copy(quilt)
    edit(quilt, a, "First prose.", "New prose.")
    p = prepare(scan(quilt), a, [], True)
    incorporate(scan(quilt), a, p["token"])
    assert (quilt.root / DOC).read_text() == before
    assert "New prose." in (quilt.root / "drafting/parts/first.tex").read_text()


def test_close_keeps_snapshot_frees_scope_and_reopen_checks_overlap(quilt):
    from loom.draft_lifecycle import close_draft, reopen_draft
    from loom.render.build import build

    a = copy(quilt)
    edit(quilt, a, "First statement.", "Proposal.")
    before = (quilt.root / a).read_bytes()
    assert close_draft(scan(quilt), a, "Tester")["confirmation_required"]
    assert a in scan(quilt).masters
    assert close_draft(scan(quilt), a, "Tester", confirmed=True)["closed"]
    result = scan(quilt)
    assert a not in result.masters
    assert "zk-0001-ai-01" not in result.nodes
    manifest = build(quilt).manifest
    closed = next(m for m in manifest["masters"] if m["path"] == a)
    assert closed["closed"] and "zk-0001-ai-01" in closed["closed_keys"]
    assert "Proposal." in (quilt.root / ".loom/cache/site" / closed["fragment"]).read_text()
    assert (quilt.root / a).read_bytes() == before
    b = copy(quilt, name="replacement")
    with pytest.raises(SyncError, match="overlaps"):
        reopen_draft(scan(quilt), a, "Tester")
    close_draft(scan(quilt), b, "Tester", confirmed=True)
    assert not reopen_draft(scan(quilt), a, "Tester")["closed"]
    assert a in scan(quilt).masters


@pytest.mark.tex
def test_saved_context_stays_readable_until_refresh(quilt):
    """A section draft is made by TeX in its saved context: a reference out of it names the saved paper, which stays readable until the draft is refreshed."""
    from loom.drafts import copy_states
    from loom.render.build import build
    from loom.section_drafts import pinned_scan

    a = copy(quilt, "zk-0200", "second")
    edit(quilt, DOC, "First statement.", "Changed outside scope.")
    saved = pinned_scan(scan(quilt), a)
    assert "First statement." in saved.files[DOC].text
    state = copy_states(scan(quilt), load_history(quilt.history_dir))[0]
    assert not state.stale
    manifest = build(quilt).manifest
    master = next(m for m in manifest["masters"] if m["path"] == a)
    assert master["context_changed"]
    html = (quilt.root / ".loom/cache/site" / master["fragment"]).read_text()
    assert "data-context-document=" in html
    context = next(m for m in manifest["masters"] if m["path"] == master["context_document"])
    assert "First statement." in (quilt.root / ".loom/cache/site" / context["fragment"]).read_text()
    refresh(scan(quilt), a)
    assert "Changed outside scope." in pinned_scan(scan(quilt), a).files[DOC].text


def test_choices_cas_and_only_changed_choices_invalidated(quilt):
    from loom.adopt import decide, decisions

    a = copy(quilt)
    edit(quilt, a, "First statement.", "Proposal.")
    result = scan(quilt)
    data = comparison(result, a)
    row = decide(result, a, ["zk-0001"], False, data["fingerprint"], "Tester", revision=0)
    assert row["revision"] == 1
    with pytest.raises(SyncError, match="another tab"):
        decide(result, a, [], False, data["fingerprint"], "Tester", revision=0)
    edit(quilt, DOC, "Second prose.", "Unrelated.")
    assert decisions(scan(quilt), a, "Tester")["keys"] == ["zk-0001"]
    edit(quilt, a, "Proposal.", "Different proposal.")
    choices = decisions(scan(quilt), a, "Tester")
    assert choices["keys"] == [] and choices["invalidated"] == ["zk-0001"]


def test_missing_preamble_definition_requires_explicit_choice(quilt):
    a = copy(quilt)
    edit(quilt, a, "\\begin{document}", "\\newcommand{\\newterm}{x}\n\\begin{document}")
    edit(quilt, a, "First statement.", r"Now $\newterm$.")
    with pytest.raises(SyncError, match="Include Preamble"):
        prepare(scan(quilt), a, ["zk-0001"])
    p = prepare(scan(quilt), a, ["zk-0001"], preamble=True)
    assert "newcommand" in p["patch"]


def test_a_macro_the_paper_already_has_is_not_asked_for(quilt):
    """Redefining a macro, or using one a loaded `.sty` defines, adds nothing the paper lacks, so the preamble isn't asked for (plan 0.25.2)."""
    (quilt.root / "drafting/defs.sty").write_text("\\newcommand{\\fromsty}{y}\n")
    edit(quilt, DOC, "\\begin{document}", "\\usepackage{defs}\n\\newcommand{\\term}{t}\n\\begin{document}")
    a = copy(quilt)
    edit(quilt, a, "\\begin{document}", "\\renewcommand{\\term}{T}\n\\begin{document}")
    edit(quilt, a, "First statement.", r"Now $\term$ and $\fromsty$.")
    assert prepare(scan(quilt), a, ["zk-0001"])["patch"]


def test_source_move_keeps_scope_and_current_destination(quilt):
    from tests.helpers import ok

    a = copy(quilt)
    edit(quilt, a, "First statement.", "Moved proposal.")
    ok("mv", DOC, "drafting/renamed.tex", cwd=quilt.root)
    result = scan(load_quilt(quilt.root))
    p = prepare(result, a, ["zk-0001"])
    assert p["source"] == "drafting/renamed.tex"
    incorporate(result, a, p["token"])
    assert "Moved proposal." in (quilt.root / "drafting/renamed.tex").read_text()


def test_shared_node_in_disjoint_scopes_changes_once(quilt):
    (quilt.root / "drafting" / "nodes").mkdir()
    node = TEXT[TEXT.index("\\begin{lemma}") : TEXT.index("\\end{lemma}") + len("\\end{lemma}")]
    (quilt.root / "drafting/nodes/shared.tex").write_text(node)
    text = TEXT.replace(node, "\\input{nodes/shared}")
    text = text.replace("Second prose.", "Second prose.\n\\input{nodes/shared}")
    (quilt.root / DOC).write_text(text)
    a = copy(quilt)
    b = copy(quilt, "zk-0200", "second")
    edit(quilt, a, "First statement.", "Shared proposal.")
    p = prepare(scan(quilt), a, ["zk-0001"])
    incorporate(scan(quilt), a, p["token"])
    assert (quilt.root / DOC).read_text() == text
    assert "Shared proposal." in (quilt.root / "drafting/nodes/shared.tex").read_text()
    assert any(
        row["key"] == "zk-0001" and "Shared proposal." in row["current"]
        for row in comparison(scan(quilt), b)["changes"]
    )


@pytest.mark.tex
def test_section_preview_compiles_in_saved_paper_context(quilt):
    from loom.section_drafts import preview_in_paper

    a = copy(quilt, "zk-0200", "second")
    preview = preview_in_paper(scan(quilt), a)
    assert (quilt.root / ".loom/cache/site" / preview["pdf"]).read_bytes().startswith(b"%PDF")
    assert (quilt.root / DOC).read_text() == TEXT


def test_close_draft_with_removed_scope_root_keeps_its_text(quilt):
    from loom.draft_lifecycle import close_draft

    a = copy(quilt)
    edit(quilt, a, "\\label{zk-0100-ai-01}", "")
    assert close_draft(scan(quilt), a, "Tester")["confirmation_required"]
    close_draft(scan(quilt), a, "Tester", confirmed=True)
    assert a not in scan(quilt).masters


def test_local_style_edit_invalidates_exact_preview(quilt):
    (quilt.root / "drafting" / "local.sty").write_text("\\newcommand{\\localterm}{x}\n")
    edit(quilt, DOC, "\\begin{document}", "\\usepackage{local}\n\\begin{document}")
    a = copy(quilt)
    edit(quilt, a, "First statement.", "Changed statement.")
    p = prepare(scan(quilt), a, ["zk-0001"])
    (quilt.root / "drafting" / "local.sty").write_text("\\newcommand{\\localterm}{y}\n")
    with pytest.raises(SyncError, match="context changed"):
        incorporate(scan(quilt), a, p["token"])


def test_scoped_cli_dry_runs_write_no_source_or_context(quilt):
    from tests.helpers import json_of

    def contents():
        return {str(p.relative_to(quilt.root)): p.read_bytes() for p in quilt.root.rglob("*") if p.is_file()}

    before = contents()
    proposed = json_of("draft", DOC, "--ai", "first", "--section", "zk-0100", "--dry-run", "--json", cwd=quilt.root)
    assert proposed["dry_run"] and contents() == before
    a = copy(quilt)
    edit(quilt, DOC, "Second prose.", "Updated outside context.")
    before = contents()
    proposed = json_of("ai", "refresh", a, "--dry-run", "--json", cwd=quilt.root)
    assert proposed["dry_run"] and proposed["written"]
    assert contents() == before


def test_unselected_preamble_names_its_own_flag(quilt):
    from loom.adopt import nothing_to_incorporate

    a = copy(quilt)
    edit(quilt, a, "\\begin{document}", "\\newcommand{\\newword}{word}\n\\begin{document}")
    preview = prepare(scan(quilt), a, [], False, preamble=False)
    assert not preview["patch"]
    assert "--preamble-changes" in nothing_to_incorporate(preview)


def test_a_gone_annotation_is_re_anchored_once_per_build_and_again_when_its_block_changes(quilt, monkeypatch):
    """The section draft carries the build's own marks, so a build resolves the annotations and finds a lost one's place once; the place is worked out again only when the texts it is found between change."""
    import loom.render.build as build_module
    import loom.render.versions as versions
    from loom.render.build import build
    from tests.helpers import ok

    a = copy(quilt)
    said = ok(
        "annotate",
        "zk-0001-ai-01",
        "Which?",
        "--quote",
        "First statement",
        "--type",
        "note",
        "--as",
        "A. Author",
        cwd=quilt.root,
    )
    ann = said.output.split()[0]
    gone = f'<mark class="annotation gone" data-annotation="{ann}"></mark>'
    resolved, placed = [], []
    monkeypatch.setattr(versions, "_ALIGNED", {})
    real_gone, real_aligned = build_module.gone_annotations, versions._aligned
    monkeypatch.setattr(build_module, "gone_annotations", lambda *a: resolved.append(1) or real_gone(*a))
    monkeypatch.setattr(versions, "_aligned", lambda *a: placed.append(a) or real_aligned(*a))

    def built() -> list[str]:
        m = build(quilt).manifest
        master = next(x for x in m["masters"] if x["path"] == a)
        return [
            (quilt.root / ".loom/cache/site" / f).read_text()
            for f in (master["fragment"], m["nodes"]["zk-0001-ai-01"]["fragment"])
        ]

    edit(quilt, a, "First statement.", "Initial claim.")
    assert all(gone + "Initial claim." in html for html in built())
    assert (len(resolved), len(placed)) == (1, 1)
    assert all(gone + "Initial claim." in html for html in built())
    assert (len(resolved), len(placed)) == (2, 1)
    edit(quilt, a, "Initial claim.", "Some initial claim.")
    assert all(gone + "Some initial claim." in html for html in built())
    assert (len(resolved), len(placed)) == (3, 2)


def typeset(root, base, preamble, texts, cache_dir, envs, engine, aux, timeout, math="mathjax"):
    """One TeX4ht run as a working TeX4ht makes it, as far as these tests read it: prose a paragraph of its words marked as typeset, with each figure it includes as the PDF TeX4ht names for loom to convert; a statement refused, as TeX refuses a text, so it stands as its source."""
    from html import escape

    from loom.render.snippets import Snippet, _Run

    def made(text):
        if text.lstrip().startswith("\\begin"):
            return Snippet(None, "statements are not typeset here")
        words = escape(" ".join(re.sub(r"\\includegraphics\{[^}]*\}", "", text).split()))
        figures = "".join(f'<img src="{f}.pdf" alt="" />' for f in re.findall(r"\\includegraphics\{([^}]*)\}", text))
        return Snippet(f'<p data-at=":1">Typeset: {words}{figures}</p>')

    return _Run({i: made(text) for i, text in texts}, None, True)


@pytest.fixture
def drafting(monkeypatch):
    """An empty memo of section drafts' renderings, a count of the renderings actually made, and a TeX4ht that works (`typeset`): the test tier's makes no page, which no rendering may keep."""
    import loom.render.snippets as snippets
    import loom.section_drafts as drafts

    made = []
    real = drafts._draft
    monkeypatch.setattr(drafts, "_draft", lambda *a: made.append(1) or real(*a))
    monkeypatch.setattr(snippets, "_one_run", typeset)
    drafts._drafted.clear()
    return made


def drafted(q, path):
    """The published fragments of the section draft at `path` and of its saved paper, after a build of `q` as it is now."""
    from loom.paths import SITE
    from loom.render.build import build

    manifest = build(q).manifest
    master = next(m for m in manifest["masters"] if m["path"] == path)
    context = next(m for m in manifest["masters"] if m["path"] == master["context_document"])
    return tuple((q.root / SITE / m["fragment"]).read_text() for m in (master, context))


@pytest.mark.parametrize(
    "changed", ["the draft", "its ledger entry", "a file of its saved context", "the config", "whether TeX4ht is here"]
)
def test_a_section_draft_is_rendered_once_and_again_when_any_input_changes(quilt, drafting, changed, monkeypatch):
    """A section draft is rendered in its saved context by TeX; a build renders it once for the draft's text, its ledger entry, the saved context's files, the config and whether TeX4ht is here, and again when any of them changes."""
    import shutil

    import loom.section_drafts as drafts
    from loom.section_drafts import metadata

    if changed == "its ledger entry":
        # a second paper in the draft's directory, saved with its context
        (quilt.root / "drafting" / "other.tex").write_text(TEXT.replace("First prose.", "Another paper's prose."))
    a = copy(quilt)
    first = drafted(quilt, a)
    assert drafted(quilt, a) == first and len(drafting) == 1
    q = quilt
    if changed == "the draft":
        edit(quilt, a, "First statement.", "Initial claim.")
    elif changed == "its ledger entry":
        # the entry alone names another of the saved papers as the draft's context; no file changes
        read = drafts.metadata

        def other(result, copy):
            meta = read(result, copy)
            return {**meta, "context": {**meta["context"], "source": "drafting/other.tex"}}

        monkeypatch.setattr(drafts, "metadata", other)
    elif changed == "a file of its saved context":
        saved = quilt.root / metadata(scan(quilt), a)["context"]["path"] / DOC
        saved.write_text(saved.read_text().replace("Second prose.", "Second prose, changed."))
    elif changed == "the config":
        (quilt.root / "config.toml").write_text((quilt.root / "config.toml").read_text() + 'home = "README.md"\n')
        q = load_quilt(quilt.root)
    else:
        which = shutil.which
        monkeypatch.setattr(shutil, "which", lambda name, *a, **k: None if name == "make4ht" else which(name, *a, **k))
    again = drafted(q, a)
    assert len(drafting) == 2
    drafts._drafted.clear()
    assert again == drafted(q, a)
    # no setting changes a draft's rendering today, and what TeX made of the draft is in the snippet cache, so neither changes what is published; each is read in the rendering, so it is made again
    assert again != first or changed in ("the config", "whether TeX4ht is here")


def test_a_section_draft_is_not_rendered_again_after_an_edit_elsewhere_or_a_note(quilt, drafting):
    """A word changed in the paper outside the draft's saved context, or a note written on the draft, renders nothing of the draft again; the note's mark is placed on what was rendered."""
    from tests.helpers import ok

    a = copy(quilt)
    first = drafted(quilt, a)
    edit(quilt, DOC, "Second prose.", "Second prose, changed.")
    assert drafted(quilt, a) == first
    ok(
        "annotate",
        "zk-0001-ai-01",
        "Which?",
        "--quote",
        "First statement",
        "--type",
        "note",
        "--as",
        "A. Author",
        cwd=quilt.root,
    )
    marked = drafted(quilt, a)
    assert 'class="annotation"' in marked[0] and 'class="annotation"' not in first[0]
    assert len(drafting) == 1


@pytest.mark.parametrize("stopped", ["TeX4ht made no page: it said nothing", "make4ht timed out after 600 seconds"])
def test_a_section_draft_rendered_while_tex_failed_for_the_machines_sake_is_typeset_at_the_next_build(
    quilt, drafting, stopped, monkeypatch
):
    """A TeX run that stopped with nothing said against a text, or ran out of time, is the machine's and the snippet cache remembers nothing of it: the draft shows as its source for that build alone, and the next build, after a change elsewhere, typesets it."""
    import loom.render.snippets as snippets
    import loom.section_drafts as drafts
    from loom.render.snippets import _Run

    a = copy(quilt)
    monkeypatch.setattr(snippets, "_one_run", lambda *args: _Run({}, None, False, stopped))
    assert "Typeset" not in drafted(quilt, a)[0]
    monkeypatch.setattr(snippets, "_one_run", typeset)
    edit(quilt, DOC, "Second prose.", "Second prose, changed.")
    again = drafted(quilt, a)
    assert "Typeset: " in again[0]
    drafts._drafted.clear()
    assert again == drafted(quilt, a)


def test_a_figure_no_tool_converted_in_a_section_draft_is_converted_at_the_next_build(quilt, drafting, monkeypatch):
    """A figure the draft includes that no tool on the machine converts shows unconverted for that build alone: a converter installed since converts it at the next build, after a change elsewhere."""
    import shutil

    import loom.section_drafts as drafts

    edit(quilt, DOC, "First prose.", "First prose. \\includegraphics{fig}")
    (quilt.root / "drafting" / "fig.pdf").write_bytes(b"%PDF-1.4 a figure\n")
    a = copy(quilt)
    which = shutil.which
    monkeypatch.setattr(
        shutil,
        "which",
        lambda name, *args, **kw: None if name in ("pdftocairo", "dvisvgm") else which(name, *args, **kw),
    )
    assert 'src="fig.pdf"' in drafted(quilt, a)[0]
    monkeypatch.setattr(shutil, "which", which)
    edit(quilt, DOC, "Second prose.", "Second prose, changed.")
    again = drafted(quilt, a)
    assert re.search(r'src="svg/[0-9a-f]{16}\.svg"', again[0])
    drafts._drafted.clear()
    assert again == drafted(quilt, a)


def test_a_forced_build_in_another_process_is_not_undone_by_a_rendering_from_before_it(quilt, drafting, monkeypatch):
    """`loom build --force` in a terminal tries again every text TeX refused, here for a package installed since; the next build here, after a note on the draft, renders the draft again rather than putting back the refusal it remembers."""
    import subprocess
    import sys

    import loom.render.snippets as snippets
    from loom.render.snippets import Snippet, _Run
    from tests.helpers import ok

    def refusing(*args):
        made = typeset(*args)
        return _Run(
            {
                i: Snippet(None, "File `reviewpkg.sty' not found.") if "reviewpkg" in t else made.pieces[i]
                for i, t in args[3]
            },
            None,
            True,
        )

    edit(quilt, DOC, "First prose.", "First prose. \\reviewpkg")
    a = copy(quilt)
    monkeypatch.setattr(snippets, "_one_run", refusing)
    assert not re.search(r"Typeset: [^<]*First prose", drafted(quilt, a)[0])
    # the package installed: TeX would make the text now, and the refusal stays remembered until a forced build
    monkeypatch.setattr(snippets, "_one_run", typeset)
    forced = subprocess.run(
        [sys.executable, "-m", "loom", "build", "--force"], cwd=quilt.root, capture_output=True, text=True, timeout=300
    )
    assert forced.returncode in (0, 1), forced.stdout + forced.stderr
    ok(
        "annotate",
        "zk-0001-ai-01",
        "Which?",
        "--quote",
        "First statement",
        "--type",
        "note",
        "--as",
        "A. Author",
        cwd=quilt.root,
    )
    marked = drafted(quilt, a)[0]
    assert re.search(r"Typeset: [^<]*First prose", marked) and 'class="annotation"' in marked


def test_a_section_draft_publishes_its_pictures_again_when_the_site_is_removed(quilt, drafting):
    """`.loom/cache/` may be deleted at any time: with the site removed under a live server, the next build, after a change elsewhere, publishes every picture the draft names."""
    import shutil

    from loom.paths import SITE

    edit(quilt, DOC, "First prose.", "First prose. \\includegraphics{fig}")
    (quilt.root / "drafting" / "fig.pdf").write_bytes(b"%PDF-1.4 a figure\n")
    a = copy(quilt)
    first = drafted(quilt, a)[0]
    named = _PICTURE.findall(first)
    assert named and all((quilt.root / SITE / n).is_file() for n in named)
    shutil.rmtree(quilt.root / SITE)
    edit(quilt, DOC, "Second prose.", "Second prose, changed.")
    assert drafted(quilt, a)[0] == first
    assert all((quilt.root / SITE / n).is_file() for n in named)


def test_a_section_draft_is_rendered_again_when_the_cache_it_was_made_from_is_removed(quilt, drafting):
    """With the snippet cache removed under a live server, the next build renders the draft again, so the build's index names only files that are there."""
    import shutil

    from loom.lifetimes import read_index
    from loom.paths import BLOCKS, CACHE

    a = copy(quilt)
    first = drafted(quilt, a)
    shutil.rmtree(quilt.root / BLOCKS)
    edit(quilt, DOC, "Second prose.", "Second prose, changed.")
    assert drafted(quilt, a) == first and len(drafting) == 2
    index = read_index(quilt.root)
    named = {n for n in [*index.beside, *(n for ns in index.uses.values() for n in ns)] if n.startswith("blocks/")}
    assert named and all((quilt.root / CACHE / n).exists() for n in named)


def test_what_a_remembered_section_draft_hands_out_is_the_builds_own(quilt, drafting):
    """A build that changes the macro sets it published, or the nodes it was handed, changes nothing the next build publishes."""
    import loom.section_drafts as drafts
    from loom.render.build import build

    edit(quilt, DOC, "\\newtheorem{lemma}{Lemma}", "\\newtheorem{lemma}{Lemma}\n\\newcommand{\\R}{\\mathbb{R}}")
    a = copy(quilt)
    sets = build(quilt).manifest["macros"]["sets"]
    master = next(m for m in build(quilt).manifest["masters"] if m["path"] == a)
    published = {k: v for k, v in sets.items() if k in (master["macros"], "context:" + master["context_document"])}
    assert len(published) == 2 and all(published.values())
    for macros in published.values():
        macros[0]["changed"] = True
        macros.append({"name": "added"})
    (entry,) = (drafts._drafted.get(k, lambda: None) for k in drafts._drafted)
    with pytest.raises(TypeError):
        entry.nodes["zk-0001"] = "changed"
    again = build(quilt).manifest["macros"]["sets"]
    drafts._drafted.clear()
    fresh = build(quilt).manifest["macros"]["sets"]
    assert len(drafting) == 2
    assert {k: again[k] for k in published} == {k: fresh[k] for k in published}
