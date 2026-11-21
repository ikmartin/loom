"""The Web's reads over the drafts: their results listed by document or by status, a search in their statements, a result's neighbourhood and its graph (`docs/design/library.md`, "The views"; `docs/specs/evidence.md` §8).

A result is a theorem-like block of a document of the person's, named by its key as the manifest names it, drawn from the manifest's numbers and fragments and the scan's edges, its `lean` from the evidence (§5). The library's nodes join these lists with the node store; until then a scope that asks for them finds none, and nothing here guesses them.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from loom.evidence.log import Evidence, Record
from loom.evidence.status import status
from loom.evidence.web import DraftWeb, Here

if TYPE_CHECKING:
    from loom.scan.nodes import NodeRec
    from loom.scan.scan import ScanResult

#: The scopes a person chooses in the Web.
SCOPES = ("library", "draft", "deps", "all")
#: A status's place when results are sorted by it: what waits on the person before what is settled (the views spec, §5.2).
_BY_STATUS = {"unattested": 2, "changed": 2, "waiting": 2, "none": 3, "rerun": 3, "failed": 3, "formalized": 6}
#: The most rows of what uses a result sent at once; the rest are counted.
USED_BY = 50
#: The most rows of a column of the graph drawn; a longer one draws one fewer and counts the rest.
COLUMN = 6
#: What an excerpt leaves out whole: an environment's head and foot with its options, a label, a reference or a citation with its argument; then any command, brace, dollar or tie.
_FRAME = re.compile(
    r"\\(?:begin|end)\s*\{[^}]*\}(?:\s*\[[^\]]*\])?"
    r"|\\(?:label|[a-zA-Z]*ref|[cC]ref|cite[a-z]*)\*?\s*(?:\[[^\]]*\]\s*)?\{[^}]*\}"
)
_COMMAND = re.compile(r"\\[A-Za-z@]+\*?|[{}$~]")
_SPACE = re.compile(r"\s+")


class ScopeError(ValueError):
    """A scope that is not one of `SCOPES`, or that needs a document and was given none."""


@dataclass
class Drafts:
    """The drafts' results as the Web reads them, from one scan, the published manifest and the evidence.

    Every question is memoised on the instance, which lives for one read.
    """

    result: ScanResult
    manifest: dict[str, Any]
    evidence: Evidence
    lean_now: Callable[[Record], bool]
    _status: dict[str, str] = field(default_factory=dict, repr=False)

    @cached_property
    def web(self) -> DraftWeb:
        return DraftWeb(self.result)

    @cached_property
    def documents(self) -> list[str]:
        """The person's documents, in path order."""
        return sorted(m for m in self.result.masters if self.result.document_role(m) == "person")

    @cached_property
    def results(self) -> list[NodeRec]:
        """Every result of the person's documents, in document order."""
        mine = set(self.documents)
        found = [n for n in self.web.blocks if set(n.reached_by) & mine]
        return sorted(found, key=lambda n: (n.order, n.file, n.start))

    @cached_property
    def _keys(self) -> dict[str, NodeRec]:
        return {n.key: n for n in self.results}

    @cached_property
    def position(self) -> dict[str, int]:
        """Each result's place in document order."""
        return {n.key: i for i, n in enumerate(self.results)}

    def node(self, key: str) -> NodeRec | None:
        """A result of the drafts by its key; None for anything else."""
        return self._keys.get(key)

    @cached_property
    def _formal(self) -> set[str]:
        """The labels some `lean` or `attested` record names: every other result reads `none` without computing it."""
        return {
            r.on.name for r in self.evidence.records if r.on and r.on.kind == "label" and r.kind in ("lean", "attested")
        }

    def lean(self, key: str) -> str:
        """A result's `lean` (§5.2), computed only where a record speaks of its label."""
        if key not in self._status:
            node = self._keys[key]
            if not set(node.labels) & self._formal:
                self._status[key] = "none"
            else:
                self._status[key] = status(self.evidence, self.web, Here("block", key), lean_now=self.lean_now).lean
        return self._status[key]

    def row(self, key: str) -> dict[str, Any]:
        """A result as a list sends it (`ROW`): its key, its name and title, its taxon's word, its document, `paper` null for a draft's, and its `lean`."""
        node = self._keys[key]
        published = self.manifest.get("nodes", {}).get(key, {})
        taxon = str(published.get("taxon") or node.taxon or "")
        doc = next((d for d in node.reached_by if d in self.documents), node.reached_by[0] if node.reached_by else None)
        numbers = published.get("numbers") or {}
        given = numbers.get(doc) or next(iter(numbers.values()), None)
        number = given.get("number") if isinstance(given, dict) else None
        return {
            "result": key,
            "name": f"{taxon} {number}".strip() if number else taxon,
            "title": published.get("title") or node.title,
            "taxon": taxon.lower(),
            "source": {"doc": doc},
            "paper": None,
            "lean": self.lean(key),
        }

    def scope(self, scope: str, doc: str | None) -> list[str]:
        """The keys a scope holds: one draft's results, those with every result they use by statement or proof, every draft's, or the library's (none before the node store)."""
        if scope not in SCOPES:
            raise ScopeError(f"scope is one of {', '.join(SCOPES)}")
        if scope == "library":
            return []
        if scope == "all":
            return [n.key for n in self.results]
        if not doc:
            raise ScopeError(f"the scope {scope} names a draft in doc")
        own = [n.key for n in self.results if doc in n.reached_by]
        if scope == "draft":
            return own
        seen = set(own)
        todo = list(own)
        while todo:
            for used in self.uses_all(todo.pop()):
                if used not in seen:
                    seen.add(used)
                    todo.append(used)
        return [n.key for n in self.results if n.key in seen]

    def _targets(self, key: str) -> list[str]:
        return [t for t in self.result.dependencies.review_targets(key) if t in self._keys and t != key]

    def uses(self, key: str) -> tuple[list[str], list[tuple[str, int]]]:
        """What a result's statement uses, and what each of its proofs uses as `(key, proof's number among them)`."""
        node = self._keys[key]
        statement = self._targets(key)
        proofs: list[tuple[str, int]] = []
        for n, proof in enumerate(node.proofs):
            for t in self._targets(proof):
                # a proof's own statement is what it proves, not what it uses
                if t != key and t not in [p for p, _ in proofs]:
                    proofs.append((t, n))
        return statement, proofs

    def uses_all(self, key: str) -> list[str]:
        """Everything a result uses, by statement or by proof."""
        statement, proofs = self.uses(key)
        return list(dict.fromkeys([*statement, *(p for p, _ in proofs)]))

    @cached_property
    def used_by(self) -> dict[str, list[tuple[str, bool]]]:
        """Each result, with the results that use it and whether by a proof."""
        out: dict[str, list[tuple[str, bool]]] = {}
        for n in self.results:
            statement, proofs = self.uses(n.key)
            for t in statement:
                out.setdefault(t, []).append((n.key, False))
            for t, _ in proofs:
                if not any(k == n.key for k, _p in out.get(t, [])):
                    out.setdefault(t, []).append((n.key, True))
        return out

    def text(self, key: str) -> str:
        """A result's statement as written, comments blanked: what search reads and a snippet is cut from."""
        from loom.scan.owntext import own_text
        from loom.scan.source import blank_comments

        return blank_comments(own_text(self.result, self._keys[key]))


