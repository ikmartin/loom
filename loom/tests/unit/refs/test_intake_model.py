"""A model of the library under random use: drops, takes, answers, unfiles, undos, command-line adds, deletes, gathering, pastes and hand edits of the bibliography, some two at once, checked after every step against what must always hold. Every PDF a person gave is still somewhere unless they discarded it, and the records never name what is not there.

Built on the integrator's re-check of the intake (2026-11-17), whose model found an undo writing an entry into the middle of another and an undo deleting a PDF from under a work. One step in twenty stops inside its act, at a random one of its file operations, as a killed process would; after it, every PDF given and not discarded on the person's word is still somewhere, no entry names a place without its PDF, and every later act answers or refuses in a sentence. `LOOM_MODEL_STEPS` runs it longer by hand, and `LOOM_MODEL_SEEDS` (comma-separated) on other seeds.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import re
import shutil
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from loom.paths import INCOMING
from loom.refs.added import NotDeletable, delete_work
from loom.refs.fetch import FetchRefused, work_dir
from loom.refs.identity import identify
from loom.refs.intake import IntakeRefused, Item, _acts, answer, receive, take, undo, unfile, waiting, waiting_file
from loom.refs.pages import storage_root
from loom.refs.scan import scan_bibliography, versions_of
from loom.scan.bib import BibEntry, parse_bib
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.unit._quilts import showcase
from tests.unit.refs._made_pdfs import fake_pdf

WHO = "A. Author"
BIB = ".loom/library/bibliography.bib"
HEX = re.compile(r"[0-9a-f]{64}")
STEPS = int(os.environ.get("LOOM_MODEL_STEPS", "120"))
SEEDS = [int(x) for x in os.environ.get("LOOM_MODEL_SEEDS", "2,3,20261117").split(",")]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pool(where: Path) -> dict[str, Path]:
    """The PDFs a person gives: distinct papers, look-alikes of the showcase's works with other bytes, one citing another's identifier, an erratum, and a scan with no text."""
    pages: dict[str, str] = {}
    for i, w in enumerate(("Alpha", "Bravo", "Charlie", "Delta")):
        pages[f"u{i}"] = f"Distinct topic {w} in algebraic settings\nPerson{w} Surname{w}\nAbstract. Body text.\n"
    for k in range(3):
        pages[f"bel{k}"] = "Median orders on weighted digraphs\nRosalind Bellamy\n" + f"Variant {k}.\n" + "\fmore" * k
    for k in range(2):
        pages[f"cor{k}"] = "Flows on infinite quivers: a survey\nHilario Cortez\n" + f"Scan {k}.\n" + "\fmore" * k
    pages["ardpub"] = "doi:10.9999/jic.2024.12\nCycle spaces of finite quivers\nElspeth Arden\nAbstract. Revised.\n"
    pages["cite"] = (
        "Remarks on acyclic orientations\nTomas Lind\nWe answer a question raised in arXiv:2504.01234 about cycles.\n"
    )
    pages["erratum"] = (
        "Erratum to doi:10.4171/showcase/19-2\nErratum: Median orders on weighted digraphs\nRosalind Bellamy\n"
    )
    pages["sametitle"] = "Distinct topic Alpha in algebraic settings\nOther Person\nA different paper.\n"
    pages["scan"] = ""
    return {name: fake_pdf(where / f"{name}.pdf", text) for name, text in pages.items()}


class Model:
    """The quilt, what was given to it, and what the person discarded."""

    def __init__(self, q: Path, tmp: Path, seed: int) -> None:
        self.q, self.tmp, self.rng = q, tmp, random.Random(seed)
        self.pool = _pool(tmp / "pool")
        #: Every PDF given, by hash, that the person has not discarded.
        self.alive: dict[str, str] = {}
        #: The person's own files the command line took in, which nothing may change.
        self.outside: list[tuple[Path, str]] = []
        self.drops: set[str] = set()
        self.lock = threading.Lock()
        self.serial = 0

    def bib(self) -> dict[str, BibEntry]:
        return scan(load_quilt(self.q)).bib

    def home(self, entry: BibEntry) -> Path | None:
        try:
            return work_dir(self.q, entry)
        except FetchRefused:
            return None

    def next(self) -> int:
        with self.lock:
            self.serial += 1
            return self.serial

    # ---- acts: each says what it did, or None when it had nothing to act on; `gone` gathers the hashes the person discarded

    def drop(self, r: random.Random, gone: set[str]) -> str | None:
        name = r.choice(list(self.pool))
        data = self.pool[name].read_bytes()
        as_ = r.choice([f"{name}.pdf", f"Writer - 2020 - Paper {name}.pdf", f"copy of {name}.pdf"])
        got = receive(self.q, as_, io.BytesIO(data), len(data))
        with self.lock:
            self.drops.add(got["incoming"])
            self.alive[_sha(data)] = name
        return f"drop {name}"

    def take(self, r: random.Random, gone: set[str]) -> str | None:
        waits = [x for x in waiting(self.q) if x["state"] == "received"]
        if not waits:
            return None
        pick = r.choice(waits)["id"]
        mode = r.choice(["plain", "plain", "new", "for"])
        work = r.choice(list(self.bib())) if mode == "for" else ""
        (row,) = take(load_quilt(self.q), self.bib(), [Item(drop=pick, work=work, new=mode == "new")], by=WHO)
        if row.state == "here":
            assert "these very bytes" in row.why, row  # only the same bytes are already here
        return f"take {pick[:8]} {mode} {work} -> {row.state} {row.citekey}"

    def answer(self, r: random.Random, gone: set[str]) -> str | None:
        asked = [x for x in waiting(self.q) if x["state"] == "question"]
        if not asked:
            return None
        pick = r.choice(asked)
        same = r.choice([None, *(c["citekey"] for c in pick["candidates"])])
        row = answer(load_quilt(self.q), self.bib(), pick["id"], same, by=WHO)
        if row.state == "here" and HEX.fullmatch(pick["id"]):
            assert "these very bytes" in row.why, row
        return f"answer {pick['id'][:8]} {same} -> {row.state} {row.citekey}"

    def unfile(self, r: random.Random, gone: set[str]) -> str | None:
        held = [k for k, e in self.bib().items() if (h := self.home(e)) is not None and (h / "paper.pdf").is_file()]
        if not held:
            return None
        key = r.choice(held)
        off = unfile(scan(load_quilt(self.q)), key, by=WHO)
        with self.lock:
            self.drops.add(off["incoming"])
        return f"unfile {key}"

    def undo(self, r: random.Random, gone: set[str]) -> str | None:
        with self.lock:
            standing = sorted(d for d in self.drops if (self.q / INCOMING / d).is_dir())
        if not standing:
            return None
        d = r.choice(standing)
        acts = _acts(self.q / INCOMING / d)
        act = acts[-1].get("act", "") if acts and r.random() < 0.85 else r.choice(["", "deadbeef"])
        # the person's word, which stands once given, if the act stops on the way
        discards = bool(HEX.fullmatch(d)) and (
            not acts  # a drop never taken, discarded
            or (len(acts) == 1 and acts[-1]["kind"] == "added" and not (acts[-1].get("waiting") or {}).get("over"))
        )
        if discards:
            gone.add(d)
        try:
            said, _row = undo(scan(load_quilt(self.q)), d, by=WHO, act=act)
        except IntakeRefused as refused:
            if refused.code != "no-such-intake":  # gone already: an act beside this one discarded it
                gone.discard(d)
            raise
        return f"undo {d[:8]} -> {said}"

    def cli(self, r: random.Random, gone: set[str]) -> str | None:
        name = r.choice(list(self.pool))
        src = self.tmp / "outside" / str(self.next()) / f"{name} cli.pdf"
        src.parent.mkdir(parents=True)
        shutil.copy(self.pool[name], src)
        with self.lock:
            self.outside.append((src, _sha(src.read_bytes())))  # the person's own file, which stays theirs
        mode = r.choice(["plain", "new", "for"])
        work = r.choice(list(self.bib())) if mode == "for" else ""
        item = Item(path=src, work=work, on_word=mode == "for", new=mode == "new")
        (row,) = take(load_quilt(self.q), self.bib(), [item], by=WHO)
        if row.state == "here":
            assert "these very bytes" in row.why, row
        with self.lock:
            if row.id:
                self.drops.add(row.id)
        return f"cli {name} {mode} {work} -> {row.state} {row.citekey}"

    def delete(self, r: random.Random, gone: set[str]) -> str | None:
        added = [k for k, e in self.bib().items() if e.fields.get("loom-added")]
        if not added:
            return None
        key = r.choice(added)
        res = scan(load_quilt(self.q))
        shas = []
        for k in [key, *versions_of(res.bib).get(key, [])]:
            h = self.home(res.bib[k]) if k in res.bib else None
            if h is not None and (h / "paper.pdf").is_file():
                shas.append(_sha((h / "paper.pdf").read_bytes()))
        gone.update(shas)
        try:
            return delete_work(res, key, WHO)
        except NotDeletable as refused:
            if refused.code != "no-such-work":  # deleted already by an act beside this one
                gone.difference_update(shas)
            raise

    def gather(self, r: random.Random, gone: set[str]) -> str | None:
        report = scan_bibliography(load_quilt(self.q))
        return f"gather +{[c.key for c in report.added]}"

    def edit(self, r: random.Random, gone: set[str]) -> str | None:
        added = [k for k, e in self.bib().items() if e.fields.get("loom-added")]
        if not added:
            return None
        key = r.choice(added)
        path = self.q / BIB
        text = path.read_text(encoding="utf-8")
        if r.random() < 0.5:
            m = re.search(r"(@\w+\{" + re.escape(key) + r",\n\s*title = \{)", text)
            if not m:
                return None
            path.write_text(text[: m.end()] + "Corrected " + text[m.end() :], encoding="utf-8")
            return f"hand edit: retitled {key}"
        new = f"{key}x"
        if new in self.bib():
            return None
        path.write_text(text.replace("{" + key + ",", "{" + new + ",", 1), encoding="utf-8")
        return f"hand edit: renamed {key} {new}"

    def paste(self, r: random.Random, gone: set[str]) -> str | None:
        text = r.choice(
            [
                f"@article{{pasted{r.randrange(3)}, title={{A Pasted Paper {r.randrange(3)}}}, author={{Paste, Pat}}, year={{2021}}}}",
                "@article{pastedB, title={Median orders on weighted digraphs}, author={Bellamy, Rosalind}, year={2019}}",
                f"10.1234/abc.{r.randrange(3)}",
            ]
        )
        rows = take(load_quilt(self.q), self.bib(), [Item(text=text)], by=WHO)
        with self.lock:
            self.drops.update(row.id for row in rows if row.id)
        return f"paste -> {[x.state for x in rows]}"


#: Each act and how often it comes.
ACTS: list[tuple[str, int]] = [
    ("drop", 14),
    ("take", 16),
    ("answer", 8),
    ("unfile", 10),
    ("undo", 22),
    ("cli", 8),
    ("gather", 4),
    ("paste", 4),
    ("delete", 4),
    ("edit", 3),
]
#: The acts a step stops midway, each of which writes.
STOPPABLE = ("drop", "take", "answer", "unfile", "undo", "cli", "delete")
#: The acts that run two at once.
PAIRED = ("take", "unfile", "undo", "cli", "gather", "answer", "drop")


def _present(m: Model) -> set[str]:
    out = set()
    for base in (storage_root(m.q), m.q / INCOMING):
        for p in base.rglob("*.pdf") if base.is_dir() else []:
            if "cache" not in p.parts:
                out.add(_sha(p.read_bytes()))
    return out


def _faults(m: Model, crashed: bool = False) -> list[str]:
    """What must always hold, broken: the bibliography whole, each entry's place holding its PDF and no other entry's, one work to each identity, the ledger and each drop's record true to what is there, and every PDF given still somewhere. Once an act has been stopped midway, a drop may hold what the stopped act left, and a temporary file may be left behind."""
    bad = []
    text = (m.q / BIB).read_text(encoding="utf-8")
    keys = [k for _, k in re.findall(r"^@(\w+)\{([^,\s]+),", text, re.M)]
    parsed = parse_bib(text)
    if dup := sorted({k for k in keys if keys.count(k) > 1}):
        bad.append(f"keys twice in the bibliography: {dup}")
    if len(set(keys)) != len(parsed):
        bad.append(f"{len(set(keys))} entries begin and {len(parsed)} parse")
    homes: dict[Path, str] = {}
    ids: dict[str, str] = {}
    for k, e in parsed.items():
        if "@" in "".join(str(v) for v in e.fields.values()):
            bad.append(f"{k} swallowed another entry")
        filed = str(e.fields.get("loom-file") or "").strip()
        if filed:
            h = storage_root(m.q) / filed
            if not (h / "paper.pdf").is_file():
                bad.append(f"{k} names {filed}, which holds no PDF")
            if h in homes:
                bad.append(f"{k} and {homes[h]} both name {filed}")
            homes[h] = k
        if not e.fields.get("loom-copy-of") and (wid := identify(e)):
            s = str(wid[0])
            if s in ids and s.startswith("work:"):
                bad.append(f"{k} and {ids[s]} are one work, {s}")
            ids[s] = k
    ledger_path = storage_root(m.q) / "copied.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.is_file() else {}
    for sha, rec in ledger.items():
        if str(rec.get("from", "")).lower().endswith(".pdf"):
            paper = storage_root(m.q) / rec["to"] / "paper.pdf"
            if not paper.is_file() or _sha(paper.read_bytes()) != sha:
                bad.append(f"the ledger sends {sha[:8]} to {rec['to']}, which does not hold it")
    base = m.q / INCOMING
    for d in sorted(base.iterdir()) if base.is_dir() else []:
        if d.name.startswith("."):
            continue
        acts, pdf = _acts(d), waiting_file(d)
        if not crashed and not acts and pdf is None and not (d / "question.json").is_file():
            bad.append(f"drop {d.name[:8]} holds, records and waits on nothing: {sorted(x.name for x in d.iterdir())}")
        if pdf is not None and HEX.fullmatch(d.name) and _sha(pdf.read_bytes()) != d.name:
            bad.append(f"drop {d.name[:8]} holds other bytes")
        if not crashed and acts and acts[-1]["kind"] == "added" and acts[-1].get("home"):
            paper = m.q / acts[-1]["home"] / "paper.pdf"
            if not paper.is_file() or _sha(paper.read_bytes()) != acts[-1]["sha"]:
                bad.append(f"drop {d.name[:8]} added {acts[-1]['citekey']}, and the store does not hold it")
        if acts and acts[-1]["kind"] == "unfiled" and not (d / acts[-1]["name"]).is_file():
            bad.append(f"drop {d.name[:8]} unfiled {acts[-1]['citekey']}, and its file is gone")
    there = _present(m)
    bad += [
        f"{what} ({sha[:8]}), given and not discarded, is nowhere" for sha, what in m.alive.items() if sha not in there
    ]
    bad += [f"the person's own {src.name} changed" for src, sha in m.outside if _sha(src.read_bytes()) != sha]
    if not crashed:
        bad += [f"left behind {p.name}" for p in m.q.rglob("*") if p.name.endswith((".loom-tmp", ".part"))]
    waiting(m.q)
    return bad


