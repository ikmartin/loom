"""The index loom derives from the library's nodes and the tag log (docs/design/library.md, "Scale"): SQLite at `.loom/cache/library/nodes.sqlite3`, with an FTS5 table for the words of statements and proofs.

Nothing makes it before it is asked for: `NodeIndex.open` makes it on first use and brings it up to date on each, reading again only the files whose size or modification time changed, and a file changed within `RACY` of the last update, whose time may not have moved. The tag log is replayed whole when it changed. An index of another version, or one SQLite cannot read, is made again; `rebuild` makes it again at will. A file that cannot be read as a node is left out of it; `checks` reports it.

A work's order is kept with records not built yet: `position` waits for them, and until then a work's statements stand in their numbers' order, read naturally, then by first page.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import time
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.library import ids
from loom.library.body import CITES, REFS, blank_comments, entry_of, labels
from loom.library.node import SUFFIX, Node, NodeUnreadable, node_hash, read_node
from loom.library.tags import replay
from loom.paths import LIBRARY_NODES, NODE_INDEX, TAG_LOG
from loom.scan.bib import parse_bib

#: The index's own number: an index of another is made again. Raised whenever what the index holds or how it is read changes.
VERSION = 1
#: Nanoseconds before the last update within which a file is read again though its size and time agree, since a change in the same tick leaves them as they were.
RACY = 2_000_000_000
#: Commands whose names carry no meaning, left out of a body's indexed words; any other command's name is a word, so `\Hom`, `\alpha` and `\otimes` find the statements that use them. `\begin` and `\end` take their environment's name with them.
QUIET = frozenset(
    {
        "emph", "textbf", "textit", "textrm", "textsf", "texttt", "textsc", "textup", "textnormal", "text", "mbox", "hbox",
        "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "mathbb", "mathcal", "mathfrak", "mathscr", "boldsymbol",
        "operatorname", "left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "middle",
        "begin", "end", "item", "label", "quad", "qquad", "displaystyle", "textstyle", "limits", "nolimits", "noindent",
        "par", "newline", "linebreak", "hspace", "vspace", "medskip", "smallskip", "bigskip", "ldots", "dots", "cdots",
        "colon", "mathop", "mathrel", "mathbin", "nonumber", "notag", "tag", "footnote", "ensuremath",
    }
)  # fmt: skip
_POINTED = re.compile(
    r"\\(?:" + "|".join(sorted(REFS | CITES | {"label"}, key=len, reverse=True)) + r")\*?\s*(?:\[[^\]]*\]\s*)*\{[^}]*\}"
)
_ENVIRONMENT = re.compile(r"\\(?:begin|end)\s*\{[^}]*\}")
_COMMAND = re.compile(r"\\([A-Za-z@]+)")
#: A word of a search shaped like a printed number with a dot, `3.4` or `A.2`, which matches a number exactly; a bare `2` or `2024` is a word.
#: The words a search is made of, as the index's tokenizer splits them: runs of letters and digits.
_TOKEN = re.compile(r"[^\W_]+")
_NUMBER = re.compile(r"[A-Za-z]?\d+(?:\.\d+)+[a-z]?|[A-Z](?:\.\d+)+")

_SCHEMA = """
CREATE TABLE files(name TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, hash TEXT NOT NULL, node TEXT);
CREATE TABLE nodes(
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, taxon TEXT NOT NULL, number TEXT, title TEXT, source TEXT, pages TEXT,
    parent TEXT, empty INTEGER NOT NULL, hash TEXT NOT NULL, citekey TEXT, numkey TEXT, pagekey TEXT, position INTEGER,
    header TEXT NOT NULL, body TEXT NOT NULL
);
CREATE INDEX nodes_source ON nodes(source);
CREATE INDEX nodes_parent ON nodes(parent);
CREATE INDEX nodes_taxon ON nodes(taxon);
CREATE INDEX nodes_number ON nodes(number);
CREATE INDEX nodes_citekey ON nodes(citekey COLLATE NOCASE);
CREATE INDEX nodes_folded ON nodes(id COLLATE NOCASE);
CREATE INDEX nodes_stubs ON nodes(source) WHERE kind = 'statement' AND empty = 1;
CREATE TABLE edges(src TEXT NOT NULL, kind TEXT NOT NULL, dst TEXT NOT NULL, PRIMARY KEY (src, kind, dst)) WITHOUT ROWID;
CREATE INDEX edges_dst ON edges(dst, kind);
CREATE TABLE anchors(owner TEXT NOT NULL, anchor TEXT NOT NULL, number TEXT, PRIMARY KEY (owner, anchor)) WITHOUT ROWID;
CREATE TABLE tags(node TEXT NOT NULL, folded TEXT NOT NULL, shown TEXT NOT NULL, PRIMARY KEY (node, folded)) WITHOUT ROWID;
CREATE INDEX tags_folded ON tags(folded);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE words USING fts5(name, title, work, text, tokenize = 'unicode61 remove_diacritics 2', prefix = '2 3');
"""
_ROW = "id, kind, taxon, number, title, source, pages, parent, empty, hash"


class IndexUnavailable(RuntimeError):
    """The index cannot be made on this Python: its SQLite lacks FTS5."""


@dataclass(frozen=True)
class Row:
    """A node as a list shows it: its id and kind, the header's words, whether it has text, and its hash."""

    id: str
    kind: str
    taxon: str
    number: str | None
    title: str | None
    source: str | None
    pages: str | None
    parent: str | None
    empty: bool
    hash: str