def drafts(result: ScanResult, manifest: dict[str, Any], root: Any) -> Drafts:
    """The drafts' results for one read of the quilt at `root`."""
    from loom.evidence.log import replay
    from loom.evidence.status import files_unchanged

    return Drafts(result, manifest, replay(root), files_unchanged(root))


def _status_order(d: Drafts, key: str) -> int:
    return _BY_STATUS.get(d.lean(key), 4)


def listing(
    d: Drafts, scope: str, doc: str | None, *, sort: str = "document", opened: list[str] | None = None, offset: int = 0
) -> dict[str, Any]:
    """`web-list`: the results a scope holds, by document in sections or by status two hundred at a time.

    Parameters
    ----------
    d : Drafts
        The drafts as read now.
    scope : str
        One of `SCOPES`.
    doc : str, optional
        The draft `draft` and `deps` are of.
    sort : str, default 'document'
        `document` or `status`.
    opened : list of str, optional
        The groups (documents) whose rows are sent though folded by default.
    offset : int, default 0
        By status, where the two hundred sent begin.

    Returns
    -------
    dict
        `{count, sections, undigested}` by document; `{count, rows, more}` by status.
    """
    keys = d.scope(scope, doc)
    if sort == "status":
        ordered = sorted(keys, key=lambda k: (_status_order(d, k), d.position[k]))
        page = ordered[offset : offset + 200]
        return {"count": len(keys), "rows": [d.row(k) for k in page], "more": max(0, len(ordered) - offset - len(page))}
    opened = opened or []
    if scope in ("draft", "deps"):
        own = [k for k in keys if doc in d.node(k).reached_by]  # type: ignore[union-attr]
        sections: list[dict[str, Any]] = [{"head": "draft", "doc": doc, "rows": [d.row(k) for k in own]}]
        if scope == "deps":
            others = [k for k in keys if k not in own]
            sections.append({"head": "uses", "doc": doc, "groups": _groups(d, others, opened, open_all=True)})
        return {"count": len(keys), "sections": sections, "undigested": 0}
    sections = [{"head": "drafts", "groups": _groups(d, keys, opened, open_all=False)}]
    if scope == "all":
        sections.append({"head": "library", "groups": []})
    return {"count": len(keys), "sections": sections, "undigested": 0}


