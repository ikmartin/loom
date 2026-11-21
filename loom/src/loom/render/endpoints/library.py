"""The library: adding, filing, deleting and ignoring works, verifying and discarding a proposed result, a library run, the anchor of a selection on a work's page, and bringing forward a quilt an earlier loom made."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.paths import INCOMING
from loom.render.endpoints.base import ApiError, Handler, _scan, _str, plain, said

if TYPE_CHECKING:
    from loom.library.carry import Carried

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
    uploads = root / INCOMING

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
        # filed, the drop waits no longer; one an act of the intake stands on is the intake's to keep
        if not (uploads / sha / "act.json").is_file():
            import shutil

            shutil.rmtree(uploads / sha, ignore_errors=True)
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


def _runner(root: Path, who: str) -> Any:
    """`(citekey, fetch) -> job`: the run that reads a work's pages, and with `fetch` fetches it, on the publisher's runner; None where it runs none, and pages are read at once."""
    from loom.refs.build import WORK_STEPS

    jobs = _JOBS.get(root.resolve())
    if jobs is None:
        return None

    def run(citekey: str, fetch: bool) -> dict[str, Any]:
        return jobs.submit([citekey], WORK_STEPS if fetch else ("map",), who=who, online=False).to_json()  # type: ignore[no-any-return]

    return run


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
        return {"ok": True, "result": f"took the {which} off {ref}; it waits to be taken in", **off}
    except IntakeRefused as exc:
        raise _refused(exc) from exc


def _allowance(body: dict[str, Any]) -> bool | None:
    """The person's allowance of the network for this one act, `online` in the body, or None when the quilt's setting decides."""
    online = body.get("online")
    if online is not None and not isinstance(online, bool):
        raise ApiError("bad-field", "online is true or false: the network allowed or not for this one act")
    return online


def _library_works(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-works` (library-views.md §3.1): every work as a row, gathering first; `doc` adds the labels that document's compile cites each work by."""
    from loom.library.index import NodeIndex
    from loom.library.works import works

    doc = _str(body, "doc")
    rows = works(_scan(root), doc=doc)
    with NodeIndex.open(root) as index:
        gen = index.generation()
    return {"ok": True, "result": f"{len(rows)} works", "gen": gen, "works": rows}


def _library_act(root: Path, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    """The person's acts on one work (library-views.md §3.1, §7): `library-look-up`, `library-entry`, `library-delete` and `library-restore`; the author's."""
    from loom.library.acts import ActRefused, delete, edit_entry, look_up, restore
    from loom.scan.quilt import load_quilt

    who = _author(root, body)
    try:
        if endpoint == "library-restore":
            undo = _str(body, "undo", required=True) or ""
            ref = restore(root, undo, by=who, kind="person")
            return {"ok": True, "result": f"put back {ref}", "ref": ref}
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
            return {"ok": True, "result": f"looked {ref} up", "ref": ref}
        if endpoint == "library-entry":
            bibtex = _str(body, "bibtex", required=True) or ""
            edit_entry(root, ref, bibtex, by=who, kind="person")
            return {"ok": True, "result": f"rewrote the entry of {ref}", "ref": ref}
        undo = delete(root, ref, by=who, kind="person")
        return {"ok": True, "result": f"deleted {ref}", "undo": undo}
    except ActRefused as exc:
        raise ApiError(exc.code, exc.message, status=exc.status) from exc


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


def _library_upgrade(root: Path, body: dict[str, Any]) -> dict[str, Any]:
    """`library-upgrade`: bring a quilt an earlier loom made forward, its library carried into the node store and this loom's number stamped, as `loom upgrade` does; the author's.

    The carry holds the id lock and the library's lock itself, and carries nothing a second time, so a `loom upgrade` beside it does no harm. A quilt already in this loom's layout carries nothing and is answered `already current`; one in a layout this loom neither reads nor carries is refused `format-unknown`.
    """
    from loom import layout
    from loom.cli.report import counted
    from loom.identity import is_agent
    from loom.library.carry import carry
    from loom.scan.quilt import load_quilt, reviewer_identity
    from loom.scan.scan import scan

    if is_agent(_str(body, "author") or reviewer_identity(root)[0]):
        raise ApiError(
            "author-only", "An agent reads and annotates; only the author brings the quilt forward", status=403
        )
    if not layout.carriable(root):
        why = layout.refusal(root)
        if why is not None:
            raise ApiError("format-unknown", why, status=409)
        return {"ok": True, "result": "already current", "carried": _carried(None)}
    done = carry(root, scan(load_quilt(root, older=True)), write=True)
    layout.stamp(root)
    return {
        "ok": True,
        "result": f"brought the quilt forward to format {layout.NUMBER}, {counted(len(done.references), 'work')} carried into the library",
        "carried": _carried(done),
    }


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
    "library-delete": _library_act,
    "library-restore": _library_act,
    "library-look-up": _library_act,
    "library-entry": _library_act,
    "library-works": plain(_library_works),
    "library-ignore": plain(_library_ignore),
    "library-receive": plain(_library_receive),
    "library-take": _intake,
    "library-answer": _intake,
    "library-undo": _intake,
    "library-unfile": _intake,
    "library-upgrade": plain(_library_upgrade),
    "locate": plain(_locate),
}
#: Of these, the ones that answer and change nothing the manifest shows.
READS: tuple[str, ...] = ("locate", "library-recognise", "library-lookup", "library-works")
#: The ones the publisher does not rebuild after: the reads, those whose run or filing publishes what it changes, and the upgrade, after which a waiting publisher builds as it starts (`ServeSession.bring_forward`).
NO_REBUILD: tuple[str, ...] = (*READS, "library-update", "library-upload", "library-receive", "library-upgrade")
#: The ones that change records alone, so the publication builds from the last scan.
RECORD_WRITES: tuple[str, ...] = ()
#: The ones that take the library's lock themselves, once every lookup has answered, and so run outside the publication's lock: a slow service holds up no rebuild and no other write.
OWN_LOCK: tuple[str, ...] = ("library-take", "library-answer", "library-look-up")
