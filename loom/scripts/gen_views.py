"""Write docs/specs/fixture/views/: for each read and write of Review's and the Web's families (docs/specs/evidence.md §6 to §8), a sample request and the answer loom gives it, one file each. The viewer's sample data is these files, so the two sides cannot drift apart.

They are made on a copy of the synthetic quilt whose last build is the conformance fixture's manifest, with a short history of asks and evidence, under a fixed time and an empty home, so they need no TeX and come out the same each time.

Usage: uv run python scripts/gen_views.py [--check]   (--check exits 1 when a checked-in file is stale)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

LOOM_DIR = Path(__file__).resolve().parent.parent
REPO = LOOM_DIR.parent
OUT = REPO / "docs" / "specs" / "fixture" / "views"
#: The fixture's own fixed time, so the samples' times read as the manifest's.
FIXED = "2026-09-16T00:00:00Z"
PERSON = "The synthetic quilt"
AGENT = "Probe Agent"


def _isolated(home: Path) -> None:
    """An empty home and a fixed clock for this process; no agent's marker, since the person acts here."""
    from loom.identity import AGENT_MARKERS

    os.environ.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        LOOM_FIXED_TIME=FIXED,
        LOOM_PROGRESS="off",
    )
    for marker in AGENT_MARKERS:
        os.environ.pop(marker, None)


def _quilt(tmp: Path) -> Path:
    """A copy of the synthetic quilt with the fixture's manifest as its last build, a Lean file, and the person's name saved."""
    from loom.paths import MANIFEST
    from loom.scan.quilt import save_author

    root = tmp / "synthetic"
    shutil.copytree(LOOM_DIR / "tests" / "quilts" / "synthetic", root, ignore=shutil.ignore_patterns("build", ".git"))
    (root / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO / "docs" / "specs" / "fixture" / "manifest.json", root / MANIFEST)
    (root / "lean").mkdir(exist_ok=True)
    (root / "lean" / "Synthetic.lean").write_text("theorem sy_0007 : True := trivial\n", encoding="utf-8")
    save_author(PERSON)
    return root


def _history(root: Path) -> None:
    """What waits for the person and for agents: Lean on two results, one attested then gone stale, an agent's question and request for a paper, and a person's ask an agent took."""
    from loom.evidence.asks import ask, say
    from loom.evidence.log import write
    from loom.evidence.subjects import Subject, Who
    from loom.evidence.web import DraftWeb
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    person, agent, loom = Who("person", PERSON), Who("agent", AGENT), Who("loom")
    web = DraftWeb(scan(load_quilt(root)))
    lean_file = "sha256:" + hashlib.sha256((root / "lean" / "Synthetic.lean").read_bytes()).hexdigest()

    def lean(label: str, statement: str) -> Any:
        here = web.heres(label)[0]
        subject = web.subject(here)
        assert subject is not None, label
        declaration = {"name": "Synthetic." + label.replace("-", "_"), "kind": "theorem", "role": "states", "names": {"label": label}, "statement": statement, "axioms": ["propext"], "sorry": False}  # fmt: skip
        record = write(
            root,
            "lean",
            loom,
            on=subject,
            project={
                "root": "lean",
                "toolchain": "leanprover/lean4:v4.36.0",
                "mathlib": "9d581dfff2e41de989072ea63abf3daf69311520",
                "manifest": "sha256:" + "2" * 64,
            },  # fmt: skip
            files={"lean/Synthetic.lean": lean_file},
            declarations=[declaration],
            assumed=[],
            uses=[],
            replay={"tool": "leanchecker", "exit": 0, "output": ""},
            ok=True,
        )
        return here, subject, record

    # Lean accepted sy-0202 and nobody has attested it: a row to attest
    lean("sy-0202", "sha256:" + "a" * 64)
    # sy-0007 attested over a closure one of whose members has changed since: a row whose attestation went stale
    here, subject, record = lean("sy-0007", "sha256:" + "b" * 64)
    closure = [{k[0]: k[1], "hash": v} for k, v in sorted(web.closure(here).items())]
    stale = [{**m, "hash": "sha256:" + "c" * 64} if i == 0 else m for i, m in enumerate(closure)] or [{"label": "sy-0001", "hash": "sha256:" + "c" * 64}]  # fmt: skip
    write(root, "attested", person, on=subject, lean=record.id, statements={record.get("declarations")[0]["name"]: "sha256:" + "b" * 64}, closure=stale, rulings=[])  # fmt: skip
    for name, digest in web.notation(here).items():
        write(root, "attested", person, on=Subject("macro", name, digest))
    read = ask(root, person, "read", "agent", {"node": "sy-00B7"}, origin=["drafting/main.tex"], nodes=["sy-00B7"])
    say(root, agent, "took", read.id, session="s-2026-09-16-a8k2rx")
    # asked by the session working on that task, which the person's row names
    ask(root, agent, "question", "person", {"label": "sy-0007"}, origin=["drafting/main.tex"], text="The lemma's composite: of the two maps or of their involutions?", choices=["the maps", "the involutions"], under=read.id)  # fmt: skip
    ask(root, agent, "paper", "person", {"ref": "sy-00A1-ref"}, origin=["drafting/main.tex"], ref="sy-00A1-ref", link="https://doi.org/10.1000/example.1999.2", want="pdf", words="The publisher's page asks for a login.")  # fmt: skip