def _groups(d: Drafts, keys: list[str], opened: list[str], *, open_all: bool) -> list[dict[str, Any]]:
    """The keys by the document that holds them, each group's rows sent only when it is open."""
    by_doc: dict[str, list[str]] = {}
    for k in keys:
        node = d.node(k)
        home = next((x for x in node.reached_by if x in d.documents), "") if node else ""
        by_doc.setdefault(home, []).append(k)
    out = []
    for home in sorted(by_doc):
        group: dict[str, Any] = {"group": home, "n": len(by_doc[home])}
        if open_all or home in opened:
            group["rows"] = [d.row(k) for k in by_doc[home]]
        out.append(group)
    return out


def group(d: Drafts, scope: str, doc: str | None, home: str) -> dict[str, Any]:
    """`web-group`: one document's results within a scope, for a group opened after the list was sent."""
    keys = [k for k in d.scope(scope, doc) if home in d.node(k).reached_by]  # type: ignore[union-attr]
    return {"group": home, "n": len(keys), "rows": [d.row(k) for k in keys]}


def _plain(text: str) -> str:
    """A statement in plain words for an excerpt: its environment's head and foot and its labels, then commands, braces and ties dropped, spaces made one."""
    words = _SPACE.sub(" ", _COMMAND.sub(" ", _FRAME.sub(" ", text))).strip()
    return re.sub(r" ([,.;:)])", r"\1", words)


def search(d: Drafts, scope: str, doc: str | None, q: str, *, limit: int = 50) -> dict[str, Any]:
    """`web-search`: results whose number, name or title holds the query, then those whose statement's words do, each statement hit with the words around it.

    Words are compared without regard to case; a query of several words must find them in order, spaces between them read as any space. A hit's `snippet` is cut from the statement's LaTeX at spaces, about sixty characters either side.
    """
    words = q.split()
    if not words:
        return {"count": 0, "hits": []}
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words), re.I)
    named: list[dict[str, Any]] = []
    in_text: list[dict[str, Any]] = []
    for key in d.scope(scope, doc):
        row = d.row(key)
        if any(pattern.search(str(row.get(f) or "")) for f in ("name", "title")):
            named.append({"row": row, "snippet": None})
            continue
        text = d.text(key)
        found = pattern.search(text)
        if found:
            before = text[max(0, found.start() - 60) : found.start()]
            after = text[found.end() : found.end() + 60]
            before = before[before.find(" ") + 1 :] if found.start() > 60 and " " in before else before
            after = after[: after.rfind(" ")] if " " in after and found.end() + 60 < len(text) else after
            in_text.append(
                {"row": row, "snippet": {"before": before.lstrip(), "match": found.group(0), "after": after.rstrip()}}
            )
    hits = (named + in_text)[:limit]
    return {"count": len(named) + len(in_text), "hits": hits}


