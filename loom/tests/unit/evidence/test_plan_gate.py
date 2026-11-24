"""What `formal-plan` names before the target reads formalized is what the gate asks, both ways, over random libraries of real node files: the list is empty exactly when the target reads formalized; when every thing named that can be done is done, round after round, and the Lean is written as the plan says, the target reads formalized unless something nobody can do now stands; with any one left undone it does not.

Each library has definitions and lemmas, stubs, nodes compared or not, some with Lean of their own (which may use the Lean of what their header uses, or come round to the target's), attested or not, some whose text changed after, and some deleted from the library; a draft's target uses some by its statement and others by its proof, and may cite a result no node answers for. The plan is asked as the endpoint asks it (`plan.asked`, `status.needs`, `plan.needed`). Doing a thing is what the person, or the agent and the person, would do: put a deleted node back, fill a stub and compare it, compare a node, attest a Lean on its text now, or have one written and attest it; a citation and a Lean that comes round are done by nobody. The target's own Lean is then written honestly, each library result to assume an axiom of it and each library result to state, and each with its Lean already, used by it. A node's notation is held known and empty here, as its work's macros will make it, so the plan and the gate are tested apart from that.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from loom.evidence.log import Evidence, parse
from loom.evidence.plan import STATED, Item, Need, asked, asked_of, elaborated, needed, plan, target_need
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

    def __init__(self, lib: LibraryWeb, statement: list[str], cites: list[str]) -> None:
        self.lib, self.statement, self.cites = lib, statement, cites

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
        return list(self.cites) if here == T else []

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
        self.cites: list[str] = []
        #: a node whose own Lean uses the target's, so the target's, resting on it, comes round
        self.round: str | None = None
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
                if self.round is None and self.rng.random() < 0.1:
                    self.round = n
                record = self.lean(n, [u for u in node.uses if self.rng.random() < 0.3], target=self.round == n)
                if self.rng.random() < 0.6:
                    self.attest(n, record)
                    if self.rng.random() < 0.25:
                        changed.append(n)
        for n in changed:
            self.write(Node(**{**self.nodes[n].__dict__, "pages": "2"}))
        self.statement = [x for x in self.ids if self.rng.random() < 0.4]
        self.proof = [x for x in self.ids if x not in self.statement and self.rng.random() < 0.4]
        self.cites = ["R Theorem 2"] if self.rng.random() < 0.1 else []
        #: deleted from the library after all that, its records kept
        self.gone = [x for x in self.ids if self.rng.random() < 0.1]
        for n in self.gone:
            (folder(self.root) / f"{n}.node").unlink()

    def write(self, node: Node) -> None:
        self.nodes[node.id] = node
        (folder(self.root) / f"{node.id}.node").write_bytes(node_bytes(node))

    def web(self) -> Joined:
        lib = Known(self.root)
        return Joined(Target(lib, getattr(self, "statement", []), self.cites), lib)

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

    def lean(self, n: str, uses: list[str], *, target: bool = False) -> dict[str, Any]:
        """Lean of a node's own, a `def` for a definition, an axiom for a lemma, that uses the Lean of `uses`, and the target's with `target`."""
        web = self.web()
        s = web.subject(Here("node", n))
        assert s is not None
        kind = "def" if self.nodes[n].taxon in STATED else "axiom"
        declaration = {"name": f"x_{n}", "kind": kind, "role": "states", "names": {"node": n}, "statement": h("5"), "axioms": [], "sorry": False}  # fmt: skip
        used = [{"node": u, "hash": web.subject(Here("node", u)).hash} for u in uses]  # type: ignore[union-attr]
        used += [{"label": LABEL, "hash": h("7")}] if target else []
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
            def planned() -> list[Any]:
                nodes, assumed, rests = asked(found, target, lambda k: k != "T", key_of)
                nodes += [n for kind, n in web.closure(T) if kind == "node" and n not in nodes]
                return needs(ev, web, nodes, assumed, now, frozenset({LABEL}), web.cited(T), T, rests)

            leaves = asked_of(ev, web, self.status("T"), now, planned)

            def own(key: tuple[str, str]) -> tuple[str, Status, bool] | None:
                if key == ("label", LABEL):
                    return "T", self.status("T"), elaborated(ev, self.status("T"), now)
                return (key[1], standing[key[1]], elaborated(ev, standing[key[1]], now)) if key[0] == "node" else None

            mine = target_need("T", self.status("T"), elaborated(ev, self.status("T"), now))
            return ([mine] if mine else []) + needed(leaves, own, web.texts)

        self.found = plan(["T"], [], item, uses, before)
        return self.found.before

    def do(self, need: Need) -> None:
        """Do one entry as the list says: the person's now, the agent's after (a Lean written, which the person attests in a later round)."""
        if need.why == "missing":
            self.write(self.nodes[need.key])
        elif need.why == "not-read":
            self.write(Node(**{**self.nodes[need.key].__dict__, "body": f"Text of {need.key}."}))
            self.compare(need.key)
        elif need.why == "not-checked":
            self.compare(need.key)
        elif need.when == "after" and need.key == "T":
            self.plan()
            self.formalize()
        elif need.when == "after":
            self.lean(need.key, [])
        else:
            self.attest(need.key)

    def formalize(self) -> None:
        """The target's own Lean, written as the plan says."""
        web = self.web()
        assume = [k for k, _ in self.found.assume]
        # a node still deleted is used by nothing Lean can name
        used = [k for k in [*self.found.state, *self.found.lean] if web.subject(Here("node", k)) is not None]
        decls = [{"name": "t", "kind": "theorem", "role": "states", "names": {"label": LABEL}, "statement": h("1"), "axioms": ["propext", *(f"ax_{a}" for a in assume)], "sorry": False}]  # fmt: skip
        decls += [{"name": f"ax_{a}", "kind": "axiom", "role": "states", "names": {"node": a}, "statement": h("5"), "axioms": [], "sorry": False} for a in assume]  # fmt: skip
        uses = [{"node": u, "hash": web.subject(Here("node", u)).hash} for u in used]  # type: ignore[union-attr]
        self.add({"kind": "lean", "by": {"kind": "loom"}, "on": {"label": LABEL, "hash": h("7")}, "project": {"root": "lean", "toolchain": "t", "mathlib": "m", "manifest": h("2")}, "files": {"lean/A.lean": h("8")}, "declarations": decls, "assumed": [], "uses": uses, "replay": {"tool": "x", "exit": 0, "output": ""}, "ok": True})  # fmt: skip