def _first_row(answer: dict[str, Any]) -> str:
    return str(next(r["row"] for g in answer["groups"] for r in g["rows"]))


def _first_result(answer: dict[str, Any]) -> str:
    return str(next(r["result"] for section in answer["sections"] for g in section.get("groups", []) for r in g.get("rows", [])))  # fmt: skip


def samples(tmp: Path) -> dict[str, dict[str, Any]]:
    """Each sample by its file's name: the endpoint, the request and loom's answer."""
    from loom.render.api import ApiError, handle

    _isolated(tmp / "home")
    root = _quilt(tmp)
    _history(root)
    out: dict[str, dict[str, Any]] = {}

    def call(name: str, endpoint: str, body: dict[str, Any] | Callable[[], dict[str, Any]]) -> dict[str, Any]:
        request = body() if callable(body) else body
        try:
            answer = handle(root, endpoint, request)
        except ApiError as exc:
            answer = {"status": exc.status, **exc.answer()}
        out[name] = {"endpoint": endpoint, "request": request, "answer": answer}
        return answer

    call("review-counts", "review-counts", {})
    listed = call("review-list", "review-list", {})
    call("review-list.questions", "review-list", {"kind": "questions"})
    call("review-list.draft", "review-list", {"doc": "drafting/main.tex"})
    call("review-row", "review-row", lambda: {"row": _first_row(listed)})
    changed = next(r["row"] for g in listed["groups"] for r in g["rows"] if g["kind"] == "attested-changed")
    call("review-row.attested-changed", "review-row", {"row": changed})
    task = next(r for g in listed["groups"] for r in g["rows"] if g["kind"] == "agents")
    question = next(r for g in listed["groups"] for r in g["rows"] if g["kind"] == "questions")
    web = call("web-list", "web-list", {"scope": "all", "open": ["drafting/main.tex"]})
    call("web-list.status", "web-list", {"scope": "draft", "doc": "drafting/main.tex", "sort": "status"})
    call("web-group", "web-group", {"scope": "all", "group": "drafting/main.tex"})
    call("web-search", "web-search", {"scope": "all", "q": "involution"})
    result = _first_result(web)
    call("web-focus", "web-focus", {"scope": "all", "result": result, "more": True})
    call("web-graph", "web-graph", {"scope": "all", "result": result})
    # the writes, after every read, since they change what the reads would answer
    call("review-answer", "review-answer", {"question": question["question"], "choice": 1, "text": "and say which you used"})  # fmt: skip
    call("review-answer.closed", "review-answer", {"question": question["question"], "text": "again"})
    call("review-task", "review-task", {"kind": "ask", "on": {"key": "sy-0001", "quote": "a pair of a set"}, "text": "Is this the usual pair?", "docs": ["drafting/main.tex"]})  # fmt: skip
    call("review-task-delete", "review-task-delete", {"task": task["task"]})
    return out


def render(sample: dict[str, Any]) -> str:
    return json.dumps(sample, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


#: The files of this folder that are this generator's: Review's and the Web's samples. Another generator writes the Library's beside them, and neither reads, writes or clears the other's.
MINE = ("review-*.json", "web-*.json")


def mine(folder: Path) -> dict[str, str]:
    """This generator's files in `folder`, by name, with their text; another generator's are not read."""
    if not folder.is_dir():
        return {}
    return {p.name: p.read_text(encoding="utf-8") for pattern in MINE for p in folder.glob(pattern)}


def main(check: bool, out: Path = OUT) -> int:
    """Write the samples into `out`, clearing only this generator's files there; with `check`, write nothing and say which of them are stale."""
    with tempfile.TemporaryDirectory(prefix="loom-views-") as tmp:
        made = {f"{name}.json": render(sample) for name, sample in samples(Path(tmp)).items()}
    text = json.dumps(made)
    if Path(tempfile.gettempdir()).as_posix() in text or "loom-views-" in text:
        raise SystemExit("a sample names the temporary quilt's place; a reply must not carry a path outside the quilt")
    have = mine(out)
    if check:
        stale = sorted(set(made) ^ set(have) | {n for n in made if have.get(n) != made[n]})
        for name in stale:
            print(f"stale: {out / name}")
        return 1 if stale else 0
    out.mkdir(parents=True, exist_ok=True)
    for name in set(have) - set(made):
        (out / name).unlink()
    for name, body in made.items():
        (out / name).write_text(body, encoding="utf-8")
    print(f"wrote {len(made)} samples to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