@dataclass(frozen=True)
class Snippet:
    """Where a search's words stand in a statement's LaTeX: the matching words, a whole formula when they are inside one, and the words before and after, cut at spaces outside mathematics, `…` marking a cut."""

    before: str
    match: str
    after: str


@dataclass(frozen=True)
class Hit:
    """A statement a search found: where the words matched, `name` (its taxon and number, or its title), `text`, `proof` or `work`; the words around the match in its LaTeX, for `text` and `proof`; and the proof the words were found in when they were not in the statement."""

    row: Row
    where: str | None = None
    snippet: Snippet | None = None
    in_proof: str | None = None


@dataclass(frozen=True)
class Refreshed:
    """What bringing the index up to date did: the files read, the nodes changed and removed, whether the tags changed, and the generation it left."""

    read: int
    changed: int
    removed: int
    tags: bool
    generation: int = 0


def words(body: str) -> str:
    """The words of a body as the index holds them: comments, the arguments of `\\ref`, `\\cite` and `\\label`, environments' names and `QUIET`'s commands left out, every other command's name a word."""
    text = _POINTED.sub(" ", blank_comments(body))
    text = _ENVIRONMENT.sub(" ", text)
    return _COMMAND.sub(lambda m: " " if m.group(1) in QUIET else f" {m.group(1)} ", text)


def natural(value: str | None) -> str | None:
    """A sort key that reads a number's digits as numbers: 3.2 before 3.10, before A.1."""
    if value is None:
        return None
    return "".join(part.zfill(10) if part.isdigit() else part for part in re.split(r"(\d+)", value))


def _work(entry_text: str) -> tuple[str | None, str]:
    """A reference's citekey, and the words a search of its work matches: the key, the authors, the title and the year."""
    entry = entry_of(entry_text)
    if entry is None or not entry.key:
        return None, ""
    fields = next(iter(parse_bib(entry_text).values()), None)
    got = fields.fields if fields else {}
    return entry.key, " ".join([entry.key, *(words(got.get(k, "")) for k in ("author", "title", "year"))])


