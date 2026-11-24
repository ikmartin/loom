"""Loom's own work on the works a draft cites, unasked (`docs/design/library.md`, "Loom alone"): each work the library's stubs name is tried once for what it holds, one at a time, by a worker of the server's after each build. It compiles nothing.

A try fetches, under `online`, arXiv's PDF for a work whose entry states an arXiv number and that holds no PDF, and its source too where it holds neither, one request at a time naming loom and its version, each filed under the work its entry names (`references.attach`). Then a work that holds a source is surveyed and numbered from its PDF alone (`survey.confirmed`); a work that holds only a PDF waits for a reader, since an ask is a person's to make (`evidence.asks`); a work that holds neither waits for a document. Each try is recorded in the library's log (`tried`), keyed by what the work holds and its arXiv number, so a work is tried again only once those change; a try the network being off held back records nothing.
"""

from __future__ import annotations

import tempfile
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loom.library import documents, ids, log
from loom.library.store import folder, read

if TYPE_CHECKING:
    from loom.library.node import Node

#: Who a try is recorded as.
LOOM = {"by": "loom", "kind": "loom"}


@dataclass(frozen=True)
class Tried:
    """What one try of a work came to: `outcome` is `surveyed`, `waiting` or `failed`, `why` the survey's own word or what the work waits for, and `held` whether the network being off held part of it back, so it is not recorded."""

    ref: str
    on: str
    outcome: str
    why: str | None = None
    held: bool = False


def arxiv_of(node: Node) -> str | None:
    """The arXiv number a reference's entry states, its version kept; None where it states none."""
    from loom.library.entries import identifiers
    from loom.scan.bib import parse_bib

    for entry in parse_bib(node.body).values():
        found = next((i.removeprefix("arxiv:") for i in identifiers(entry.fields) if i.startswith("arxiv:")), None)
        return found
    return None


def key_of(node: Node) -> str:
    """What a work is tried for: the documents it holds and the arXiv number it states."""
    return "|".join(f"{k}:{v}" for k, v in (("tex", node.tex), ("pdf", node.pdf), ("arxiv", arxiv_of(node))) if v)


def wanted(root: Path) -> list[str]:
    """The works the library's stubs name, in the order of their references' ids."""
    from loom.library.node import NodeUnreadable, read_node

    nodes = folder(root)
    out: set[str] = set()
    if not nodes.is_dir():
        return []
    for path in nodes.glob("*.node"):
        if ids.kind_of(path.stem) != ids.STATEMENT:
            continue
        try:
            node = read_node(path.read_bytes(), path.name)
        except NodeUnreadable:
            continue
        if node.empty and node.source:
            out.add(node.source)
    return sorted(out)


def due(root: Path) -> list[str]:
    """The works the stubs name that were never tried for what they hold now."""
    acts = log.replay(root)
    out: list[str] = []
    for ref in wanted(root):
        node = read(root, ref)
        if node is None:
            continue
        on = key_of(node)
        if not any(act.get("event") == "tried" and act.get("on") == on for act in acts.of(ref)):
            out.append(ref)
    return out


def attempt(root: Path, ref: str, *, online: bool) -> Tried | None:
    """Try one work: fetch what it lacks under `online`, then survey it from what it holds, and record the try.

    Parameters
    ----------
    root : Path
        The quilt.
    ref : str
        The work's reference.
    online : bool
        Whether the network may be used.

    Returns
    -------
    Tried or None
        What the try came to, recorded unless `held`; None for a reference no longer in the library.
    """
    from loom.refs import fetch

    node = read(root, ref)
    if node is None:
        return None
    ident, held, failed = arxiv_of(node), False, None
    if ident and not node.pdf:
        if not online:
            held = True
        else:
            try:
                node = _fetched(root, ref, ident, want_source=not node.tex)
            except fetch.FetchRefused as exc:
                failed = str(exc)
    on = key_of(node)
    if failed is not None:
        tried = Tried(ref, on, "failed", f"fetch: {failed}"[:300], held)
    elif node.tex:
        tried = _surveyed(root, node, on, held)
    else:
        tried = Tried(ref, on, "waiting", "pdf-only" if node.pdf else "no-document", held)
    if not tried.held:
        log.record(root, "tried", ref, **LOOM, on=on, outcome=tried.outcome, why=tried.why)
    return tried


