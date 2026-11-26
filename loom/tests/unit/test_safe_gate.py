"""The Safe gate's check (`docs/plans/0.32-v0.1.md`, the Safe gate): seeded sequences of acts on copies of the three committed quilts, each paired with a stand-in Overleaf project and holding an agent's document, checked for damage after every act and for the exact bytes after every undo.

The acts, each through loom's own entry point and never a file written around it: an agent's document taken in (`adopt.incorporate`), undone by restoring the version it stamped (`history-restore`); an update from Overleaf (`overleaf-update`) after a colleague pushed to a local bare repository, sometimes over the person's own change there; a library PDF filed as a work of its own or on a work with none, unfiled, and the last such act undone (`library.intake`); a Keep and its undo (`change-keep`, `change-undo`); and single acts of `test_write_safety`'s sequence (suggest, typing, Keep all, Discard and its undo, a tick, a setting).

No damage, a refused act being none, is `Run.check` after every act, with three more: an agent's words taken in stand at most once, an update leaves the mirror holding the project's bytes, and a library act touches no file of the person's and leaves every document a reference names in the store. Exact bytes: an undo of a Keep in a file as the Keep left it gives back the bytes before it, and elsewhere takes out that Keep's words at one place and nothing else; restoring an adoption's version gives back each file it wrote; undoing the last library act leaves the library's nodes and store as before it. The library writes loom's own records, outside the door (`docs/design/writes.md`), so the gate holds it to the person's files and to its undo; the mirror is read-only outside an update, which has no undo in loom.

`LOOM_GATE_SEEDS=A:B` runs seeds A to B-1 on each quilt in place of the everyday 0:4; a failure names its seed.
"""

from __future__ import annotations

import io
import os
import re
import shutil
from pathlib import Path

import pytest

from loom.library import documents
from loom.library.intake import IntakeRefused, Item, Library, receive, take, undo, unfile
from loom.paths import LIBRARY
from tests.helpers import ok
from tests.unit._mirror import PERSON, colleague, edit, overleaf
from tests.unit._pdfs import lines_pdf
from tests.unit.test_write_safety import AGENT, QUILTS, Run, call, files, scan, sentence, step, waiting

#: The three committed quilts the gate runs on.
QUILT_NAMES = ("demo", "showcase", "synthetic")
#: The everyday seeds, or `LOOM_GATE_SEEDS=A:B`.
SEEDS = range(*(int(n) for n in os.environ.get("LOOM_GATE_SEEDS", "0:4").split(":")))
STEPS = 14
#: The Overleaf stand-in's project and the folder it is mirrored in.
PROJECT, MIRROR = "6a0b1c2d3e4f5a6b7c8d9e0f", "overleaf"
PROJECT_FILES = {
    "main.tex": "\\documentclass{article}\n\\newtheorem{lemma}{Lemma}\n\\begin{document}\nThe mirrored paper opens here.\n\n\\begin{lemma}\nEvery mirrored widget has a bound.\n\\end{lemma}\n\n\\input{part}\n\nIt closes here.\n\\end{document}\n",
    "part.tex": "A part of the mirrored paper, its first line.\n\nIts second paragraph, written in Overleaf.\n",
}
COPIES = ".loom/agents/copies"
ME = "Pat"


class Gate(Run):
    """One sequence on one quilt: `Run`'s record of edits and typed words, with what each Keep, adoption and library act left, for its undo."""

    def __init__(self, root: Path, seed: int, work: Path, bare: Path, main: str, copy: str) -> None:
        super().__init__(root, seed)
        self.work = work  # outside the quilt: PDFs before they are dropped, and the colleague's clone
        self.kept: dict[str, tuple[str, bytes, bytes]] = {}  # edit id -> (file, its bytes before the Keep, after)
        self.adoptions: list[tuple[str, str, dict[str, bytes | None]]] = []  # (document, landmark, each file before)
        self.taken: set[str] = set()  # words an agent wrote into its copy and loom took in
        self.library: list[tuple[str, str, dict[str, bytes]]] = []  # (drop, act, the library before it), newest last
        self.clone = colleague(work, bare)
        self.main, self.copy = main, copy


def library_files(root: Path) -> dict[str, bytes]:
    """The library's nodes and store, as bytes; its log is append-only and an undo is a line of its own."""
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / LIBRARY).rglob("*") if p.is_file()}


