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
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loom.library import ids
from loom.library.body import CITES, REFS, blank_comments, entry_of, labels
from loom.library.node import KEYS, SUFFIX, Node, NodeUnreadable, node_hash, read_node
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
CREATE TABLE edges(src TEXT NOT NULL, kind TEXT NOT NULL, dst TEXT NOT NULL, PRIMARY KEY (src, kind, dst)) WITHOUT ROWID;
CREATE INDEX edges_dst ON edges(dst, kind);
CREATE TABLE anchors(owner TEXT NOT NULL, anchor TEXT NOT NULL, PRIMARY KEY (owner, anchor)) WITHOUT ROWID;
CREATE TABLE tags(node TEXT NOT NULL, folded TEXT NOT NULL, shown TEXT NOT NULL, PRIMARY KEY (node, folded)) WITHOUT ROWID;
CREATE INDEX tags_folded ON tags(folded);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE words USING fts5(number, title, work, text, tokenize = 'unicode61 remove_diacritics 2', prefix = '2 3');
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
class Hit:
    """A statement a search found, and the proof the words were found in when they were not in the statement."""

    row: Row
    in_proof: str | None = None


@dataclass(frozen=True)
class Refreshed:
    """What bringing the index up to date did: the files read, the nodes changed and removed, and whether the tags were replayed."""

    read: int
    changed: int
    removed: int
    tags: bool


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

        Returns
        -------
        Refreshed
            What was read and changed.
        """
        folder = self.root / LIBRARY_NODES
        started = time.time_ns()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            done = self._refresh(folder, started)
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return done

    def _refresh(self, folder: Path, started: int) -> Refreshed:
        last = int(self._meta("refreshed") or 0)
        known = {
            name: (size, mtime, digest)
            for name, size, mtime, digest in self.db.execute("SELECT name, size, mtime_ns, hash FROM files")
        }
        present: dict[str, os.stat_result] = {}
        with contextlib.suppress(FileNotFoundError, NotADirectoryError):
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name.endswith(SUFFIX) and entry.is_file():
                        present[entry.name] = entry.stat()
        read = changed = 0
        works: set[str] = set()
        fresh: set[str] = set()
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
        removed = 0
        for name in set(known) - set(present):
            works |= self._forget(name)
            removed += 1
        if works:
            self._rework(works, fresh)
        tags = self._retag(last)
        self._set_meta("refreshed", str(started))
        return Refreshed(read, changed, removed, tags)

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
            "INSERT OR IGNORE INTO anchors(owner, anchor) VALUES (?, ?)",
            [(node.id, p.target) for p in labels(node.body)],
        )
        if node.kind in (ids.STATEMENT, ids.PROOF):
            work = self._work_words(node.source)
            self.db.execute(
                "INSERT INTO words(rowid, number, title, work, text) VALUES (?, ?, ?, ?, ?)",
                (cur.lastrowid, node.number or "", words(node.title or ""), work, words(node.body)),
            )
        return {node.id} if node.kind == ids.REFERENCE else set()

    def _work_words(self, source: str | None) -> str:
        if not source:
            return ""
        row = self.db.execute("SELECT body FROM nodes WHERE id = ?", (source,)).fetchone()
        return _work(row[0])[1] if row else ""

    def _rework(self, works: set[str], fresh: set[str]) -> None:
        """Make again the work words of every node read from one of `works`, whose entries changed, but those put in by this pass, which have them."""
        for work in works:
            text = self._work_words(work)
            rows = self.db.execute(
                "SELECT rowid, id FROM nodes WHERE source = ? AND kind IN ('statement', 'proof')", (work,)
            ).fetchall()
            self.db.executemany(
                "UPDATE words SET work = ? WHERE rowid = ?", [(text, r[0]) for r in rows if r[1] not in fresh]
            )

    def _retag(self, last: int) -> bool:
        """Replay the tag log into the index when it changed since the last update, by its size and time, or was written within `RACY` of it; whether it was."""
        try:
            st = (self.root / TAG_LOG).stat()
            stamp, racy = f"{st.st_size}:{st.st_mtime_ns}", st.st_mtime_ns >= last - RACY
        except FileNotFoundError:
            stamp, racy = "none", False
        if self._meta("tags") == stamp and not racy:
            return False
        tags = replay(self.root)
        self.db.execute("DELETE FROM tags")
        self.db.executemany(
            "INSERT INTO tags(node, folded, shown) VALUES (?, ?, ?)",
            [
                (node, folded, tags.spelled[folded])
                for node, on in tags.holders.items()
                for folded, who in on.items()
                if who
            ],
        )
        self._set_meta("tags", stamp)
        return True

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
        header = json.loads(found[0])
        keys: dict[str, Any] = {k: tuple(v) if isinstance(v, list) else v for k, v in header.items() if k in KEYS}
        return Node(id=header["id"], taxon=header["taxon"], body=found[1], schema=header["schema"], **keys)

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
        """The statements that match: every word of `text` among a statement's number, title, work and words, and every filter given.

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
            The best matches first; with no text, in their works' order.
        """
        numbers = [w for w in text.split() if _NUMBER.fullmatch(w)]
        terms = re.findall(r"\w+", " ".join(w for w in text.split() if w not in numbers))
        where: list[str] = ["n.kind IN ('statement', 'proof')" if proofs else "n.kind = 'statement'"]
        args: list[Any] = []
        if work:
            ref = work if ids.kind_of(work) == ids.REFERENCE else (r.id if (r := self.reference(work)) else "")
            where.append("n.source = ?")
            args.append(ref)
        if taxon:
            where.append(
                "(n.taxon = ? OR (n.kind = 'proof' AND (SELECT taxon FROM nodes p WHERE p.id = n.parent) = ?))"
            )
            args += [taxon, taxon]
        if tag:
            where.append(
                "(SELECT 1 FROM tags t WHERE t.folded = ? AND t.node = (CASE n.kind WHEN 'proof' THEN n.parent ELSE n.id END))"
            )
            args.append(tag.casefold())
        for number in numbers:
            where.append(
                "(CASE n.kind WHEN 'proof' THEN (SELECT number FROM nodes p WHERE p.id = n.parent) ELSE n.number END) = ?"
            )
            args.append(number)
        if terms:
            query = " ".join(f'"{t}"' for t in terms[:-1]) + f' "{terms[-1]}"*'
            sql = f"SELECT {', '.join('n.' + c.strip() for c in _ROW.split(','))}, bm25(words, 1.0, 4.0, 2.0, 1.0) AS score FROM words JOIN nodes n ON n.rowid = words.rowid WHERE words MATCH ? AND {' AND '.join(where)} ORDER BY score"
            found = self.db.execute(sql, [query, *args]).fetchall()
        else:
            sql = f"SELECT {', '.join('n.' + c.strip() for c in _ROW.split(','))}, 0 FROM nodes n WHERE {' AND '.join(where)} ORDER BY n.source, n.numkey IS NULL, n.numkey, n.id"
            found = self.db.execute(sql, args).fetchall()
        hits: dict[str, Hit] = {}
        for record in found:
            row = _row(record[:-1])
            if row.kind == ids.STATEMENT:
                hits[row.id] = Hit(row)
            elif row.parent and row.parent not in hits:
                parent = self.row(row.parent)
                if parent is not None:
                    hits[row.parent] = Hit(parent, row.id)
            if len(hits) >= limit:
                break
        return list(hits.values())[:limit]

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