#: The order a round does things in: what is deleted put back first, then what is read and compared, then what is attested.
ORDER = {"missing": 0, "not-read": 1, "not-checked": 2}


def _done(root: Path, seed: int, skip: tuple[int, int] | None) -> tuple[World, list[list[Need]], list[Need], Status]:
    """The library made from `seed`, worked as the list says: the person does what it names `now`, round after round until it names nothing more, then the agent what it names `after`, then the person again, up to three times; `skip`, a round and an entry of it, is never done. The rounds, the list at the end and the target's status."""
    world = World(root, seed)
    rounds: list[list[Need]] = []
    skipped: list[Need] = []

    def act(when: str) -> bool:
        todo = [n for n in world.plan() if n.when == when and n.why != "cycle" and n not in skipped]
        if skip is not None and skip[0] == len(rounds):
            skipped.append(todo.pop(skip[1]))
        rounds.append(list(todo))
        for need in sorted(todo, key=lambda n: ORDER.get(n.why, 3)):
            world.do(need)
        return bool(todo)

    for _ in range(3):
        while act("now") and len(rounds) < 30:
            pass
        if not act("after"):
            break
    return world, rounds, world.plan(), world.status("T")


@pytest.mark.parametrize("seeds", [range(0, 150), range(150, 300)], ids=str)
def test_what_the_plan_names_before_is_what_the_gate_asks_both_ways(seeds: range, tmp_path: Path) -> None:
    seen: dict[str, int] = {}
    for seed in seeds:
        world, rounds, left, after = _done(tmp_path / f"{seed}", seed, None)
        # the list names something exactly while the gate keeps the target from reading formalized
        assert (left == []) == (after.lean == "formalized"), (seed, left, after.waiting_on)
        if not world.cites and world.round is None:
            assert after.lean == "formalized", (seed, rounds, left, after.waiting_on)
        for need in [*left, *(n for r in rounds for n in r)]:
            seen[need.why] = seen.get(need.why, 0) + 1
        last = max((i for i, r in enumerate(rounds) if r), default=None)
        if after.lean == "formalized" and last is not None:
            skip = (last, random.Random(seed).randrange(len(rounds[last])))
            _, _, left, without = _done(tmp_path / f"{seed}-skip", seed, skip)
            assert without.lean != "formalized" and left, (seed, rounds[last][skip[1]])
    # every kind of thing the random libraries can ask is asked somewhere
    assert {"missing", "not-read", "not-checked", "cite", "attest", "cycle"} <= set(seen), seen
