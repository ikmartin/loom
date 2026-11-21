"""Random histories of records over small webs whose uses follow from their texts, checked against what `formalized` and `matches` must mean and against the order of the log's lines."""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from loom.evidence.log import Evidence, Record, parse
from loom.evidence.status import Status, statements_of, status
from loom.evidence.subjects import Subject
from loom.evidence.web import Here

PERSON = {"kind": "person", "name": "A. Author"}
LOOM = {"kind": "loom"}
STATEMENTS = [{"t": "1"}, {"t": "2"}, {"t": "1", "d": "3"}]
#: Lean's own axioms, which a proof may rest on and still read proved.
LEANS_OWN = frozenset({"propext", "Classical.choice", "Quot.sound"})


def h(n: int) -> str:
    return "sha256:" + format(n, "064x")


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
    """Blocks of drafts, library nodes and macros; what a text uses is drawn from the text, so it changes only when some text does."""

    seed: int
    labels: list[str]
    node_ids: list[str]
    macro_names: list[str]
    blocks: dict[str, Block] = field(default_factory=dict)
    nodes: dict[str, Node] = field(default_factory=dict)
    macros: dict[tuple[str, str], int] = field(default_factory=dict)

    def _rng(self, *parts: object) -> random.Random:
        return random.Random("|".join(map(str, (self.seed, *parts))))

    def block_uses(self, b: Block) -> tuple[list[str], list[str]]:
        r = self._rng("bu", b.key, b.text)
        return [x for x in self.labels if x != b.label and r.random() < 0.35], [
            x for x in self.node_ids if r.random() < 0.3
        ]

    def block_macros(self, b: Block) -> list[str]:
        r = self._rng("bm", b.key, b.text)
        return [m for m in self.macro_names if r.random() < 0.4]

    def node_uses(self, n: Node) -> list[str]:
        r = self._rng("nu", n.id, n.text)
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
        return Subject("label", b.label, h(b.text)) if b is not None and b.label is not None else None

    def _holders(self, label: str, near: Here) -> list[Block]:
        found = [b for b in self.w.blocks.values() if b.label == label]
        mine = self._block(near)
        close = [b for b in found if mine is not None and b.docs & mine.docs]
        return close or found

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        kind, name = key
        if kind == "node":
            n = self.w.nodes.get(name)
            return h(n.text) if n else None
        hashes = {h(b.text) for b in self._holders(name, near)}
        return hashes.pop() if len(hashes) == 1 else None

    def _direct(self, here: Here, near: Here) -> list[Here]:
        if here.kind == "node":
            n = self.w.nodes.get(here.name)
            return [Here("node", x) for x in self.w.node_uses(n)] if n else []
        b = self._block(here)
        if b is None:
            return []
        labels, nodes = self.w.block_uses(b)
        out = [Here("block", hs[0].key) for hs in (self._holders(x, here) for x in labels) if hs]
        return out + [Here("node", x) for x in nodes]

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        seen, out = {(here.kind, here.name)}, {}
        todo = self._direct(here, here)
        while todo:
            step = todo.pop(0)
            if (step.kind, step.name) in seen:
                continue
            seen.add((step.kind, step.name))
            s = self.subject(step)
            if s is not None:
                out.setdefault(s.key, s.hash)
            todo.extend(self._direct(step, here))
        return out

    def notation(self, here: Here) -> dict[str, str]:
        b = self._block(here)
        if b is None:
            return {}
        names = set(self.w.block_macros(b))
        for key in self.closure(here):
            if key[0] == "label":
                for holder in self._holders(key[1], here)[:1]:
                    names |= set(self.w.block_macros(holder))
        out: dict[str, str] = {}
        for doc in sorted(b.docs):
            for name in sorted(names - set(out)):
                if (doc, name) in self.w.macros:
                    out[name] = h(10_000 + self.w.macros[(doc, name)])
        return out

    def acceptance(self, here: Here) -> str | None:
        return None

    def stub(self, here: Here) -> bool | None:
        n = self.w.nodes.get(here.name) if here.kind == "node" else None
        return n.stub if n else None

    def holds(self, ref: str, want: str) -> bool | None:
        return None

    def cited(self, here: Here) -> list[str]:
        return []


