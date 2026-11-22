"""What `formal-plan` names before the target reads formalized is what the gate asks, both ways, over random libraries of real node files: when every thing named is done and the Lean is written as the plan says, the target reads formalized; with any one left undone it does not.

Each library has definitions and lemmas, stubs, nodes compared or not, some with Lean of their own (which may use the Lean of what their header uses), attested or not, and some whose text changed after; a draft's target uses some by its statement and others by its proof. The plan is asked as the endpoint asks it (`plan.asked`, `status.needs`, `plan.needed`). Doing a thing is what the person, or the agent and the person, would do: fill a stub and compare it, compare a node, attest a Lean on its text now, or have one written and attest it. The target's own Lean is then written honestly, each library result to assume an axiom of it and each library result to state, and each with its Lean already, used by it. A node's notation is held known and empty here, as its work's macros will make it, so the plan and the gate are tested apart from that.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from loom.evidence.log import Evidence, parse
from loom.evidence.plan import STATED, Item, Need, asked, elaborated, needed, plan, target_need
from loom.evidence.status import Status, closure_now, needs, statements_of, status
from loom.evidence.subjects import Subject
from loom.evidence.web import Here, Joined, LibraryWeb
from loom.library.node import Node, node_bytes
from loom.library.store import folder

REF = "tq-00RF-ref"
T = Here("block", "T")
LABEL = "t:main"


def h(c: str) -> str:
    return "sha256:" + c * 64


class Known(LibraryWeb):
    """The library's web with every node's notation known and empty, as its work's macros will make it."""

    def notation(self, here: Here) -> dict[str, str] | None:
        return {}


class Target:
    """The draft's one result, `T`: its statement uses `statement` (library nodes), its text fixed."""

    def __init__(self, lib: LibraryWeb, statement: list[str]) -> None:
        self.lib, self.statement = lib, statement

    def subject(self, here: Here) -> Subject | None:
        return Subject("label", LABEL, h("7")) if here == T else None

    def resolve(self, key: tuple[str, str], near: Here) -> str | None:
        return self.lib.resolve(key, near) if key[0] == "node" else (h("7") if key == ("label", LABEL) else None)

    def closure(self, here: Here) -> dict[tuple[str, str], str]:
        out: dict[tuple[str, str], str] = {}
        for n in self.statement if here == T else []:
            s = self.lib.subject(Here("node", n))
            if s is not None:
                out[("node", n)] = s.hash
                out.update(self.lib.closure(Here("node", n)))
        return out

    def notation(self, here: Here) -> dict[str, str]:
        return {}

    def acceptance(self, here: Here) -> None:
        return None

    def stub(self, here: Here) -> None:
        return None

    def holds(self, ref: str, want: str) -> None:
        return None

    def cited(self, here: Here) -> list[str]:
        return []

    def holder(self, key: tuple[str, str], near: Here) -> Here | None:
        return T if key == ("label", LABEL) else None

    def texts(self, key: tuple[str, str]) -> set[str]:
        return {h("7")} if key == ("label", LABEL) else set()


