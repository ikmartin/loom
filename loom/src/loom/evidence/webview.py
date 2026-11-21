"""The Web's reads over the drafts: their results listed by document or by status, a search in their statements, a result's neighbourhood and its graph (`docs/design/library.md`, "The views"; `docs/specs/evidence.md` §8).

A result is a theorem-like block of a document of the person's, named by its key as the manifest names it, drawn from the manifest's numbers and fragments and the scan's edges, its `lean` from the evidence (§5). What it uses is status's own walk (`web.rests_on`), so the Web and status never disagree about what rests on what. The library's nodes join these lists with the node store; until then a scope that asks for them finds none, and nothing here guesses them.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from loom.evidence.log import Evidence, Record
from loom.evidence.status import Status, brief, states, status
from loom.evidence.web import DraftWeb, Here, rests_on

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
#: What an excerpt leaves out whole: an environment's head and foot with its options, a label, a `\uses`, a reference or a citation with its arguments; then any command or escaped character, brace, dollar or tie.
_FRAME = re.compile(
    r"\\(?:begin|end)\s*\{[^}]*\}(?:\s*\[[^\]]*\])?"
    r"|\\(?:label|uses|[a-zA-Z]*ref|[cC]ref|cite[a-z]*)\*?\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}"
)
_COMMAND = re.compile(r"\\(?:[A-Za-z@]+\*?|[^A-Za-z@\s])|[{}$~]")
_SPACE = re.compile(r"\s+")
_EMPTY = re.compile(r"\(\s*\)")
#: A word, as the node index's tokenizer splits a body's or a search's words: a run of letters and digits.
_TOKEN = re.compile(r"[^\W_]+")
#: What a statement's block has and a node's body has not, left out before the node index's rules read it: the environment's head with its options and its foot, its labels, and loom's `\uses` with its labels, which the index does not know.
_BLOCK = re.compile(r"\\begin\s*\{[^}]*\}(?:\s*\[[^\]]*\])?|\\end\s*\{[^}]*\}|\\(?:label|uses)\s*\{[^}]*\}")


class ScopeError(ValueError):
    """A scope that is not one of `SCOPES`, or that needs a document and was given none."""


@dataclass
class Drafts:
    """The drafts' results as the Web reads them, from one scan, the published manifest and the evidence.

    Every question is memoised on the instance, which the endpoints keep while its scan and every file it read are unchanged (`memo.kept`), so nothing it hands out may be changed by a caller.
    """

    result: ScanResult
    manifest: dict[str, Any]
    evidence: Evidence
    lean_now: Callable[[Record], bool]
    _status: dict[str, str] = field(default_factory=dict, repr=False)
    _standing: dict[str, Status] = field(default_factory=dict, repr=False)
    _rests: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _uses: dict[str, tuple[list[str], list[tuple[str, int]]]] = field(default_factory=dict, repr=False)
    _words: dict[str, str] = field(default_factory=dict, repr=False)
    _scopes: dict[tuple[str, str | None], list[str]] = field(default_factory=dict, repr=False)

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
    def _blocks(self) -> frozenset[str]:
        return frozenset(n.key for n in self.web.blocks)

    @cached_property
    def _homes(self) -> dict[str, list[str]]:
        mine = set(self.documents)
        return {n.key: sorted(set(n.reached_by) & mine) for n in self.results}

    @cached_property
    def position(self) -> dict[str, int]:
        """Each result's place in document order."""
        return {n.key: i for i, n in enumerate(self.results)}

    def node(self, key: str) -> NodeRec | None:
        """A result of the drafts by its key; None for anything else."""
        return self._keys.get(key)

    def homes(self, key: str) -> list[str]:
        """The person's documents that read a result, in path order: the groups it is listed in."""
        return self._homes[key]

    @cached_property
    def _formal(self) -> set[str]:
        """The labels some `lean` or `attested` record names: every other result reads `none` without computing it."""
        return {
            r.on.name for r in self.evidence.records if r.on and r.on.kind == "label" and r.kind in ("lean", "attested")
        }

    def standing(self, key: str) -> Status:
        """How a result stands (§5.2), computed only where a record speaks of its label; `Status(None)`, `lean` `none`, elsewhere."""
        if key not in self._standing:
            node = self._keys[key]
            named = set(node.labels) & self._formal
            here = Here("block", key)
            self._standing[key] = (
                status(self.evidence, self.web, here, lean_now=self.lean_now) if named else Status(None)
            )
        return self._standing[key]

    def lean(self, key: str) -> str:
        """A result's `lean` word, what a list by status orders by."""
        if key not in self._status:
            self._status[key] = self.standing(key).lean
        return self._status[key]

    def row(self, key: str, doc: str | None = None) -> dict[str, Any]:
        """A result as a list sends it (`ROW`): its key, its name and title, its taxon's word, its document, `paper` null for a draft's, and how it stands, `reading` and `lean` (`status.brief`).

        Its document is `doc` where that reads it, else the first of its `homes`; its number is the one the build published for that document.
        """
        node = self._keys[key]
        published = self.manifest.get("nodes", {}).get(key, {})
        taxon = str(published.get("taxon") or node.taxon or "")
        home = doc if doc is not None and doc in node.reached_by else self.homes(key)[0]
        numbers = published.get("numbers") or {}
        given = numbers.get(home) or next(iter(numbers.values()), None)
        number = given.get("number") if isinstance(given, dict) else None
        return {
            "result": key,
            "name": f"{taxon} {number}".strip() if number else taxon,
            "title": published.get("title") or node.title,
            "taxon": taxon.lower(),
            "source": {"doc": home},
            "paper": None,
            # how it stands, never a bare word: the reading of a paper (none for a draft's), the Lean word, its role and what it waits on
            "reading": self.standing(key).reading,
            "lean": brief(self.standing(key)),
        }

    def scope(self, scope: str, doc: str | None) -> list[str]:
        """The keys a scope holds: one draft's results, those with every result they use by statement or proof, every draft's, or the library's (none before the node store)."""
        if scope not in SCOPES:
            raise ScopeError(f"scope is one of {', '.join(SCOPES)}")
        if scope in ("draft", "deps") and not doc:
            raise ScopeError(f"the scope {scope} names a draft in doc")
        if (scope, doc) not in self._scopes:
            self._scopes[scope, doc] = self._scope(scope, doc)
        return self._scopes[scope, doc]

    def _scope(self, scope: str, doc: str | None) -> list[str]:
        if scope == "library":
            return []
        if scope == "all":
            return [n.key for n in self.results]
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

    def rests(self, key: str) -> list[str]:
        """The results the statement or proof at `key` uses directly, by status's own walk (`rests_on`) over every block of the drafts, kept to the Web's results."""
        if key not in self._rests:
            self._rests[key] = [k for k in rests_on(self.result, key, self._blocks) if k in self._keys]
        return self._rests[key]

    def uses(self, key: str) -> tuple[list[str], list[tuple[str, int]]]:
        """What a result's statement uses, and what each of its proofs uses as `(key, proof's number among them)`."""
        if key not in self._uses:
            proofs: list[tuple[str, int]] = []
            for n, proof in enumerate(self._keys[key].proofs):
                for t in self.rests(proof):
                    # a proof's own statement is what it proves, not what it uses
                    if t != key and t not in [p for p, _ in proofs]:
                        proofs.append((t, n))
            self._uses[key] = (self.rests(key), proofs)
        return self._uses[key]

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
        """A result's statement as written, comments blanked: what its words and an excerpt are made from."""
        from loom.scan.owntext import own_text
        from loom.scan.source import blank_comments

        return blank_comments(own_text(self.result, self._keys[key]))

    def words(self, key: str) -> str:
        """A result's statement as search reads it (`_statement_words`)."""
        if key not in self._words:
            self._words[key] = _statement_words(self.text(key))
        return self._words[key]


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
        `{count, sections, undigested}` by document; `{count, rows, more}` by status. `count` is the results the scope holds, each once, though a result two documents read is in the group of each.
    """
    keys = d.scope(scope, doc)
    if sort == "status":
        ordered = sorted(keys, key=lambda k: (_status_order(d, k), d.position[k]))
        page = ordered[offset : offset + 200]
        return {
            "count": len(keys),
            "rows": [d.row(k, doc) for k in page],
            "more": max(0, len(ordered) - offset - len(page)),
        }
    opened = opened or []
    if scope in ("draft", "deps"):
        own = [k for k in keys if doc in d.node(k).reached_by]  # type: ignore[union-attr]
        sections: list[dict[str, Any]] = [{"head": "draft", "doc": doc, "rows": [d.row(k, doc) for k in own]}]
        if scope == "deps":
            groups = _groups(d, _grouped(d, scope, doc), opened, open_all=True)
            sections.append({"head": "uses", "doc": doc, "groups": groups})
        return {"count": len(keys), "sections": sections, "undigested": 0}
    sections = [{"head": "drafts", "groups": _groups(d, keys, opened, open_all=False)}]
    if scope == "all":
        sections.append({"head": "library", "groups": []})
    return {"count": len(keys), "sections": sections, "undigested": 0}


def _grouped(d: Drafts, scope: str, doc: str | None) -> list[str]:
    """The keys a scope lists in groups by document: under `deps` those its draft does not read, else all of them.

    `web-list` and `web-group` both read this, so a group opened later holds what the list counted in it.
    """
    keys = d.scope(scope, doc)
    if scope == "deps":
        return [k for k in keys if doc not in d.node(k).reached_by]  # type: ignore[union-attr]
    return keys


def _groups(d: Drafts, keys: list[str], opened: list[str], *, open_all: bool) -> list[dict[str, Any]]:
    """The keys in a group for each of the person's documents that reads them (`homes`), a group's rows sent only when it is open.

    A result two documents read is in both groups, its row in each naming that document.
    """
    by_doc: dict[str, list[str]] = {}
    for k in keys:
        for home in d.homes(k):
            by_doc.setdefault(home, []).append(k)
    out = []
    for home in sorted(by_doc):
        group: dict[str, Any] = {"group": home, "n": len(by_doc[home])}
        if open_all or home in opened:
            group["rows"] = [d.row(k, home) for k in by_doc[home]]
        out.append(group)
    return out


def group(d: Drafts, scope: str, doc: str | None, home: str) -> dict[str, Any]:
    """`web-group`: one document's group within a scope, as `web-list` counts it, for a group opened after the list was sent.

    Parameters
    ----------
    d : Drafts
        The drafts as read now.
    scope : str
        One of `SCOPES`.
    doc : str, optional
        The draft `draft` and `deps` are of.
    home : str
        The document whose group is opened.

    Returns
    -------
    dict
        `{group, n, rows}`: every result of the scope's groups (`_grouped`) that `home` reads, each row naming `home`.
    """
    keys = [k for k in _grouped(d, scope, doc) if home in d.homes(k)]
    return {"group": home, "n": len(keys), "rows": [d.row(k, home) for k in keys]}


def _plain(text: str) -> str:
    """A statement in plain words for an excerpt: its environment's head and foot, its labels, uses, references and citations, then commands, braces and ties dropped, the parentheses a reference leaves empty with them, spaces made one."""
    words = _SPACE.sub(" ", _EMPTY.sub(" ", _COMMAND.sub(" ", _FRAME.sub(" ", text)))).strip()
    return re.sub(r" ([,.;:)])", r"\1", words)


