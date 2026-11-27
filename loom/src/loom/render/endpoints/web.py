"""The Web: its reads over the drafts' results, listed, searched and followed (`docs/specs/evidence.md` §8). Each reads the scan, the published manifest and the evidence, and changes nothing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.paths import MANIFEST
from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain


def _drafts(root: Path) -> Any:
    """The drafts' results for a read: the publisher's scan, its last manifest ({} before a first build) and the evidence, kept from the last read while that scan is the same object, no file read is changed and the library's index is at the same generation (`memo.kept`, `memo.library_mark`)."""
    import json

    from loom.evidence.memo import kept, library_mark, read_files
    from loom.evidence.webview import drafts

    scan = _scan(root)

    def make() -> Any:
        path = root / MANIFEST
        manifest = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return drafts(scan, manifest, root)

    return kept(root, "web", scan, lambda: read_files(root, nodes=False), make, also=lambda: library_mark(root))


def _scope(body: dict[str, Any]) -> tuple[str, str | None]:
    return _str(body, "scope") or "all", _str(body, "doc")


def _answer(root: Path, read: Any) -> dict[str, Any]:
    """Run a read over the drafts as they are now (`_drafts`), with the library's generation it answers at (`library-views.md` §2), its refusals as the write API answers them: a scope it does not know or one wanting a draft is `bad-field`, a result it does not hold `no-such-result`.

    A library node whose text moved after the read took its hash (`Moved`) makes the drafts again and runs the read once more, so no body is sent beside a hash it is not; a second such move is `moved`, asked again.
    """
    from loom.evidence.memo import forget
    from loom.evidence.web import Moved
    from loom.evidence.webview import ScopeError
    from loom.library.generation import generation

    try:
        for attempt in (1, 2):
            try:
                return {"ok": True, **read(_drafts(root)), "gen": generation(_scan(root))}
            except Moved:
                forget(root, "web")
                if attempt == 2:
                    raise ApiError("moved", "the library changed while it was read; ask again", status=409) from None
        raise AssertionError("unreachable")
    except ScopeError as exc:
        raise ApiError("bad-field", str(exc)) from exc
    except KeyError as exc:
        raise ApiError("no-such-result", f"{exc.args[0]} is no result of a draft; reload the Web", status=404) from exc


def _web_list(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import listing

    scope, doc = _scope(body)
    sort = _str(body, "sort") or "document"
    if sort not in ("document", "status"):
        raise ApiError("bad-field", "sort is document or status")
    opened = [x for x in body.get("open") or [] if isinstance(x, str)]
    offset = body.get("offset", 0)
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ApiError("bad-field", "offset is a number of rows")
    return _answer(root, lambda d: listing(d, scope, doc, sort=sort, opened=opened, offset=offset))


def _web_group(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import group

    scope, doc = _scope(body)
    home = _str(body, "group", required=True) or ""
    return _answer(root, lambda d: group(d, scope, doc, home))


def _web_search(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import search

    scope, doc = _scope(body)
    limit = body.get("limit", 50)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ApiError("bad-field", "limit is a number of hits from 1 to 200")
    return _answer(root, lambda d: search(d, scope, doc, _str(body, "q") or "", limit=limit))


def _web_focus(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import focus

    scope, doc = _scope(body)
    key = _str(body, "result", required=True) or ""
    return _answer(root, lambda d: focus(d, scope, doc, key, more=bool(body.get("more"))))


def _web_graph(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import graph

    scope, doc = _scope(body)
    key = _str(body, "result", required=True) or ""
    return _answer(root, lambda d: graph(d, scope, doc, key))


HANDLERS: dict[str, Handler] = {
    "web-list": plain(_web_list),
    "web-group": plain(_web_group),
    "web-search": plain(_web_search),
    "web-focus": plain(_web_focus),
    "web-graph": plain(_web_graph),
}
#: Of these, the ones that answer and change nothing the manifest shows: all of them.
READS: tuple[str, ...] = tuple(HANDLERS)
#: The ones the publisher does not rebuild after.
NO_REBUILD: tuple[str, ...] = READS
#: The ones that change records alone.
RECORD_WRITES: tuple[str, ...] = ()