def held_whole(root: Path) -> list[str]:
    """Each document a reference names that the store does not hold."""
    return [
        f"{ref} names a {which} the store does not hold"
        for ref, node in Library.read(root).refs.items()
        for which in ("pdf", "tex")
        if (d := getattr(node, which)) is not None and not documents.held(root, d, which)
    ]


def gate_quilt(tmp_path: Path, name: str) -> tuple[Path, str, Path, str]:
    """A copy of the committed quilt `name` with a task list, paired with a stand-in Overleaf project in `overleaf/`, an agent's document of its main document (the quilt's own, or one drafted now), and the person's first look; with the main document, the project's bare repository and the agent's document."""
    from loom.looks import take as look
    from loom.overleaf import pair
    from loom.scan.quilt import load_quilt, save_author

    save_author(ME)
    root = tmp_path / name
    shutil.copytree(QUILTS / name, root, ignore=shutil.ignore_patterns("build", ".git"))
    (root / "tasks.md").write_text(
        "# Tasks\n\n- [ ] read the first proof again\n- [x] write the second answer\n", encoding="utf-8"
    )
    bare = overleaf(tmp_path, PROJECT_FILES, PROJECT)
    pair(load_quilt(root), PROJECT, MIRROR, "main.tex", [PERSON[1]])
    main = load_quilt(root).config.main
    copies = sorted((root / COPIES).glob("*.tex"))
    if not copies:
        ok("draft", main, "--ai", "gate", "--as", AGENT, "--quilt", root, env={"AI_AGENT": "1"})
    copy = (copies[0] if copies else root / COPIES / "gate.tex").relative_to(root).as_posix()
    look(load_quilt(root), ME)
    return root, main, bare, copy


# ---- the acts the gate adds to the write-safety sequence, each saying whether it found anything to do -------------


def write(g: Gate) -> bool:
    """One act of `test_write_safety`'s own sequence, which names itself in the trail."""
    g.trail.pop()
    step(g)
    return True


def keep(g: Gate) -> bool:
    """Keep one suggested edit, keeping the bytes of its file before and after for the undo."""
    sug = [p for p in waiting(g.root) if p.kind == "suggested"]
    if not sug:
        return False
    p = g.rng.choice(sug)
    before = files(g.root)
    g.trail[-1] += f" {p.id} ({p.state}) in {p.path}"
    g.press("change-keep", {"changes": [p.id]}, {p.path})
    after = files(g.root)
    if p.path in before and p.path in after and before[p.path] != after[p.path]:
        g.kept[p.id] = (p.path, before[p.path], after[p.path])
    return True


def undo_keep(g: Gate) -> bool:
    """Undo a Keep this sequence recorded, sometimes after the person saved a line of their own at the foot of its file: the exact bytes where the file is as the Keep left it, and otherwise that Keep's own words taken out at one place and nothing else."""
    from loom.records.edits import find

    live = [eid for eid in g.kept if (e := find(g.root, eid)) is not None and e.status == "kept"]
    if not live:
        return False
    eid = g.rng.choice(live)
    path, b, a = g.kept.pop(eid)
    f = g.root / path
    if f.read_bytes() == a and g.rng.random() < 0.5:
        mine = g.word("pt")
        f.write_bytes(a + f"% {mine}\n".encode())
        g.typed.add(mine)
    before = files(g.root)
    c = before.get(path)
    said = call(g.root, "change-undo", {"changes": [eid]})
    g.check("undo of a Keep", before, {path})
    r = files(g.root).get(path)
    g.trail[-1] += (
        f" {eid} in {path}, {'as kept' if c == a else 'since changed'}: {said.get('error') or said.get('result')}"
    )
    if c == a:
        if r != b:
            g.problems.append(f"undo of {eid}: {path} was as its Keep left it, and is not given back byte for byte")
        return True
    if r == c or c is None or r is None:
        return True  # refused, which writes nothing
    # the Keep's change, trimmed of what the bytes before and after it share at either end
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    j = 0
    while j < min(len(a), len(b)) - i and a[-1 - j] == b[-1 - j]:
        j += 1
    old, new = b[i : len(b) - j], a[i : len(a) - j]
    at = [m.start() for m in re.finditer(re.escape(new), c)] if new else []
    if not any(c[:k] + old + c[k + len(new) :] == r for k in at):
        g.problems.append(f"undo of {eid}: {path} changed other than by its Keep's words taken out at one place")
    return True