def _statement_words(text: str) -> str:
    """The words of a statement as the node index holds a body's (`library.index.words`): case and accents folded, comments, references, citations and labels left out, read from the block as a body (`_body`)."""
    from loom.library.index import words

    return words(_body(text))


def _body(text: str) -> str:
    """A statement's block as a node's body reads, its frame, labels and `\\uses` left out (`_BLOCK`)."""
    return _BLOCK.sub(" ", text)


def _holds(said: str, terms: list[str]) -> bool:
    """Whether words hold every term as the node index matches a search: each a whole word, the last also as the start of a longer one, in any order."""
    found = _TOKEN.findall(said)
    return all(t in found for t in terms[:-1]) and any(w.startswith(terms[-1]) for w in found)


def search(d: Drafts, scope: str, doc: str | None, q: str, *, limit: int = 50) -> dict[str, Any]:
    """`web-search`: results whose number, name or title holds the query, then those whose statement's words do (`_statement_words`), each statement hit with the words around it.

    Matched as the node index matches a search (`library.index`): every word of the query among the statement's words (`_statement_words`), each a whole word and the last also the start of a longer one, case and accents folded, so `label` finds neither `\\label` nor "unlabelled" and `poly` finds "polynomial". A hit's `snippet` is the index's (`library.index.snippet`): the match as written in the statement's LaTeX, a formula whole, with about sixty characters either side cut at spaces outside mathematics, "…" marking a cut.

    Parameters
    ----------
    d : Drafts
        The drafts as read now.
    scope : str
        One of `SCOPES`.
    doc : str, optional
        The draft `draft` and `deps` are of.
    q : str
        The words searched for; blank finds nothing.
    limit : int, default 50
        The most hits sent.

    Returns
    -------
    dict
        `{count, hits: [{row, snippet}]}`, `count` every hit, `snippet` null for a hit on the name or title and `{before, match, after}` for one in the statement.
    """
    from loom.library.index import snippet, words

    terms = _TOKEN.findall(words(q))
    if not terms:
        return {"count": 0, "hits": []}
    named: list[dict[str, Any]] = []
    in_text: list[dict[str, Any]] = []
    for key in d.scope(scope, doc):
        row = d.row(key, doc)
        if _holds(words(f"{row.get('name') or ''} {row.get('title') or ''}"), terms):
            named.append({"row": row, "snippet": None})
            continue
        if _holds(d.words(key), terms):
            cut = snippet(_body(d.text(key)), terms)
            where = (
                {"before": cut.before, "match": cut.match, "after": cut.after}
                if cut
                else {"before": "", "match": terms[-1], "after": ""}
            )
            in_text.append({"row": row, "snippet": where})
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
        "row": d.row(key, doc),
        "statement": {"fragment": d.manifest.get("nodes", {}).get(key, {}).get("fragment")},
        "relative_to": [] if lean == "formalized" else None,
        "rests_on": [],
        "more": _more(d, key, doc) if more else None,
        "uses": {
            "statement": [d.row(k, doc) for k in statement if k in inside],
            "proof": [{**d.row(k, doc), **({"proof": n + 1} if many else {})} for k, n in proofs if k in inside],
            "outside": {
                "statement": sum(1 for k in statement if k not in inside),
                "proof": sum(1 for k, _n in proofs if k not in inside),
            },
        },
        "used_by": {
            "rows": [d.row(k, doc) for k in users_in[:USED_BY]],
            "outside": len(users) - len(users_in),
            "more": max(0, len(users_in) - USED_BY),
        },
    }
    return answer


