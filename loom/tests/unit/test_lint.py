"""Diagnostic codes on the demo: lint's exit code, one test per warning, and the codes `check` and `atomize` report."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from loom.scan.model import Diagnostic, Location
from tests.helpers import edit, exits, json_of, ok, refused, run, the
from tests.unit._quilts import demo


def test_lint_exit_codes(tmp_path: Path) -> None:
    """An id defined twice in a file no document reads is loom's model's, a warning, and lint exits 0; read twice by the document's compile, it is the person's LaTeX, an error, and lint exits 1."""
    q = demo(tmp_path)
    (q / "drafting" / "nodes" / "bad.tex").write_text("\\begin{lemma}\\label{dm-0001}\ndup\n\\end{lemma}\n")
    r = ok("lint", cwd=q)
    assert "warning duplicate-id (model)" in r.output and r.output.splitlines()[0].startswith("2 warnings")
    edit(q / "drafting" / "main.tex", "\\end{document}", "\\input{nodes/bad}\n\\end{document}")
    r = exits(1, "lint", cwd=q)
    assert "error duplicate-id (latex)" in r.output and r.output.splitlines()[0].startswith("1 error")


def _unset_main(q: Path) -> None:
    config = q / "config.toml"
    config.write_text("".join(ln for ln in config.read_text().splitlines(keepends=True) if not ln.startswith("main ")))


def _unreadable_log_line(q: Path) -> None:
    with (q / ".loom/records/annotations" / "log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")


def _log_line_kept_twice(q: Path) -> None:
    log = q / ".loom/records/annotations" / "log.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    created = next(ln for ln in lines if '"event": "created"' in ln)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(created + "\n")


def _missing_main(q: Path) -> None:
    edit(q / "config.toml", 'main = "drafting/main.tex"', 'main = "drafting/missing.tex"')


def _unknown_table(q: Path) -> None:
    with (q / "config.toml").open("a", encoding="utf-8") as fh:
        fh.write("\n[colour]\nscheme = 1\n")


def _mac_roman_node(q: Path) -> None:
    (q / "drafting" / "nodes" / "old.tex").write_bytes(
        b"\\begin{remark}\\label{dm-0099}\nSee pages 989\xd01004.\n\\end{remark}\n"
    )


#: code -> (what provokes it on the demo, what its line must name)
WARNINGS: dict[str, tuple[Callable[[Path], None], str]] = {
    "loom:foreign-annotations": (_unreadable_log_line, ".loom/records/annotations/log.jsonl"),
    "loom:repeated-id": (_log_line_kept_twice, ".loom/records/annotations/log.jsonl"),
    "loom:main-not-found": (_missing_main, "drafting/missing.tex"),
    "loom:main-unset": (_unset_main, "[quilt] main is unset"),
    "loom:unknown-config-key": (_unknown_table, "[colour]"),
    "loom:non-utf8-source": (_mac_roman_node, "drafting/nodes/old.tex"),
}


@pytest.mark.parametrize("code", sorted(WARNINGS))
def test_a_warning_is_reported_on_one_line_naming_where(tmp_path: Path, code: str) -> None:
    q = demo(tmp_path)
    provoke, where = WARNINGS[code]
    provoke(q)
    lint = ok("lint", cwd=q).output.splitlines()  # warnings and infos only: lint exits 0
    heading = the(lint, lambda ln: code in ln.split(), f"{code} group")
    assert heading.endswith("(1)"), heading  # one diagnostic, on the one line under its heading
    line = lint[lint.index(heading) + 1]
    assert where in line, line


def test_check_reports_a_closure_that_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    q = demo(tmp_path)
    monkeypatch.setenv("FAKE_TEX_FAIL_MATCH", "closures/")  # the master compiles; every closure fails
    r = exits(1, "check", "--closures", "all", cwd=q)
    # the verdict leads stdout; a run slow enough to show progress puts it on stderr, never before the verdict
    assert r.stdout.startswith("check failed:")
    assert "loom:closure-failed" in r.stdout and "compiles  drafting/main.tex" in r.stdout


def test_atomize_refuses_a_target_file_that_exists(tmp_path: Path) -> None:
    q = demo(tmp_path)
    (q / "drafting" / "nodes" / "dm-0004.tex").write_text(
        "% a file already sits where the inline node dm-0004 would move\n"
    )
    refused(
        "atomize", "drafting/main.tex", "--to", "drafting/spine.tex", cwd=q, code=1, match="loom:atomize-target-exists"
    )


_DANGLING = "\\ref{nowhere-at-all}"


def test_a_quilt_with_nothing_to_read_says_how_to_begin(tmp_path: Path) -> None:
    """With no document and no landmark, the viewer's how-to-start page is these fixes: a paper being written, a paper being read."""
    q = tmp_path / "empty"
    ok("init", str(q), "--ai", "none", cwd=tmp_path)
    found = [d for d in json_of("lint", "--json", cwd=q)["diagnostics"] if d["code"] == "loom:no-live-document"]
    assert [f["command"] for f in found[0]["fixes"]] == ["loom import FILE", "loom library add FILE"]
    assert "\\documentclass" in found[0]["message"]


