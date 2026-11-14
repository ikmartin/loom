"""The library: adding, filing, deleting and ignoring works, verifying and discarding a proposed result, a library run, and the anchor of a selection on a work's page."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from loom.paths import BUILD
from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain, said

#: The publisher's library runs (`loom.jobs.Jobs`), offered by `offer_jobs`: `loom serve` offers its own, and nothing else runs them.
_JOBS: dict[Path, Any] = {}


def offer_jobs(root: Path, jobs: Any) -> None:
    """Let `library-update` for `root` queue its runs on `jobs`; `loom serve` offers its own."""
    _JOBS[root.resolve()] = jobs


def _busy(root: Path, citekey: str) -> None:
    """Refuse a write to the work `citekey` while a library run acts on it: the run writes its digest too, and the two would cross."""
    jobs = _JOBS.get(root.resolve())
    if citekey and jobs is not None and jobs.touching(citekey):
        raise ApiError(
            "library-busy", f"a library run is acting on {citekey}; write this when it has finished", status=409
        )


def _library_update(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-update`: queue a library run on the publisher's runner and answer with its job at once; the author's, refused to a declared agent, so an agent never grants itself the network this way. No works is every work, its bibliography gathered first; `steps` runs only those (a digest made again is `extract` alone, with `redo`)."""
    from loom.errors import NotFoundError
    from loom.identity import is_agent
    from loom.refs.build import STEPS, WORK_STEPS
    from loom.refs.update import named
    from loom.scan.quilt import load_quilt, reviewer_identity

    who = reviewer_identity(root)[0]
    if is_agent(_str(body, "author") or who):
        raise ApiError("author-only", "An agent reads and annotates; only the author starts a library run", status=403)
    jobs = _JOBS.get(root.resolve())
    if jobs is None:
        raise ApiError("no-runner", "a library run needs loom serve, which runs it beside the viewer", status=409)
    asked = body.get("works") or []
    if not isinstance(asked, list) or not all(isinstance(w, str) and w for w in asked):
        raise ApiError("bad-field", "works must be a list of works")
    works: list[str] = []
    if asked:
        try:
            works = named(load_quilt(root), _scan(root), tuple(asked))
        except NotFoundError as exc:
            raise ApiError("no-such-work", str(exc), status=404) from exc
    allowed = WORK_STEPS if works else STEPS
    steps = body.get("steps")
    if steps is not None and (not isinstance(steps, list) or not steps or not all(x in allowed for x in steps)):
        raise ApiError("bad-field", f"steps must be some of {', '.join(allowed)}")
    job = jobs.submit(
        works,
        tuple(x for x in allowed if x in steps) if steps else allowed,
        who=who,
        online=body.get("online") is True,
        redo=body.get("redo") is True,
    )
    what = ", ".join(works) if works else "every work"
    return {"ok": True, "result": f"started a library run on {what}", "job": job.to_json()}