def _more(d: Drafts, key: str, doc: str | None) -> dict[str, Any]:
    """The fold of a result's card: its proofs with what each uses, the Lean declarations that state it, and the record of what was done to it.

    Only records on this block's own text (its subject's hash) count, as in status: the declarations are the current `lean` record's (the last standing one on this text that states it), the acts those on this text.
    """
    node = d.node(key)
    assert node is not None
    proofs = [
        {"where": d.result.nodes[proof].file, "uses": [d.row(t, doc) for t in d.rests(proof) if t != key]}
        for proof in node.proofs
    ]
    subject = d.web.subject(Here("block", key))
    if subject is None:
        return {"proofs": proofs, "lean": [], "record": []}
    names = {subject.kind: subject.name}
    mine = [r for r in d.evidence.about(*subject.key) if r.on is not None and r.on.hash == subject.hash]
    current = [r for r in mine if r.kind == "lean" and states(r, subject) and d.lean_now(r)]
    lean = [
        x["name"]
        for x in (current[-1].get("declarations", []) if current else [])
        if x.get("role") == "states" and x.get("names") == names
    ]
    acts = {"lean": "lean-accepted", "attested": "attested", "compared": "verified", "digested": "digested"}
    record = [
        {"act": acts[r.kind], "by": "you" if r.by.kind == "person" else (r.by.name or "loom"), "at": r.at}
        for r in mine
        if r.kind in acts and (r.kind != "lean" or r.get("ok"))
    ]
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
        "focus": d.row(key, doc),
        "excerpt": _plain(d.text(key))[:200],
        "columns": {
            "back": [d.row(k, doc) for k in back_drawn],
            "uses": [d.row(k, doc) for k in uses_drawn],
            "used_by": [d.row(k, doc) for k in by_drawn],
        },
        "more": {"back": back_more, "uses": uses_more, "used_by": by_more},
        "edges": edges,
    }
