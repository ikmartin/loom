"""Random histories of records over small webs whose uses, citations and notation follow from their texts, checked against what `formalized` and `matches` must mean and against the order of the log's lines.

The generator is the reviewer's second fuzzer's: Lean records that fail, fail the replay, carry a `sorry`, state another result, rest on a supporting axiom, on a result of the person's stated as an axiom, or on a library node stated as one and listed or not in `assumed`; citations with and without a locator; notation per document. `earned` is written apart from `status`, from the rulings.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest

from loom.evidence.log import Evidence, Record, parse
from loom.evidence.status import Status, status
from loom.evidence.subjects import Subject
from loom.evidence.web import Here

PERSON = {"kind": "person", "name": "A. Author"}
LOOM = {"kind": "loom"}
#: Lean's own axioms, which a proof may rest on and still read proved.
LEANS_OWN = frozenset({"propext", "Classical.choice", "Quot.sound"})


def h(n: int) -> str:
    return "sha256:" + format(n, "064x")


STATEMENTS = [{"t": h(1)}, {"t": h(2)}, {"t": h(1), "d": h(3)}]


def together(hashes: set[str]) -> str:
    if len(hashes) == 1:
        return next(iter(hashes))
    return "sha256:" + hashlib.sha256(json.dumps(sorted(hashes), separators=(",", ":")).encode()).hexdigest()


@dataclass
class Block:
    key: str
    label: str | None
    docs: frozenset[str]
    text: int


@dataclass
class Node:
    id: str
    text: int
    stub: bool


@dataclass
class World:
    """Blocks of drafts, library nodes and macros per document; what a text uses, cites and is typeset with is drawn from the text."""

    seed: int
    labels: list[str]
    node_ids: list[str]
    macro_names: list[str]
    blocks: dict[str, Block] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    macros: dict[tuple[str, str], int] = field(default_factory=dict)

    def rng(self, *parts: object) -> random.Random:
        return random.Random("|".join(map(str, (self.seed, *parts))))

    def block_uses(self, b: Block) -> tuple[list[str], list[str]]:
        r = self.rng("bu", b.key, b.text)
        return [x for x in self.labels if x != b.label and r.random() < 0.35], [
            x for x in self.node_ids if r.random() < 0.3
        ]

    def block_macros(self, b: Block) -> list[str]:
        r = self.rng("bm", b.key, b.text)
        return [m for m in self.macro_names if r.random() < 0.4]

    def block_cites(self, b: Block) -> list[str]:
        r = self.rng("bc", b.key, b.text)
        return ["Cal14 Theorem 2"] if r.random() < 0.08 else (["Cal14"] if r.random() < 0.05 else [])

    def node_uses(self, n: Node) -> list[str]:
        r = self.rng("nu", n.id, n.text)
        return [x for x in self.node_ids if x != n.id and r.random() < 0.3]


class FakeWeb:
    """The `Web` protocol over a `World`, as the drafts' web and the library's will answer it."""

    def __init__(self, w: World) -> None:
        self.w = w

    def _block(self, here: Here) -> Block | None:
        return self.w.blocks.get(here.name) if here.kind == "block" else None

    def subject(self, here: Here) -> Subject | None:
        if here.kind == "node":
            n = self.w.nodes.get(here.name)
            return Subject("node", n.id, h(n.text)) if n else None
        b = self._block(here)
        return Subject("label", b.label, h(b.text)) if b and b.label else None

    def _holders(self, label: str, near: Here) -> list[Block]:
        found = [b for b in self.w.blocks.values() if b.label == label]
        mine = self._block(near)
        return [b for b in found if mine is not None and b.docs & mine.docs] or found

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        kind, name = key
        if kind == "node":
            n = self.w.nodes.get(name)
            return h(n.text) if n else None
        hashes = {h(b.text) for b in self._holders(name, near)}
        return hashes.pop() if len(hashes) == 1 else None

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        found = self._holders(key[1], near) if key[0] == "label" else []
        return Here("block", found[0].key) if found and len({b.text for b in found}) == 1 else None

    def _direct(self, here: Here) -> list[Here]:
        if here.kind == "node":
            n = self.w.nodes.get(here.name)
            return [Here("node", x) for x in self.w.node_uses(n)] if n else []
        b = self._block(here)
        if b is None:
            return []
        labels, nodes = self.w.block_uses(b)
        out = [Here("block", hs[0].key) for hs in (self._holders(x, here) for x in labels) if hs]
        return out + [Here("node", x) for x in nodes]

    def _walk(self, here: Here) -> list[Here]:
        seen, out = {(here.kind, here.name)}, []
        todo = self._direct(here)
        while todo:
            step = todo.pop(0)
            if (step.kind, step.name) in seen:
                continue
            seen.add((step.kind, step.name))
            out.append(step)
            todo.extend(self._direct(step))
        return out

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        out: dict[tuple[str, str], str] = {}
        for step in self._walk(here):
            s = self.subject(step)
            if s is not None:
                out.setdefault(s.key, s.hash)
        return out

    def _texts(self, here: Here) -> list[Block]:
        b = self._block(here)
        return [b, *(x for x in (self._block(s) for s in self._walk(here)) if x is not None)] if b else []

    def notation(self, here: Here) -> dict[str, str]:
        b = self._block(here)
        if b is None:
            return {}
        names = {m for t in self._texts(here) for m in self.w.block_macros(t)}
        rows: dict[str, set[str]] = {}
        for doc in b.docs:
            for name in names:
                if (doc, name) in self.w.macros:
                    rows.setdefault(name, set()).add(h(10_000 + self.w.macros[(doc, name)]))
        return {n: together(v) for n, v in sorted(rows.items())}

    def cited(self, here: Here) -> list[str]:
        return list(dict.fromkeys(c for t in self._texts(here) for c in self.w.block_cites(t)))

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        n = self.w.nodes.get(here.name) if here.kind == "node" else None
        return n.stub if n else None

    def holds(self, ref: str, want: str) -> bool | None:
        return None


def _axiom(name: str, names: dict[str, str] | None, role: str = "states") -> dict[str, Any]:
    return {"name": name, "kind": "axiom", "role": role, "names": names, "statement": h(30), "axioms": [], "sorry": False}  # fmt: skip


def lean_line(rng: random.Random, w: World, web: FakeWeb, here: Here, subject: Subject) -> dict[str, Any]:
    """A `lean` record as loom writes one, or one that lies in each way a record can."""
    names = {subject.kind: subject.name} if rng.random() < 0.92 else {"label": "other:thing"}
    axioms: list[str] = ["propext"]
    decls: list[dict[str, Any]] = []
    assumed: list[dict[str, str]] = []
    roll = rng.random()
    if roll < 0.06:
        axioms.append("sorryAx")
    elif roll < 0.12:
        axioms.append("cheat")
        decls.append(_axiom("cheat", None, "supports"))
    elif roll < 0.18 and w.labels:
        label = rng.choice(w.labels)
        axioms.append("ax_" + label.replace(":", "_"))
        decls.append(_axiom("ax_" + label.replace(":", "_"), {"label": label}))
    elif roll < 0.4 and w.nodes:
        node = rng.choice(list(w.nodes))
        axioms.append("ax_" + node)
        decls.append(_axiom("ax_" + node, {"node": node}))
        if rng.random() < 0.7:
            assumed.append(Subject("node", node, h(w.nodes[node].text)).to_dict())
    for name, statement in rng.choice(STATEMENTS).items():
        sorry = "sorryAx" in axioms and rng.random() < 0.7
        kind = rng.choice(["theorem"] * 7 + ["def"])
        decls.insert(0, {"name": name, "kind": kind, "role": "states", "names": names, "statement": statement, "axioms": axioms, "sorry": sorry})  # fmt: skip
    uses = []
    if rng.random() < 0.2 and w.labels:
        label = rng.choice(w.labels)
        got = web.resolve(("label", label), here)
        if got:
            uses.append(Subject("label", label, got).to_dict())
    return {
        "kind": "lean",
        "by": LOOM,
        "on": subject.to_dict(),
        "project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h(7)},
        "files": {"lean/A.lean": h(8)},
        "declarations": decls,
        "assumed": assumed,
        "uses": uses,
        "replay": {"tool": "leanchecker", "exit": 0 if rng.random() < 0.93 else 1, "output": ""},
        "ok": rng.random() < 0.88,
    }


@dataclass
class History:
    world: World
    lines: list[dict[str, Any]]
    standing: dict[str, bool]

    def add(self, line: dict[str, Any]) -> None:
        n = len(self.lines) + 1
        line = {"id": f"ev-2026-11-21-{n:05d}", "at": f"2026-11-21T{10 + n // 3600:02d}:{n // 60 % 60:02d}:{n % 60:02d}Z", **line}  # fmt: skip
        parse(line)  # every line written here is well formed
        self.lines.append(line)


def history(seed: int) -> History:
    """Edits to a world interleaved with records written as the acts write them, and some odd but well-formed ones."""
    rng = random.Random(seed)
    w = World(
        seed,
        [f"l:{i}" for i in range(rng.randint(1, 4))],
        [f"tq-{i:04d}" for i in range(rng.randint(0, 3))],
        [m for m in ("A", "B", "C") if rng.random() < 0.6],
    )
    docs = ["a.tex", "b.tex"]
    k = 0
    for label in w.labels:
        for _ in range(1 if rng.random() < 0.75 else 2):
            k += 1
            w.blocks[f"k{k}"] = Block(f"k{k}", label, frozenset(rng.sample(docs, rng.choice([1, 1, 2]))), rng.randint(0, 3))  # fmt: skip
    if rng.random() < 0.2:
        k += 1
        w.blocks[f"k{k}"] = Block(f"k{k}", None, frozenset(["a.tex"]), 0)
    for nid in w.node_ids:
        w.nodes[nid] = Node(nid, rng.randint(0, 3), rng.random() < 0.2)
    for doc in docs:
        for m in w.macro_names:
            w.macros[(doc, m)] = rng.randint(0, 2)
    web = FakeWeb(w)
    out = History(w, [], {})
    for _ in range(rng.randint(3, 30)):
        r = rng.random()
        if r < 0.25:
            _edit(w, rng, docs)
            continue
        heres = [Here("block", b) for b in w.blocks] + [Here("node", n) for n in w.nodes]
        here = rng.choice(heres) if heres else None
        subject = web.subject(here) if here else None
        if here is None or subject is None:
            continue
        if rng.random() < 0.12:
            subject = Subject(subject.kind, subject.name, h(rng.randint(0, 4)))  # a record on an earlier text
        if r < 0.5:
            out.add(lean_line(rng, w, web, here, subject))
            out.standing[out.lines[-1]["id"]] = rng.random() < 0.85
        elif r < 0.75:
            leans = [x for x in out.lines if x["kind"] == "lean" and x["on"] == subject.to_dict()]
            shown = (
                {d["name"]: d["statement"] for d in leans[-1]["declarations"] if d["role"] == "states"}
                if leans and rng.random() < 0.9
                else dict(rng.choice(STATEMENTS))
            )
            closure = [{kk[0]: kk[1], "hash": v} for kk, v in sorted(web.closure(here).items())]
            for line in leans:
                closure += [u for u in line["uses"] if u not in closure]
            if closure and rng.random() < 0.1:
                closure = closure[:-1]  # an attestation that missed a member
            out.add({"kind": "attested", "by": PERSON, "on": subject.to_dict(), "lean": "ev-2026-11-21-00000", "statements": shown, "closure": closure, "rulings": []})  # fmt: skip
            for name, digest in web.notation(here).items():
                if rng.random() < 0.9:
                    out.add({"kind": "attested", "by": PERSON, "on": {"macro": name, "hash": digest}})
        elif subject.kind == "node":
            out.add({"kind": "compared", "by": PERSON, "on": subject.to_dict(), "with": {"ref": "tq-00A1-ref", "pdf": h(9)}})  # fmt: skip
        else:
            notation = web.notation(here)
            if notation:
                name = rng.choice(sorted(notation))
                out.add({"kind": "attested", "by": PERSON, "on": {"macro": name, "hash": notation[name]}})
    return out


def _edit(w: World, rng: random.Random, docs: list[str]) -> None:
    what = rng.random()
    if what < 0.5 and w.blocks:
        rng.choice(list(w.blocks.values())).text = rng.randint(0, 4)
    elif what < 0.7 and w.nodes:
        n = rng.choice(list(w.nodes.values()))
        if rng.random() < 0.5:
            n.text = rng.randint(0, 4)
        else:
            n.stub = not n.stub
    elif what < 0.85 and w.macros:
        w.macros[rng.choice(list(w.macros))] = rng.randint(0, 3)
    elif w.blocks:
        b = rng.choice(list(w.blocks.values()))
        if rng.random() < 0.5:
            b.label = rng.choice([*w.labels, None])
        else:
            b.docs = frozenset(rng.sample(docs, rng.choice([1, 2])))


def evidence_of(lines: list[dict[str, Any]]) -> Evidence:
    ev = Evidence()
    for line in lines:
        ev.add(parse(line))
    return ev


def _later(ev: Evidence, s: Subject, of: str) -> list[Record]:
    return sorted(ev.about(s.kind, s.name, of=of), key=lambda r: r.at)


def _compared_now(ev: Evidence, web: FakeWeb, node: str) -> bool:
    s = web.subject(Here("node", node))
    return (
        s is not None
        and web.stub(Here("node", node)) is False
        and any(r.on is not None and r.on.hash == s.hash for r in ev.about("node", node, of="compared"))
    )


def earned(
    ev: Evidence,
    web: FakeWeb,
    here: Here,
    lean_now: Callable[[Record], bool],
    seen: frozenset[str] = frozenset(),
    proof: bool = True,
) -> list[str]:
    """Why the result at `here` has not earned `formalized`, [] when it has; with `proof` False, why its own Lean statement is not attested, as an assumption needs.

    From the rulings: Lean on the text now that elaborated (accepted, replayed) and, for a proof, has no `sorry`, no result of the person's stated as an axiom, and every axiom beyond Lean's three a library node or another of the person's results stated as one; the person's attestation on the text now of its statements, covering the closure as it reads now with the Lean records' uses, every notation row attested now; and for a proof also no citation, every node under it and the node itself read and compared now, each assumed node formalized itself and each assumed result of the person's with its own statement attested, round nothing already asked of.
    """
    s = web.subject(here)
    if s is None:
        return ["no subject"]
    on_text = [r for r in _later(ev, s, "lean") if r.on is not None and r.on.hash == s.hash and lean_now(r)]
    stating = [r for r in on_text if any(d["role"] == "states" and d["names"] == {s.kind: s.name} for d in r.get("declarations"))]  # fmt: skip
    if not stating:
        return ["no standing Lean record on the text now states it"]
    lean = stating[-1]
    out = []
    if not lean.get("ok") or lean.get("replay")["exit"] != 0:
        out.append("Lean did not elaborate it, or the replay failed")
    decls = {d["name"]: d for d in lean.get("declarations")}
    # a node is its own axiom, as the library is assumed
    assumed = [("node", a["node"]) for a in lean.get("assumed") if ("node", a["node"]) != s.key]
    for d in decls.values():
        if d["role"] != "states" or d["names"] != {s.kind: s.name}:
            continue
        if proof and (d["sorry"] or (s.kind == "label" and d["kind"] == "axiom")):
            out.append("not proved: a sorry, or a result of the person's stated as an axiom")
        for axiom in sorted(set(d["axioms"]) - LEANS_OWN):
            stands = decls.get(axiom, {})
            [(kind, name)] = (stands.get("names") or {"-": "-"}).items()
            if stands.get("kind") == "axiom" and stands.get("role") == "states" and kind in ("node", "label"):
                if (kind, name) != s.key:
                    assumed.append((kind, name))
                elif proof and kind != "node":
                    out.append("a result of the person's stated as its own axiom")
            elif proof:
                out.append("an axiom nothing accounts for")
    statements = {d["name"]: d["statement"] for d in decls.values() if d["role"] == "states"}
    attested = [a for a in _later(ev, s, "attested") if a.on is not None and a.on.hash == s.hash and dict(a.get("statements")) == statements]  # fmt: skip
    if not attested:
        return [*out, "no attestation on the text now of the Lean's statements"]
    held = {Subject.from_dict(m).key: Subject.from_dict(m).hash for m in attested[-1].get("closure")}
    now: dict[tuple[str, str], str | None] = dict(web.closure(here))
    for r in on_text:
        for u in r.get("uses"):
            now.setdefault(Subject.from_dict(u).key, web.resolve(Subject.from_dict(u).key, here))
    if any(held.get(k) != v for k, v in now.items()) or any(web.resolve(k, here) != v for k, v in held.items()):
        out.append("the attestation does not cover the closure as it reads now")
    for name, digest in web.notation(here).items():
        if not any(r.on is not None and r.on.hash == digest for r in ev.about("macro", name, of="attested")):
            out.append("a notation row not attested in its definition now")
    if not proof:
        return out
    if web.cited(here):
        out.append("a citation nothing answers for")
    nodes = {k[1] for k in [*now, *held] if k[0] == "node"} | ({s.name} if s.kind == "node" else set())
    if any(not _compared_now(ev, web, n) for n in nodes):
        out.append("a node under it, or itself, not read and compared now")
    for kind, name in dict.fromkeys(assumed):
        if name in seen | {s.name}:
            out.append("an assumption that comes round")
        elif kind == "node" and (not _compared_now(ev, web, name) or earned(ev, web, Here("node", name), lean_now, seen | {s.name})):  # fmt: skip
            out.append("an assumed node not settled")
        elif kind == "label":
            there = web.holder((kind, name), here)
            if there is None or earned(ev, web, there, lean_now, seen | {s.name}, proof=False):
                out.append("an assumed result of the person's whose own statement is not attested")
    return out


def said(s: Status) -> tuple[object, ...]:
    return (s.lean, s.reading, s.role, s.relative_to, s.causes, s.waiting_on, s.unattested_notation)


CHUNKS = [range(0, 200), range(200, 400), range(400, 600), range(600, 800)]


def statuses(
    seeds: range, lines: Callable[[History, random.Random], list[dict[str, Any]]] | None = None
) -> Iterator[tuple[str, Evidence, FakeWeb, Here, Callable[[Record], bool], Status, Status | None]]:
    """For each history and each result in it: where, the evidence, the web, `lean_now`, its status, and with `lines` its status over those lines instead."""
    for seed in seeds:
        made = history(seed)
        web = FakeWeb(made.world)
        ev = evidence_of(made.lines)
        lean_now: Callable[[Record], bool] = lambda rec, made=made: made.standing.get(rec.id, True)  # noqa: E731
        other = evidence_of(lines(made, random.Random(seed * 7 + 1))) if lines else None
        for here in [Here("block", b) for b in made.world.blocks] + [Here("node", n) for n in made.world.nodes]:
            s = status(ev, web, here, lean_now=lean_now)
            if s.subject is not None:
                again = status(other, web, here, lean_now=lean_now) if other is not None else None
                yield f"seed {seed} at {here.name}", ev, web, here, lean_now, s, again


@pytest.mark.parametrize("seeds", CHUNKS, ids=str)
def test_formalized_and_matches_are_earned(seeds: range) -> None:
    for where, ev, web, here, lean_now, s, _ in statuses(seeds):
        if s.lean == "formalized":
            assert earned(ev, web, here, lean_now) == [], where
        if s.reading == "matches":
            assert _compared_now(ev, web, here.name), where


@pytest.mark.parametrize("seeds", CHUNKS, ids=str)
def test_the_order_of_lines_of_different_seconds_moves_no_status(seeds: range) -> None:
    """Each thing's records are ordered by when they were written, not by where a merge put them; every line here has its own second."""
    for where, *_, s, again in statuses(seeds, lambda made, rng: rng.sample(made.lines, len(made.lines))):
        assert again is not None and said(again) == said(s), where


def _repeat(made: History, rng: random.Random) -> list[dict[str, Any]]:
    lines = list(made.lines)
    if lines:
        lines.insert(rng.randrange(len(lines) + 1), rng.choice(lines))
    return lines


@pytest.mark.parametrize("seeds", CHUNKS, ids=str)
def test_a_line_repeated_anywhere_moves_no_status(seeds: range) -> None:
    for where, *_, s, again in statuses(seeds, _repeat):
        assert again is not None and said(again) == said(s), where