def _library_add(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """Adding works by hand (plan 0.24.2): what a pasted text is (`library-recognise`), what it names (`library-lookup`), writing it into loom's bibliography (`library-add`), a dropped PDF kept and identified (`library-upload`) then filed under a work or as its own (`library-file`), and a work added by hand taken out again (`library-delete`).

    A dropped PDF is filed whatever is known about it: lookups only add what they can. Every act but recognising is the author's, refused to a declared agent; a lookup that asks for the network is too, so an agent never grants itself it. `online` is the person's allowance of the network for that one act, as `--online` is.
    """
    import base64
    import hashlib

    from loom.identity import is_agent
    from loom.refs.add import file_new, file_under, identify
    from loom.refs.added import NotDeletable, add_entry, delete_work
    from loom.refs.build import WORK_STEPS
    from loom.refs.identity import recognise
    from loom.refs.lookup import key_for, look_up
    from loom.scan.quilt import load_quilt, reviewer_identity
    from loom.scan.scan import scan

    if endpoint == "library-recognise":
        rec = recognise(_str(body, "text", required=True) or "")
        said: dict[str, Any] = {
            "ok": True,
            "result": rec.label,
            "kind": rec.kind,
            "label": rec.label,
            "value": rec.value,
        }
        if rec.entry is not None:
            said["entry"] = {k: v for k, v in rec.entry.fields.items() if not k.startswith("loom-")}
        return said
    who = reviewer_identity(root)[0]
    asks = body.get("online") is True
    if (endpoint != "library-lookup" or asks) and is_agent(_str(body, "author") or who):
        raise ApiError(
            "author-only", "An agent reads and annotates; only the author adds works to the library", status=403
        )
    quilt = load_quilt(root)
    online = quilt.config.online or asks
    uploads = root / BUILD / "uploads"

    def run(citekey: str, *, pages: bool = False) -> dict[str, Any] | None:
        """The run on the work just added or filed: what a `fetch` asks for, carrying the act's allowance of the network; else, with `pages`, reading its text, which needs none."""
        jobs = _JOBS.get(root.resolve())
        if jobs is None or not (body.get("fetch") or pages):
            return None
        steps = WORK_STEPS if body.get("fetch") else ("map",)
        return jobs.submit([citekey], steps, who=who, online=asks).to_json()  # type: ignore[no-any-return]

    if endpoint == "library-lookup":
        found = look_up(_str(body, "text", required=True) or "", _scan(root).bib, online=online)
        return {"ok": True, "result": found.state, "found": found.to_json()}
    if endpoint == "library-add":
        text = _str(body, "text", required=True) or ""
        result = _scan(root)
        found = look_up(text, result.bib, online=online)
        if found.state != "found":
            raise ApiError(f"lookup-{found.state}", found.message or f"nothing was found for {text}", status=409)
        wanted = _str(body, "key")
        key = key_for(found.entry, set(result.bib), wanted or found.key)
        if wanted and key != wanted:
            raise ApiError("key-taken", f"the library already has a work filed as {wanted}", status=409)
        rec = recognise(text)
        try:
            add_entry(quilt, found.entry, key, who, rec.entry.type if rec.entry is not None else "")
        except ValueError as exc:
            raise ApiError("not-added", str(exc), status=409) from exc
        return {"ok": True, "result": f"added {key} to the library", "citekey": key, "job": run(key)}
    if endpoint == "library-upload":
        name = Path(_str(body, "name", required=True) or "").name
        raw = _str(body, "data", required=True) or ""
        try:
            data = base64.b64decode(raw, validate=True)
        except ValueError as exc:
            raise ApiError("bad-field", "data must be the PDF in base64") from exc
        if not data.startswith(b"%PDF-"):
            raise ApiError("not-a-pdf", f"{name} is not a PDF")
        sha = hashlib.sha256(data).hexdigest()
        # kept under its own name, which is what a reference manager writes a title into
        stem = re.sub(r"[^\w .,()+-]", "_", Path(name).stem).strip() or "upload"
        path = uploads / sha / f"{stem}.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        result = _scan(root)
        seen = identify(root, result.bib, path, online=online)
        return {"ok": True, "result": f"kept {name}", "upload": sha, "name": name, **seen.to_json()}
    if endpoint == "library-file":
        sha = _str(body, "upload", required=True) or ""
        kept = sorted((uploads / sha).glob("*.pdf")) if re.fullmatch(r"[0-9a-f]{64}", sha) else []
        if not kept:
            raise ApiError("no-such-upload", f"no PDF was dropped as {sha[:12]}", status=404)
        path = kept[0]
        name = path.name
        result = _scan(root)
        # where a run can read its text, filing answers at once and the run says how far through its pages it is
        later = _JOBS.get(root.resolve()) is not None
        if body.get("new"):
            typed = body.get("entry")
            edits = {k: v for k, v in typed.items() if isinstance(v, str)} if isinstance(typed, dict) else None
            filed = file_new(
                quilt, result.bib, path, who, came_from=name, online=online, edits=edits, read_pages=not later
            )
        else:
            citekey = _str(body, "citekey", required=True) or ""
            if citekey not in result.bib:
                raise ApiError("no-such-work", f"the library has no work {citekey}", status=404)
            _busy(root, citekey)
            filed = file_under(quilt, result.bib, path, citekey, who, came_from=name, read_pages=not later)
        citekey = filed["citekey"]
        return {
            "ok": True,
            "result": f"filed {name} under {citekey}",
            **filed,
            "job": run(citekey, pages=filed["filed"]),
        }
    citekey = _str(body, "citekey", required=True) or ""
    _busy(root, citekey)
    try:
        return {"ok": True, "result": delete_work(scan(quilt), citekey, who)}
    except NotDeletable as exc:
        raise ApiError(exc.code, exc.message, status=404 if exc.code == "no-such-work" else 409) from exc


def _library_ignore(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-ignore` (plan 0.24.4): stop loom asking for a work's paper, or offering its stored document an entry, or withdraw that, as `loom library ignore` does; the author's, since whether a work can be had is a claim about the world."""
    from loom.identity import is_agent
    from loom.refs.unreadable import NotIgnorable, ignore
    from loom.scan.quilt import reviewer_identity

    who = reviewer_identity(root)[0]
    if is_agent(_str(body, "author") or who):
        raise ApiError(
            "author-only",
            "Whether a work can be obtained is the author's claim; an agent reports what it could not find",
            status=403,
        )
    citekey = _str(body, "citekey", required=True) or ""
    why = _str(body, "why", required=True) or ""
    result = _scan(root)
    if citekey not in result.bib:
        raise ApiError("no-such-work", f"the library has no work {citekey}", status=404)
    _busy(root, citekey)
    try:
        return {"ok": True, "result": ignore(result, citekey, why, who, undo=body.get("undo") is True)[1]}
    except NotIgnorable as exc:
        raise ApiError(exc.code, exc.message, status=409) from exc


def _library(root: Path, endpoint: str, body: dict[str, Any]) -> str:
    """Verify or discard a proposed digest node, through the same functions `loom library verify|discard` call.

    `library-verify` with a `statement` is edit-then-verify: the author's own rendering replaces the proposed one and both parties are recorded. It never touches `source_text`, so the anchor survives and the node stays re-checkable (plan 0.12 §5.4).

    **Both are the author's verbs, and the guard is on the declared identity** (plan 0.13 §8). The server's own environment says nothing here -- loom may be serving from the terminal an agent is working in -- so the marker is not consulted; what is refused is a writer who names itself an agent. A post with no author is the author's own click in their own browser, which is what this endpoint is for.
    """
    from loom.identity import is_agent
    from loom.refs.proposals import discard_result, verify_result
    from loom.scan.quilt import resolve_author

    node = _str(body, "node", required=True) or ""
    named = _str(body, "author")
    if named and is_agent(named):
        verb = "loom library discard" if endpoint == "library-discard" else "loom library verify"
        raise ApiError(
            "author-only",
            f"{verb} is the author's, and {named} is an agent. An agent proposes; it does not vouch for its own "
            "reading. To ask for one, write a suggestion on the result.",
            status=403,
        )
    result = _scan(root)
    found = result.nodes.get(node)
    _busy(root, getattr(found, "digest", None) or "")
    who = resolve_author(named, root)[0]
    try:
        if endpoint == "library-discard":
            return discard_result(result, node, _str(body, "why", required=True) or "", who)
        return verify_result(
            result, node, _str(body, "statement"), who, local=_str(body, "local"), taxon=_str(body, "taxon")
        )[0]
    except LookupError as exc:
        raise ApiError("no-such-node", str(exc), status=404) from exc


def _locate(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """Turn a reader's selection on a page into the anchor loom would record (plan 0.13 item 2).

    Body: `citekey`, `page`, and either `text` -- what the reader selected -- or `rects`, the rectangles they drew when there was no text worth selecting. `page` may be left out with `text`, for a link that quotes without a page: the first page whose committed text holds the quote is used. The answer carries the anchor, the page, and beside them the line a person would read.

    **Mapping happens here and not in the viewer.** The client's text layer is a third extraction of the page, after the committed page text and the word boxes; only loom holds the other two, and only loom can say what the committed text says, which is what an anchor is checked against. The client never decides what the anchor is.

    This endpoint **writes nothing**: it answers, and whether an annotation is made is a separate act.
    """
    from loom.refs.anchoring import anchor_on_page
    from loom.refs.fetch import work_dir
    from loom.refs.pages import read_map
    from loom.refs.search import grep_work

    citekey = _str(body, "citekey", required=True) or ""
    page = body.get("page")
    rects = [[float(v) for v in r] for r in body.get("rects") or []]
    text = _str(body, "text")
    if not (page is None and text) and (not isinstance(page, int) or page < 1):
        raise ApiError("bad-field", "page must be a positive integer")
    raw_span = body.get("span")
    span = (int(raw_span[0]), int(raw_span[1])) if isinstance(raw_span, list) and len(raw_span) == 2 else None
    if not text and not rects and not span:
        raise ApiError("missing-field", "one of text, rects or span is required")

    result = _scan(root)
    if citekey not in result.bib:
        raise ApiError("no-such-work", f"{citekey} is not in the bibliography", status=404)
    home = work_dir(root, result.bib[citekey])
    if read_map(home) is None or not (home / "paper.pdf").is_file():
        raise ApiError("not-readable", f"{citekey} has no copy on this machine", status=404)
    if page is None:
        hits = grep_work(home, citekey, text or "")
        if not hits:
            raise ApiError("not-found", f"no page of {citekey} holds that text", status=404)
        page = min(h.page for h in hits)
    placed = anchor_on_page(home, page, text, rects, span)
    box = placed.page_box
    return {
        "ok": True,
        "result": f"{citekey} p.{page} anchored by {placed.said}, {len(placed.anchor.quads or [])} line(s)",
        "page": page,
        "anchor": _anchor_json(placed.anchor),
        "text": placed.selector.exact,
        "page_box": {"width": box[0], "height": box[1]} if box else None,
    }


def _anchor_json(anchor: Any) -> dict[str, Any]:
    """An anchor in the shape a result record carries it, so the endpoint and the record cannot spell one differently."""
    from loom.refs.proposals import Result

    out: dict[str, Any] = Result(id="", local="", anchor=anchor).to_json()["anchor"]
    return out


HANDLERS: dict[str, Handler] = {
    "library-verify": said(_library),
    "library-discard": said(_library),
    "library-update": plain(_library_update),
    "library-recognise": _library_add,
    "library-lookup": _library_add,
    "library-add": _library_add,
    "library-upload": _library_add,
    "library-file": _library_add,
    "library-delete": _library_add,
    "library-ignore": plain(_library_ignore),
    "locate": plain(_locate),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("locate", "library-recognise", "library-lookup")
#: The ones the publisher does not rebuild after: the reads, and the two whose run or filing publishes what it changes.
NO_REBUILD: tuple[str, ...] = (*READS, "library-update", "library-upload")
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ()
