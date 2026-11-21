"""The Web: its reads over the drafts' results, listed, searched and followed (`docs/specs/evidence.md` §8). Each reads the scan, the published manifest and the evidence, and changes nothing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.paths import MANIFEST
from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain


def _drafts(root: Path) -> Any:
    """The drafts' results for one read: the publisher's scan, its last manifest ({} before a first build) and the evidence."""
    import json

    from loom.evidence.webview import drafts

    path = root / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return drafts(_scan(root), manifest, root)


def _scope(body: dict[str, Any]) -> tuple[str, str | None]:
    return _str(body, "scope") or "all", _str(body, "doc")


def _answer(read: Any) -> dict[str, Any]:
    """Run a read, its refusals as the write API answers them: a scope it does not know or one wanting a draft is `bad-field`, a result it does not hold `no-such-result`."""
    from loom.evidence.webview import ScopeError

    try:
        return {"ok": True, **read()}
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
    d = _drafts(root)
    return _answer(lambda: listing(d, scope, doc, sort=sort, opened=opened, offset=offset))


def _web_group(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import group

    scope, doc = _scope(body)
    home = _str(body, "group", required=True) or ""
    d = _drafts(root)
    return _answer(lambda: group(d, scope, doc, home))


def _web_search(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import search

    scope, doc = _scope(body)
    limit = body.get("limit", 50)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ApiError("bad-field", "limit is a number of hits from 1 to 200")
    d = _drafts(root)
    return _answer(lambda: search(d, scope, doc, _str(body, "q") or "", limit=limit))


def _web_focus(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import focus

    scope, doc = _scope(body)
    key = _str(body, "result", required=True) or ""
    d = _drafts(root)
    return _answer(lambda: focus(d, scope, doc, key, more=bool(body.get("more"))))


def _web_graph(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    from loom.evidence.webview import graph

    scope, doc = _scope(body)
    key = _str(body, "result", required=True) or ""
    d = _drafts(root)
    return _answer(lambda: graph(d, scope, doc, key))


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