def test_a_quilt_of_markdown_lessons_is_not_told_to_begin_a_document(tmp_path: Path) -> None:
    """QF-14: a quilt whose work is Markdown lessons was told nothing is being worked on, with a paper to begin as its next steps; the advice is for a quilt with nothing in it, and what loom and its agents' setup write at the root is not the person's work."""
    q = tmp_path / "course"
    ok("init", str(q), "--ai", "none", cwd=tmp_path)

    def advice() -> list[dict]:  # type: ignore[type-arg]
        return [d for d in json_of("lint", "--json", cwd=q)["diagnostics"] if d["code"] == "loom:no-live-document"]

    for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md"):
        (q / name).write_text("This directory is a quilt managed by loom.\n", encoding="utf-8")
    (said,) = advice()
    assert "nothing is being worked on" not in said["message"] and "LaTeX document" in said["message"]
    (q / "lessons").mkdir()
    (q / "lessons" / "lesson-1.md").write_text("# Lesson 1\n\n- [ ] read chapter 1\n", encoding="utf-8")
    assert advice() == []
    assert ok("status", cwd=q).stdout.strip() == "no keys of yours yet"


def _diag(message: str, line: int, *keys: str, code: str = "loom:detached-annotation") -> Diagnostic:
    return Diagnostic("info", code, message, [Location("drafting/main.tex", line)], list(keys))


def test_one_sentence_about_several_things_is_said_once_with_what_varies_under_it() -> None:
    """T2: the re-grade's `check` printed "N annotation(s) on rl-XXXX no longer match its text" nineteen times; the sentence is the heading's, once, and each line says only what is its own."""
    from loom.cli.diagnostics import groups

    ds = [_diag(f"1 annotation(s) on rl-000{n} no longer match its text", n, f"rl-000{n}") for n in (1, 2, 3)]
    (g,) = groups(ds, None)
    assert g.heading == "info loom:detached-annotation (model): 1 annotation(s) on … no longer match its text"
    assert [i.text for i in g.items] == [f"drafting/main.tex:{n}  rl-000{n}" for n in (1, 2, 3)]
    assert all(i.key is None for i in g.items)  # the text names the key, so it is not said again after it
    assert [i.data["diagnostic"]["message"] for i in g.items] == [d.message for d in ds]  # the JSON keeps each whole


def test_what_varies_is_said_without_the_punctuation_that_joined_it() -> None:
    from loom.cli.diagnostics import groups

    ds = [_diag(f"dm-000{n} refers to dm-0009, which its master does not reach", n, f"dm-000{n}") for n in (2, 3)]
    (g,) = groups(ds, None)
    assert g.heading.endswith(": … refers to dm-0009, which its master does not reach"), g.heading
    assert [i.text for i in g.items] == ["drafting/main.tex:2  dm-0002", "drafting/main.tex:3  dm-0003"]
    ds = [_diag(f"dm-0001 refers to dm-000{n}, which its master does not reach", n, "dm-0001") for n in (2, 3)]
    (g,) = groups(ds, None)
    assert [i.text for i in g.items] == ["drafting/main.tex:2  dm-0002", "drafting/main.tex:3  dm-0003"]


def test_different_sentences_that_begin_alike_are_not_folded_and_a_repeat_is_said_once() -> None:
    from loom.cli.diagnostics import groups

    a = _diag("the history ledger cannot be read in full: line 3 is not JSON", 3)
    b = _diag("the history ledger cannot be read in full: line 4: step 1 does not follow step 2", 4)
    (g,) = groups([a, b, a], None)  # `a` reported twice, as two passes over one file can
    assert g.heading == "info loom:detached-annotation (model)" and [i.text.split("  ", 1)[1] for i in g.items] == [
        a.message,
        b.message,
    ]


