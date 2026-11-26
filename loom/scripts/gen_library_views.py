"""Write docs/specs/fixture/views/library-*.json: for each read and write of the Library view that the publisher serves (docs/specs/write-api.md §2 and §6, library-views.md §3.1 to §3.5 and §6.2), a sample request and the answer loom gives it, one file each. The viewer's unit tests read these files, so its client and its sample data cannot drift from what loom sends.

Each file is `{"endpoint", "request", "answer"}`, named for its endpoint and, where there are several, for what it shows (`library-take.question.json`). `answer` is the JSON the publisher serves, its `ok` and `result` included; a refusal's is the publisher's `{"error": {"code", "message"}}` with `status`, the HTTP status, beside it. Nothing is written but these files, and none another step writes: the folder is shared with the evidence lane's samples.

How they are made:

- On two copies of the showcase quilt (`tests/quilts/showcase`, as it stands in the working tree, less `.loom/cache/` and `.loom/local/`) in a temporary folder: the quilt as it is, whose `[library] online` is false, and one with that line taken out, so its network is unasked.
- Under an empty home and a fixed clock, with no agent's marker in the environment, so the person who acts is the one the quilt's `[author]` names.
- Through the publisher's own handlers, in process: `render.api.handle` for every JSON endpoint, as `loom serve` calls it, and for `library-receive`, whose body is a file's bytes and not JSON, `endpoints.library.receive_stream` with the bytes as a stream, as the server calls it. A receive's `request` records what the server is sent beside the bytes: `{"name", "size"}`, the `?name=` of its query and its `Content-Length`.
- With no network: every take, answer and look-up runs on a quilt whose network is off or unasked, the one look-up allowed the network is refused before it asks (its work states no identifier), and any attempt to resolve a name or open a connection ends the script.
- With no TeX, and so no compile: `library-works` with `doc` answers `cited_as` null throughout, since a document's cite labels come from its compile; a work's outline is its source's survey as the unasked path makes it, numbered by its stored PDF's text, which poppler reads.
- A work's results digested by `library-digest`, after the reads of a work as it was, so the reads of its nodes have nodes to read; the quilt names no reviewer here, so a digest that must ask an agent is refused (`no-reviewer`).
- The reads first, on the quilt as it is, then the writes, each after the ones it needs, since a write changes what a read would answer.

Under the fixed clock loom answers alike on every run: the works list's `gen` is the fixed time, and the ids the intake and the acts answer with (`x-…` acts, `q-…` questions, `u-…` undos) are drawn from one fixed sequence (`loom.records.ids`).

Usage: uv run python scripts/gen_library_views.py [--check]   (--check writes nothing and exits 1 when a written file is stale)
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

LOOM_DIR = Path(__file__).resolve().parent.parent
REPO = LOOM_DIR.parent
OUT = REPO / "docs" / "specs" / "fixture" / "views"
#: The files this script owns in `OUT`; the rest are the evidence lane's.
MINE = "library-*.json"
SHOWCASE = LOOM_DIR / "tests" / "quilts" / "showcase"
#: The clock: a day after the showcase's last record, so every act here comes after everything the quilt holds.
FIXED = "2026-09-19T09:00:00Z"
#: Works in the showcase's library: one with a PDF and a source, one with a PDF alone, and one holding no document and stating no identifier.
ARDEN, BELLAMY, CORTEZ = "sh-0402-ref", "sh-0403-ref", "sh-0404-ref"
#: The work made by a drop and never looked up, whose row says `unconfirmed`.
ARDEN_V2 = "sh-0405-ref"
DOC = "drafting/main-atomic.tex"


# ---- the process: home, clock, ids, network ---------------------------------------------------------------------------


def _isolated(home: Path) -> None:
    """An empty home and a fixed clock for this process, and no agent's marker, since the person acts here.

    Git is held to the copies (`GIT_CEILING_DIRECTORIES`), since minting a stem reads the git history of the folder a quilt is in, which would differ by where the temporary folder is.
    """
    from loom.identity import AGENT_MARKERS

    os.environ.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        LOOM_FIXED_TIME=FIXED,
        LOOM_PROGRESS="off",
        GIT_CEILING_DIRECTORIES=str(home.parent),
    )
    for name in (*AGENT_MARKERS, "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        os.environ.pop(name, None)


def _no_network(*args: Any, **kwargs: Any) -> NoReturn:
    """What resolving a name or opening a connection does here: end the script, saying so."""
    raise SystemExit("a sample reached for the network: every take, answer and look-up here runs without it")


def _offline() -> None:
    """Make any name this process resolves, and any connection it opens, end the script.

    A look-up the code would send to a service ends it before a byte leaves, so a sample can never depend on what doi.org, arXiv or zbMATH answer.
    """
    socket.getaddrinfo = _no_network
    socket.create_connection = _no_network
    socket.socket.connect = _no_network  # type: ignore[method-assign]
    socket.socket.connect_ex = _no_network  # type: ignore[method-assign]


# ---- the quilts ---------------------------------------------------------------------------------------------------------


def _copy(tmp: Path, name: str) -> Path:
    """A copy of the showcase as the working tree holds it, in `tmp` under `name`.

    What loom derives and keeps on one machine (`.loom/cache/`, `.loom/local/`) is left out, so a run of loom in the test quilt cannot reach a sample: a compile's cite labels or a waiting drop would.
    """

    def ignored(folder: str, names: list[str]) -> set[str]:
        here = {".git"} & set(names)
        if Path(folder) == SHOWCASE / ".loom":
            here |= {"cache", "local"} & set(names)
        return here

    root = tmp / name
    shutil.copytree(SHOWCASE, root, ignore=ignored)
    return root


def _quilts(tmp: Path) -> tuple[Path, Path]:
    """The showcase with its network off, and a copy whose `[library] online` is unset, which a take that does not say refuses."""
    from loom.scan.quilt import load_quilt

    off = _copy(tmp, "showcase")
    unasked = _copy(tmp, "unasked")
    config = unasked / "config.toml"
    text, n = re.subn(r"(?m)^online\s*=.*\n", "", config.read_text(encoding="utf-8"))
    assert n == 1, "the showcase's config.toml no longer sets [library] online on a line of its own"
    config.write_text(text, encoding="utf-8")
    on, asked = load_quilt(off).config, load_quilt(unasked).config
    assert on.online_asked and not on.online, "the showcase's network is to be off"
    assert not asked.online_asked, "the copy's network is to be unasked"
    return off, unasked


def _pdf(tag: str) -> bytes:
    """A one-page PDF with no text on its page, made a file of its own by `tag` in a comment.

    It states no identifier on its page whatever poppler the machine has, or none, so what the intake makes of it comes from the name it is dropped under.
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
    ]
    out = bytearray(b"%PDF-1.4\n% " + tag.encode() + b"\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


#: A TeX source of one file, whose title and authors a drop reads, and whose preamble becomes the work's macros node.
SOURCE = rb"""\documentclass{article}
\usepackage{amsmath,amsthm}
\newtheorem{theorem}{Theorem}
\newcommand{\Tw}{\mathcal{T}}
\title{Gadget towers}
\author{Ada Halberd \and Bruno Ravel}
\begin{document}
\maketitle
\begin{theorem}\label{thm:towers}
Every gadget tower $\Tw$ of height $n$ has at most $2^n$ floors.
\end{theorem}
\end{document}
"""

#: Cortez 2007's entry as the person corrects it, a volume added, which `library-entry` writes in place of the one gathering made.
ENTRY = """@article{Cortez07,
  author = {Cortez, Hilario},
  title = {Flows on infinite quivers: a survey},
  journal = {Bull. Imag. Soc.},
  volume = {12},
  year = {2007},
  pages = {1--44},
}
"""


# ---- the samples --------------------------------------------------------------------------------------------------------


def samples(tmp: Path) -> dict[str, dict[str, Any]]:
    """Each sample by its file's name, less `.json`: the endpoint, the request and loom's answer."""
    _isolated(tmp / "home")
    _offline()
    from loom.cli._quilt import open_scan
    from loom.library.generation import generation
    from loom.render.api import ApiError, handle
    from loom.render.endpoints.library import WRITES, answered, receive_stream

    root, unasked = _quilts(tmp)
    out: dict[str, dict[str, Any]] = {}

    def keep(name: str, endpoint: str, request: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
        assert name not in out, name
        out[name] = {"endpoint": endpoint, "request": request, "answer": answer}
        return answer

    def call(name: str | None, endpoint: str, request: dict[str, Any], *, on: Path = root) -> dict[str, Any]:
        """One JSON endpoint as the publisher serves it, a write answered with the library's generation it left, kept as `name` unless None; a refusal answers its body with its status."""
        try:
            answer = handle(on, endpoint, request)
            if endpoint in WRITES:
                answer = answered(endpoint, answer, generation(open_scan(str(on))))
        except ApiError as exc:
            answer = {"status": exc.status, **exc.answer()}
        return keep(name, endpoint, request, answer) if name else answer

    def receive(name: str | None, file: str, data: bytes, *, on: Path = root) -> dict[str, Any]:
        """`library-receive` as the server calls it: the bytes streamed, the name from the query, the length from `Content-Length`."""
        request = {"name": file, "size": len(data)}
        try:
            answer = answered(
                "library-receive", receive_stream(on, file, io.BytesIO(data), len(data)), generation(open_scan(str(on)))
            )
        except ApiError as exc:
            answer = {"status": exc.status, **exc.answer()}
        return keep(name, "library-receive", request, answer) if name else answer

    def dropped(file: str, data: bytes, *, on: Path = root) -> str:
        """A file received as a drop, its sample not kept: the drop's id, which a take names."""
        got = receive(None, file, data, on=on)
        assert "incoming" in got, got
        return str(got["incoming"])

    # -- the reads, on the library as the showcase has it
    works = call("library-works", "library-works", {})
    call("library-works.doc", "library-works", {"doc": DOC})
    call("library-works.unchanged", "library-works", {"since": works["gen"]})
    # where the notes on a stored paper stand on its pages, which the reader draws them from
    placed = call("library-places", "library-places", {"ref": BELLAMY})
    call("library-places.page", "library-places", {"ref": BELLAMY, "pages": [2]})
    call("library-places.unchanged", "library-places", {"ref": BELLAMY, "since": placed["gen"]})
    call("library-places.no-document", "library-places", {"ref": CORTEZ})
    # a work's tab: its outline, before anything of it is digested; held as a PDF alone; held as neither
    call("library-work", "library-work", {"ref": ARDEN})
    call("library-work.pdf", "library-work", {"ref": BELLAMY})
    call("library-work.no-document", "library-work", {"ref": CORTEZ})
    call("library-digest-scopes", "library-digest-scopes", {"ref": ARDEN})
    call("library-digest-scopes.pdf", "library-digest-scopes", {"ref": BELLAMY})
    call("library-digest-scopes.all", "library-digest-scopes", {"all": True})
    call("library-node.item", "library-node", {"ref": ARDEN, "item": "lem:saturated"})
    call("library-find", "library-find", {"ref": BELLAMY, "q": "median order"})
    call("library-find.no-document", "library-find", {"ref": CORTEZ, "q": "Theorem"})
    # Arden 2024 digested by the person, then its nodes read beside their pages
    call("library-digest", "library-digest", {"refs": [ARDEN], "scope": "all"})
    call("library-digest.no-reviewer", "library-digest", {"refs": [BELLAMY], "scope": "all"})
    call("library-digest.no-document", "library-digest", {"refs": [CORTEZ], "scope": "all"})
    lemma = _labelled(root, ARDEN, "lem:saturated")
    call("library-work.digested", "library-work", {"ref": ARDEN})
    call("library-node", "library-node", {"node": lemma})
    call("library-node.brief", "library-node", {"node": lemma, "brief": True})
    call("library-node.no-such-node", "library-node", {"node": "sh-0ZZZ"})
    call("library-places.nodes", "library-places", {"ref": ARDEN, "pages": [1, 2]})
    call("library-places.node", "library-places", {"node": lemma})

    # -- a drop on the quilt that has not said whether loom may use the network (library-views.md Open 36): received, refused, taken again with `online: false`, and undone; and a look-up there
    paper = receive("library-receive", "2209.01234v2.pdf", _pdf("2209.01234v2"), on=unasked)
    take = {"items": [{"incoming": paper["incoming"]}]}
    call("library-take.network-unasked", "library-take", take, on=unasked)
    added = call("library-take.added", "library-take", {**take, "online": False}, on=unasked)
    row = added["rows"][0]
    call("library-undo", "library-undo", {"id": row["id"], "act": row["act"]}, on=unasked)
    call("library-look-up.network-unasked", "library-look-up", {"ref": ARDEN_V2}, on=unasked)

    # -- the rest on the showcase, whose network is off: a file that is no paper, then a take for each state a row can be in
    receive("library-receive.not-a-document", "reading-list.txt", b"Halberd and Ravel, Gadget towers\n")
    source = dropped("gadget-towers.tex", SOURCE)
    call("library-take.added-source", "library-take", {"items": [{"incoming": source}]})
    under = dropped("cortez-survey.pdf", _pdf("cortez-survey"))
    call("library-take.added-under", "library-take", {"items": [{"incoming": under, "for": CORTEZ}]})
    pasted = call("library-take.pasted", "library-take", {"items": [{"text": "2311.04567\n10.1000/example.2020.7"}]})
    here = dropped("bellamy-median-orders.pdf", _stored_pdf(root, BELLAMY))
    call("library-take.here", "library-take", {"items": [{"incoming": here}]})
    # a file stating an arXiv number two works state: Arden's second version, its PDF taken off first, is the candidate, and Arden 2024, which holds a PDF, is held
    call(None, "library-unfile", {"ref": ARDEN_V2})
    asked = dropped("2504.01234v3.pdf", _pdf("2504.01234v3"))
    question = call("library-take.question", "library-take", {"items": [{"incoming": asked}]})
    nothing = "ISBN 978-3-16-148410-0\nthe paper Okafor mentioned"
    call("library-take.cannot", "library-take", {"items": [{"text": nothing}]})
    reprint = dropped("bellamy-reprint.pdf", _pdf("bellamy-reprint"))
    call("library-take.has-document", "library-take", {"items": [{"incoming": reprint, "for": BELLAMY}]})

    # -- the question answered: by a work it does not offer, then by the one it offers, Arden's second version, under which it is filed on the person's word though the other states the number too
    first = question["rows"][0]["question"]
    call("library-answer.not-a-candidate", "library-answer", {"question": first, "same": CORTEZ})
    call("library-answer.same", "library-answer", {"question": first, "same": ARDEN_V2})
    # and another file stating the number, which both works now hold one of, so it is asked about as a copy, kept as a work of its own
    reprint_v3 = dropped("2504.01234v3 (1).pdf", _pdf("2504.01234v3 (1)"))
    second = call(None, "library-take", {"items": [{"incoming": reprint_v3}]})["rows"][0]["question"]
    call("library-answer", "library-answer", {"question": second, "same": None})

    # -- a pasted work taken out again, as a drop's add is; and the same undo again, which finds nothing standing
    row = pasted["rows"][0]
    call("library-undo.pasted", "library-undo", {"id": row["id"], "act": row["act"]})
    call("library-undo.no-such-intake", "library-undo", {"id": row["id"], "act": row["act"]})

    # -- a work's PDF taken off it, and put back by undoing that
    off = call("library-unfile", "library-unfile", {"ref": BELLAMY})
    call("library-undo.unfile", "library-undo", {"id": off["incoming"], "act": off["act"]})

    # -- a PDF taken off its work and filed on it again, that filing undone: the drop waits again, and the undo answers its row
    off = call(None, "library-unfile", {"ref": CORTEZ})
    back = call(None, "library-take", {"items": [{"incoming": off["incoming"], "for": CORTEZ}]})
    call("library-undo.waits-again", "library-undo", {"id": off["incoming"], "act": back["rows"][0]["act"]})

    # -- look-ups, refused with the network off, and allowed it for one look-up of a work that states nothing to look up, which is refused before it asks
    call("library-look-up.offline", "library-look-up", {"ref": ARDEN_V2})
    call("library-look-up.no-identifier", "library-look-up", {"ref": CORTEZ, "online": True})

    # -- an entry rewritten, and refused for a key another work has
    call("library-entry", "library-entry", {"ref": CORTEZ, "bibtex": ENTRY})
    call("library-entry.key-taken", "library-entry", {"ref": CORTEZ, "bibtex": ENTRY.replace("Cortez07", "Arden24")})

    # -- a work deleted, and put back
    gone = call("library-delete", "library-delete", {"ref": ARDEN})
    call("library-restore", "library-restore", {"undo": gone["undo"]})
    return out


def _labelled(root: Path, ref: str, label: str) -> str:
    """The id of the node of a work digested from the result its source labels `label`."""
    from loom.library.digest import of_work

    return next(n.id for n in of_work(root, ref) if n.label == label)


def _stored_pdf(root: Path, ref: str) -> bytes:
    """The bytes of the PDF a work holds, as the store keeps them: dropped again, they are `here`."""
    from loom.library import documents
    from loom.library.store import read

    node = read(root, ref)
    assert node is not None and node.pdf, f"{ref} holds no PDF in the showcase"
    return documents.path_of(root, node.pdf, "pdf").read_bytes()


def render(sample: dict[str, Any]) -> str:
    """A sample as its file holds it, formatted as the evidence lane's are."""
    return json.dumps(sample, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main(check: bool) -> int:
    """Write the samples, or with `check` say which written ones are stale; only `library-*.json` is read, written or removed.

    A sample naming the temporary folder stops the script, since it would differ on every run.
    """
    with tempfile.TemporaryDirectory(prefix="loom-library-views-") as tmp:
        made = {f"{name}.json": render(sample) for name, sample in samples(Path(tmp)).items()}
        leaked = [name for name, body in made.items() if tmp in body or Path(tmp).resolve().as_posix() in body]
    if leaked:
        raise SystemExit(f"a sample names the temporary quilt's place, which differs on every run: {', '.join(leaked)}")
    have = {p.name: p.read_text(encoding="utf-8") for p in OUT.glob(MINE)} if OUT.is_dir() else {}
    if check:
        stale = sorted(set(made) ^ set(have) | {n for n in made if have.get(n) != made[n]})
        for name in stale:
            print(f"stale: {OUT.relative_to(REPO) / name}")
        return 1 if stale else 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name in set(have) - set(made):
        (OUT / name).unlink()
    for name, body in made.items():
        (OUT / name).write_text(body, encoding="utf-8")
    print(f"wrote {len(made)} samples to {OUT.relative_to(REPO)}/{MINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