def _tree(q: Path) -> dict[str, bytes]:
    return {
        p.relative_to(q).as_posix(): p.read_bytes()
        for p in sorted(q.rglob("*"))
        if p.is_file() and not p.relative_to(q).as_posix().startswith(".loom/cache/")
    }


class Stopped(BaseException):
    """A process killed inside an act; a BaseException, so no `except Exception` in loom catches it, as nothing catches a kill."""


#: The file operations an act may be stopped at.
OPS = [
    (os, "replace"),
    (os, "rename"),
    (os, "link"),
    (os, "unlink"),
    (shutil, "copyfile"),
    (shutil, "copy2"),
    (shutil, "rmtree"),
]


@contextmanager
def _stopped_at(n: int) -> Iterator[None]:
    """Stop the act run inside at its `n`-th file operation; an act with fewer runs whole."""
    seen = [0]
    real = {(mod, name): getattr(mod, name) for mod, name in OPS}

    def wrap(f: Callable[..., object]) -> Callable[..., object]:
        def op(*args: object, **kwargs: object) -> object:
            seen[0] += 1
            if seen[0] == n:
                raise Stopped(f"stopped at file operation {n}, {getattr(f, '__name__', f)}")
            return f(*args, **kwargs)

        return op

    for (mod, name), f in real.items():
        setattr(mod, name, wrap(f))
    try:
        yield
    finally:
        for (mod, name), f in real.items():
            setattr(mod, name, f)