def focus(d: Drafts, scope: str, doc: str | None, key: str, *, more: bool = False) -> dict[str, Any]:
    """`web-focus`: a result, its statement's fragment, what it is verified relative to, what its statement and its proofs use, and what uses it, each list held to the scope with what lies outside counted."""
    node = d.node(key)
    if node is None:
        raise KeyError(key)
    inside = set(d.scope(scope, doc))
    statement, proofs = d.uses(key)
    many = len(node.proofs) > 1
    users = d.used_by.get(key, [])
    users_in = [u for u, _p in users if u in inside]
    lean = d.lean(key)
    answer: dict[str, Any] = {
        "row": d.row(key),
        "statement": {"fragment": d.manifest.get("nodes", {}).get(key, {}).get("fragment")},
        "relative_to": [] if lean == "formalized" else None,
        "rests_on": [],
        "more": _more(d, key) if more else None,
        "uses": {
            "statement": [d.row(k) for k in statement if k in inside],
            "proof": [{**d.row(k), **({"proof": n + 1} if many else {})} for k, n in proofs if k in inside],
            "outside": {
                "statement": sum(1 for k in statement if k not in inside),
                "proof": sum(1 for k, _n in proofs if k not in inside),
            },
        },
        "used_by": {
            "rows": [d.row(k) for k in users_in[:USED_BY]],
            "outside": len(users) - len(users_in),
            "more": max(0, len(users_in) - USED_BY),
        },
    }
    return answer


def _more(d: Drafts, key: str) -> dict[str, Any]:
    """The fold of a result's card: its proofs with what each uses, the Lean declarations that state it, and the record of what was done to it."""
    node = d.node(key)
    assert node is not None
    proofs = []
    for proof in node.proofs:
        uses = [t for t in d.result.dependencies.review_targets(proof) if d.node(t) is not None and t != key]
        proofs.append({"where": d.result.nodes[proof].file, "uses": [d.row(t) for t in uses]})
    acts = {"lean": "lean-accepted", "attested": "attested", "compared": "verified", "digested": "digested"}
    record = []
    lean: list[str] = []
    for label in node.labels:
        for r in d.evidence.about("label", label):
            if r.kind == "lean" and r.get("ok"):
                lean = [x["name"] for x in r.get("declarations", []) if x.get("role") == "states"]
            if r.kind in acts and (r.kind != "lean" or r.get("ok")):
                record.append(
                    {"act": acts[r.kind], "by": "you" if r.by.kind == "person" else (r.by.name or "loom"), "at": r.at}
                )
    return {"proofs": proofs, "lean": lean, "record": record}


def graph(d: Drafts, scope: str, doc: str | None, key: str) -> dict[str, Any]:
    """`web-graph`: four columns, two steps back, what it uses, the result, what uses it; a column of more than `COLUMN` draws one fewer and counts the rest; the edges only among what is drawn."""
    if d.node(key) is None:
        raise KeyError(key)
    inside = set(d.scope(scope, doc))
    uses = [k for k in d.uses_all(key) if k in inside]
    back = [
        k for k in dict.fromkeys(b for u in uses for b in d.uses_all(u)) if k in inside and k != key and k not in uses
    ]
    used_by = [k for k, _p in d.used_by.get(key, []) if k in inside]

    def cut(keys: list[str]) -> tuple[list[str], int]:
        return (keys, 0) if len(keys) <= COLUMN else (keys[: COLUMN - 1], len(keys) - COLUMN + 1)

    (back_drawn, back_more), (uses_drawn, uses_more), (by_drawn, by_more) = cut(back), cut(uses), cut(used_by)
    drawn = {key, *back_drawn, *uses_drawn, *by_drawn}
    edges = []
    for src in sorted(drawn):
        statement, proofs = d.uses(src)
        for t in statement:
            if t in drawn:
                edges.append({"from": src, "to": t, "proof": False})
        for t, _n in proofs:
            if t in drawn and t not in statement:
                edges.append({"from": src, "to": t, "proof": True})
    return {
        "focus": d.row(key),
        "excerpt": _plain(d.text(key))[:200],
        "columns": {
            "back": [d.row(k) for k in back_drawn],
            "uses": [d.row(k) for k in uses_drawn],
            "used_by": [d.row(k) for k in by_drawn],
        },
        "more": {"back": back_more, "uses": uses_more, "used_by": by_more},
        "edges": edges,
    }