class NodeIndex:
    """The index of one quilt's library, brought up to date when opened.

    Use `NodeIndex.open(root)`, as a context manager or closed by hand. It is also a `checks.StoreView`, which a write checks a node against.
    """

    def __init__(self, root: Path, db: sqlite3.Connection) -> None:
        self.root = root
        self.db = db
        self._works: dict[str, str] = {}

    # ---- making and keeping ------------------------------------------------------------------------------------------

    @classmethod
    def open(cls, root: Path, *, refresh: bool = True) -> NodeIndex:
        """The quilt's index, made if it is not there and brought up to date.

        Parameters
        ----------
        root : Path
            The quilt.
        refresh : bool, default True
            Bring it up to date with the files and the tag log; False only for a caller that has just done so.

        Returns
        -------
        NodeIndex
            Open; close it, or use it in a `with`.

        Raises
        ------
        IndexUnavailable
            Where this Python's SQLite has no FTS5.
        """
        path = root / NODE_INDEX
        path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in (1, 2):
            db: sqlite3.Connection | None = None
            try:
                db = cls._connect(path)
                index = cls(root, db)
                if refresh:
                    index.refresh()
                return index
            except sqlite3.DatabaseError as exc:
                # a file SQLite cannot read is made again; a lock held too long, an `OperationalError`, is not
                if db is not None:
                    db.close()
                if type(exc) is not sqlite3.DatabaseError or attempt == 2:
                    raise
                _remove(path)
        raise AssertionError("unreachable")

    @staticmethod
    def _connect(path: Path) -> sqlite3.Connection:
        db = sqlite3.connect(path, timeout=60, isolation_level=None, check_same_thread=False)
        try:
            db.execute("PRAGMA synchronous = NORMAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version == VERSION:
                return db
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version != VERSION:
                for kind, name in db.execute(
                    "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'view')"
                ).fetchall():
                    if not name.startswith("sqlite_") and not name.startswith("words_"):
                        db.execute(f'DROP {kind.upper()} IF EXISTS "{name}"')
                try:
                    for statement in _SCHEMA.split(";"):
                        if statement.strip():
                            db.execute(statement)
                except sqlite3.OperationalError as exc:
                    if "fts5" in str(exc):
                        raise IndexUnavailable(
                            "this Python's SQLite has no FTS5, which the library's index needs; a Python from python.org, Homebrew or uv has it"
                        ) from exc
                    raise
                db.execute(f"PRAGMA user_version = {VERSION}")
            db.execute("COMMIT")
            return db
        except BaseException:
            with contextlib.suppress(sqlite3.Error):
                db.execute("ROLLBACK")
            db.close()
            raise

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> NodeIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def rebuild(self) -> Refreshed:
        """Make the index again from the files and the tag log, whatever it held.

        Returns
        -------
        Refreshed
            Every file read.
        """
        self.db.execute("BEGIN IMMEDIATE")
        try:
            for table in ("files", "nodes", "edges", "anchors", "tags", "meta", "words"):
                self.db.execute(f"DELETE FROM {table}")
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return self.refresh()

    def refresh(self) -> Refreshed:
        """Bring the index up to date with the files and the tag log.

        The folder is looked at once, without the write lock; only when something differs is the lock taken, and what was seen is read under it. The time of the update is taken before the look, so a file that changes while it is read is read again at the next.

        Returns
        -------
        Refreshed
            What was read and changed.
        """
        started = time.time_ns()
        present = _scan(self.root / LIBRARY_NODES)
        if self._unchanged(present):
            return Refreshed(0, 0, 0, False, self.generation())
        return self._update(present, started, None)

    def take(self, names: Iterable[str]) -> Refreshed:
        """Bring the index up to date for the files `names` alone, which a writer has just written or removed; the rest waits for the next update, which reads them again since they were written after the last.

        Parameters
        ----------
        names : iterable of str
            File names, `<id>.node`.

        Returns
        -------
        Refreshed
            What was read and changed.
        """
        folder = self.root / LIBRARY_NODES
        only = set(names)
        present: dict[str, os.stat_result] = {}
        for name in only:
            with contextlib.suppress(FileNotFoundError):
                present[name] = (folder / name).stat()
        return self._update(present, time.time_ns(), only)

    def _update(self, present: dict[str, os.stat_result], started: int, only: set[str] | None) -> Refreshed:
        self._works = {}
        self.db.execute("BEGIN IMMEDIATE")
        try:
            done = self._refresh(present, started, only)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return done

    def _unchanged(self, present: dict[str, os.stat_result]) -> bool:
        """Whether nothing needs reading: the same files with the same sizes and times, none written within `RACY` of the last update, and the tag log as it was."""
        last = int(self._meta("refreshed") or 0)
        if not last:
            return False
        known = {name: (size, mtime) for name, size, mtime in self.db.execute("SELECT name, size, mtime_ns FROM files")}
        if len(known) != len(present):
            return False
        for name, st in present.items():
            if known.get(name) != (st.st_size, st.st_mtime_ns) or st.st_mtime_ns >= last - RACY:
                return False
        return self._tags_due(last) is None

    def _tags_due(self, last: int) -> str | None:
        """The tag log's stamp when it must be replayed, its size and time differing from the last replay's or written within `RACY` of the last update; None when it need not be."""
        try:
            st = (self.root / TAG_LOG).stat()
            stamp, racy = f"{st.st_size}:{st.st_mtime_ns}", st.st_mtime_ns >= last - RACY
        except FileNotFoundError:
            stamp, racy = "none", False
        return stamp if self._meta("tags") != stamp or racy else None

    def _refresh(self, present: dict[str, os.stat_result], started: int, only: set[str] | None) -> Refreshed:
        """Read what differs among `present` under the write lock; `only` limits the update to those files, and then neither the tags nor the time of the last update move."""
        folder = self.root / LIBRARY_NODES
        last = int(self._meta("refreshed") or 0)
        rows = self.db.execute("SELECT name, size, mtime_ns, hash FROM files")
        known = {name: (size, mtime, digest) for name, size, mtime, digest in rows if only is None or name in only}
        read = changed = 0
        works: set[str] = set()
        fresh: set[str] = set()
        moved = False
        # references first, so a statement read in the same pass finds its work's words
        for name, st in sorted(present.items(), key=lambda item: not item[0].endswith(f"-ref{SUFFIX}")):
            was = known.get(name)
            if was and was[0] == st.st_size and was[1] == st.st_mtime_ns and st.st_mtime_ns < last - RACY:
                continue
            try:
                data = (folder / name).read_bytes()
            except OSError:
                continue
            read += 1
            digest = node_hash(data)
            if was and was[2] == digest:
                self.db.execute(
                    "UPDATE files SET size = ?, mtime_ns = ?, hash = ? WHERE name = ?",
                    (st.st_size, st.st_mtime_ns, digest, name),
                )
                continue
            changed += 1
            if was:
                moved |= self._has_node(name)
                works |= self._forget(name)
            node = None
            with contextlib.suppress(NodeUnreadable):
                node = read_node(data, name)
            self.db.execute(
                "INSERT INTO files(name, size, mtime_ns, hash, node) VALUES (?, ?, ?, ?, ?)",
                (name, st.st_size, st.st_mtime_ns, digest, node.id if node else None),
            )
            if node is not None:
                works |= self._remember(node, digest)
                fresh.add(node.id)
                moved = True
        removed = 0
        for name in set(known) - set(present):
            moved |= self._has_node(name)
            works |= self._forget(name)
            removed += 1
        if works:
            self._rework(works, fresh)
        tags = False if only is not None else self._retag(last)
        if only is None:
            self._set_meta("refreshed", str(started))
        generation = self.generation() + (1 if moved or tags else 0)
        self._set_meta("generation", str(generation))
        return Refreshed(read, changed, removed, tags, generation)

    def _has_node(self, name: str) -> bool:
        """Whether the file `name` gave the index a node."""
        row = self.db.execute("SELECT node FROM files WHERE name = ?", (name,)).fetchone()
        return bool(row and row[0])

    def _forget(self, name: str) -> set[str]:
        """Take the file `name` and its node out; the works whose words must be made again."""
        row = self.db.execute("SELECT node FROM files WHERE name = ?", (name,)).fetchone()
        self.db.execute("DELETE FROM files WHERE name = ?", (name,))
        if not row or row[0] is None:
            return set()
        node_id = row[0]
        was = self.db.execute("SELECT rowid, kind, source FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if was is None:
            return set()
        self.db.execute("DELETE FROM words WHERE rowid = ?", (was[0],))
        self.db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
        self.db.execute("DELETE FROM edges WHERE src = ?", (node_id,))
        self.db.execute("DELETE FROM anchors WHERE owner = ?", (node_id,))
        self._works.pop(node_id, None)
        return {node_id} if was[1] == ids.REFERENCE else set()

    def _remember(self, node: Node, digest: str) -> set[str]:
        """Put a node in; the works whose words must be made again."""
        citekey = None
        if node.kind == ids.REFERENCE:
            citekey, _ = _work(node.body)
        first_page = (node.pages or "").split("-")[0] or None
        cur = self.db.execute(
            f"INSERT INTO nodes({_ROW}, citekey, numkey, pagekey, header, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                node.id, node.kind, node.taxon, node.number, node.title, node.source, node.pages, node.parent, int(node.empty),
                digest, citekey, natural(node.number), natural(first_page), json.dumps(node.header()), node.body,
            ),
        )  # fmt: skip
        edges = [(node.id, "uses", t) for t in node.uses] + [(node.id, "mentions", t) for t in node.mentions]
        if node.source:
            edges.append((node.id, "source", node.source))
        self.db.executemany("INSERT OR IGNORE INTO edges(src, kind, dst) VALUES (?, ?, ?)", edges)
        self.db.executemany(
            "INSERT OR IGNORE INTO anchors(owner, anchor, number) VALUES (?, ?, ?)",
            [(node.id, p.target, dict(node.anchors).get(p.target)) for p in labels(node.body)],
        )
        if node.kind in (ids.STATEMENT, ids.PROOF):
            work = self._work_words(node.source)
            name = f"{node.taxon} {node.number or ''}".strip() if node.kind == ids.STATEMENT else ""
            self.db.execute(
                "INSERT INTO words(rowid, name, title, work, text) VALUES (?, ?, ?, ?, ?)",
                (cur.lastrowid, name, words(node.title or ""), work, words(node.body)),
            )
        return {node.id} if node.kind == ids.REFERENCE else set()

    def _work_words(self, source: str | None) -> str:
        """The words a search of `source`'s work matches, read once an update."""
        if not source:
            return ""
        if source not in self._works:
            row = self.db.execute("SELECT body FROM nodes WHERE id = ?", (source,)).fetchone()
            self._works[source] = _work(row[0])[1] if row else ""
        return self._works[source]

    def _rework(self, works: set[str], fresh: set[str]) -> None:
        """Make again the work words of every node read from one of `works`, whose entries changed, but those put in by this pass, which have them."""
        for work in works:
            self._works.pop(work, None)
            text = self._work_words(work)
            rows = self.db.execute(
                "SELECT rowid, id FROM nodes WHERE source = ? AND kind IN ('statement', 'proof')", (work,)
            ).fetchall()
            self.db.executemany(
                "UPDATE words SET work = ? WHERE rowid = ?", [(text, r[0]) for r in rows if r[1] not in fresh]
            )

    def _retag(self, last: int) -> bool:
        """Replay the tag log into the index when `_tags_due` says so; whether the tags on any node changed."""
        stamp = self._tags_due(last)
        if stamp is None:
            return False
        tags = replay(self.root)
        now = {
            (node, folded, tags.spelled[folded])
            for node, on in tags.holders.items()
            for folded, who in on.items()
            if who
        }
        was = set(self.db.execute("SELECT node, folded, shown FROM tags").fetchall())
        self._set_meta("tags", stamp)
        if now == was:
            return False
        self.db.execute("DELETE FROM tags")
        self.db.executemany("INSERT INTO tags(node, folded, shown) VALUES (?, ?, ?)", sorted(now))
        return True

    def generation(self) -> int:
        """The index's generation: a number raised by every update that changes a node or the tags on one, and by nothing else.

        A publisher that keeps a generation of its own for the views raises it whenever this one moves, so a view asks again only when what it was sent from the library may differ.

        Returns
        -------
        int
            0 for an index never updated.
        """
        return int(self._meta("generation") or 0)

    def _meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def _set_meta(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))

    # ---- what a write is checked against (`checks.StoreView`) --------------------------------------------------------

    def kind(self, node_id: str) -> str | None:
        row = self.db.execute("SELECT kind FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return row[0] if row else None

    def empty(self, node_id: str) -> bool:
        row = self.db.execute("SELECT empty FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return row is None or bool(row[0])

    def anchors(self, node_id: str) -> frozenset[str]:
        return frozenset(r[0] for r in self.db.execute("SELECT anchor FROM anchors WHERE owner = ?", (node_id,)))

    def anchor_number(self, anchor: str) -> str | None:
        """The number the source prints for `anchor`, from its owner's `anchors`; None when the owner gives it none or defines no such anchor.

        Parameters
        ----------
        anchor : str
            An anchor's id, `owner-eqNN` or `owner-itNN`.

        Returns
        -------
        str or None
            The number as `\\ref` prints it, without the parentheses `\\eqref` adds.
        """
        row = self.db.execute("SELECT number FROM anchors WHERE anchor = ?", (anchor,)).fetchone()
        return row[0] if row else None

    def keyed(self, key: str) -> frozenset[str]:
        rows = self.db.execute("SELECT id FROM nodes WHERE citekey = ? COLLATE NOCASE AND kind = 'reference'", (key,))
        return frozenset(r[0] for r in rows)

    def same_but_case(self, node_id: str) -> list[str]:
        """The nodes whose ids equal `node_id` ignoring case and are not it, which a case-blind file system would write over."""
        rows = self.db.execute("SELECT id FROM nodes WHERE id = ? COLLATE NOCASE AND id != ?", (node_id, node_id))
        return sorted(r[0] for r in rows)

    # ---- the questions -----------------------------------------------------------------------------------------------

    def node(self, node_id: str) -> Node | None:
        """The node `node_id` as its file says it, or None when the library has no such readable node.

        Parameters
        ----------
        node_id : str
            The id.

        Returns
        -------
        Node or None
            Every key of its header and its body.

        See Also
        --------
        row : the same node as a list shows it, with its hash.
        """
        found = self.db.execute("SELECT header, body FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if found is None:
            return None
        return Node.from_header(json.loads(found[0]), found[1])

    def row(self, node_id: str) -> Row | None:
        """The node `node_id` as a list shows it, with its hash, or None."""
        found = self.db.execute(f"SELECT {_ROW} FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return _row(found) if found else None

    def reference(self, citekey: str) -> Row | None:
        """The reference whose entry's key is `citekey`, compared ignoring case, or None."""
        found = self.db.execute(
            f"SELECT {_ROW} FROM nodes WHERE citekey = ? COLLATE NOCASE AND kind = 'reference' ORDER BY id", (citekey,)
        ).fetchone()
        return _row(found) if found else None

    def work(self, reference: str) -> list[Row]:
        """The nodes read from the work `reference`, in the paper's order: each statement followed by its proofs, then the work's proofs of other works' statements.

        Parameters
        ----------
        reference : str
            The reference's id.

        Returns
        -------
        list of Row
            Statements in their place's order where it is recorded, else their numbers' read naturally, then by first page and id.
        """
        statements = self._rows(
            f"SELECT {_ROW} FROM nodes WHERE source = ? AND kind = 'statement' ORDER BY position IS NULL, position, numkey IS NULL, numkey, pagekey, id",
            (reference,),
        )
        proofs = self._rows(
            f"SELECT {_ROW} FROM nodes WHERE source = ? AND kind = 'proof' ORDER BY pagekey, id", (reference,)
        )
        by_parent: dict[str, list[Row]] = {}
        for proof in proofs:
            by_parent.setdefault(proof.parent or "", []).append(proof)
        out: list[Row] = []
        for statement in statements:
            out.append(statement)
            out.extend(sorted(by_parent.pop(statement.id, []), key=lambda r: r.id))
        out.extend(p for rest in by_parent.values() for p in rest)
        return out

    def uses(self, node_id: str) -> list[Row]:
        """The nodes `node_id`'s header says its text uses, in id order; one not in the library is left out."""
        return self._edge("SELECT dst FROM edges WHERE src = ? AND kind = 'uses'", node_id)

    def mentions(self, node_id: str) -> list[Row]:
        """The nodes `node_id`'s header says its text mentions, in id order."""
        return self._edge("SELECT dst FROM edges WHERE src = ? AND kind = 'mentions'", node_id)

    def used_by(self, node_id: str) -> list[Row]:
        """The nodes whose text uses `node_id`, in id order."""
        return self._edge("SELECT src FROM edges WHERE dst = ? AND kind = 'uses'", node_id)

    def mentioned_by(self, node_id: str) -> list[Row]:
        """The nodes whose text mentions `node_id`, in id order."""
        return self._edge("SELECT src FROM edges WHERE dst = ? AND kind = 'mentions'", node_id)

    def proofs(self, statement: str) -> list[Row]:
        """The proofs of `statement`, in id order, which is the order they were given in."""
        return self._rows(f"SELECT {_ROW} FROM nodes WHERE parent = ? AND kind = 'proof' ORDER BY id", (statement,))

    def stubs(self, reference: str | None = None) -> list[Row]:
        """The statements whose text has not been read, of one work or of all, in their works' order."""
        where, args = ("AND source = ?", (reference,)) if reference else ("", ())
        return self._rows(
            f"SELECT {_ROW} FROM nodes WHERE kind = 'statement' AND empty = 1 {where} ORDER BY source, numkey IS NULL, numkey, id",
            args,
        )

    def search(
        self,
        text: str = "",
        *,
        work: str | None = None,
        taxon: str | None = None,
        tag: str | None = None,
        proofs: bool = False,
        limit: int = 50,
    ) -> list[Hit]:
        """The statements that match: every word of `text` among a statement's name (taxon and number), title, work and words, and every filter given.

        Parameters
        ----------
        text : str, default ''
            Words, all of which must match, the last also as the start of a longer word; a word shaped like a number (`3.4`, `A.2`) matches a number exactly.
        work : str, optional
            A reference's id or its entry's key.
        taxon : str, optional
            The statements of this taxon.
        tag : str, optional
            The statements with this tag, in any case.
        proofs : bool, default False
            Look in proofs' words as well; a statement found by a proof's alone is marked with that proof.
        limit : int, default 50
            The most to return.

        Returns
        -------
        list of Hit
            Each with where it matched and, for a match in a statement's or a proof's text, the words around it (`snippet`); matches on the name first, then the best; with no text, in their works' order.
        """
        numbers = [w for w in text.split() if _NUMBER.fullmatch(w)]
        terms = _TOKEN.findall(" ".join(w for w in text.split() if w not in numbers))
        where: list[str] = ["n.kind IN ('statement', 'proof')" if proofs else "n.kind = 'statement'"]
        args: list[Any] = []
        if work:
            ref = work if ids.kind_of(work) == ids.REFERENCE else (r.id if (r := self.reference(work)) else "")
            where.append("n.source = ?")
            args.append(ref)
        if taxon:
            of_taxon = "(SELECT id FROM nodes WHERE taxon = ?)"
            where.append(f"(n.taxon = ? OR n.parent IN {of_taxon})" if proofs else "n.taxon = ?")
            args += [taxon] * (2 if proofs else 1)
        if tag:
            tagged = "(SELECT node FROM tags WHERE folded = ?)"
            where.append(f"(n.id IN {tagged} OR n.parent IN {tagged})" if proofs else f"n.id IN {tagged}")
            args += [tag.casefold()] * (2 if proofs else 1)
        for number in numbers:
            numbered = "(SELECT id FROM nodes WHERE number = ?)"
            where.append(f"(n.number = ? OR n.parent IN {numbered})" if proofs else "n.number = ?")
            args += [number] * (2 if proofs else 1)
        columns = ", ".join("n." + c.strip() for c in _ROW.split(","))
        named: set[str] = set()
        if terms:
            query = " ".join(f'"{t}"' for t in terms[:-1]) + f' "{terms[-1]}"*'
            sql = f"SELECT {columns}, bm25(words, 4.0, 4.0, 2.0, 1.0) AS score FROM words CROSS JOIN nodes n ON n.rowid = words.rowid WHERE words MATCH ? AND {' AND '.join(where)} ORDER BY score"
            found = self.db.execute(sql, [query, *args]).fetchall()
            by_name = self.db.execute("SELECT rowid FROM words WHERE words MATCH ?", (f"{{name title}} : {query}",))
            rowids = [r[0] for r in by_name]
            if rowids:
                marks = ",".join("?" * len(rowids))
                named = {r[0] for r in self.db.execute(f"SELECT id FROM nodes WHERE rowid IN ({marks})", rowids)}
        else:
            sql = f"SELECT {columns}, 0 FROM nodes n WHERE {' AND '.join(where)} ORDER BY n.source, n.numkey IS NULL, n.numkey, n.id"
            found = self.db.execute(sql, args).fetchall()
        # a statement's own match is kept over one in its proof, wherever each ranked
        own: dict[str, Row] = {}
        via: dict[str, str] = {}
        ranked: dict[str, None] = {}
        for record in found:
            row = _row(record[:-1])
            if row.kind == ids.STATEMENT:
                own.setdefault(row.id, row)
                ranked.setdefault(row.id)
            elif row.parent:
                via.setdefault(row.parent, row.id)
                ranked.setdefault(row.parent)
        on_name = [i for i in ranked if i in named or (numbers and not terms)]
        chosen = [*on_name, *(i for i in ranked if i not in set(on_name))][:limit]
        hits: list[Hit] = []
        for statement in chosen:
            shown = own.get(statement) or self.row(statement)
            if shown is None:
                continue
            if not terms:
                hits.append(Hit(shown, "name" if numbers else None))
            elif statement in own:
                cut = None if statement in named else snippet(self._body(statement), terms)
                hits.append(Hit(shown, "name" if statement in named else "text" if cut else "work", cut))
            else:
                cut = snippet(self._body(via[statement]), terms)
                hits.append(Hit(shown, "proof" if cut else "work", cut, via[statement]))
        return hits

    def _body(self, node_id: str) -> str:
        found = self.db.execute("SELECT body FROM nodes WHERE id = ?", (node_id,)).fetchone()
        return found[0] if found else ""

    def tags(self, node_id: str) -> list[str]:
        """The tags on `node_id`, as first written, in alphabetical order ignoring case."""
        rows = self.db.execute("SELECT shown FROM tags WHERE node = ?", (node_id,)).fetchall()
        return sorted((r[0] for r in rows), key=str.casefold)

    def tagged(self, tag: str) -> list[Row]:
        """The nodes in the library with `tag`, in any case, in id order."""
        return self._rows(
            f"SELECT {', '.join('n.' + c.strip() for c in _ROW.split(','))} FROM tags t JOIN nodes n ON n.id = t.node WHERE t.folded = ? ORDER BY n.id",
            (tag.casefold(),),
        )

    def tags_in_use(self) -> list[tuple[str, int]]:
        """Each tag on a node of the library with how many it is on, the most used first: what is offered before a new tag is coined."""
        rows = self.db.execute(
            "SELECT t.shown, COUNT(*) FROM tags t JOIN nodes n ON n.id = t.node GROUP BY t.folded ORDER BY COUNT(*) DESC, t.folded"
        )
        return [(r[0], r[1]) for r in rows]

    def count(self) -> int:
        """How many nodes the index holds."""
        return int(self.db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])

    def _edge(self, sql: str, node_id: str) -> list[Row]:
        return self._rows(f"SELECT {_ROW} FROM nodes WHERE id IN ({sql}) ORDER BY id", (node_id,))

    def _rows(self, sql: str, args: Iterable[Any]) -> list[Row]:
        return [_row(r) for r in self.db.execute(sql, tuple(args))]


def snippet(body: str, terms: list[str], before: int = 60, after: int = 60) -> Snippet | None:
    """Where the first of `terms` to occur stands in `body`, the last term also as the start of a longer word, matched as the index matches: ignoring case and accents, not in a comment, an id or an environment's name; None when none occurs.

    A match is the whole word it starts, and inside a formula the whole formula. The words around it run about `before` and `after` characters and are cut at a space outside mathematics, whitespace made single spaces.
    """
    text = blank_comments(body)
    folded, owner = _folded(_searchable(text))
    best: tuple[int, int] | None = None
    for i, term in enumerate(terms):
        key, _ = _folded(term)
        end = "" if i == len(terms) - 1 else r"(?![^\W_])"
        m = re.search(r"(?<![^\W_])" + re.escape(key) + end, folded)
        if m and (best is None or owner[m.start()] < best[0]):
            best = (owner[m.start()], owner[m.end() - 1] + 1)
    if best is None:
        return None
    start, stop = best
    while stop < len(text) and text[stop].isalnum():
        stop += 1
    maths = _maths(text)
    for lo, hi in maths:
        if lo <= start < hi:
            start, stop = lo, max(stop, hi)
            break

    def outside(i: int) -> bool:
        return text[i].isspace() and not any(lo <= i < hi for lo, hi in maths)

    if start <= before:
        left, lead = 0, ""
    else:
        cuts = [i for i in range(start - before, start) if outside(i)]
        left, lead = (cuts[0] + 1, "…") if cuts else (start, "…")
    if len(text) - stop <= after:
        right, tail = len(text), ""
    else:
        cuts = [i for i in range(stop, stop + after) if outside(i)]
        right, tail = (cuts[-1], "…") if cuts else (stop, "…")

    def tidy(part: str) -> str:
        return re.sub(r"\s+", " ", part)

    return Snippet(
        lead + tidy(text[left:start]).lstrip(), tidy(text[start:stop]), tidy(text[stop:right]).rstrip() + tail
    )


def _searchable(text: str) -> str:
    """`text`, its comments blanked, with what else the index does not read made spaces of the same length: the arguments of `\\ref`, `\\cite` and `\\label`, environments' names, and `QUIET`'s commands."""
    for pattern in (_POINTED, _ENVIRONMENT):
        text = pattern.sub(lambda m: " " * len(m.group(0)), text)
    return _COMMAND.sub(lambda m: " " * len(m.group(0)) if m.group(1) in QUIET else m.group(0), text)


def _folded(text: str) -> tuple[str, list[int]]:
    """`text` without case or accents, as the index's tokenizer reads it, and for each of its characters the place in `text` it came from."""
    out: list[str] = []
    owner: list[int] = []
    for i, ch in enumerate(text):
        plain = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c)).casefold()
        out.append(plain)
        owner.extend([i] * len(plain))
    return "".join(out), owner


_MATH = re.compile(
    r"\$\$.*?\$\$|(?<!\\)\$.*?(?<!\\)\$|\\\(.*?\\\)|\\\[.*?\\\]"
    r"|\\begin\{(equation|align|gather|multline|eqnarray|displaymath|math|flalign|alignat)(\*?)\}.*?\\end\{\1\2\}",
    re.S,
)


def _maths(text: str) -> list[tuple[int, int]]:
    """The spans of `text` that are mathematics: `$…$`, `$$…$$`, `\\(…\\)`, `\\[…\\]` and the display environments."""
    return [(m.start(), m.end()) for m in _MATH.finditer(text)]


def _scan(folder: Path) -> dict[str, os.stat_result]:
    """Each node file directly in `folder`, by name, with its `stat`; empty when there is no folder."""
    present: dict[str, os.stat_result] = {}
    with contextlib.suppress(FileNotFoundError, NotADirectoryError):
        with os.scandir(folder) as entries:
            for entry in entries:
                if entry.name.endswith(SUFFIX) and entry.is_file():
                    present[entry.name] = entry.stat()
    return present


def _row(record: Any) -> Row:
    id_, kind, taxon, number, title, source, pages, parent, empty, digest = record
    return Row(id_, kind, taxon, number, title, source, pages, parent, bool(empty), digest)


def _remove(path: Path) -> None:
    for p in (path, path.with_name(path.name + "-journal")):
        with contextlib.suppress(FileNotFoundError):
            p.unlink()


@contextlib.contextmanager
def opened(root: Path) -> Iterator[NodeIndex]:
    """The quilt's index, up to date, for the length of the block."""
    index = NodeIndex.open(root)
    try:
        yield index
    finally:
        index.close()
