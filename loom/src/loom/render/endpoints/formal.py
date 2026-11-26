"""Formalization: what asking an agent to formalize results comes to, the asking, the person's attestation of a Lean statement (`docs/specs/evidence.md` §7), and the switch and loom's own check (`loom.formal`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain
from loom.render.endpoints.review import _as, _person, one_block

#: The status each refusal of an act answers with; any other is 409.
_STATUS = {"author-only": 403, "agent-only": 403, "no-such-result": 404, "no-such-node": 404, "no-such-proposal": 404, "no-such-citation": 404, "refused": 400}  # fmt: skip


def refusal(exc: Any) -> ApiError:
    """An act's refusal (`evidence.acts.ActRefused`) as the write API answers it."""
    return ApiError(exc.code, str(exc), status=_STATUS.get(exc.code, 409))


def webs(root: Path) -> tuple[Any, Any]:
    """The drafts' web over the publisher's scan, and that web joined with the library's."""
    from loom.evidence.web import DraftWeb, Joined, LibraryWeb

    drafts = DraftWeb(_scan(root))
    return drafts, Joined(drafts, LibraryWeb(root))


def here_of(drafts: Any, result: str) -> Any:
    """Where a result is, by what a row names it with: a draft's block by its key, as the records resolve one, its place key too (`review.one_block`), which is asked first since it has the shape of a node's id, else a node by its id; `no-such-result` (404) otherwise, `ambiguous` (409) for a label naming several blocks."""
    from loom.evidence.subjects import is_node
    from loom.evidence.web import Here, blocks_named

    if blocks_named(drafts.result, result) or not is_node(result):
        return Here("block", one_block(drafts.result, result).key)
    return Here("node", result)