def _fetched(root: Path, ref: str, ident: str, *, want_source: bool) -> Node:
    """arXiv's PDF of `ident`, and its source where `want_source`, fetched one request at a time and filed under `ref`; the reference as written."""
    from loom.library.references import attach
    from loom.refs import fetch

    with tempfile.TemporaryDirectory(prefix="loom-fetch-") as tmp:
        pdf = documents.put_pdf(root, fetch.arxiv_pdf(ident, Path(tmp) / "pdf"))
        node = attach(root, ref, "pdf", pdf, **LOOM, source=f"arXiv {ident}")
        if want_source:
            got = fetch.arxiv_source(ident, Path(tmp) / "tex")
            if got.suffix != ".pdf":
                tex = documents.put_source(root, got, name=got.name)
                node = attach(root, ref, "tex", tex, **LOOM, source=f"arXiv {ident}")
    return node


def _surveyed(root: Path, node: Node, on: str, held: bool) -> Tried:
    """A work holding a source, surveyed and numbered from its PDF alone."""
    from loom.library import survey

    assert node.tex is not None
    src = documents.source_dir(root, node.tex)
    main = documents.main_file(src)
    if main is None:
        return Tried(node.id, on, "failed", "no-main", held)
    pdf_path = documents.path_of(root, node.pdf, "pdf") if node.pdf else None
    s = survey.confirmed(root, node.tex, src, main.relative_to(src).as_posix(), pdf=node.pdf, pdf_path=pdf_path)
    return Tried(node.id, on, "surveyed" if s.state == "ready" else "failed", s.why, held)


class Unasked:
    """The server's one worker for the unasked job: works wanted are tried one at a time, each once while it is wanted again.

    Parameters
    ----------
    root : Path
        The quilt.
    online : callable
        Whether the network may be used now, read at each try.
    tried : callable, optional
        Called with each try's outcome, from the worker, after it is recorded.
    """

    def __init__(self, root: Path, online: Callable[[], bool], tried: Callable[[Tried], None] = lambda t: None) -> None:
        self.root = root
        self._online = online
        self._tried = tried
        self._cond = threading.Condition()
        self._due: list[str] = []
        self._thread: threading.Thread | None = None
        self._stopped = False
        self._busy = False

    def want(self, refs: Iterable[str]) -> None:
        """Ask for each of `refs` to be tried, once, after those asked before."""
        with self._cond:
            if self._stopped:
                return
            self._due += [r for r in refs if r not in self._due]
            if self._thread is None and self._due:
                self._thread = threading.Thread(target=self._work, name="loom-unasked", daemon=True)
                self._thread.start()
            self._cond.notify_all()

    def idle(self, timeout: float) -> bool:
        """Wait until nothing is due or under way, at most `timeout` seconds; whether it got there."""
        with self._cond:
            return self._cond.wait_for(lambda: not self._due and not self._busy, timeout)

    def stop(self) -> None:
        """Take nothing more; a try under way ends on its own."""
        with self._cond:
            self._stopped = True
            self._due.clear()
            self._cond.notify_all()

    def _work(self) -> None:
        while True:
            with self._cond:
                while not self._due and not self._stopped:
                    self._cond.wait()
                if self._stopped:
                    return
                ref = self._due.pop(0)
                self._busy = True
            try:
                # asked again by a build while it was tried, it is tried once: what is due is read afresh
                done = attempt(self.root, ref, online=self._online()) if ref in due(self.root) else None
            except Exception as exc:  # noqa: BLE001 -- one work's try must not end the server's worker
                done = Tried(ref, "", "failed", f"{type(exc).__name__}: {exc}"[:300])
            finally:
                with self._cond:
                    self._busy = False
                    self._cond.notify_all()
            if done is not None:
                self._tried(done)