class World:
    """One random library, its records, and the target, made again from `seed` alone."""

    def __init__(self, root: Path, seed: int) -> None:
        self.root, self.rng = root, random.Random(seed)
        self.lines: list[dict[str, Any]] = []
        nodes = folder(root)
        nodes.mkdir(parents=True)
        (nodes / f"{REF}.node").write_bytes(node_bytes(Node(id=REF, taxon="reference", pdf=h("9"), body="@article{R,\n  title = {R},\n}\n")))  # fmt: skip
        self.ids = [f"tq-000{i}" for i in range(self.rng.randint(2, 6))]
        self.nodes: dict[str, Node] = {}
        for i, n in enumerate(self.ids):
            uses = tuple(x for x in self.ids[:i] if self.rng.random() < 0.35)
            stub = self.rng.random() < 0.2
            taxon = "definition" if self.rng.random() < 0.35 else "lemma"
            self.write(Node(id=n, taxon=taxon, source=REF, pages="1", uses=uses, body="" if stub else f"Text of {n}."))
        changed = []
        for n in self.ids:
            node, s = self.nodes[n], self.web().subject(Here("node", n))
            assert s is not None
            if not node.empty and self.rng.random() < 0.6:
                self.compare(n)
            # a node over a stub has no Lean here: reading the stub would change what its attestation names
            over_stub = any(self.nodes[k].empty for _, k in self.web().closure(Here("node", n)))
            if not node.empty and not over_stub and self.rng.random() < 0.5:
                record = self.lean(n, [u for u in node.uses if self.rng.random() < 0.3])
                if self.rng.random() < 0.6:
                    self.attest(n, record)
                    if self.rng.random() < 0.25:
                        changed.append(n)
        for n in changed:
            self.write(Node(**{**self.nodes[n].__dict__, "pages": "2"}))
        self.statement = [x for x in self.ids if self.rng.random() < 0.4]
        self.proof = [x for x in self.ids if x not in self.statement and self.rng.random() < 0.4]

    def write(self, node: Node) -> None:
        self.nodes[node.id] = node
        (folder(self.root) / f"{node.id}.node").write_bytes(node_bytes(node))

    def web(self) -> Joined:
        lib = Known(self.root)
        return Joined(Target(lib, self.statement if hasattr(self, "statement") else []), lib)

    def evidence(self) -> Evidence:
        ev = Evidence()
        for line in self.lines:
            ev.add(parse(line))
        return ev

    def add(self, line: dict[str, Any]) -> dict[str, Any]:
        n = len(self.lines) + 1
        line = {"id": f"ev-2026-11-21-{n:06d}", "at": f"2026-11-21T{n // 3600:02d}:{n // 60 % 60:02d}:{n % 60:02d}Z", **line}  # fmt: skip
        self.lines.append(line)
        return line

    def compare(self, n: str) -> None:
        s = self.web().subject(Here("node", n))
        assert s is not None
        self.add({"kind": "compared", "by": {"kind": "person", "name": "A"}, "on": s.to_dict(), "with": {"ref": REF, "pdf": h("9")}})  # fmt: skip

    def lean(self, n: str, uses: list[str]) -> dict[str, Any]:
        """Lean of a node's own, a `def` for a definition, an axiom for a lemma, that uses the Lean of `uses`."""
        web = self.web()
        s = web.subject(Here("node", n))
        assert s is not None
        kind = "def" if self.nodes[n].taxon in STATED else "axiom"
        declaration = {"name": f"x_{n}", "kind": kind, "role": "states", "names": {"node": n}, "statement": h("5"), "axioms": [], "sorry": False}  # fmt: skip
        used = [{"node": u, "hash": web.subject(Here("node", u)).hash} for u in uses]  # type: ignore[union-attr]
        return self.add({"kind": "lean", "by": {"kind": "loom"}, "on": s.to_dict(), "project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")}, "files": {"lean/A.lean": h("8")}, "declarations": [declaration], "assumed": [], "uses": used, "replay": {"tool": "x", "exit": 0, "output": ""}, "ok": True})  # fmt: skip

    def attest(self, n: str, record: dict[str, Any] | None = None) -> None:
        """The person attests a result's Lean on its text now (the latest standing one, or `record`) over its closure as it reads now."""
        web, ev = self.web(), self.evidence()
        here = T if n == "T" else Here("node", n)
        s = web.subject(here)
        assert s is not None
        found = ev.by_id(record["id"]) if record else ev.by_id(status(ev, web, here, lean_now=lambda r: True).lean_record or "")  # fmt: skip
        assert found is not None
        closure = [{k: m, "hash": v} for (k, m), v in sorted(closure_now(web, here, [found]).items())]
        self.add({"kind": "attested", "by": {"kind": "person", "name": "A"}, "on": s.to_dict(), "lean": found.id, "statements": statements_of(found), "closure": closure, "rulings": []})  # fmt: skip

    def status(self, n: str) -> Status:
        return status(self.evidence(), self.web(), T if n == "T" else Here("node", n), lean_now=lambda r: True)

    def plan(self) -> list[Need]:
        web, ev = self.web(), self.evidence()
        now: Any = lambda r: True  # noqa: E731
        standing = {n: self.status(n) for n in self.ids}

        def item(key: str) -> Item:
            if key == "T":
                return Item("T", True, True, False, self.status("T"))
            return Item(key, False, True, self.nodes[key].taxon in STATED, standing[key])

        def uses(key: str) -> tuple[list[str], list[str]]:
            return (self.statement, self.proof) if key == "T" else (list(self.nodes[key].uses), [])

        def key_of(key: str) -> tuple[str, str]:
            return ("label", LABEL) if key == "T" else ("node", key)

        def before(target: str, found: Any) -> list[Need]:
            nodes, assumed, rests = asked(found, target, lambda k: k != "T", key_of)
            nodes += [n for kind, n in web.closure(T) if kind == "node" and n not in nodes]
            leaves = needs(ev, web, nodes, assumed, now, frozenset({LABEL}), [], T, rests)

            def own(key: tuple[str, str]) -> tuple[str, Status, bool] | None:
                return (key[1], standing[key[1]], elaborated(ev, standing[key[1]], now)) if key[0] == "node" else None

            mine = target_need("T", self.status("T"), elaborated(ev, self.status("T"), now))
            return ([mine] if mine else []) + needed(leaves, own)

        self.found = plan(["T"], [], item, uses, before)
        return self.found.before

    def do(self, need: Need) -> None:
        if need.why == "not-read":
            self.write(Node(**{**self.nodes[need.key].__dict__, "body": f"Text of {need.key}."}))
            self.compare(need.key)
        elif need.why == "not-checked":
            self.compare(need.key)
        elif need.key != "T" and need.when == "after":
            self.attest(need.key, self.lean(need.key, []))
        elif need.key != "T":
            self.attest(need.key)

    def formalize(self) -> None:
        """The target's own Lean, written as the plan says, and the person's attestation of it."""
        web = self.web()
        assume = [k for k, _ in self.found.assume]
        used = [k for k in self.found.state] + self.found.lean
        decls = [{"name": "t", "kind": "theorem", "role": "states", "names": {"label": LABEL}, "statement": h("1"), "axioms": ["propext", *(f"ax_{a}" for a in assume)], "sorry": False}]  # fmt: skip
        decls += [{"name": f"ax_{a}", "kind": "axiom", "role": "states", "names": {"node": a}, "statement": h("5"), "axioms": [], "sorry": False} for a in assume]  # fmt: skip
        uses = [{"node": u, "hash": web.subject(Here("node", u)).hash} for u in used]  # type: ignore[union-attr]
        record = self.add({"kind": "lean", "by": {"kind": "loom"}, "on": {"label": LABEL, "hash": h("7")}, "project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")}, "files": {"lean/A.lean": h("8")}, "declarations": decls, "assumed": [], "uses": uses, "replay": {"tool": "x", "exit": 0, "output": ""}, "ok": True})  # fmt: skip
        self.attest("T", record)


def _done(root: Path, seed: int, skip: int | None) -> tuple[list[Need], Status]:
    world = World(root, seed)
    named = world.plan()
    order = {"not-read": 0, "not-checked": 1}
    for i, need in sorted(enumerate(named), key=lambda x: order.get(x[1].why, 2)):
        if i != skip:
            world.do(need)
    if skip is None or named[skip].key != "T":
        world.formalize()
    return named, world.status("T")


@pytest.mark.parametrize("seeds", [range(0, 150), range(150, 300)], ids=str)
def test_what_the_plan_names_before_is_what_the_gate_asks_both_ways(seeds: range, tmp_path: Path) -> None:
    named_any = 0
    for seed in seeds:
        named, after = _done(tmp_path / f"{seed}", seed, None)
        assert after.lean == "formalized", (seed, named, after.waiting_on)
        if named:
            skip = random.Random(seed).randrange(len(named))
            _, without = _done(tmp_path / f"{seed}-{skip}", seed, skip)
            assert without.lean != "formalized", (seed, named[skip])
            named_any += 1
    assert named_any > len(seeds) // 2
