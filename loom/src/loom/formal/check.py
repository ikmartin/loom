"""Loom's certifying check of the quilt's Lean: a clean rebuild of the project, then loom's own probe, which replays the build in Lean's kernel and reads what it states, every step inside the fence under Lean's own profile (`fence.lean_argv`), recorded as one `lean` record for each result a declaration names (`docs/specs/evidence.md` §3.4).

What a record says is read from what loom ran and nothing an agent wrote about it: which declaration states which result is the marker `@[loom "NAME"]` as the built project holds it, the axioms are those Lean's own constants reach, and the verdict is the build's and the replay's exit. A record names every Lean file it rests on by its hash, so it stops standing when any of them changes (`status.files_unchanged`), and names the result's text by its hash, so it is no longer current once the statement changes; a definition's text that changed moves the person's attestation, which names it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loom import fence, paths
from loom.evidence.subjects import Subject, Who, is_node
from loom.formal import install, switch

#: Loom's probe, run with `lean --run` inside the fence (`assets/lean/Probe.lean`).
PROBE = Path(__file__).parent.parent / "assets" / "lean" / "Probe.lean"
#: The project's files besides its modules that every record names: what Lake builds from.
CONFIG = ("lakefile.toml", "lean-toolchain", "lake-manifest.json")
#: The longest a step may run, in seconds: a rebuild of a project whose Mathlib is whole, on a loaded machine.
TIMEOUT = 3600
#: The most of the replay's output a record keeps.
OUTPUT = 20_000
#: The replay a record names: the probe hands every declaration of the project's modules to Lean's kernel over the modules they import from outside it, as leanchecker does one module at a time.
REPLAY = "Lean.Kernel.Environment.replay"
_ERROR = re.compile(r"^error: (?:\./)?(?P<path>[^:\s]+\.lean):(?P<rest>.*)$")


class Refused(Exception):
    """Loom could not check the Lean on this machine, in a sentence for the person or the agent; no record was written."""


@dataclass
class Checked:
    """What a check did: the records written, the results already observed as they stand, the markers that name nothing loom knows, Lean's errors, and each step's seconds."""

    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    steps: list[tuple[str, float]] = field(default_factory=list)


def modules(proj: Path) -> dict[str, str]:
    """The project's modules, by name, each with its path from the project: every `.lean` file of its two libraries (`install.MARKER_MODULE`, `install.LIBRARY`), outside hidden folders, which are all the modules a project of loom's shape (`install.untrusted`) can build."""
    out: dict[str, str] = {}
    for path in sorted(proj.rglob("*.lean")):
        rel = path.relative_to(proj)
        if any(part.startswith(".") for part in rel.parts) or not path.is_file():
            continue
        name = ".".join(rel.with_suffix("").parts)
        if any(name == lib or name.startswith(lib + ".") for lib in (install.MARKER_MODULE, install.LIBRARY)):
            out[name] = rel.as_posix()
    return out


def _digest(path: Path) -> str | None:
    try:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check(root: Path, say: Callable[[str], None] = lambda _: None) -> Checked:
    """Run loom's certifying check of the quilt's Lean project and record what Lean said.

    Parameters
    ----------
    root : Path
        The quilt's root.
    say : callable, optional
        Told each step as it starts, in words.

    Returns
    -------
    Checked
        The records written and what else the check found.

    Raises
    ------
    Refused
        When formalization is off for this quilt on this machine, the fence cannot be put up, the toolchain or Mathlib's build is missing, the project requires what loom does not install, or the Lean changed while loom checked it. Nothing is recorded and nothing ran unfenced.
    """
    if not switch.is_on(root):
        raise Refused("formalization is off for this quilt on this machine; the person turns it on")
    proj = install.project(root)
    if not (proj / "lakefile.toml").is_file():
        raise Refused(f"the quilt has no Lean project in {install.LEAN}/")
    try:
        name = install.toolchain_of(proj)
    except install.Refused as e:
        raise Refused(str(e)) from None
    problems = install.untrusted(proj)
    if problems:
        raise Refused("the Lean project requires what loom does not install: " + "; ".join(problems))
    toolchain = install.toolchain_folder(name)
    if not (toolchain / "bin" / "lake").is_file():
        raise Refused(f"the toolchain {name} is not installed here; turning formalization on again installs it")
    missing = [p for p in _packages(proj) if not (proj / paths.LAKE_PACKAGES / p).is_dir()]
    if missing:
        raise Refused(
            f"{', '.join(missing)} is not installed in the Lean project here; turning formalization on again fetches it"
        )
    why = fence.lean_state()
    if why is not None:
        raise Refused(
            f"loom could not check the Lean on this machine: the fence is not up ({why}), and the check runs fenced or not at all"
        )
    mods = modules(proj)
    if not mods:
        raise Refused(f"the Lean project holds no module of {install.LIBRARY}")
    with tempfile.TemporaryDirectory(prefix="loom-probe-") as probe:
        shutil.copyfile(PROBE, Path(probe) / "Probe.lean")
        places = fence.lean_places(project=proj, toolchain=toolchain, probe=Path(probe))
        if fence.lean_leaks(places):
            raise Refused(
                "the Lean project or its toolchain lies in a folder that holds your own files, which the fence would open"
            )
        from loom.errors import EnvError
        from loom.locks import locked

        lock = locked(proj / paths.LAKE_LOCK, wait=1)
        try:
            lock.__enter__()
        except EnvError:
            raise Refused("loom is already checking this quilt's Lean; ask again once it is done") from None
        try:
            return _check(root, proj, name, toolchain, mods, places, Path(probe) / "Probe.lean", say)
        finally:
            lock.__exit__(None, None, None)


def _check(
    root: Path,
    proj: Path,
    name: str,
    toolchain: Path,
    mods: dict[str, str],
    places: dict[str, str],
    probe: Path,
    say: Callable[[str], None],
) -> Checked:
    """`check` once its preconditions hold: the fenced steps, then the records."""
    done = Checked()
    if not install.marker_is_loom_s(root):
        raise Refused(
            f"{install.LEAN}/{install.MARKER_MODULE}.lean is not loom's marker module as loom ships it; turning formalization on again puts it back"
        )
    read = [*(p for p in mods.values()), *CONFIG]
    before = {p: _digest(proj / p) for p in read}
    if any(h is None for h in before.values()):
        raise Refused(
            "the Lean project lacks "
            + ", ".join(p for p, h in before.items() if h is None)
            + "; turning formalization on again makes it"
        )
    own, build = proj / paths.LAKE_LOOM, proj / paths.LAKE_BUILD
    for p in (proj, proj / paths.LAKE, own, build):
        if p.is_symlink() or (p.exists() and not p.is_dir()):
            raise Refused(f"{p.relative_to(root)} is not a folder of the project's own; remove it and check again")
    # the two folders the check removes, each a plain folder in the project's .lake: loom's own for its runs, and Lake's build of the project's modules, which the check makes again from clean
    shutil.rmtree(own, ignore_errors=True)
    (own / "home").mkdir(parents=True)
    (own / "tmp").mkdir()
    shutil.rmtree(build, ignore_errors=True)
    lake = str(toolchain / "bin" / "lake")
    env = {
        "PATH": os.pathsep.join([str(toolchain / "bin"), f"{places['DEVDIR']}/usr/bin", "/usr/bin", "/bin"]),
        "HOME": str(own / "home"),
        "TMPDIR": str(own / "tmp"),
        "LANG": "en_US.UTF-8",
    }

    def run(step: str, argv: list[str]) -> subprocess.CompletedProcess[str]:
        say(step)
        t = time.monotonic()
        try:
            got = _fenced(argv, places, proj, env)
        finally:
            done.steps.append((step, time.monotonic() - t))
        return got

    if "mathlib" in _packages(proj):
        whole = run("checking that Mathlib's build is whole", [lake, "build", "--no-build", "Mathlib"])
        if whole.returncode != 0:
            raise Refused(
                "Mathlib's build in the project is not whole, and loom will not compile Mathlib; turning formalization on again fetches it"
            )
    built = run("building the Lean project from clean", [lake, "build", *(f"+{m}" for m in mods)])
    errors = _errors(built.stdout + built.stderr)
    done.errors = [e for es in errors.values() for e in es]
    ready = [m for m, p in mods.items() if (build / "lib" / "lean" / Path(p).with_suffix(".olean")).is_file()]
    if not ready:
        raise Refused("no module of the Lean project built:\n" + "\n".join(done.errors[:12] or [built.stdout[-2000:]]))
    lib = Path("lib") / "lean"
    deps = [f"path={(proj / paths.LAKE_PACKAGES / p / paths.LAKE_BUILD / lib).resolve()}" for p in _packages(proj)]
    probed = run(
        "replaying the build in Lean's kernel and reading what it states",
        [str(toolchain / "bin" / "lean"), "--run", str(probe), f"own={(build / lib).resolve()}", *deps, *ready],
    )
    if probed.returncode != 0:
        # the probe never answered, as when the machine was short of memory: no observation, so nothing is recorded
        raise Refused(
            "loom's probe of the built project failed; check again:\n" + (probed.stdout + probed.stderr)[-2000:]
        )
    try:
        found = json.loads(probed.stdout.strip().splitlines()[-1])
        replayed = {
            "tool": REPLAY,
            "exit": int(found["replay"]["exit"]),
            "output": str(found["replay"]["output"])[-OUTPUT:],
        }
    except (ValueError, IndexError, KeyError, TypeError):
        raise Refused("loom's probe of the built project said nothing loom can read") from None
    after = {p: _digest(proj / p) for p in read}
    if after != before or set(modules(proj)) != set(mods):
        raise Refused("the Lean changed while loom checked it; check again once it is still")
    _record(root, name, mods, before, found, errors, replayed, done)
    return done


def _packages(proj: Path) -> list[str]:
    """The packages the project's manifest pins, by name."""
    try:
        manifest = json.loads((proj / "lake-manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return (
        [str(p.get("name")) for p in manifest.get("packages", []) if isinstance(p, dict)]
        if isinstance(manifest, dict)
        else []
    )


def _fenced(
    argv: list[str], places: dict[str, str], cwd: Path, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run one step inside the fence, in its own process group, stopped whole at `TIMEOUT`."""
    from loom.tex.runner import stop_run

    proc = subprocess.Popen(
        fence.lean_argv(argv, places),
        cwd=cwd,
        env={**env, "PWD": str(cwd)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        stop_run(proc)
        proc.communicate()
        raise Refused(f"a step of the check ran past {TIMEOUT // 60} minutes and was stopped") from None
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def _errors(output: str) -> dict[str, list[str]]:
    """Lean's errors in a build's output, by the module's path from the project."""
    out: dict[str, list[str]] = {}
    for line in output.splitlines():
        m = _ERROR.match(line.strip())
        if m:
            out.setdefault(m["path"], []).append(f"{m['path']}:{m['rest']}")
    return out


@dataclass
class _Decl:
    name: str
    module: str
    kind: str
    statement: str
    axioms: list[str]
    uses: list[str]
    internal: bool
    means: list[str]


def _statement_hashes(decls: dict[str, _Decl]) -> dict[str, str]:
    """Each declaration's statement hash: what it says, with the statement of each declaration of the project it names there, in turn, so a theorem stated with a helper definition no marker names stops matching an attestation once that definition says something else."""
    out: dict[str, str] = {}

    def of(name: str, seen: frozenset[str]) -> str:
        if name in out:
            return out[name]
        d = decls[name]
        named = sorted((n, of(n, seen | {name})) for n in d.means if n in decls and n not in seen and n != name)
        digest = (
            "sha256:" + hashlib.sha256(json.dumps([d.statement, named], ensure_ascii=False).encode("utf-8")).hexdigest()
        )
        if not seen:
            out[name] = digest
        return digest

    for name in decls:
        of(name, frozenset())
    return out


def _resolver(root: Path) -> Callable[[str], list[Subject]]:
    """What a marker names now: each text of a draft's result bearing it as a label, by its own label, else the library's node of that id; [] for nothing."""
    from loom.evidence.web import DraftWeb, Here, LibraryWeb
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan

    drafts = DraftWeb(scan(load_quilt(root)))
    library = LibraryWeb(root)

    def resolve(marker: str) -> list[Subject]:
        if marker in drafts.bearing:
            found = [drafts.subject(h) for h in drafts.heres(marker)]
            return list(dict.fromkeys(s for s in found if s is not None))
        if is_node(marker, "statement"):
            got = library.subject(Here("node", marker))
            return [got] if got is not None else []
        return []

    return resolve


def _record(
    root: Path,
    toolchain: str,
    mods: dict[str, str],
    hashes: dict[str, str | None],
    found: dict[str, Any],
    errors: dict[str, list[str]],
    replayed: dict[str, Any],
    done: Checked,
) -> None:
    """Write one `lean` record for each text of each result a declaration's marker names, unless the latest record on it says the same."""
    from loom.evidence import log

    decls: dict[str, _Decl] = {}
    markers: dict[str, str] = {}
    for d in found.get("declarations", []):
        if d.get("marker") is not None and d["name"].endswith("._loom"):
            markers[d["name"].removesuffix("._loom")] = d["marker"]
            continue
        decls[d["name"]] = _Decl(
            d["name"],
            d["module"],
            d["kind"],
            d["statement"],
            list(d["axioms"]),
            list(d["uses"]),
            bool(d["internal"]),
            list(d.get("means", [])),
        )
    imports: dict[str, list[str]] = {m: list(v) for m, v in found.get("modules", {}).items()}
    statements = _statement_hashes(decls)
    resolve = _resolver(root)
    named: dict[str, list[Subject]] = {}
    for decl, marker in markers.items():
        subjects = resolve(marker)
        if not subjects:
            done.unknown.append(f"{decl}: {marker}")
        named[decl] = subjects
    by_result: dict[tuple[str, str], list[str]] = {}
    for decl, subjects in named.items():
        for s in subjects:
            by_result.setdefault(s.key, []).append(decl)
    manifest = json.loads((root / install.LEAN / "lake-manifest.json").read_text(encoding="utf-8"))
    mathlib = next((p.get("rev", "") for p in manifest.get("packages", []) if p.get("name") == "mathlib"), "")
    project = {
        "root": install.LEAN,
        "toolchain": toolchain,
        "mathlib": mathlib or "none",
        "manifest": hashes["lake-manifest.json"],
    }
    evidence = log.replay(root)
    for decl, subjects in named.items():
        for subject in subjects:
            if by_result[subject.key][0] != decl:
                continue  # one record for a result, however many declarations state it
            cone = _cone(by_result[subject.key], decls)
            fields = _fields(subject, cone, decls, markers, named, mods, imports, hashes, errors, project, statements)
            fields["replay"] = replayed
            latest = evidence.about(*subject.key, of="lean")
            if latest and latest[-1].on == subject and _same(latest[-1].fields, fields):
                done.unchanged.append(subject.name)
                continue
            log.write(root, "lean", Who("loom"), on=subject, **fields)
            done.written.append(subject.name)


def _cone(start: list[str], decls: dict[str, _Decl]) -> list[str]:
    """Every declaration of the project `start` reaches through what each uses, `start` first, in the order reached."""
    out, todo = list(dict.fromkeys(start)), list(start)
    while todo:
        d = decls.get(todo.pop(0))
        for u in d.uses if d else []:
            if u in decls and u not in out:
                out.append(u)
                todo.append(u)
    return out


def _fields(
    subject: Subject,
    cone: list[str],
    decls: dict[str, _Decl],
    markers: dict[str, str],
    named: dict[str, list[Subject]],
    mods: dict[str, str],
    imports: dict[str, list[str]],
    hashes: dict[str, str | None],
    errors: dict[str, list[str]],
    project: dict[str, Any],
    statements: dict[str, str],
) -> dict[str, Any]:
    """A `lean` record's fields for `subject` but its replay: its declarations, what it assumes and uses, the files it rests on and the verdict."""
    rows: list[dict[str, Any]] = []
    assumed: list[dict[str, str]] = []
    uses: list[dict[str, str]] = []
    for name in cone:
        d = decls[name]
        if d.internal:
            continue
        others = [s for s in named.get(name, []) if s.key != subject.key] if name in markers else []
        mine = name in markers and any(s.key == subject.key for s in named.get(name, []))
        states = mine or bool(others)
        names = {subject.kind: subject.name} if mine else ({others[0].kind: others[0].name} if others else None)
        rows.append(
            {
                "name": name,
                "kind": d.kind
                if d.kind in ("theorem", "def", "axiom", "structure", "inductive", "abbrev", "opaque")
                else "def",
                "role": "states" if states else "supports",
                "names": names,
                "statement": statements[name],
                "axioms": d.axioms,
                "sorry": "sorryAx" in d.axioms,
            }
        )
        for s in others:
            entry = s.to_dict()
            if d.kind == "axiom" and s.kind == "node":
                if entry not in assumed:
                    assumed.append(entry)
            elif entry not in uses:
                uses.append(entry)
    touched = {decls[n].module for n in cone}
    closure, todo = set(touched), list(touched)
    while todo:
        for m in imports.get(todo.pop(), []):
            if m not in closure:
                closure.add(m)
                todo.append(m)
    files = {f"{install.LEAN}/{mods[m]}": hashes[mods[m]] for m in sorted(closure) if m in mods}
    files |= {f"{install.LEAN}/{p}": hashes[p] for p in CONFIG}
    wrong = [e for m in sorted(closure) if m in mods for e in errors.get(mods[m], [])]
    fields: dict[str, Any] = {
        "project": project,
        "files": files,
        "declarations": rows,
        "assumed": assumed,
        "uses": uses,
        "ok": not wrong,
    }
    if wrong:
        fields["errors"] = wrong
    return fields


def _same(old: Any, new: dict[str, Any]) -> bool:
    """Whether a record already says what `new` would: every field the same, the replay's output aside."""
    keys = set(new) | {"on"}
    a = {k: old.get(k) for k in keys if k not in ("on", "replay")}
    b = {k: new.get(k) for k in keys if k not in ("on", "replay")}
    return a == b and (old.get("replay") or {}).get("exit") == new["replay"]["exit"]
