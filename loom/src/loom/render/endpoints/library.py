"""The library: the intake, the works list, the person's acts on a work, the anchor of a selection on a work's page, and bringing forward a quilt an earlier loom made."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain

if TYPE_CHECKING:
    from loom.library.carry import Carried


def _author(root: Path, body: dict[str, Any]) -> str:
    """Who acts, refused to a declared agent: what enters the library, and what leaves it, is the author's."""
    from loom.identity import is_agent
    from loom.scan.quilt import reviewer_identity

    who = reviewer_identity(root)[0]
    if is_agent(_str(body, "author") or who):
        raise ApiError(
            "author-only",
            "An agent reads and annotates; only the author takes works into the library or out of it",
            status=403,
        )
    return who


def _refused(exc: Any) -> ApiError:
    return ApiError(exc.code, exc.message, status=exc.status)


def _intake(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """The library's intake (specs/write-api.md §6): take in received files and pasted works, answer a question, undo an act on a drop, take a document off its work. The author's, each through the one function `loom library add` goes through (`library.intake`)."""
    from loom.library.intake import IntakeRefused, Item, answer, take, undo, unfile
    from loom.scan.quilt import load_quilt

    who = _author(root, body)
    quilt = load_quilt(root)
    try:
        if endpoint == "library-take":
            items = body.get("items")
            if not isinstance(items, list) or not items:
                raise ApiError("missing-field", "items is required: the files received and the texts pasted")
            online = _allowance(body)
            if online is None and not quilt.config.online_asked:
                raise ApiError(
                    "network-unasked",
                    "this quilt has not said whether loom may look papers up online: take it again with online false, or ask once and save the answer as library.online",
                    status=409,
                )
            taken: list[Item] = []
            for item in items:
                if not isinstance(item, dict):
                    raise ApiError("bad-field", "each item is {incoming, for?} or {text}")
                drop, text, work = item.get("incoming"), item.get("text"), item.get("for")
                if work is not None and not isinstance(work, str):
                    raise ApiError("bad-field", "for is the reference a file was dropped on")
                if isinstance(drop, str) and drop:
                    taken.append(Item(drop=drop, work=work or ""))
                elif isinstance(text, str) and text.strip():
                    taken.append(Item(text=text))
                else:
                    raise ApiError("bad-field", "each item is {incoming, for?} or {text}")
            rows = take(
                root, taken, by=who, online=quilt.config.online if online is None else online, result=_scan(root)
            )
            counts = {s: sum(1 for r in rows if r.state == s) for s in ("added", "here", "question", "cannot")}
            said = ", ".join(f"{n} {s}" for s, n in counts.items() if n)
            return {"ok": True, "result": f"took in {len(rows)}: {said}", "rows": [r.to_json() for r in rows]}
        if endpoint == "library-answer":
            question = _str(body, "question", required=True) or ""
            if "same" not in body:
                raise ApiError("missing-field", "same is required: the work it is, or null for a work of its own")
            same = body["same"]
            if same is not None and not isinstance(same, str):
                raise ApiError("bad-field", "same must be a reference or null")
            online = _allowance(body)
            row = answer(
                root,
                question,
                same,
                by=who,
                online=quilt.config.online if online is None else online,
                result=_scan(root),
            )
            return {"ok": True, "result": f"{row.name}: {row.state}", "row": row.to_json()}
        if endpoint == "library-undo":
            drop = _str(body, "id", required=True) or ""
            done, again = undo(root, drop, by=who, act=_str(body, "act") or "")
            return {"ok": True, "result": done, **({"row": again.to_json()} if again is not None else {})}
        ref = _str(body, "ref", required=True) or ""
        which = _str(body, "which") or "pdf"
        if which not in ("pdf", "tex"):
            raise ApiError("bad-field", "which is pdf or tex")
        off = unfile(root, ref, which=which, by=who)
        from loom.library.intake import WORD

        return {"ok": True, "result": f"took the {WORD[which]} off {_named(root, ref)}; it waits to be taken in", **off}
    except IntakeRefused as exc:
        raise _refused(exc) from exc


def _allowance(body: dict[str, Any]) -> bool | None:
    """The person's allowance of the network for this one act, `online` in the body, or None when the quilt's setting decides."""
    online = body.get("online")
    if online is not None and not isinstance(online, bool):
        raise ApiError("bad-field", "online is true or false: the network allowed or not for this one act")
    return online


def _library_works(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-works` (library-views.md §3.1): every work as a row, a read that gathers and writes nothing; `doc` adds the labels that document's compile cites each work by; `since`, the generation last answered, is answered `unchanged` while it stands."""
    from loom.library.works import generation, works

    doc = _str(body, "doc")
    since = body.get("since")
    if since is not None and (not isinstance(since, int) or isinstance(since, bool)):
        raise ApiError("bad-field", "since is the gen of an earlier answer, a number")
    result = _scan(root)
    gen = generation(result, doc=doc)
    if since == gen:
        return {"ok": True, "result": "unchanged", "gen": gen, "unchanged": True}
    rows = works(result, doc=doc)
    return {"ok": True, "result": f"{len(rows)} works", "gen": gen, "works": rows}


def _library_places(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-places` (library-views.md §3.3): where each annotation on a work's stored PDF stands on its pages, for the reader to draw; `pages` limits it to those; `since` is answered `unchanged` while the work's PDF and the annotation log stand."""
    from loom.library.places import PlacesRefused, places

    ref = _str(body, "ref", required=True) or ""
    pages = body.get("pages")
    if pages is not None and not (
        isinstance(pages, list) and all(isinstance(p, int) and not isinstance(p, bool) and p > 0 for p in pages)
    ):
        raise ApiError("bad-field", "pages is a list of page numbers, from 1")
    since = body.get("since")
    if since is not None and (not isinstance(since, int) or isinstance(since, bool)):
        raise ApiError("bad-field", "since is the gen of an earlier answer, a number")
    try:
        found = places(_scan(root), ref, pages)
    except PlacesRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    if since == found.gen:
        return {"ok": True, "result": "unchanged", "gen": found.gen, "unchanged": True}
    return {
        "ok": True,
        "result": f"{len(found.places)} placed",
        "gen": found.gen,
        "pdf": found.pdf,
        "places": found.places,
    }


def _library_act(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """The person's acts on one work (library-views.md §3.1, §7): `library-look-up`, `library-entry`, `library-delete` and `library-restore`; the author's."""
    from loom.library.acts import ActRefused, delete, edit_entry, look_up, restore
    from loom.scan.quilt import load_quilt

    who = _author(root, body)
    try:
        if endpoint == "library-restore":
            undo = _str(body, "undo", required=True) or ""
            ref = restore(root, undo, by=who, kind="person")
            return {"ok": True, "result": f"put back {_named(root, ref)}", "ref": ref}
        ref = _str(body, "ref", required=True) or ""
        if endpoint == "library-look-up":
            quilt = load_quilt(root)
            # `online: true` is the person's word for this one look-up, the question a row asks right after a drop on a quilt with the network off
            allowed = _allowance(body)
            if not (quilt.config.online if allowed is None else allowed):
                raise ApiError(
                    "network-unasked" if allowed is None and not quilt.config.online_asked else "offline",
                    "a look-up needs the network, which this quilt has not allowed: allow it for this one look-up with online true, or save library.online",
                    status=409,
                )
            look_up(root, ref, by=who, kind="person")
            return {"ok": True, "result": f"looked {_named(root, ref)} up", "ref": ref}
        if endpoint == "library-entry":
            bibtex = _str(body, "bibtex", required=True) or ""
            edit_entry(root, ref, bibtex, by=who, kind="person")
            return {"ok": True, "result": f"rewrote the entry of {_named(root, ref)}", "ref": ref}
        named = _named(root, ref)
        undo = delete(root, ref, by=who, kind="person")
        return {"ok": True, "result": f"deleted {named}", "undo": undo}
    except ActRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc


def _named(root: Path, ref: str) -> str:
    """A work as a person reads it in a write's `result`, its short name (`Smith 2024`); its key, or else its ref, when its entry names neither author nor title."""
    from loom.library.entries import read_entry, short
    from loom.library.store import read

    node = read(root, ref)
    entry = read_entry(node.body) if node is not None else None
    return short(entry.fields, entry.key) if entry is not None else ref


def _library_receive(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-receive` takes a file's bytes as they stream, which the publisher reads before any JSON (`render.serve`); a JSON body is not a file."""
    raise ApiError(
        "bad-request", "send the file's bytes as application/octet-stream, with its name in the query (?name=)"
    )


def receive_stream(root: Path, name: str, stream: Any, length: int) -> dict[str, Any]:
    """The publisher's way into `library-receive`: keep the streamed bytes as a drop, or raise ApiError."""
    from loom.library.intake import IntakeRefused, receive

    try:
        got = receive(root, name, stream, length)
    except IntakeRefused as exc:
        raise _refused(exc) from exc
    return {"ok": True, "result": f"received {got['name']}", **got}


def _library_upgrade(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-upgrade`: bring a quilt an earlier loom made forward by the one function `loom upgrade` runs (`loom.upgrade.upgrade`): its library carried into the node store and this loom's number stamped, then the ignore files, the agents' layer and the client files made this loom's; the author's.

    The carry holds the id lock and the library's lock itself and carries nothing a second time, and the rest writes only what differs, so a `loom upgrade` beside it does no harm. A quilt already in this loom's layout carries nothing, `carried` all zero; one in a layout this loom neither reads nor carries is refused `format-unknown`.
    """
    from loom import layout
    from loom.identity import is_agent
    from loom.scan.quilt import reviewer_identity
    from loom.upgrade import upgrade
    from loom.writes import WriteRefused

    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError(
            "author-only", "An agent reads and annotates; only the author brings the quilt forward", status=403
        )
    why = None if layout.carriable(root) else layout.refusal(root)
    if why is not None:
        raise ApiError("format-unknown", why, status=409)
    try:
        done = upgrade(root)
    except WriteRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc
    return {"ok": True, "result": done.verdict(), "carried": _carried(done.carried), "agents": done.agents()}


def _carried(done: Carried | None) -> dict[str, Any]:
    """`library-upgrade`'s `carried`: what `library.carry.carry` did, its works counted; None, nothing carried, is all zeros."""
    if done is None:
        return {
            "references": 0,
            "documents": 0,
            "notes_rekeyed": 0,
            "overviews": 0,
            "links_rewritten": 0,
            "removed": [],
            "problems": [],
        }
    return {
        "references": len(done.references),
        "documents": done.documents,
        "notes_rekeyed": done.notes_rekeyed,
        "overviews": done.overviews,
        "links_rewritten": done.links_rewritten,
        "removed": list(done.removed),
        "problems": list(done.problems),
    }


def _locate(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Turn a reader's selection on a page of a work's PDF into the anchor loom would record (plan 0.13 item 2).

    Body: `ref`, the work's reference (its id, or the key its entry has), `page`, and either `text` -- what the reader selected -- or `rects`, the rectangles they drew when there was no text worth selecting. `page` may be left out with `text`, for a link that quotes without a page: the first page whose text holds the quote is used. The answer carries the anchor, the page, and beside them the line a person would read.

    **Mapping happens here and not in the viewer.** The client's text layer is a third extraction of the page, after loom's page text and word boxes; only loom holds the other two, and only loom can say what its page text says, which is what an anchor is checked against. The client never decides what the anchor is.

    This endpoint **writes nothing**: it answers, and whether an annotation is made is a separate act.
    """
    from loom.library.references import named
    from loom.library.store import read
    from loom.records.marks import reference_pdf
    from loom.refs.anchoring import anchor_on_page
    from loom.refs.pages import mapped, read_page
    from loom.refs.search import find_in_page

    asked = _str(body, "ref", required=True) or ""
    page = body.get("page")
    rects = [[float(v) for v in r] for r in body.get("rects") or []]
    text = _str(body, "text")
    if not (page is None and text) and (not isinstance(page, int) or page < 1):
        raise ApiError("bad-field", "page must be a positive integer")
    raw_span = body.get("span")
    span = (int(raw_span[0]), int(raw_span[1])) if isinstance(raw_span, list) and len(raw_span) == 2 else None
    if not text and not rects and not span:
        raise ApiError("missing-field", "one of text, rects or span is required")

    ref = named(_scan(root), asked)
    if ref is None:
        raise ApiError("no-such-ref", f"the library has no work {asked}", status=404)
    node = read(root, ref)
    pdf = reference_pdf(root, ref)
    home = mapped(root, node.pdf) if node is not None and node.pdf and pdf is not None else None
    if home is None or pdf is None:
        raise ApiError("not-readable", f"{asked} holds no readable PDF on this machine", status=404)
    if page is None:
        pages = sorted(int(p.stem) for p in (home / "pages").glob("*.txt"))
        page = next((n for n in pages if find_in_page(read_page(home, n) or "", text or "")), None)
        if page is None:
            raise ApiError("not-found", f"no page of {asked} holds that text", status=404)
    placed = anchor_on_page(home, pdf, page, text, rects, span)
    box = placed.page_box
    return {
        "ok": True,
        "result": f"{ref} p.{page} anchored by {placed.said}, {len(placed.anchor.quads or [])} line(s)",
        "page": page,
        "anchor": placed.anchor.to_dict(),
        "text": placed.selector.exact,
        "page_box": {"width": box[0], "height": box[1]} if box else None,
    }


HANDLERS: dict[str, Handler] = {
    "library-delete": _library_act,
    "library-restore": _library_act,
    "library-look-up": _library_act,
    "library-entry": _library_act,
    "library-works": plain(_library_works),
    "library-places": plain(_library_places),
    "library-receive": plain(_library_receive),
    "library-take": _intake,
    "library-answer": _intake,
    "library-undo": _intake,
    "library-unfile": _intake,
    "library-upgrade": plain(_library_upgrade),
    "locate": plain(_locate),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("locate", "library-works", "library-places")
#: The ones the publisher does not rebuild after: the reads, a file received and not yet taken, and the upgrade, after which a waiting publisher builds as it starts (`ServeSession.bring_forward`).
NO_REBUILD: tuple[str, ...] = (*READS, "library-receive", "library-upgrade")
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ()
#: The ones that take the library's lock themselves, once every lookup has answered, and so run outside the publication's lock: a slow service holds up no rebuild and no other write.
OWN_LOCK: tuple[str, ...] = ("library-take", "library-answer", "library-look-up")