def _run(
    act: Callable[[random.Random, set[str]], str | None], r: random.Random, gone: set[str], out: list[str]
) -> None:
    try:
        out.append(str(act(r, gone)))
    except Stopped as stopped:
        out.append(f"{act.__name__} STOPPED, {stopped}")
    except (IntakeRefused, NotDeletable) as refused:
        out.append(f"{act.__name__} refused {getattr(refused, 'code', '')}")
    except Exception as exc:  # noqa: BLE001 -- what the model reports, with the step
        out.append(f"{act.__name__} FAILED {type(exc).__name__}: {exc}")


def _paired(
    bar: threading.Barrier,
    act: Callable[[random.Random, set[str]], str | None],
    r: random.Random,
    gone: set[str],
    out: list[str],
) -> None:
    bar.wait()
    _run(act, r, gone, out)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_library_under_random_use_never_loses_a_document_or_damages_a_record(tmp_path: Path, seed: int) -> None:
    q = showcase(tmp_path)
    m = Model(q, tmp_path, seed)
    m.bib()
    total = sum(w for _, w in ACTS)
    crashed, stops = False, 0
    for step in range(STEPS):
        gone: set[str] = set()
        before = _tree(q)
        out: list[str] = []
        if m.rng.random() < 0.12:
            acts = [getattr(m, m.rng.choice(PAIRED)) for _ in range(2)]
            rs = [random.Random(m.rng.random()) for _ in acts]
            bar = threading.Barrier(2)
            threads = [
                threading.Thread(target=_paired, args=(bar, act, r, gone, out)) for act, r in zip(acts, rs, strict=True)
            ]
            for th in threads:
                th.start()
            for th in threads:
                th.join(120)
            what = " || ".join(out)
        else:
            x = m.rng.uniform(0, total)
            name = next((n for n, w in ACTS if (x := x - w) <= 0), ACTS[-1][0])
            if m.rng.random() < 0.05:
                name = m.rng.choice(STOPPABLE)
                with _stopped_at(m.rng.randint(1, 12)):
                    _run(getattr(m, name), m.rng, gone, out)
            else:
                _run(getattr(m, name), m.rng, gone, out)
            what = out[0]
            stops += " STOPPED, " in what
            crashed = crashed or " STOPPED, " in what
            if " refused " in what:
                assert _tree(q) == before, f"step {step}: {what}, and still changed the quilt"
        assert "FAILED" not in what, f"step {step}: {what}"
        for sha in gone:
            m.alive.pop(sha, None)
        bad = _faults(m, crashed)
        assert not bad, f"step {step} ({what}): {bad}"
    assert stops or STEPS < 100, "no act was stopped midway"