def test_a_key_the_message_does_not_name_is_still_said() -> None:
    from loom.cli.diagnostics import item

    assert item(_diag("its basis is not stated", 7, "dm-0002")).key == "dm-0002"
    assert item(_diag("dm-0002 has no basis", 7, "dm-0002")).key is None


def _fixes(q: Path, code: str) -> list[str]:
    diags = json.loads(run("lint", "--json", cwd=q).stdout)["diagnostics"]
    return [f["command"] for d in diags if d["code"] == code for f in d.get("fixes", [])]


def test_every_finding_names_what_resolves_it_and_the_command_works(tmp_path: Path) -> None:
    """T3: `uses-missing`, `detached-annotation` and `unreachable` named no command; each now names one, and the one it names runs in that state."""
    q = demo(tmp_path)
    proof = q / "drafting" / "nodes" / "dm-0003.tex"
    edit(proof, "\\uses{dm-0002}\nBy Lemma", "\\uses{dm-0002}\nAs in Definition~\\ref{def:widget}, by Lemma")
    (q / "drafting" / "nodes" / "stray.tex").write_text("\\begin{remark}\\label{dm-0099}\nStray.\n\\end{remark}\n")
    a = ok(
        "annotate",
        "dm-0002",
        "Which orbits?",
        "--quote",
        "one-point orbits",
        "--type",
        "question",
        "--as",
        "Tester",
        cwd=q,
    ).output.split()[0]
    # an untyped mark only informs, so nothing resolves it and its detachment names no fix
    ok("annotate", "dm-0002", "--quote", "one-point orbits", "--as", "Tester", cwd=q)
    edit(q / "drafting" / "nodes" / "dm-0002.tex", "the one-point orbits", "the orbits of one point")
    assert "add dm-0001 to the \\uses of dm-0003/proof" in _fixes(q, "loom:uses-missing")
    assert _fixes(q, "unreachable") == ["\\input{nodes/stray} in a document, or remove drafting/nodes/stray.tex"]
    assert _fixes(q, "loom:detached-annotation") == [f'loom annotate --resolve {a} "…"']
    ok("annotate", "--resolve", a, "The orbit is still there, reworded.", "--as", "Tester", cwd=q)
    assert _fixes(q, "loom:detached-annotation") == []
    # a fork whose patch was never applied: its node file is unreachable, and the fix says what the patch would do, with no command the cut list removes
    (q / "drafting" / "nodes" / "stray.tex").unlink()
    ok("fork", "dm-0001", "--in", "drafting/main.tex", cwd=q)
    (orphan,) = _fixes(q, "unreachable")[:1]
    diags = json.loads(run("lint", "--json", cwd=q).stdout)["diagnostics"]
    assert (
        orphan.startswith("\\input{nodes/dm-")
        and " in drafting/main.tex in place of dm-0001, whose references there become dm-" in orphan
    )
    assert "loom fork" not in json.dumps(diags)


def _rows(q: Path, code: str) -> list[dict]:  # type: ignore[type-arg]
    """`loom lint --json`'s diagnostics of one code."""
    out: list[dict] = json.loads(run("lint", "--json", cwd=q).stdout)["diagnostics"]  # type: ignore[type-arg]
    return [d for d in out if d["code"] == code]


def test_every_diagnostic_says_whose_it_is_to_fix(tmp_path: Path) -> None:
    """The person's own, or an agent's copy's: Problems in the viewer listed 174 errors and none was in the author's files."""
    q = demo(tmp_path)
    edit(q / "drafting" / "nodes" / "dm-0002.tex", "the one-point orbits", f"the one-point orbits {_DANGLING}")
    ok("draft", "drafting/main.tex", "--ai", "aidoc.tex", cwd=q)
    copy = q / ".loom" / "agents" / "copies" / "aidoc.tex"
    copy.write_text(
        copy.read_text(encoding="utf-8").replace("\\end{document}", "See \\ref{nowhere-in-the-copy}.\n\\end{document}"),
        encoding="utf-8",
    )
    rows = _rows(q, "dangling-link")
    whose = {d["locations"][0]["file"]: d["owner"] for d in rows}
    assert whose == {"drafting/nodes/dm-0002.tex": "person", ".loom/agents/copies/aidoc.tex": "copy"}, rows
    assert all("act" not in f for d in rows for f in d.get("fixes", []))