def adopt(g: Gate) -> bool:
    """The agent writes a sentence into a block of its document, and the person takes in every block it offers, with the document's own changes."""
    from loom.adopt import comparison, incorporate, prepare
    from loom.sync import SyncError

    copy = g.root / g.copy
    text = copy.read_text(encoding="utf-8")
    ends = list(re.finditer(r"\\end\{(lemma|theorem|proposition|corollary|definition|remark|proof|example)\}", text))
    if not ends:
        return False
    at = g.rng.choice(ends).start()
    mk = g.word("ag")
    copy.write_text(text[:at] + sentence(g.rng, 8, mk) + "\n" + text[at:], encoding="utf-8")  # the agent's own write
    before = files(g.root)
    try:
        result = scan(g.root)
        offered = [r["key"] for r in comparison(result, g.copy)["changes"] if r.get("offered")]
        prep = prepare(result, g.copy, offered, document=True) if offered else {}
        if not prep.get("patch"):
            g.trail[-1] += f" {mk}: nothing offered"
            return True
        done = incorporate(scan(g.root), g.copy, prep["token"])
    except SyncError as exc:
        g.trail[-1] += f" {mk}: refused ({exc})"
        g.check("a refused adoption", before, set())
        return True
    paths = set(prep["paths"])
    g.trail[-1] += f" {mk} into {sorted(paths)}, landmark {done.get('landmark')}"
    g.check("adoption", before, paths)
    if mk in b"\n".join(files(g.root).values()).decode("utf-8", "replace"):
        g.taken.add(mk)
    if done.get("landmark"):
        g.adoptions.append((g.main, str(done["landmark"]), {p: before.get(p) for p in paths}))
    return True


def restore(g: Gate) -> bool:
    """Undo an adoption by restoring the version it stamped: every file it wrote is given back byte for byte."""
    from loom.history.ledger import load_history
    from loom.scan.quilt import load_quilt

    if not g.adoptions:
        return False
    doc, landmark, was = g.adoptions.pop(g.rng.randrange(len(g.adoptions)))
    entry = load_history(load_quilt(g.root).history_dir).landmark(landmark)
    holds = set((entry.get("files") if entry is not None else None) or {doc})
    before = files(g.root)
    said = call(g.root, "history-restore", {"document": doc, "version": landmark})
    g.trail[-1] += f" {landmark} of {doc}: {said.get('error') or said.get('result')}"
    if "error" in said:
        g.check("a refused restore", before, set())
        return True
    g.check("restore", before, holds)
    now = files(g.root)
    for path, data in was.items():
        if now.get(path) != data:
            g.problems.append(f"restore of {landmark}: {path} is not as it was before the adoption")
    return True


def update(g: Gate) -> bool:
    """A colleague changes the project in Overleaf, the person sometimes changes the same file here, and the person updates."""
    rel = g.rng.choice(sorted(PROJECT_FILES))
    lines = (g.clone / rel).read_text(encoding="utf-8").split("\n")
    mk = g.word("ov")
    lines.insert(g.rng.randrange(1, len(lines)), sentence(g.rng, 6, mk))
    edit(g.clone, f"edit {mk}", {rel: "\n".join(lines)})
    here = g.root / MIRROR / rel
    if g.rng.random() < 0.3:  # the person's own change to the mirrored file, which the update writes over and keeps
        mine = g.word("pt")
        here.write_text(here.read_text(encoding="utf-8") + f"\n{mine}\n", encoding="utf-8")
        g.typed.add(mine)
        g.trail[-1] += f" over {mine} here"
    before = files(g.root)
    said = call(g.root, "overleaf-update", {})
    g.trail[-1] += f" {mk} in {rel}: {said.get('error') or said.get('result', {}).get('state')}"
    g.check("update from Overleaf", before, {f"{MIRROR}/{r}" for r in PROJECT_FILES})
    now = files(g.root)
    for r in PROJECT_FILES:
        if now.get(f"{MIRROR}/{r}") != (g.clone / r).read_bytes():
            g.problems.append(f"update {mk}: {MIRROR}/{r} does not hold the project's bytes")
    return True


