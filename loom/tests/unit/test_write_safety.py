"""Writes to the person's files hold up over sequences of acts: seeded runs of suggest, hand edits, Keep, Keep all, Discard and their undo, a tick and a setting, through the write API's handler on a copy of the synthetic quilt, each act checked against the invariants loom promises.

The invariants, checked after every act loom performs: only the files the act names change; the same request sent again changes nothing; every suggested edit's text (each carries a unique word) stands at most once, and a ready one is never already in its file; text the person typed is in a file or in a kept text; and the bytes a write replaced are kept in the history first. The `KNOWN` tests pin damage found by the v0.1 safety study and are expected to fail until it is fixed.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from pathlib import Path
from typing import Any

import pytest

import loom

QUILTS = Path(loom.__file__).resolve().parents[2] / "tests" / "quilts"
AGENT = "Agent Smith"
WORDS = "orbit group action finite widget lemma bound measure compact dense closed map kernel image quotient series limit converges uniformly hence suppose every exists integral norm space basis linear operator".split()


# ---- the quilt and the person -----------------------------------------------------------------------------------


@pytest.fixture
def q(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A copy of the synthetic quilt, edits tracked, with a Markdown task list; the person is `Pat`, and no agent marker is set."""
    for m in ("AI_AGENT", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX_SANDBOX", "CURSOR_AGENT", "GEMINI_CLI"):
        monkeypatch.delenv(m, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    from loom.scan.quilt import save_author

    save_author("Pat")
    root = tmp_path / "q"
    shutil.copytree(QUILTS / "synthetic", root, ignore=shutil.ignore_patterns("build", ".git"))
    (root / "tasks.md").write_text(
        "# Tasks\n\n- [ ] read the first proof again\n- [x] write the second answer\n", encoding="utf-8"
    )
    from loom.config_edit import set_values
    from loom.scan.quilt import load_quilt

    try:
        set_values(load_quilt(root), {"review.track_edits": True})
    except Exception:  # noqa: BLE001 -- a loom from before edit tracking refuses the table
        pass
    call(root, "change-keep", {"all": True})  # the first look
    return root


def call(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    from loom.render.api import ApiError, handle

    try:
        return handle(root, endpoint, dict(body))
    except ApiError as exc:
        return {"error": exc.code}


def suggest(root: Path, key: str, new: str, *more: str) -> str | None:
    from click.testing import CliRunner

    from loom.cli import main

    res = CliRunner().invoke(
        main,
        ["suggest", key, "--with", new, *more, "--as", AGENT, "--json", "--quilt", str(root)],
        env={"AI_AGENT": "1"},
    )
    return str(json.loads(res.stdout)["edit"]) if res.exit_code == 0 else None


def files(root: Path) -> dict[str, bytes]:
    """Every file outside `.loom/`, as bytes."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and ".loom" not in p.relative_to(root).parts
    }


def scan(root: Path) -> Any:
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan as scan_

    return scan_(load_quilt(root))


def waiting(root: Path, result: Any = None) -> list[Any]:
    from loom.pending import pending

    return pending(result or scan(root), "Pat")


def kept_in_history(root: Path, data: bytes) -> bool:
    text = data.decode("utf-8")
    p = root / ".loom/history/texts" / f"{hashlib.sha256(text.encode()).hexdigest()}.md"
    return p.is_file() and p.read_bytes() == data


# ---- the invariants ---------------------------------------------------------------------------------------------


class Run:
    """One sequence: what the harness filed, typed and expects."""

    def __init__(self, root: Path, seed: int) -> None:
        self.root = root
        self.rng = random.Random(seed)
        self.markers: dict[str, str] = {}  # edit id -> its unique word
        self.typed: set[str] = set()
        self.n = 0
        self.problems: list[str] = []
        self.trail: list[str] = []  # what was done, for the failure message

    def word(self, kind: str) -> str:
        self.n += 1
        return f"{kind}{''.join(chr(97 + (self.n * 7 + i * 3) % 26) for i in range(3))}{self.n:03d}x"

    def check(self, act: str, before: dict[str, bytes], allowed: set[str]) -> dict[str, bytes]:
        from loom.records.edits import replay

        after = files(self.root)
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        if not changed <= allowed:
            self.problems.append(f"{act}: changed {sorted(changed - allowed)}, which it does not name")
        for k in changed & set(before):
            if k == "config.toml":
                continue  # no version is kept of the config (SAFE-10): test_saving_settings_keeps_the_config_first
            if before[k] and not kept_in_history(self.root, before[k]):
                self.problems.append(f"{act}: the text of {k} before the write is kept nowhere")
        blob = b"\n".join(after.values()).decode("utf-8", "replace")
        for mk in sorted(self.typed):
            if mk not in blob and not any(
                mk.encode() in p.read_bytes() for p in (self.root / ".loom/history").rglob("*.md")
            ):
                self.problems.append(f"{act}: the person's {mk} is gone and kept nowhere")
        states = {p.id: p.state for p in waiting(self.root) if p.kind == "suggested"}
        status = {e.id: e.status for e in replay(self.root)[0]}
        for eid, mk in self.markers.items():
            n = blob.count(mk)
            if n > 1:
                self.problems.append(f"{act}: {eid}'s text stands {n} times")
            if status.get(eid) == "open" and states.get(eid) == "ready" and n:
                self.problems.append(f"{act}: {eid} is ready to keep while its text already stands")
        return after

    def press(self, endpoint: str, body: dict[str, Any], allowed: set[str]) -> None:
        """Send a request, check it, send it again and check that nothing more changed."""
        before = files(self.root)
        call(self.root, endpoint, body)
        after = self.check(endpoint, before, allowed)
        call(self.root, endpoint, body)
        if files(self.root) != after:
            self.problems.append(f"{endpoint} {body} sent twice changed the files again")


def sentence(rng: random.Random, n: int, mark: str) -> str:
    ws = [rng.choice(WORDS) for _ in range(n)]
    ws.insert(rng.randrange(n + 1), mark)
    return " ".join(ws)


def blocks(root: Path, result: Any) -> list[Any]:
    return [
        n
        for n in result.nodes.values()
        if n.kind in ("environment", "proof")
        and not n.file.startswith(".loom/")
        and any(result.document_role(d) == "person" for d in n.reached_by or [])
    ]


def quote_in(result: Any, node: Any, rng: random.Random) -> str | None:
    """A run of two to four words standing once in the block's own text, inside it (never its `\\begin` or `\\end`)."""
    from loom.records.edits import body_span
    from loom.records.selectors import find_quote
    from loom.records.store import Records

    own = Records.own_pieces(result, node)[0]
    a, b = body_span(own)
    toks = [
        m
        for m in re.finditer(r"\S+", own)
        if a <= m.start() and m.end() <= b and "\\" not in m.group() and "%" not in m.group()
    ]
    for _ in range(20):
        if len(toks) < 3:
            return None
        i = rng.randrange(len(toks) - 1)
        quote = own[toks[i].start() : toks[min(len(toks) - 1, i + rng.randint(1, 3))].end()]
        if len(find_quote(own, quote)) == 1 and not quote.startswith("-"):
            return quote
    return None


def step(run: Run) -> None:
    """One act drawn from the run's generator."""
    rng, root = run.rng, run.root
    op = rng.choices(
        ["suggest", "section", "type", "edit", "keep", "keep_all", "discard", "undo_discard", "tick", "setting"],
        [6, 2, 2, 4, 6, 2, 2, 1, 1, 1],
    )[0]
    run.trail.append(op)
    if (
        run.typed
    ):  # what the person deleted in their own last act was theirs to delete; loom's acts are checked as they happen
        blob = b"\n".join(files(root).values())
        run.typed = {w for w in run.typed if w.encode() in blob}
    if op in ("suggest", "section"):
        if op == "section":  # the hwk1 shape: a problem and its answer after \maketitle
            mk = run.word("sm")
            new = f"\\section*{{Problem {mk}}}\n{sentence(rng, 24, 'and')}\n\\begin{{proof}}[Answer]\n{sentence(rng, 24, 'so')}\n\\end{{proof}}"
            eid = suggest(root, "drafting/main.tex", new, "--quote", "\\maketitle", "--after")
        else:
            result = scan(root)
            node = rng.choice(blocks(root, result))
            quote = quote_in(result, node, rng)
            mk = run.word("sg")
            new = sentence(rng, rng.choice([3, 6, 30]), mk)
            where = rng.choice(["--after", "--before", None]) if quote else rng.choice(["--after", "--before"])
            more = (["--quote", quote] if quote else []) + ([where] if where else [])
            eid = suggest(root, node.key, new, *more)
            run.trail[-1] += f" {node.key} {more} {new[:40]!r}"
        if eid:
            run.markers[eid] = mk
        run.check("suggest", files(root), set())
        return
    if op == "type":  # the person writes an open suggestion of twenty words or more in by hand, then works inside it
        from loom.records.edits import Placed, compose, find

        result = scan(root)
        opens = [
            e for eid in run.markers if (e := find(root, eid)) and e.status == "open" and len(e.with_text.split()) >= 20
        ]
        placed = [(e, pl) for e, pl in compose(result, opens) if isinstance(pl, Placed)]
        if placed:
            e, pl = rng.choice(placed)
            text = result.files[pl.file].text
            mine = run.word("pt")
            typed = pl.text.replace(run.markers[e.id], f"{run.markers[e.id]} {mine}")
            (root / pl.file).write_text(text[: pl.at[0]] + typed + text[pl.at[1] :], encoding="utf-8")
            run.typed.add(mine)
            run.trail[-1] += f" {e.id} by hand into {pl.file}, with {mine} inside"
        return
    if op == "edit":  # the person's own words somewhere in a block
        node = rng.choice(blocks(root, scan(root)))
        text = (root / node.file).read_text(encoding="utf-8")
        at = text.find(" ", node.start + (node.end - node.start) // 2, node.end)
        if at > 0:
            mine = run.word("pt")
            (root / node.file).write_text(text[:at] + f" {mine}" + text[at:], encoding="utf-8")
            run.typed.add(mine)
            run.trail[-1] += f" {mine} into {node.key}"
        return
    pend = waiting(root)
    sug = [p for p in pend if p.kind == "suggested"]
    if op == "keep" and sug:
        p = rng.choice(sug)
        run.trail[-1] += f" {p.id} ({p.state})"
        run.press("change-keep", {"changes": [p.id]}, {p.path})
    elif op == "keep_all":
        run.press("change-keep", {"all": True}, {p.path for p in sug})
    elif op == "discard" and pend:
        p = rng.choice(pend)
        run.trail[-1] += f" {p.id} ({p.kind})"
        run.press("change-discard", {"changes": [p.id]}, {p.path} if p.kind == "edit" else set())
    elif op == "undo_discard":
        from loom.records.edits import replay

        gone = [e.id for e in replay(root)[0] if e.status == "discarded" and e.id in run.markers]
        if gone:
            before = files(root)
            call(root, "change-discard", {"changes": [rng.choice(gone)], "undo": True})
            run.check("undo of a discard", before, set())
    elif op == "tick":
        from loom.tasks import items

        t = items((root / "tasks.md").read_text(encoding="utf-8"))[0]
        before = files(root)
        call(root, "file-tick", {"path": "tasks.md", "task": t.id, "done": not t.done})
        run.check("tick", before, {"tasks.md"})
        t2 = items((root / "tasks.md").read_text(encoding="utf-8"))[0]
        call(root, "file-tick", {"path": "tasks.md", "task": t2.id, "done": t.done})
        if files(root)["tasks.md"] != before["tasks.md"]:
            run.problems.append("tick then untick did not give back tasks.md")
    elif op == "setting":
        before = files(root)
        call(root, "settings-save", {"changes": {"quilt.name": f"widgets {rng.randrange(99)}"}})
        run.check("settings", before, {"config.toml"})


# ---- the tests --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(4))
def test_a_seeded_sequence_of_writes_keeps_the_persons_text(q: Path, seed: int) -> None:
    run = Run(q, seed)
    for _ in range(16):
        step(run)
        assert not run.problems, (run.problems, run.trail)


def test_a_kept_edit_that_opens_a_section_is_written_once_however_often_keep_is_pressed(q: Path) -> None:
    """1ac44c5e: a kept suggestion that opened a section read as not taken, and each press pasted it again."""
    run = Run(q, 0)
    new = "\\section*{Preface}\nThese notes collect what is known about widgets and gadgets.\n\\begin{proof}[Answer]\nNone yet.\n\\end{proof}"
    eid = suggest(q, "drafting/main.tex", new, "--quote", "\\maketitle", "--after")
    run.markers[eid] = "These notes collect"
    run.press("change-keep", {"changes": [eid]}, {"drafting/main.tex"})
    assert not run.problems, run.problems


def test_text_written_in_and_worked_inside_is_not_written_again(q: Path) -> None:
    """2e106a45: the person wrote a long suggestion in and worked inside it; Keep pasted it a second time."""
    run = Run(q, 0)
    new = "These notes collect what is known about widgets, what each lemma rests on, and which questions stay open for a reader to settle on a later pass."
    eid = suggest(q, "drafting/main.tex", new, "--quote", "\\maketitle", "--after")
    run.markers[eid] = "These notes collect"
    main = q / "drafting/main.tex"
    main.write_text(
        main.read_text().replace("\\maketitle", "\\maketitle\n" + new.replace("rests on,", "rests on, with a sketch,")),
        encoding="utf-8",
    )
    run.press("change-keep", {"changes": [eid]}, {"drafting/main.tex"})
    assert not run.problems, run.problems


# Damage the v0.1 safety study found (docs/reports/v0.1-study/raw/safety.md); each test passes once its finding is fixed.


def filed(root: Path, key: str, new: str, quote: str, placement: str) -> str:
    """A suggested edit written into the log directly, as one was before `loom suggest` refused its quote."""
    from loom.clock import stamp, today
    from loom.records.edits import append_new
    from loom.records.selectors import make_selector
    from loom.records.store import Records
    from loom.scan.owntext import key_hash

    result = scan(root)
    own = Records.own_pieces(result, result.nodes[key])[0]
    event = {
        "event": "created",
        "when": stamp(),
        "author": AGENT,
        "kind": "agent",
        "target": key,
        "against": key_hash(result, key),
        "anchor": make_selector(own, quote).to_dict(),
        "with": new,
        "placement": placement,
    }
    return append_new(root, event, today())


def test_an_edit_placed_after_its_blocks_end_is_not_written_twice(q: Path) -> None:
    """`loom suggest` has refused a quote that reaches a block's `\\end{…}` since 72dd301d; an edit filed before that and written in by hand past the `\\end{remark}` is read as taken where it stands, and never written again."""
    node = q / "drafting/nodes/sy-000A.tex"
    new = "A gadget with three points has one fixed point."
    eid = filed(q, "sy-000A", new, "\\end{remark}", "after")
    node.write_text(
        node.read_text().replace("\\end{remark}", "\\end{remark} " + new), encoding="utf-8"
    )  # written in by hand
    assert [p.state for p in waiting(q) if p.id == eid] == ["taken"]
    call(q, "change-keep", {"changes": [eid]})
    assert node.read_text().count(new) == 1


def test_a_section_suggested_after_a_line_and_typed_in_there_by_hand_is_not_written_again(q: Path) -> None:
    """The shape of the study's `r_section_in_block`: the new text opens a section, so once it is in it is the block's child, and is read in the file where it stands."""
    main = q / "drafting/main.tex"
    new = "\\section*{Preface}\nA word before the setup."
    eid = suggest(q, "drafting/main.tex", new, "--quote", "\\maketitle", "--after")
    main.write_text(main.read_text().replace("\\maketitle", "\\maketitle\n" + new, 1), encoding="utf-8")
    assert [p.state for p in waiting(q) if p.id == eid] == ["taken"]
    call(q, "change-keep", {"changes": [eid]})
    assert main.read_text().count("A word before the setup.") == 1


def test_a_short_edit_written_in_and_touched_is_not_written_twice(q: Path) -> None:
    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    node.write_text(
        node.read_text().replace("with the swap.", "with the swap. Each swap fixes no point."), encoding="utf-8"
    )
    call(q, "change-keep", {"changes": [eid]})
    assert node.read_text().count("Each swap fixes") == 1


def test_a_short_edit_written_in_at_the_foot_of_a_body_and_touched_is_not_written_twice(q: Path) -> None:
    """Showcase seed 3031 of the door's spike: a few words suggested at the foot of a body, typed in and worked inside, then written a second time by Keep."""
    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--after")
    node.write_text(node.read_text().replace("{Kre99}.", "{Kre99}.\nEach swap fixes no point."), encoding="utf-8")
    call(q, "change-keep", {"changes": [eid]})
    assert node.read_text().count("Each swap fixes") == 1
    assert [p.state for p in waiting(q) if p.id == eid] == ["unplaced"]


def test_a_save_made_while_keep_runs_is_not_lost(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loom.history.acts as acts

    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    real = acts.keep_versions

    def and_a_save(*args: Any, **kw: Any) -> Any:
        out = real(*args, **kw)
        node.write_text(node.read_text() + "% a line the editor saved\n", encoding="utf-8")
        return out

    monkeypatch.setattr(acts, "keep_versions", and_a_save)
    call(q, "change-keep", {"changes": [eid]})
    assert "a line the editor saved" in node.read_text()


def test_a_save_made_while_keep_runs_moves_the_edit_with_it(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loom.history.acts as acts

    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    real = acts.keep_versions
    saves = [b"% the editor saved\n"]

    def and_a_save_above(*args: Any, **kw: Any) -> Any:
        out = real(*args, **kw)
        if saves:
            node.write_bytes(saves.pop() + node.read_bytes())
        return out

    monkeypatch.setattr(acts, "keep_versions", and_a_save_above)
    assert call(q, "change-keep", {"changes": [eid]})["done"] == [eid]
    text = node.read_text()
    assert text.startswith("% the editor saved\n") and text.count("with the swap. Each swap fixes nothing.") == 1


def test_an_edit_on_a_block_named_by_place_stays_on_that_block(q: Path) -> None:
    main = q / "drafting/main.tex"
    text = main.read_text()
    empty = "\\begin{proof}[Answer]\n\\end{proof}\n"
    main.write_text(
        text.replace("\\end{document}", f"\\section*{{One}}\n{empty}\\section*{{Two}}\n{empty}\\end{{document}}"),
        encoding="utf-8",
    )
    result = scan(q)
    keys = sorted(
        (n.start, k)
        for k, n in result.nodes.items()
        if n.file == "drafting/main.tex" and k.startswith("drafting/main.tex#proof:")
    )
    last = keys[-1][1]  # the empty proof under Two
    a = suggest(q, last, "The answer to two. ANSWER-TWO")
    b = suggest(q, "drafting/main.tex", "\\section*{Zero}\n" + empty.strip(), "--quote", "\\maketitle", "--after")
    call(q, "change-keep", {"changes": [b]})
    call(q, "change-keep", {"changes": [a]})
    after = main.read_text()
    assert after.index("ANSWER-TWO") > after.index("\\section*{Two}")


def test_an_answer_typed_into_a_block_named_by_place_is_not_written_again_once_a_block_is_put_in_before_it(
    q: Path,
) -> None:
    """SAFE-1, shape 5: the answer an agent suggested, typed in by the person, and a problem put in before it; the key then named another block, which did not read as the answer taken, and Keep wrote the answer a second time."""
    main = q / "drafting/main.tex"
    empty = "\\begin{proof}[Answer]\n\\end{proof}\n"
    main.write_text(
        main.read_text().replace(
            "\\end{document}", f"\\section*{{One}}\n{empty}\\section*{{Two}}\n{empty}\\end{{document}}"
        ),
        encoding="utf-8",
    )
    result = scan(q)
    last = max((n.start, k) for k, n in result.nodes.items() if k.startswith("drafting/main.tex#proof:"))[1]
    eid = suggest(q, last, "Four, by ANSWER-TWO.")
    text = main.read_text()
    at = text.rindex("\\begin{proof}[Answer]\n") + len("\\begin{proof}[Answer]\n")
    main.write_text(text[:at] + "Four, by ANSWER-TWO.\n" + text[at:], encoding="utf-8")  # typed in by hand
    main.write_text(
        main.read_text().replace("\\section*{One}", f"\\section*{{Zero}}\n{empty}\\section*{{One}}"), encoding="utf-8"
    )
    call(q, "change-keep", {"changes": [eid]})
    assert main.read_text().count("ANSWER-TWO") == 1


def test_a_suggestion_on_a_sections_body_keeps_its_heading_and_label(q: Path) -> None:
    """CUT-14 of the v0.1 study: Keep replaced `\\section{…}\\label{…}` with the suggested text. This body holds a line bringing in another file, which would go with it, so it is not replaced at all; text at its head goes below the heading."""
    results = q / "drafting/sections/results.tex"
    assert suggest(q, "sy-0200", "The results.") is None
    head = suggest(q, "sy-0200", "Read this first.", "--before")
    assert call(q, "change-keep", {"changes": [head]})["done"] == [head]
    text = results.read_text()
    assert "\\section{Results}\\label{sy-0200}\n\nRead this first.\nThe main results" in text
    assert text.count("\\input{nodes/sy-0003}") == 1


def test_a_suggestion_at_the_foot_of_a_file_whose_text_all_belongs_to_its_section_is_written_once(q: Path) -> None:
    """The integrator's review of step 4: such a file has no text of its own, so Keep writes at the file's end, and the taken test looked for the text nowhere; a sentence typed in there by hand read as not taken, and Keep wrote it a second time."""
    key = "drafting/sections/appendix.tex"
    appendix = q / key
    typed = suggest(q, key, "Zebra closing sentence for this file.", "--after")
    appendix.write_text(
        appendix.read_text().rstrip("\n") + "\nZebra closing sentence for this file.\n", encoding="utf-8"
    )
    assert [p.state for p in waiting(q) if p.id == typed] == ["taken"]
    call(q, "change-keep", {"changes": [typed]})
    assert appendix.read_text().count("Zebra closing") == 1
    # typed in and touched, it is unplaced: the file's own last words were recorded beside where it goes
    touched = suggest(q, key, "Zebra second sentence.", "--after")
    appendix.write_text(appendix.read_text() + "Zebra second sentence, reworded.\n", encoding="utf-8")
    assert [p.state for p in waiting(q) if p.id == touched] == ["unplaced"]
    call(q, "change-keep", {"changes": [touched]})
    assert appendix.read_text().count("Zebra second") == 1


def test_a_replacement_that_trims_its_quote_is_written(q: Path) -> None:
    """The integrator's review of step 4: a replacement whose new text is a part of its quote read as taken the moment it was suggested, and Keep recorded it kept and wrote nothing. Its quote still stands whole, so it is not in."""
    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "the swap.", "--quote", "with the swap.")
    assert [p.state for p in waiting(q) if p.id == eid] == ["ready"]
    assert call(q, "change-keep", {"changes": [eid]})["done"] == [eid]
    text = node.read_text()
    assert "\\{1,2\\}$ the swap." in text and "with the swap." not in text


def test_keep_leaves_line_endings_alone(q: Path) -> None:
    node = q / "drafting/nodes/sy-000A.tex"
    node.write_bytes(node.read_bytes().replace(b"\n", b"\r\n"))
    call(q, "change-keep", {"all": True})
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    call(q, "change-keep", {"changes": [eid]})
    assert node.read_bytes().count(b"\r\n") == 3


def test_saving_settings_keeps_the_config_first(q: Path) -> None:
    config = q / "config.toml"
    old = config.read_bytes()
    call(q, "settings-save", {"changes": {"quilt.name": "widgets"}})
    call(q, "settings-save", {"changes": {"quilt.name": "gadgets"}})
    assert kept_in_history(q, config.read_bytes().replace(b"gadgets", b"widgets")) and kept_in_history(q, old)
    assert config.stat().st_mode & 0o777 == 0o644


def test_restoring_a_version_keeps_every_file_it_overwrites(q: Path) -> None:
    results, node = q / "drafting/sections/results.tex", q / "drafting/nodes/sy-0006.tex"
    results.write_text(
        results.read_text().replace("\\input{nodes/sy-0006}", "% \\input{nodes/sy-0006}"), encoding="utf-8"
    )
    node.write_text(node.read_text() + "% MY-NEW-PARAGRAPH\n", encoding="utf-8")
    kept = node.read_bytes()
    call(q, "history-restore", {"document": "drafting/main.tex", "version": "widgets-v1"})
    assert "MY-NEW-PARAGRAPH" in node.read_text() or kept_in_history(q, kept)


def test_discarding_an_agents_edit_in_a_crlf_file_gives_back_its_bytes(q: Path) -> None:
    f = q / "drafting/sections/appendix.tex"
    f.write_bytes(f.read_bytes().replace(b"\n", b"\r\n"))
    call(q, "change-keep", {"all": True})
    original = f.read_bytes()
    text = original.decode()
    at = text.rfind("the")
    f.write_bytes((text[:at] + "AGENT-WORDS" + text[at + 3 :]).encode())
    ids = [c.id for c in waiting(q) if c.kind == "edit" and c.path == "drafting/sections/appendix.tex"]
    call(q, "change-discard", {"changes": ids})
    assert f.read_bytes() == original


def test_keeping_an_insertion_writes_it_even_when_its_words_stand_elsewhere_in_the_block(q: Path) -> None:
    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "\\cite[Theorem 2.1]{Kre99}", "--quote", "Gadgets exist:", "--after")
    call(q, "change-keep", {"changes": [eid]})
    assert node.read_text().count("\\cite[Theorem 2.1]{Kre99}") == 2


# The door (`loom.writes`, docs/design/writes.md): each writer it carries, cut short by a crash between the journal and the file, leaves the file as it was, and the next act settles it. A crash is a BaseException raised just before the rename, which the door's own failure handling does not catch, so the journal and the temp file are left as a dead process leaves them.


class Died(BaseException):
    """The process dies here."""


def dying_before_the_rename(monkeypatch: pytest.MonkeyPatch, after: int = 0) -> Any:
    """Make a rename of a person's file die, the first or the one after `after` others; returns what puts the real one back."""
    import loom.writes as writes

    real = writes._rename
    count = [0]

    def rename(tmp: Path, target: Path) -> None:
        if count[0] == after:
            raise Died
        count[0] += 1
        real(tmp, target)

    monkeypatch.setattr(writes, "_rename", rename)
    return lambda: monkeypatch.setattr(writes, "_rename", real)


def door(root: Path) -> list[str]:
    """The journal's events, in order."""
    p = root / ".loom/history/writes.jsonl"
    return [json.loads(line)["event"] for line in p.read_text().splitlines()] if p.is_file() else []


def no_temps(root: Path) -> bool:
    return not [p for p in root.rglob("*.loom-tmp") if ".loom" not in p.relative_to(root).parts]


def test_a_tick_cut_short_before_its_write_leaves_the_file_and_ticks_once_after(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.tasks import items

    tasks = q / "tasks.md"
    before = tasks.read_bytes()
    task = items(tasks.read_text())[0].id
    revive = dying_before_the_rename(monkeypatch)
    with pytest.raises(Died):
        call(q, "file-tick", {"path": "tasks.md", "task": task, "done": True})
    revive()
    assert tasks.read_bytes() == before
    assert "error" not in call(q, "file-tick", {"path": "tasks.md", "task": task, "done": True})
    assert tasks.read_bytes() == before.replace(b"- [ ] read", b"- [x] read")
    assert door(q)[-4:] == ["begin", "aborted", "begin", "done"] and no_temps(q)
    assert kept_in_history(q, before)


def test_a_tick_changes_one_character_of_a_crlf_task_list(q: Path) -> None:
    from loom.tasks import items

    tasks = q / "tasks.md"
    tasks.write_bytes(tasks.read_bytes().replace(b"\n", b"\r\n"))
    before = tasks.read_bytes()
    task = items(tasks.read_bytes().decode())[0].id
    assert "error" not in call(q, "file-tick", {"path": "tasks.md", "task": task, "done": True})
    assert tasks.read_bytes() == before.replace(b"- [ ] read", b"- [x] read")


def test_a_task_list_that_is_not_utf8_is_never_ticked(q: Path) -> None:
    tasks = q / "tasks.md"
    tasks.write_bytes("# Tâches\n\n- [ ] relire Schröder\n".encode("latin-1"))
    before = tasks.read_bytes()
    said = call(q, "file-tick", {"path": "tasks.md", "task": "t-1", "done": True})
    assert said == {"error": "not-a-task"} and tasks.read_bytes() == before


def test_settings_cut_short_before_the_write_leave_config_as_it_was(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = q / "config.toml"
    before = config.read_bytes()
    revive = dying_before_the_rename(monkeypatch)
    with pytest.raises(Died):
        call(q, "settings-save", {"changes": {"quilt.name": "widgets"}})
    revive()
    assert config.read_bytes() == before
    assert "error" not in call(q, "settings-save", {"changes": {"quilt.name": "widgets"}})
    assert no_temps(q)
    assert b'name = "widgets"' in config.read_bytes() and kept_in_history(q, before)
    assert door(q)[-4:] == ["begin", "aborted", "begin", "done"]
    assert config.stat().st_mode & 0o777 == 0o644


def an_agents_edit(q: Path) -> tuple[Path, bytes, list[str]]:
    """An agent's in-place edit to the appendix since the person's look: the file, its bytes before, and the change's ids."""
    f = q / "drafting/sections/appendix.tex"
    original = f.read_bytes()
    text = original.decode()
    at = text.rfind("the")
    f.write_bytes((text[:at] + "AGENT-WORDS" + text[at + 3 :]).encode())
    return f, original, [c.id for c in waiting(q) if c.kind == "edit" and c.path == "drafting/sections/appendix.tex"]


def test_a_discard_cut_short_before_its_write_leaves_the_file_and_discards_once_after(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    f, original, ids = an_agents_edit(q)
    edited = f.read_bytes()
    revive = dying_before_the_rename(monkeypatch)
    with pytest.raises(Died):
        call(q, "change-discard", {"changes": ids})
    revive()
    assert f.read_bytes() == edited
    assert call(q, "change-discard", {"changes": ids})["done"] == ids
    assert f.read_bytes() == original and no_temps(q)
    assert door(q)[-4:] == ["begin", "aborted", "begin", "done"]


def test_a_save_made_while_discard_runs_is_kept(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import loom.history.acts as acts

    f, original, ids = an_agents_edit(q)
    real = acts.keep_versions

    def and_a_save(*args: Any, **kw: Any) -> Any:
        out = real(*args, **kw)
        f.write_bytes(b"% the editor saved\n" + f.read_bytes())
        return out

    monkeypatch.setattr(acts, "keep_versions", and_a_save)
    assert call(q, "change-discard", {"changes": ids})["done"] == ids
    assert f.read_bytes() == b"% the editor saved\n" + original


def test_a_put_back_cut_short_before_its_write_leaves_the_file_and_puts_back_once_after(
    q: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt

    f, original, ids = an_agents_edit(q)
    edited = f.read_bytes()
    call(q, "change-discard", {"changes": ids})
    undone = [e for e in load_history(load_quilt(q).history_dir).entries if e.action == "undo"][-1]
    revive = dying_before_the_rename(monkeypatch)
    with pytest.raises(Died):
        call(q, "history-restore", {"path": "drafting/sections/appendix.tex", "text": undone.get("from")})
    revive()
    assert f.read_bytes() == original
    assert "error" not in call(
        q, "history-restore", {"path": "drafting/sections/appendix.tex", "text": undone.get("from")}
    )
    assert f.read_bytes() == edited and no_temps(q)


def test_putting_back_a_text_never_writes_outside_the_quilt(q: Path) -> None:
    stored = next((q / ".loom/history/texts").glob("*.md"))
    for path in ("../outside-the-quilt.txt", "/tmp/outside-the-quilt.txt", "drafting/../../outside-the-quilt.txt"):
        said = call(q, "history-restore", {"path": path, "text": "sha256:" + stored.stem})
        assert said == {"error": "outside-quilt"}, path
    assert not (q.parent / "outside-the-quilt.txt").exists()


def test_a_version_gives_back_the_bytes_it_kept(q: Path) -> None:
    node, other = q / "drafting/nodes/sy-000A.tex", q / "drafting/nodes/sy-0006.tex"
    node.write_bytes(node.read_bytes().replace(b"\n", b"\r\n"))
    other.write_bytes(other.read_bytes() + "% Schröder\n".encode("latin-1"))
    kept = {node: node.read_bytes(), other: other.read_bytes()}
    assert "error" not in call(q, "history-record", {"document": "drafting/main.tex", "name": "bytes"})
    node.write_bytes(node.read_bytes() + b"% later\r\n")
    other.write_bytes(other.read_bytes() + "% später\n".encode("latin-1"))
    assert "error" not in call(q, "history-restore", {"document": "drafting/main.tex", "version": "main-bytes"})
    assert {f: f.read_bytes() for f in kept} == kept


@pytest.mark.parametrize("after", [0, 1])
def test_a_restore_cut_short_is_undone_whole(q: Path, monkeypatch: pytest.MonkeyPatch, after: int) -> None:
    from loom.writes import recover

    node, results = q / "drafting/nodes/sy-000A.tex", q / "drafting/sections/results.tex"
    node.write_text(node.read_text() + "% MINE-A\n", encoding="utf-8")
    results.write_text(results.read_text() + "% MINE-B\n", encoding="utf-8")
    mine = {node: node.read_bytes(), results: results.read_bytes()}
    revive = dying_before_the_rename(monkeypatch, after)
    with pytest.raises(Died):
        call(q, "history-restore", {"document": "drafting/main.tex", "version": "widgets-v1"})
    revive()
    assert recover(q, q / ".loom/history")[0].startswith("undid")
    assert {f: f.read_bytes() for f in mine} == mine and no_temps(q)


def kept_lines(root: Path, eid: str) -> int:
    log = root / ".loom/edits/log.jsonl"
    return sum(
        1
        for line in log.read_text().splitlines()
        if json.loads(line).get("event") == "kept" and json.loads(line)["id"] == eid
    )


def test_two_keeps_of_one_edit_at_once_write_it_once(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    import time

    import loom.pending as pending_

    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    real = pending_._rescan

    def slow(result: Any) -> Any:
        time.sleep(0.5)  # between the write and the records the old Keep made after it
        return real(result)

    monkeypatch.setattr(pending_, "_rescan", slow)
    said: list[dict[str, Any]] = []
    threads = [
        threading.Thread(target=lambda: said.append(call(q, "change-keep", {"changes": [eid]}))) for _ in range(2)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert node.read_text().count("Each swap fixes nothing.") == 1 and kept_lines(q, eid) == 1


def test_two_keeps_in_one_file_at_once_both_land_once(q: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading

    import loom.history.acts as acts

    node = q / "drafting/nodes/sy-000A.tex"
    x = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    y = suggest(q, "sy-000A", "Indeed.", "--quote", "Gadgets exist:", "--before")
    real = acts.keep_versions
    inside, go_on = threading.Event(), threading.Event()

    def held(*args: Any, **kw: Any) -> Any:
        out = real(*args, **kw)
        if threading.current_thread().name == "B" and args[2] == acts.APPLY:
            inside.set()
            go_on.wait(5)  # B holds the door while A plans from a scan made before B writes
        return out

    monkeypatch.setattr(acts, "keep_versions", held)
    said: dict[str, Any] = {}
    b = threading.Thread(target=lambda: said.update(b=call(q, "change-keep", {"changes": [y]})), name="B")
    b.start()
    assert inside.wait(30)
    a = threading.Thread(target=lambda: said.update(a=call(q, "change-keep", {"changes": [x]})), name="A")
    a.start()
    go_on.set()
    a.join()
    b.join()
    text = node.read_text()
    assert said["a"]["done"] == [x] and said["b"]["done"] == [y], said
    assert text.count("Each swap fixes nothing.") == 1 and text.count("Indeed.") == 1


def test_an_edit_in_a_file_that_is_not_utf8_is_never_written(q: Path) -> None:
    node = q / "drafting/nodes/sy-000A.tex"
    node.write_bytes(node.read_text().replace("Gadgets exist:", "Gadgets exist (Schröder, Gödel):").encode("latin-1"))
    before = node.read_bytes()
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    listed = next(p for p in waiting(q) if p.id == eid)
    assert listed.state == "unplaced" and "not UTF-8" in (listed.why or "")
    said = call(q, "change-keep", {"changes": [eid]})
    assert said["done"] == [] and "not UTF-8" in said["refused"][0]["why"]
    assert node.read_bytes() == before


def test_keeping_into_a_symlinked_file_writes_its_target_and_keeps_the_link(q: Path) -> None:
    node = q / "drafting/nodes/sy-000A.tex"
    shared = q / "shared" / "remark.txt"
    shared.parent.mkdir()
    shared.write_bytes(node.read_bytes())
    node.unlink()
    node.symlink_to(shared)
    eid = suggest(q, "sy-000A", "Each swap fixes nothing.", "--quote", "with the swap.", "--after")
    assert call(q, "change-keep", {"changes": [eid]})["done"] == [eid]
    assert node.is_symlink() and shared.read_text().count("Each swap fixes nothing.") == 1


def test_keeping_into_a_file_no_document_reads_keeps_its_bytes_first(q: Path) -> None:
    scratch = q / "drafting/scratch.tex"
    scratch.write_text("\\begin{lemma}\\label{sy-7777}\nMY-OWN-WORDS hold here.\n\\end{lemma}\n", encoding="utf-8")
    before = scratch.read_bytes()
    eid = suggest(q, "sy-7777", "as the count shows", "--quote", "MY-OWN-WORDS")
    assert call(q, "change-keep", {"changes": [eid]})["done"] == [eid]
    assert "as the count shows" in scratch.read_text() and kept_in_history(q, before)


def dying(monkeypatch: pytest.MonkeyPatch, where: str) -> Any:
    """Make Keep die at `where`; returns what puts every real function back."""
    import loom.history.acts as acts
    import loom.writes as writes

    if where == "between the journal and the file":
        return dying_before_the_rename(monkeypatch)
    module, name, test = {
        "before the journal": (acts, "keep_versions", lambda *a, **k: a[2] == acts.APPLY),
        "between the file and its records": (writes, "_append_records", lambda *a, **k: True),
        "between the records and done": (writes, "_append_journal", lambda *a, **k: a[1]["event"] == "done"),
    }[where]
    real = getattr(module, name)

    def die(*args: Any, **kw: Any) -> Any:
        if test(*args, **kw):
            raise Died
        return real(*args, **kw)

    monkeypatch.setattr(module, name, die)
    return lambda: monkeypatch.setattr(module, name, real)


@pytest.mark.parametrize(
    "where",
    [
        "before the journal",
        "between the journal and the file",
        "between the file and its records",
        "between the records and done",
    ],
)
@pytest.mark.parametrize(
    "new",
    [
        "Each swap fixes nothing.",
        "Each swap of the gadget's two points fixes neither, so a gadget with a swap has no fixed point.",
    ],
)
def test_a_keep_cut_short_anywhere_writes_the_edit_once(
    q: Path, monkeypatch: pytest.MonkeyPatch, where: str, new: str
) -> None:
    """The study's crash harness (`docs/reports/v0.1-study/safety-harness/crash/`): a Keep killed at each point, then pressed again."""
    node = q / "drafting/nodes/sy-000A.tex"
    eid = suggest(q, "sy-000A", new, "--quote", "with the swap.", "--after")
    assert eid
    revive = dying(monkeypatch, where)
    with pytest.raises(Died):
        call(q, "change-keep", {"changes": [eid]})
    revive()
    call(q, "change-keep", {"changes": [eid]})
    assert node.read_text().count(new) == 1 and kept_lines(q, eid) == 1 and no_temps(q)
    assert not [p for p in waiting(q) if p.id == eid]