def lean_line(subject: Subject, statements: dict[str, str], r: random.Random, assumed: list[Subject], uses: list[Subject]) -> dict[str, Any]:  # fmt: skip
    """A `lean` record as loom writes one, now and then one that fails, states another result, has a `sorry`, an axiom it does not account for, or a replay the kernel refused."""
    states = r.random() < 0.93
    sorry = r.random() < 0.1
    axioms = ["sorryAx"] if sorry else (["Stray.ax"] if r.random() < 0.05 else ["propext"])
    kind = r.choice(["theorem"] * 6 + ["def", "axiom"])
    names = {subject.kind: subject.name} if states else {"label": "other:thing"}
    return {
        "kind": "lean",
        "by": LOOM,
        "on": subject.to_dict(),
        "project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h(7)},
        "files": {"lean/A.lean": h(8)},
        "declarations": [
            {
                "name": n,
                "kind": kind,
                "role": "states",
                "names": names,
                "statement": h(int(s)),
                "axioms": axioms,
                "sorry": sorry,
            }  # fmt: skip
            for n, s in statements.items()
        ],
        "assumed": [a.to_dict() for a in assumed],
        "uses": [u.to_dict() for u in uses],
        "replay": {"tool": "leanchecker", "exit": 0 if r.random() < 0.95 else 1, "output": ""},
        "ok": r.random() < 0.85,
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
    """Edits to a world interleaved with records written as the acts write them, and some odd but well-formed ones: an attestation over a stale closure or an earlier text, a Lean record that does not prove."""
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
        if rng.random() < 0.15:
            subject = Subject(subject.kind, subject.name, h(rng.randint(0, 4)))  # a record on an earlier text
        if r < 0.5:
            assumed = [Subject("node", x, h(w.nodes[x].text)) for x in w.nodes if rng.random() < 0.25]
            uses = []
            if rng.random() < 0.2:
                label = rng.choice(w.labels)
                got = web.resolve(("label", label), here)
                if got:
                    uses.append(Subject("label", label, got))
            out.add(lean_line(subject, rng.choice(STATEMENTS), rng, assumed, uses))
            out.standing[out.lines[-1]["id"]] = rng.random() < 0.85
        elif r < 0.75:
            leans = [x for x in out.lines if x["kind"] == "lean" and x["on"].get(subject.kind) == subject.name]
            shown = (
                {d["name"]: d["statement"] for d in leans[-1]["declarations"] if d["role"] == "states"}
                if leans and rng.random() < 0.9
                else {n: h(int(s)) for n, s in rng.choice(STATEMENTS).items()}
            )
            closure = [{kk[0]: kk[1], "hash": v} for kk, v in sorted(web.closure(here).items())]
            for u in leans[-1]["uses"] if leans else []:
                if u not in closure:
                    closure.append(u)
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


def proves(record: Record, subject: Subject) -> bool:
    """Written apart from `status.proves`, from the spec's words: accepted, replayed by the kernel, stating the result with no `sorry` and no axiom but Lean's three and those it states."""
    if not record.get("ok") or record.get("replay")["exit"] != 0:
        return False
    decls = record.get("declarations")
    mine = [d for d in decls if d["role"] == "states" and d["names"] == {subject.kind: subject.name}]
    own = {d["name"] for d in decls if d["kind"] == "axiom"}
    return bool(mine) and all(not d["sorry"] and set(d["axioms"]) <= LEANS_OWN | own for d in mine)


def compared_now(ev: Evidence, web: FakeWeb, node: str) -> bool:
    s = web.subject(Here("node", node))
    return (
        s is not None
        and web.stub(Here("node", node)) is False
        and any(r.on is not None and r.on.hash == s.hash for r in ev.about("node", node, of="compared"))
    )


def unearned(ev: Evidence, web: FakeWeb, here: Here, lean_now: Callable[[Record], bool]) -> list[str]:
    """Why a `formalized` status is not earned; [] when it is."""
    subject = web.subject(here)
    assert subject is not None
    leans = [r for r in ev.about(*subject.key, of="lean") if r.on is not None and r.on.hash == subject.hash and lean_now(r)]  # fmt: skip
    proving = [r for r in leans if proves(r, subject)]
    if not proving:
        return ["no standing Lean record on the text now proves it"]
    attestations = [
        r
        for r in ev.about(*subject.key, of="attested")
        if r.on is not None
        and r.on.hash == subject.hash
        and any(dict(r.get("statements")) == statements_of(x) for x in proving)  # fmt: skip
    ]
    if not attestations:
        return ["no attestation on the text now of a proving record's statements"]
    now = web.closure(here)
    held = []
    for a in attestations:
        named = {Subject.from_dict(m).key: Subject.from_dict(m).hash for m in a.get("closure")}
        wrong = [k for k, v in named.items() if web.resolve(k, here) != v]
        wrong += [k for k, v in now.items() if named.get(k) != v]
        wrong += [Subject.from_dict(u).key for x in proving for u in x.get("uses") if Subject.from_dict(u).key not in named]  # fmt: skip
        held.append(wrong)
    out = [f"the attestation does not hold {min(held, key=len)}"] if all(held) else []
    for name, digest in web.notation(here).items():
        if not any(r.on is not None and r.on.hash == digest for r in ev.about("macro", name, of="attested")):
            out.append(f"notation {name} not attested in its definition now")
    out += [f"{k[1]} under it is not read and compared now" for k in now if k[0] == "node" and not compared_now(ev, web, k[1])]  # fmt: skip
    return out


def said(s: Status) -> tuple[object, ...]:
    return (s.lean, s.reading, s.role, s.causes, s.waiting_on, s.unattested_notation)


CHUNKS = [range(0, 150), range(150, 300), range(300, 450), range(450, 600)]


def statuses(lines: Callable[[History, random.Random], list[dict[str, Any]]] | None = None, seeds: range = range(0)):  # type: ignore[no-untyped-def]
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
    for where, ev, web, here, lean_now, s, _ in statuses(seeds=seeds):
        if s.lean == "formalized":
            assert unearned(ev, web, here, lean_now) == [], where
        if s.reading == "matches":
            assert compared_now(ev, web, here.name), where


@pytest.mark.parametrize("seeds", CHUNKS, ids=str)
def test_the_order_of_the_lines_moves_no_status(seeds: range) -> None:
    """Each thing's records are ordered by when they were written, not by where a merge put them."""
    for where, _ev, _web, _here, _now, s, again in statuses(lambda made, rng: rng.sample(made.lines, len(made.lines)), seeds):  # fmt: skip
        assert again is not None and said(again) == said(s), where


def _repeat(made: History, rng: random.Random) -> list[dict[str, Any]]:
    lines = list(made.lines)
    if lines:
        lines.insert(rng.randrange(len(lines) + 1), rng.choice(lines))
    return lines


@pytest.mark.parametrize("seeds", CHUNKS, ids=str)
def test_a_line_repeated_anywhere_moves_no_status(seeds: range) -> None:
    for where, _ev, _web, _here, _now, s, again in statuses(_repeat, seeds):
        assert again is not None and said(again) == said(s), where