def _formal_attest(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-attest`: the person's word that the Lean statement of the observation says what the result says, on its texts now; recorded as the reviewer whatever `author` names, which the answer says."""
    from loom.evidence.acts import ActRefused, attest
    from loom.evidence.status import files_unchanged

    who = _person(root, body)
    result = _str(body, "result", required=True) or ""
    observation = _str(body, "observation", required=True) or ""
    drafts, web = webs(root)
    try:
        attest(root, web, here_of(drafts, result), observation, who, lean_now=files_unchanged(root))
    except ActRefused as exc:
        raise refusal(exc) from exc
    return {"ok": True, "result": "attested" + _as(body, who)}


class _Planner:
    """One read's way to a plan: the drafts' results as the Web reads them, the library's by its files, each as an `Item`, what each uses, and each as a list's row."""

    def __init__(self, root: Path) -> None:
        import json

        from loom.evidence.web import Joined, LibraryWeb
        from loom.evidence.webview import drafts
        from loom.paths import MANIFEST

        try:
            manifest = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            manifest = {}
        self.manifest: dict[str, Any] = manifest
        self.root = root
        self.drafts = drafts(_scan(root), manifest, root)
        self.library = LibraryWeb(root)
        self.web = Joined(self.drafts.web, self.library)
        self._nodes: dict[str, Any] = {}

    def _node(self, key: str) -> Any:
        from loom.evidence.status import status
        from loom.evidence.web import Here

        if key not in self._nodes:
            self._nodes[key] = status(self.drafts.evidence, self.web, Here("node", key), lean_now=self.drafts.lean_now)
        return self._nodes[key]

    def item(self, key: str) -> Any:
        from loom.evidence.plan import STATED, Item

        node = self.drafts.node(key)
        if node is not None:
            taxon = str(self.manifest.get("nodes", {}).get(key, {}).get("taxon") or node.taxon or "").lower()
            return Item(key, True, bool(node.labels), taxon in STATED, self.drafts.standing(key))
        held = self.library.file(key)
        return Item(key, False, True, held is not None and held[1].taxon in STATED, self._node(key))

    def uses(self, key: str) -> tuple[list[str], list[str]]:
        if self.drafts.node(key) is not None:
            statement, proofs = self.drafts.uses(key)
            return statement, [p for p, _ in proofs]
        held = self.library.file(key)
        # a library result is assumed, never proved: what its proofs use is not followed
        return ([u for u in held[1].uses if self.library.file(u) is not None] if held else []), []

    def key_of(self, key: str) -> tuple[str, str] | None:
        """A result's lasting name as records name it: a node's id, or a draft's label; None for a draft's result with none."""
        from loom.evidence.web import Here

        if self.drafts.is_library(key):
            return ("node", key)
        found = self.drafts.web.subject(Here("block", key))
        return found.key if found is not None else None

    def elaborated(self, found: Any) -> bool:
        """Whether a result's current Lean record is on its text now, still stands and elaborated: accepted, and the kernel's replay passed."""
        from loom.evidence.plan import elaborated

        return elaborated(self.drafts.evidence, found, self.drafts.lean_now)

    def before(self, target: str, found: Any) -> list[Any]:
        """What stands before `target` reads formalized, from the gate's own needs (`plan.asked_of`) of its Lean, or of the Lean the request will make (`plan.asked`, `status.needs`), each as the person reads it (`plan.needed`), the target's own Lean first."""
        from loom.evidence.acts import attest_refusal, unreadable
        from loom.evidence.plan import asked, asked_of, needed, target_need
        from loom.evidence.status import Waiting, needs
        from loom.evidence.web import Here

        here = Here("block", target)
        evidence, now = self.drafts.evidence, self.drafts.lean_now

        def planned() -> list[Waiting]:
            nodes, assumed, rests = asked(found, target, self.drafts.is_library, self.key_of)
            nodes += [n for kind, n in self.web.closure(here) if kind == "node" and n not in nodes]
            subject = self.web.subject(here)
            seen = frozenset({subject.name}) if subject is not None else frozenset()
            return needs(evidence, self.web, nodes, assumed, now, seen, list(self.web.cited(here)), here, rests)

        leaves = asked_of(evidence, self.web, self.drafts.standing(target), now, planned)

        def refusal(at: Here) -> Any:
            return lambda: attest_refusal(evidence, self.web, at, now)

        def own(key: tuple[str, str]) -> Any:
            if key[0] == "node":
                if not self.drafts.is_library(key[1]):
                    return None
                found = self._node(key[1])
                return key[1], found, self.elaborated(found), refusal(Here("node", key[1]))
            there = self.drafts.web.holder(key, here)
            if there is None or self.drafts.node(there.name) is None:
                return None
            standing = self.drafts.standing(there.name)
            return there.name, standing, self.elaborated(standing), refusal(there)

        standing = self.drafts.standing(target)

        def paper(node: str) -> str | None:
            return unreadable(self.root, node)

        mine = target_need(target, standing, self.elaborated(standing), refusal(here), self.web.texts, paper)
        return mine + [n for n in needed(leaves, own, self.web.texts, paper) if n not in mine]

    def row(self, key: str) -> dict[str, Any]:
        from loom.evidence.webview import node_row

        if self.drafts.node(key) is not None:
            # a result of the person's carries its statement's fragment, which the panel shows a click away
            return {**self.drafts.row(key), "fragment": self.manifest.get("nodes", {}).get(key, {}).get("fragment")}
        held = self.library.file(key)
        return node_row(key, self._node(key), held[1] if held else None, self.library)

    def entry(self, need: Any) -> dict[str, Any]:
        """One thing standing before, as `before` sends it: a result's row, a citation's `{cite}`, a label's `{label, results}` with a row for each block bearing it, or a node the library holds no result by, `{node}`."""
        if need.of == "cite":
            return {"cite": need.key}
        if need.of == "label":
            return {"label": need.key, "results": [self.row(n.key) for n in self.drafts.web.bearing.get(need.key, [])]}
        if need.of == "node":
            return {"node": need.key}
        return self.row(need.key)

    def target(self, key: str) -> dict[str, Any]:
        row = self.row(key)
        fragment = self.manifest.get("nodes", {}).get(key, {}).get("fragment")
        return {"key": key, "name": row["name"], "title": row["title"], "doc": row["source"]["doc"], "statement": {"fragment": fragment}}  # fmt: skip


def _results(body: dict[str, Any], name: str, *, required: bool) -> list[str]:
    value = body.get(name)
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value) or not all(isinstance(k, str) and k for k in value):
        raise ApiError("bad-field", f"{name} is a {'nonempty ' if required else ''}list of results' keys")
    return list(dict.fromkeys(value))


def _planned(root: Path, body: dict[str, Any]) -> tuple[_Planner, list[str], list[str]]:
    """The planner for one read, the targets and the results chosen assumed for now; a target that is no result of the person's documents is `no-such-result` (404)."""
    planner = _Planner(root)
    # each key as the records resolve one, a place key as well as a label key
    targets = [_drafts_key(planner, k) for k in _results(body, "targets", required=True)]
    assume = [_drafts_key(planner, k) if not planner.drafts.is_library(k) else k for k in _results(body, "assume", required=False)]  # fmt: skip
    for key in targets:
        if planner.drafts.node(key) is None:
            raise ApiError("no-such-result", f"{key} is no result of your documents; reload", status=404)
    return planner, list(dict.fromkeys(targets)), list(dict.fromkeys(assume))


def _drafts_key(planner: _Planner, key: str) -> str:
    """A requested result's key now, as the records resolve one (`review.one_block`); `no-such-result`, `ambiguous` as it refuses."""
    return str(one_block(planner.drafts.result, key).key)


def _formal_plan(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-plan`: what asking an agent to formalize the targets comes to, and what stops it or stands before it reads formalized."""
    from loom.evidence.plan import plan
    from loom.library.generation import generation

    planner, targets, assume = _planned(root, body)
    found = plan(targets, assume, planner.item, planner.uses, planner.before)
    row = planner.row
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for need in found.before:
        groups.setdefault((need.why, need.when), []).append({**planner.entry(need), "for": found.asking[need]})
    return {
        "ok": True,
        "targets": [planner.target(k) for k in found.targets],
        "state": [row(k) for k in found.state],
        "prove": [{**row(k), "assume": chosen} for k, chosen in found.prove],
        "assume": [{**row(k), "why": why} for k, why in found.assume],
        "formalized": [row(k) for k in found.formalized],
        "stops": [row(k) for k in found.stops],
        "before": [{"why": why, "when": when, "results": results} for (why, when), results in groups.items()],
        "gen": generation(_scan(root)),
    }


def _formal_ask(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-ask`: one task for an agent for each target, its plan in it; refused `needs-label` while a target, or a result to state or prove, has no label, which loom never writes."""
    from loom.evidence.asks import AskRefused, ask
    from loom.evidence.asks import refusal as ask_refusal
    from loom.evidence.plan import plan
    from loom.evidence.web import Here

    who = _person(root, body)
    planner, targets, assume = _planned(root, body)
    plans = {t: plan([t], assume, planner.item, planner.uses) for t in targets}
    stops = list(dict.fromkeys(k for p in plans.values() for k in p.stops))
    if stops:
        names = ", ".join(planner.row(k)["name"] or k for k in stops)
        raise ApiError("needs-label", f"{names} needs a label first; add it in your source", status=409)

    def subject(key: str) -> dict[str, Any]:
        found = planner.web.subject(Here("block" if planner.drafts.node(key) is not None else "node", key))
        if found is None:
            raise ApiError("needs-label", f"{key} needs a label first; add it in your source", status=409)
        return found.to_dict()

    # every target's ask is made and checked before any is written, so a refusal leaves none written
    asks: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for key, p in plans.items():
        target = subject(key)
        fields = {
            "origin": planner.drafts.homes(key),
            "target": target,
            "state": [subject(k) for k in p.state],
            "prove": [subject(k) for k, chosen in p.prove if not chosen],
            "assume": [subject(k) for k, chosen in p.prove if chosen] + [subject(k) for k, _why in p.assume],
        }
        problem = ask_refusal(who, "formalize", "agent", {"label": target["label"]}, **fields)
        if problem:
            raise ApiError("refused", problem, status=400)
        asks.append(({"label": target["label"]}, fields))
    tasks = []
    for on, fields in asks:
        try:
            tasks.append(ask(root, who, "formalize", "agent", on, **fields).id)
        except AskRefused as exc:
            raise ApiError("refused", str(exc), status=400) from exc
    return {"ok": True, "tasks": tasks, "result": f"asked for {len(tasks)}" + _as(body, who)}


def _formal_state(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-state`: whether formalization is on for the quilt on this machine, whether it has a Lean project, whether loom can check Lean here, and what the server is doing for it or did last."""
    from loom import fence
    from loom.formal import install, jobs, switch

    job = jobs.current(root)
    return {
        "ok": True,
        "on": switch.is_on(root),
        "project": install.LEAN if (install.project(root) / "lakefile.toml").is_file() else None,
        "fence": fence.lean_state(),
        "job": job.to_dict() if job else None,
    }


def _formal_enable(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-enable`: the person turns formalization on for the quilt on this machine, which starts the install, or off; refused for a declared agent, since turning it on lets loom run code on this machine."""
    from loom.formal import install, jobs, switch

    _person(root, body)
    on = body.get("on")
    if not isinstance(on, bool):
        raise ApiError("bad-field", "on is true or false")
    if not on:
        switch.turn_off(root)
        return {"ok": True, "result": "formalization is off on this machine"}
    switch.turn_on(root)

    def work(tell: Any) -> dict[str, Any]:
        done = install.install(root, say=tell)
        return {"steps": [{"step": s, "seconds": round(t, 1)} for s, t in done.steps]}

    started = jobs.start(root, "install", work)
    if started is None:
        raise ApiError("busy", "loom is already installing or checking Lean for this quilt", status=409)
    return {"ok": True, "result": "formalization is on; installing Lean"}


def _formal_check(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`formal-check`: run loom's own check of the quilt's Lean again, in the background; `off` (409) while formalization is off here, `busy` (409) while an install or a check runs."""
    from loom.formal import jobs, switch

    if not switch.is_on(root):
        raise ApiError("off", "formalization is off for this quilt on this machine", status=409)
    if jobs.start_check(root) is None:
        raise ApiError("busy", "loom is already installing or checking Lean for this quilt", status=409)
    return {"ok": True, "result": "checking the Lean"}


HANDLERS: dict[str, Handler] = {
    "formal-plan": plain(_formal_plan),
    "formal-ask": plain(_formal_ask),
    "formal-attest": plain(_formal_attest),
    "formal-state": plain(_formal_state),
    "formal-enable": plain(_formal_enable),
    "formal-check": plain(_formal_check),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("formal-plan", "formal-state")
#: The ones the publisher does not rebuild after: the reads, and the two that start work in the background, which writes nothing the build reads but records.
NO_REBUILD: tuple[str, ...] = (*READS, "formal-enable", "formal-check")
#: The ones that change records alone, so the publication builds from the last scan, which tells the viewer something changed.
RECORD_WRITES: tuple[str, ...] = ("formal-ask", "formal-attest")