def test_the_manifest_and_lint_agree_whose_each_diagnostic_is(tmp_path: Path) -> None:
    """The viewer's Problems reads the manifest and `loom lint --json` the scan; one stamp serves both."""
    q = demo(tmp_path)
    edit(q / "drafting" / "nodes" / "dm-0002.tex", "the one-point orbits", f"the one-point orbits {_DANGLING}")
    run("build", cwd=q)
    published = json.loads((q / ".loom" / "cache" / "site" / "manifest.json").read_text(encoding="utf-8"))[
        "diagnostics"
    ]
    assert published and all(d.get("owner") in ("person", "copy") for d in published), published
    linted = json.loads(run("lint", "--json", cwd=q).stdout)["diagnostics"]
    key = lambda d: (d["code"], d["message"])  # noqa: E731
    assert {key(d): d["owner"] for d in linted} == {
        key(d): d["owner"] for d in published if key(d) in {key(x) for x in linted}
    }
    assert _rows(q, "dangling-link")[0]["owner"] == "person"


def test_a_library_result_of_no_work_put_there_by_hand_is_said(tmp_path: Path) -> None:
    """The review's D-23: no write lets a statement or a proof with no `source` into the store (check 11); one a person puts there by hand is an error lint says."""
    from loom.paths import LIBRARY_NODES

    q = demo(tmp_path)
    (q / LIBRARY_NODES).mkdir(parents=True, exist_ok=True)
    (q / LIBRARY_NODES / "dm-0Z01.node").write_text(
        '+++\nschema = 1\nid = "dm-0Z01"\ntaxon = "lemma"\n+++\nA lemma of no work.\n'
    )
    rows = _rows(q, "loom:node-incomplete")
    assert [d["locations"][0]["file"] for d in rows] == [f"{LIBRARY_NODES}/dm-0Z01.node"], rows


def test_every_check_of_the_library_s_store_is_said(tmp_path: Path) -> None:
    """Lint says each `loom:node-*` the store's checks give, not only a result of no work: here a statement pointing at a node the store does not hold."""
    from loom.paths import LIBRARY_NODES

    q = demo(tmp_path)
    (q / LIBRARY_NODES).mkdir(parents=True, exist_ok=True)
    (q / LIBRARY_NODES / "dm-0Z01-ref.node").write_text(
        '+++\nschema = 1\nid = "dm-0Z01-ref"\ntaxon = "reference"\n+++\n@misc{Ref01, title = {A work}}\n'
    )
    (q / LIBRARY_NODES / "dm-0Z02.node").write_text(
        '+++\nschema = 1\nid = "dm-0Z02"\ntaxon = "lemma"\nsource = "dm-0Z01-ref"\nuses = ["dm-0Z09"]\n+++\nBy Lemma~\\ref{dm-0Z09}.\n'
    )
    rows = [
        d for d in json.loads(run("lint", "--json", cwd=q).stdout)["diagnostics"] if d["code"].startswith("loom:node-")
    ]
    assert rows and {d["locations"][0]["file"] for d in rows} == {f"{LIBRARY_NODES}/dm-0Z02.node"}, rows


def test_a_bib_entry_gathering_cannot_keep_is_said_at_its_line_and_nothing_is_written(tmp_path: Path) -> None:
    """The review's M-23: lint runs gathering's checks of the entries the drafts read without writing, and says each it cannot keep where the build's Problems does."""
    from tests.unit.library.test_gather import BAD, BIB, quilt

    root = quilt(tmp_path)
    (root / "refs.bib").write_text(BIB + BAD)
    (root / "main.tex").write_text((root / "main.tex").read_text().replace("\\cite{Jon19}", "\\cite{Jon19,Bad1}"))
    [row] = _rows(root, "loom:bib-entry-refused")
    assert (row["locations"][0]["file"], row["locations"][0]["line"]) == (
        "refs.bib",
        (BIB + BAD).splitlines().index("@article{Bad1,") + 1,
    )
    assert "jnotdefined" in row["message"] and row["owner"] == "person"
    assert not (root / ".loom/library/nodes").exists(), "lint writes no reference"