def file_pdf(g: Gate) -> bool:
    """A PDF dropped and filed: as a work of its own, or on a work of the library that holds no PDF."""
    mk = g.word("lb")
    pdf = lines_pdf(g.work / "pdfs" / f"{mk}.pdf", [[f"Gadgets {mk} and their bounds", "Jane Smith"]])
    data = pdf.read_bytes()
    bare = sorted(ref for ref, n in Library.read(g.root).refs.items() if n.pdf is None)
    onto = g.rng.choice(bare) if bare and g.rng.random() < 0.5 else ""
    before, lib = files(g.root), library_files(g.root)
    drop = str(receive(g.root, pdf.name, io.BytesIO(data), len(data))["incoming"])
    (row,) = take(g.root, [Item(drop=drop, work=onto)], by=ME)
    g.trail[-1] += f" {mk} {'onto ' + onto if onto else 'as its own'}: {row.state}"
    g.check("filing a PDF", before, set())
    if row.act:
        g.library.append((drop, row.act, lib))
    return True


def unfile_pdf(g: Gate) -> bool:
    """A PDF taken off its work, which then waits again."""
    held = sorted(ref for ref, n in Library.read(g.root).refs.items() if n.pdf is not None)
    if not held:
        return False
    ref = g.rng.choice(held)
    before, lib = files(g.root), library_files(g.root)
    try:
        off = unfile(g.root, ref, by=ME)
    except IntakeRefused as exc:
        g.trail[-1] += f" {ref}: refused {exc.code}"
        g.check("a refused unfile", before, set())
        if library_files(g.root) != lib:
            g.problems.append(f"a refused unfile of {ref} changed the library")
        return True
    g.trail[-1] += f" {ref}"
    g.check("unfiling a PDF", before, set())
    g.library.append((str(off["incoming"]), str(off["act"]), lib))
    return True


def undo_library(g: Gate) -> bool:
    """The last library act undone: the library's nodes and store are as they were before it."""
    if not g.library:
        return False
    drop, act, lib = g.library.pop()
    before = files(g.root)
    try:
        said, _ = undo(g.root, drop, act=act, by=ME)
    except IntakeRefused as exc:
        g.problems.append(f"the undo of the last library act {act} was refused: {exc.code} {exc}")
        return True
    g.trail[-1] += f" {act}: {said}"
    g.check("a library undo", before, set())
    now = library_files(g.root)
    if now != lib:
        g.problems.append(
            f"undo of {act}: the library differs from before it in {sorted(k for k in set(now) | set(lib) if now.get(k) != lib.get(k))}"
        )
    return True


#: Each act and its weight in the draw.
ACTS = {
    "write": (write, 6),
    "keep": (keep, 4),
    "undo": (undo_keep, 4),
    "adopt": (adopt, 3),
    "restore": (restore, 2),
    "update": (update, 3),
    "file": (file_pdf, 3),
    "unfile": (unfile_pdf, 2),
    "lib-undo": (undo_library, 3),
}


def act(g: Gate) -> None:
    """One act drawn from the gate's mix, drawn again while the one drawn finds nothing to do; then the checks `Run.check` does not make."""
    while True:
        name = g.rng.choices(list(ACTS), [w for _, w in ACTS.values()])[0]
        g.trail.append(name)
        g.typed = {w for w in g.typed if w.encode() in b"\n".join(files(g.root).values())}
        if ACTS[name][0](g):
            break
        g.trail.pop()
    blob = b"\n".join(files(g.root).values()).decode("utf-8", "replace")
    for mk in sorted(g.taken):
        if blob.count(mk) > 1:
            g.problems.append(f"{name}: the agent's {mk} stands {blob.count(mk)} times")
    g.problems.extend(f"{name}: {p}" for p in held_whole(g.root))


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("name", QUILT_NAMES)
def test_a_seeded_sequence_of_acts_does_no_damage_and_each_undo_gives_back_the_bytes(
    tmp_path: Path, name: str, seed: int
) -> None:
    root, main, bare, copy = gate_quilt(tmp_path, name)
    g = Gate(root, seed * 1000 + QUILT_NAMES.index(name), tmp_path, bare, main, copy)
    for _ in range(STEPS):
        act(g)
        assert not g.problems, (
            f"seed {seed} on {name}; run it alone with LOOM_GATE_SEEDS={seed}:{seed + 1} and -k {name}",
            g.problems,
            g.trail,
        )
