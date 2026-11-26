"""The checks behind `loom doctor`: the machine's tools and what they can do, the author name, the viewer bundle, and, inside a quilt, the quilt's own setup.

Every item is `ok`, `warn` (it works, but the person will hit something) or `fail` (a command they need will refuse or misbehave), and every item that is not ok carries a one-line remedy. The quilt's items call the functions the owning commands use -- `loom upgrade`, `loom lint` -- rather than restating them. Tools are found through shutil.which, so tests point PATH at the fake TeX shim; the probes run at once and share one deadline, PROBE_TIMEOUT, so a hung tool is reported rather than waited on.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loom.paths import AI, LOOM_GITIGNORE
from loom.version import __version__

if TYPE_CHECKING:
    from loom.cli.report import Report as OutReport

OK, WARN, FAIL = "ok", "warn", "fail"
#: required: missing fails; optional: missing warns, and present but broken fails, since loom uses it when present; quilt: the quilt section
REQUIRED, OPTIONAL, QUILT = "required", "optional", "quilt"
#: Seconds a probe may take before its tool is reported as hung.
PROBE_TIMEOUT = 10.0

_MAC = platform.system() == "Darwin"
TEX = (
    "brew install --cask mactex-no-gui"
    if _MAC
    else "install TeX Live (https://tug.org/texlive) or apt install texlive-full"
)
POPPLER = "brew install poppler" if _MAC else "apt install poppler-utils"
GIT = "brew install git" if _MAC else "apt install git"
GHOSTSCRIPT = "brew install ghostscript" if _MAC else "apt install ghostscript"
#: The one remedy for loom's own TeX, which touches nothing but loom's directory.
REPAIR = "Repair TeX: loom doctor --repair installs loom's own TeX, Ghostscript and poppler (no password; about 120 MB, once)"
#: The remedies `REPAIR` stands in for unless the person keeps their own TeX (`[tex] use = "mine"`); on a Mac it also installs Ghostscript and poppler.
_TEX_REMEDIES = (TEX, "tlmgr install biber", "tlmgr install make4ht tex4ht", *((POPPLER, GHOSTSCRIPT) if _MAC else ()))
#: Seconds biber is given on top of `PROBE_TIMEOUT`: TeX Live's biber unpacks itself on its first run, which takes longer.
BIBER_GRACE = 30.0
VENDOR = "cd viewer && npm run build && cd ../loom && uv run python scripts/vendor_viewer.py ../viewer/build"


@dataclass
class Item:
    """One line of the report; `extra` holds the fields some items add to the JSON (a tool's `path`, the bundle's `source` and `interface`)."""

    name: str
    status: str
    severity: str
    detail: str = ""
    remedy: str = ""
    extra: dict[str, Any] = field(default_factory=dict)
    #: An item that reports rather than checks, whose detail is printed even when it is ok.
    shown: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "severity": self.severity,
            "detail": self.detail,
            "remedy": self.remedy,
            **self.extra,
        }


@dataclass(frozen=True)
class Tool:
    name: str
    severity: str
    flag: tuple[str, ...]
    remedy: str
    #: what loom uses it for, said when it is missing
    use: str


TOOLS = [
    Tool("latexmk", REQUIRED, ("-v",), TEX, "every compile runs it"),
    Tool("pdflatex", REQUIRED, ("--version",), TEX, "the default engine"),
    Tool("dvisvgm", REQUIRED, ("--version",), TEX, "the pictures TeX draws in a document's HTML, and PDF figures"),
    Tool(
        "latex",
        OPTIONAL,
        ("--version",),
        TEX,
        "the DVI TeX4ht makes a document's HTML from; without it documents show as their source",
    ),
    Tool("xelatex", OPTIONAL, ("--version",), TEX, "an engine a quilt may name"),
    Tool("lualatex", OPTIONAL, ("--version",), TEX, "an engine a quilt may name"),
    Tool("bibtex", OPTIONAL, ("--version",), TEX, "bibliographies made with \\bibliography"),
    Tool("biber", OPTIONAL, ("--version",), "tlmgr install biber", "bibliographies made with biblatex"),
    Tool("kpsewhich", OPTIONAL, ("--version",), TEX, "finding the TeX tree's files a source reads"),
    Tool(
        "make4ht",
        OPTIONAL,
        ("--version",),
        "tlmgr install make4ht tex4ht",
        "a document's HTML as TeX makes it, and text no compile makes; without it they show as their source",
    ),
    Tool("extractbb", OPTIONAL, ("--version",), TEX, "the size of a PDF or image figure in a document's HTML"),
    Tool("pdftotext", OPTIONAL, ("-v",), POPPLER, "works' page text and geometry, and the identity test"),
    Tool("pdfinfo", OPTIONAL, ("-v",), POPPLER, "works' page rotation"),
    Tool(
        "gs",
        OPTIONAL,
        ("--version",),
        GHOSTSCRIPT,
        "EPS figures, the arrows of diagrams drawn in PostScript, and pictures TeX4ht makes as PNG",
    ),
    Tool(
        "pdftocairo",
        OPTIONAL,
        ("-v",),
        POPPLER,
        "PDF figures, where dvisvgm --pdf stands in less faithfully, and the crop of a page an agent is given beside a mark on a PDF",
    ),
    Tool(
        "git",
        OPTIONAL,
        ("--version",),
        GIT,
        "loom init --git and the Overleaf mirror",
    ),
]


@dataclass
class Report:
    python: str
    loom: str
    quilt: Path | None = None
    items: list[Item] = field(default_factory=list)
    strict: bool = False

    @property
    def failing(self) -> list[str]:
        return [i.name for i in self.items if i.status == FAIL]

    @property
    def warnings(self) -> list[str]:
        return [i.name for i in self.items if i.status == WARN]

    @property
    def exit_code(self) -> int:
        """2 when an item fails, or under --strict when one warns; else 0. Doctor never exits 1, which in loom means the quilt's content."""
        return 2 if self.failing or (self.strict and self.warnings) else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "python": self.python,
            "loom": self.loom,
            "quilt": str(self.quilt) if self.quilt else None,
            "ok": self.exit_code == 0,
            "failing": self.failing,
            "warnings": self.warnings,
            "items": [i.to_dict() for i in self.items],
        }

    def summary(self) -> str:
        warned = self.warnings
        count = f"{len(warned)} warning{'s' if len(warned) != 1 else ''}"
        if self.failing:
            tail = f"; warnings: {', '.join(warned)}" if self.strict and warned else f" ({count})" if warned else ""
            return f"failing: {', '.join(self.failing)}{tail}"
        if warned:
            return f"warnings: {', '.join(warned)}" if self.strict else f"ok ({count})"
        return "ok"

    def report(self) -> OutReport:
        """The report `loom doctor` prints: the summary as its verdict, an item per check, machine first, with a `fix:` line under each item that is not ok, then the directories the tools were found in."""
        from loom.cli.report import Group, Report, counted
        from loom.cli.report import Item as Line

        width = max(len(i.name) for i in self.items)
        groups = []
        for section, items in (
            ("machine", [i for i in self.items if i.severity != QUILT]),
            (f"quilt {self.quilt.name}" if self.quilt else "quilt", [i for i in self.items if i.severity == QUILT]),
        ):
            if not items:
                continue
            # what is fine is counted and named on one line; what is not is listed, each remedy said once under the first item it fixes (T2)
            fine = [i for i in items if i.status == OK and not i.shown]
            lines = [Line(f"ok    {counted(len(fine), 'check')}: {', '.join(i.name for i in fine)}")] if fine else []
            rest = [i for i in items if i.status != OK or i.shown]
            for n, i in enumerate(rest):
                earlier = any(j.remedy == i.remedy for j in rest[:n])
                fixes = [_home(i.remedy)] if i.remedy and not earlier else []
                said = f"{i.status:<4}  {i.name:<{width}}  {_home(i.detail)}".rstrip()
                lines.append(Line(said, fixes=fixes, data=i.to_dict()))
            groups.append(Group(section, lines, limit=None, problem=True))
        # a path runs longer than a line, so each directory is said once, with what was found in it, rather than beside every tool
        found: dict[str, list[str]] = {}
        for i in self.items:
            path = i.extra.get("path")
            if path and i.severity != QUILT:
                p = Path(str(path))
                found.setdefault(_home(str(p if p.is_dir() else p.parent) + "/").rstrip("/"), []).append(i.name)
        groups.append(Group("found in", [Line(", ".join(names), key=d) for d, names in found.items()], limit=None))
        data = self.to_dict()
        del data["ok"]
        return Report(
            self.summary(),
            ok=self.exit_code == 0,
            exit=self.exit_code,
            lines=[f"loom {self.loom}, python {self.python}"],
            groups=groups,
            data=data,
        )


def _bundle_words(source: str, version: str) -> str:
    """Which viewer `loom serve` serves, in words: where it comes from, and the commit it was built from and when."""
    from loom.viewer_bundle import STAMP

    whose = _whose(source)
    m = STAMP.fullmatch(version.strip())
    when = re.search(r"vendored (\d{4}-\d{2}-\d{2})", version)
    if m is None:
        return f"{whose}, {version}" if version else whose
    return f"{whose}, built from commit {m.group(1)}" + (f" on {when.group(1)}" if when else "")


def _whose(source: str) -> str:
    """Where the viewer `loom serve` serves comes from, as a reader says it."""
    return "the viewer loom ships" if source == "vendored" else f"the viewer {source} names"


def _home(text: str) -> str:
    """`text` with each path under the home directory written `~/…` and under the temporary directory `$TMPDIR/…`, as a person types them; the JSON keeps them whole."""
    for base, said in ((Path.home(), "~"), (Path(tempfile.gettempdir()), "$TMPDIR")):
        for form in dict.fromkeys((str(base), os.path.realpath(base))):
            text = text.replace(form.rstrip("/") + "/", said + "/")
    return text


@dataclass(frozen=True)
class Answer:
    """What a probed command said: its exit code (None when it could not start or hung) and its output."""

    code: int | None
    out: str = ""
    err: str = ""
    hung: bool = False

    @property
    def first_line(self) -> str:
        lines = (self.out.strip() or self.err.strip()).splitlines()
        return lines[0].strip()[:60] if lines else ""


class Probe:
    """One command started now and read later, in a process group of its own so a hung one can be killed whole.

    Every probe is started from one thread before any is read: forking while another thread runs can leave a child stuck before its exec on macOS, holding a copy of every pipe open at the time, so that each probe then looks hung.
    """

    def __init__(self, argv: list[str]) -> None:
        from loom.machine import unpacked

        self.error = ""
        try:
            self.proc: subprocess.Popen[str] | None = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                start_new_session=True,
                # `biber` unpacks into the machine's one folder for it, as in every TeX run loom starts (`tex.runner.tex_env`)
                env={**os.environ, "PAR_GLOBAL_TMPDIR": str(unpacked())},
            )
        except OSError as exc:
            self.proc, self.error = None, str(exc)

    def answer(self, deadline: float) -> Answer:
        """Its output, waiting no later than `deadline` (a `time.monotonic` value); past it the process group is killed and the answer is `hung`."""
        if self.proc is None:
            return Answer(None, err=self.error)
        left = deadline - time.monotonic()
        # one that finished while an earlier probe used up the time is read, not reported hung
        timeout = left if left > 0 or self.proc.poll() is None else 1.0
        try:
            out, err = self.proc.communicate(timeout=max(0.0, timeout))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except OSError:
                self.proc.kill()
            try:
                self.proc.communicate(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            return Answer(None, hung=True)
        return Answer(self.proc.returncode, out, err)


def _tiny_pdf() -> bytes:
    """A valid one-page PDF, 72 points square, for the `-bbox-layout` probe."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 72 72] >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def _bbox(got: Answer, item: Item) -> None:
    """pdftotext must write `-bbox-layout` word boxes, which anchoring on a work's page and the viewer's highlights need; xpdf's has no such flag."""
    if got.hung:
        item.status, item.detail = FAIL, f"{item.detail}: hung writing word boxes (-bbox-layout)"
    elif got.code != 0 or "<page " not in got.out:
        item.status, item.detail = (
            FAIL,
            f"{item.detail}: no -bbox-layout, so works' pages have no geometry (xpdf's?)",
        )
    else:
        return
    from loom.tex import private

    item.remedy = (
        REPAIR
        if _MAC and private.active(year=False).kind != private.MINE
        else f"{POPPLER}, and put poppler's pdftotext first on PATH"
    )


_BIBER = re.compile(r"biber version:?\s*(\d+)\.(\d+)", re.I)
_BIBLATEX = re.compile(r"\\def\\abx@version\{(\d+)\.(\d+)")


def biber_pairs(biber: tuple[int, int], biblatex: tuple[int, int]) -> bool | None:
    """Whether a biber reads what a biblatex writes: since biber 2.15 and biblatex 3.15 each release pairs with the other's of the same minor number, as the two are released together.

    None when both are older than that, since those pairs followed no rule a comparison could apply, or when either major number is not the one that rule covers.
    """
    if biber[0] != 2 or biblatex[0] != 3:
        return None
    if biber[1] < 15 and biblatex[1] < 15:
        return None
    return biber[1] == biblatex[1]


def _biber(found: Answer, item: Item) -> None:
    """Compare biber with the biblatex kpsewhich found; a mismatch is the classic failure of a hand-updated TeX tree."""
    m = _BIBER.search(item.detail)
    sty = Path(found.out.strip().splitlines()[0]) if found.code == 0 and found.out.strip() else None
    try:
        text = sty.read_text(encoding="utf-8", errors="replace") if sty else ""
    except OSError:
        text = ""
    b = _BIBLATEX.search(text)
    if m is None or b is None:
        return
    mine, theirs = (int(m.group(1)), int(m.group(2))), (int(b.group(1)), int(b.group(2)))
    pairs = biber_pairs(mine, theirs)
    said = f"biber {mine[0]}.{mine[1]}, biblatex {theirs[0]}.{theirs[1]}"
    if pairs is None:
        item.detail = f"{said} (pairs this old are not compared)"
    elif pairs:
        item.detail = said
    else:
        item.status, item.detail = (
            WARN,
            f"{said}: by their version numbers they do not pair, so biblatex documents are unlikely to compile",
        )
        item.remedy = "tlmgr update biber biblatex, so both come from one TeX Live; compiling a master that uses biblatex settles it"


def check_tex() -> Item:
    """Which TeX loom's runs use, its year and where it is: loom's own, the person's, or none."""
    from loom.tex import private

    tex = private.active()
    extra: dict[str, Any] = {"path": str(tex.bin) if tex.bin else None, "kind": tex.kind, "year": tex.year}
    if tex.kind == private.LOOM:
        if not private.works():
            return Item("tex", FAIL, REQUIRED, f"{tex.label} does not answer", REPAIR, extra)
        if tex.year != private.YEAR:
            return Item("tex", WARN, REQUIRED, f"{tex.label}; this loom expects TeX Live {private.YEAR}", REPAIR, extra)
        return Item("tex", OK, REQUIRED, tex.label, "", extra)
    if tex.kind == private.MINE:
        why = (
            '; loom\'s own is installed, and [tex] use = "mine" keeps yours'
            if private.loom_bin() is not None
            else "; packages it lacks are yours to install"
        )
        return Item("tex", OK, REQUIRED, f"{tex.label}{why}", "", extra)
    return Item("tex", FAIL, REQUIRED, "none: documents show as their source and no PDF is made", REPAIR, extra)


def check_fence() -> Item:
    """Whether a TeX compile loom starts is fenced on this machine (`loom.fence.state`), in the person's words, with the way to turn it off or why it is not up: said in every state, and a warning only where loom's own test found the fence leaking."""
    from loom import fence

    why = fence.state()
    if why is None:
        return Item(
            "tex fence",
            OK,
            OPTIONAL,
            f"on: a file loom compiles reads only its own folder, the TeX in use with your own TeX files, and the system's programs, and reaches no network; {fence.OFF}=off turns it off for a paper it breaks",
            "",
            {"state": None},
            shown=True,
        )
    said, remedy = {
        "off": (
            f"off, as {fence.OFF}=off asks: a file loom compiles can read any file you can",
            f"unset {fence.OFF} to fence compiles again",
        ),
        "absent": (
            "not on this system: a file loom compiles can read any file you can",
            "none yet: the fence is macOS's",
        ),
        "nested": (
            "not here: loom runs inside another sandbox, which holds no second, so a file loom compiles reads what that sandbox allows",
            "run loom outside an agent's sandboxed shell to fence its compiles",
        ),
        "leaks": (
            "not holding: a file read past it in loom's own test, so loom compiles unfenced and a file it compiles can read any file you can",
            "tell loom's maintainers; nothing is fenced until it holds",
        ),
    }[why]
    # a fence off, absent or nested breaks nothing, so it is said, not warned of; one that leaks is loom's own failing
    if why == "leaks":
        return Item("tex fence", WARN, OPTIONAL, said, remedy, {"state": why})
    return Item("tex fence", OK, OPTIONAL, f"{said} ({remedy})", "", {"state": why}, shown=True)


def check_tools() -> list[Item]:
    """Find every tool, ask its version, and probe what loom needs of it beyond presence: pdftotext's word boxes, and whether biber pairs with biblatex.

    Every probe starts before any is read and all share one deadline, so doctor takes as long as its slowest tool, and at most PROBE_TIMEOUT.
    """
    from loom import gitprog
    from loom.tex import private

    tex = private.active()
    paths = {t.name: shutil.which(t.name) for t in TOOLS}
    stub = paths["git"] is not None and gitprog.apple_stub(paths["git"])
    with tempfile.TemporaryDirectory(prefix="loom-doctor-") as tmp:
        # running Apple's stub opens a dialog offering to install the Command Line Tools, so it is not run
        probes = {t.name: Probe([p, *t.flag]) for t in TOOLS if (p := paths[t.name]) and not (t.name == "git" and stub)}
        if paths["pdftotext"]:
            pdf = Path(tmp) / "page.pdf"
            pdf.write_bytes(_tiny_pdf())
            probes["-bbox-layout"] = Probe(
                [paths["pdftotext"], "-q", "-bbox-layout", "-f", "1", "-l", "1", str(pdf), "-"]
            )
        if paths["biber"] and paths["kpsewhich"]:
            probes["biblatex.sty"] = Probe([paths["kpsewhich"], "biblatex.sty"])
        deadline = time.monotonic() + PROBE_TIMEOUT
        answers = {
            name: probe.answer(deadline + (BIBER_GRACE if name == "biber" else 0.0)) for name, probe in probes.items()
        }
    items = []
    for tool in TOOLS:
        path = paths[tool.name]
        remedy = REPAIR if tool.remedy in _TEX_REMEDIES and tex.kind != private.MINE else tool.remedy
        if path is None and tool.name == "biber" and tex.kind == private.LOOM:
            items.append(
                Item(
                    tool.name, OK, tool.severity, "fetched the first time a document uses biblatex", "", {"path": None}
                )
            )
            continue
        if path is None:
            status = FAIL if tool.severity == REQUIRED else WARN
            items.append(Item(tool.name, status, tool.severity, f"not found: {tool.use}", remedy, {"path": None}))
            continue
        if tool.name == "git" and stub:
            items.append(
                Item(
                    tool.name,
                    WARN,
                    tool.severity,
                    "only Apple's installer stub: running it asks to install the Command Line Tools",
                    "xcode-select --install, or leave it: loom works without git but for loom init --git and the Overleaf mirror",
                    {"path": path},
                )
            )
            continue
        got = answers[tool.name]
        item = Item(tool.name, OK, tool.severity, got.first_line or "found", "", {"path": path})
        if got.hung:
            item.status, item.detail = FAIL, f"hung: {' '.join(tool.flag)} did not answer in {PROBE_TIMEOUT:g} s"
            item.remedy = f"reinstall it ({remedy}), or take {path} off PATH"
        elif got.code is None:
            item.status, item.detail, item.remedy = FAIL, f"cannot run: {got.err}", remedy
        elif tool.name == "pdftotext":
            _bbox(answers["-bbox-layout"], item)
        elif tool.name == "biber" and "biblatex.sty" in answers:
            _biber(answers["biblatex.sty"], item)
        items.append(item)
    return items


def check_author(quilt: Any) -> Item:
    """The name `accept` and `annotate` record: `--as`, else the user config, else git."""
    from loom.scan.quilt import NoAuthorError, resolve_author, user_config_path

    try:
        name, source = resolve_author(None, cwd=quilt.root if quilt else None)
    except NoAuthorError:
        remedy = f'add name = "Your Name" under [author] in {user_config_path()}, or git config --global user.name "Your Name"'
        return Item("author", WARN, OPTIONAL, "none: accept and annotate refuse without one", remedy)
    note = (
        "; the author config.toml names is ignored, since the reviewer is whoever runs loom: set yours in the viewer's Settings"
        if quilt is not None and quilt.config.author_declared
        else ""
    )
    return Item("author", OK, OPTIONAL, f"{name} (from {source}){note}")


def check_bundle() -> Item:
    """Which viewer bundle `loom serve` would serve, and whether it reads this loom's manifests."""
    from loom.viewer_bundle import (
        BundleEnvError,
        checkout_of,
        env_problem,
        find_bundle,
        parse_stamp,
        staleness,
        vendored_path,
    )

    try:
        info = find_bundle()
    except BundleEnvError:
        info = None
    checkout = checkout_of(info.path if info else vendored_path()) if not info or info.source == "vendored" else None
    stamp = parse_stamp(info.version) if info else None
    extra: dict[str, Any] = {
        "source": info.source if info else None,
        "path": str(info.path) if info else None,
    }
    item = Item("viewer bundle", OK, REQUIRED, _bundle_words(info.source, info.version) if info else "", "", extra)
    bad_env = env_problem()
    if bad_env:
        item.status = FAIL
        item.detail = f"{bad_env}; loom serve refuses"
        item.remedy = "point LOOM_VIEWER_BUNDLE at a built viewer (the directory holding index.html), or unset it"
    elif info is None:
        item.status, item.detail = FAIL, "not found: loom serve refuses"
        item.remedy = (
            VENDOR if checkout else "reinstall loom, whose package carries the viewer, or set LOOM_VIEWER_BUNDLE"
        )
    elif stamp is None:
        item.status = WARN
        item.detail += ": its stamp names no commit, so whether it is current cannot be told"
        item.remedy = "use a bundle loom/scripts/vendor_viewer.py stamped"
    elif checkout is not None:
        why = staleness(checkout, stamp, PROBE_TIMEOUT)
        if why:
            item.status, item.detail = WARN, f"{_whose('vendored')}, {'; '.join(why)}"
            # vendor_viewer.py refuses a viewer with uncommitted changes
            item.remedy = ("commit the viewer's changes, then " if stamp.endswith("-dirty") else "") + VENDOR
    return item


def check_engine(quilt: Any) -> Item:
    """The quilt's `[quilt] engine` is one loom knows and is installed; `% !TEX program` in a master may still name another."""
    from loom.tex.runner import ENGINE_FLAGS

    engine = quilt.config.engine.strip().lower()
    if engine not in ENGINE_FLAGS:
        return Item(
            "engine",
            WARN,
            QUILT,
            f"engine = {quilt.config.engine!r} is not one of {', '.join(ENGINE_FLAGS)}; loom compiles with pdflatex",
            "set engine under [quilt] in config.toml",
        )
    path = shutil.which(engine)
    if path is None:
        from loom.tex import private

        remedy = TEX if private.active().kind == private.MINE else REPAIR
        return Item("engine", FAIL, QUILT, f"{engine}: not found, so every compile here fails", remedy, {"path": None})
    return Item("engine", OK, QUILT, engine, "", {"path": path})


def check_permissions(root: Path) -> Item:
    """The permission files of the apps the quilt is set up for (`.claude/settings.json`, `.codex/rules/loom.rules`) byte for byte what this loom's table renders into the quilt (`vendor_files`, the person's own settings in Claude Code's kept), in the variant the quilt's files say. One loom leaves alone warns at every run, saying why."""
    from loom.ai.clients import PROJECT, chosen
    from loom.ai.layout import (
        CLAUDE_SETTINGS,
        SHELL,
        blocker,
        quilt_config,
        read_plain,
        settings_left,
        variant,
        vendor_files,
    )

    shell = variant(root) == SHELL
    config = quilt_config(root)
    apps = chosen(root, None)
    shipped = vendor_files(config, shell=shell, apps=apps, root=root)
    wanted = tuple(shipped)
    layer = (root / AI).is_dir()
    # a file of the person's that loom leaves alone holds none of its rules, which is said at every run
    left = settings_left(root, config) if CLAUDE_SETTINGS in vendor_files(config, shell=shell, apps=apps) else ""
    # the other permission files loom leaves alone, a link among them, said at every run with why
    held = {rel: why for rel in wanted if rel != CLAUDE_SETTINGS and (why := blocker(root, rel))} if layer else {}
    present = [rel for rel in wanted if rel not in held and (root / rel).is_file()]
    if not layer and not present and not left:
        return Item("permissions", OK, QUILT, f"no {AI}/ (loom ai init writes it and them)")
    stale = [rel for rel in present if read_plain(root, rel) != shipped[rel]]
    absent = [rel for rel in wanted if rel not in present and rel not in held] if layer else []
    if not stale and not absent and not left and not held:
        how = "agents here run loom in a shell" if shell else "agents here attach over MCP"
        return Item(
            "permissions", OK, QUILT, f"{', '.join(present)}: {how}", extra={"variant": SHELL if shell else "mcp"}
        )
    said = [f"{rel} missing: an agent here runs without loom's table" for rel in absent]
    said += [f"{rel}: not what this loom lets agents run" for rel in stale]
    if left:
        said.append(
            f"{CLAUDE_SETTINGS}: none of loom's rules is in force for Claude Code, since {left}; make it a JSON object in a file of the quilt's own, and loom upgrade writes them in"
        )
    label = {c.permissions: c.label for c in PROJECT if c.permissions}
    said += [
        f"{rel}: loom leaves it alone, since {why}, so what {label.get(rel, 'the app')} reads there is not loom's table; make it a file of the quilt's own, and loom upgrade writes it"
        for rel, why in held.items()
    ]
    # beside an .loom/agents/instructions/, `loom upgrade` writes both; without one, `loom ai init` does
    return Item("permissions", WARN, QUILT, "; ".join(said), "loom upgrade" if layer else "loom ai init")


def check_mcp(root: Path) -> list[Item]:
    """The MCP client files (`ai.clients`) and the SDK `loom mcp` needs, where the quilt's agents attach over MCP.

    A client file git tracks fails: it names this machine's loom and quilt, and a clone would start them on another's.
    """
    from loom.ai.clients import PROJECT, write_clients
    from loom.ai.layout import SHELL, variant
    from loom.mcp.sdk import has_sdk, reinstall_hint

    if not (root / AI).is_dir():
        return [Item("mcp", OK, QUILT, f"no {AI}/ (loom ai init writes the client files)")]
    if variant(root) == SHELL:
        return [Item("mcp", OK, QUILT, "none: agents here run loom in a shell")]
    rep = write_clients(root, write=False)
    key = {c.file: c.key for c in PROJECT}
    items = []
    if rep.tracked:
        items.append(
            Item(
                "mcp",
                FAIL,
                QUILT,
                f"tracked by git: {', '.join(rep.tracked)}, which name this machine's loom and quilt",
                f"git rm --cached {' '.join(rep.tracked)}",
            )
        )
    missing = [rel for rel in rep.written if not (root / rel).exists()]
    stale = [rel for rel in rep.written if rel not in missing]
    said = [f"missing: {', '.join(missing)}"] * bool(missing)
    said += [f"naming another loom or path: {', '.join(stale)}"] * bool(stale)
    if said:
        items.append(
            Item("mcp", WARN, QUILT, "; ".join(said) + "; an agent's app starts loom from these", "loom ai init")
        )
    if rep.foreign:
        items.append(
            Item(
                "mcp",
                WARN,
                QUILT,
                f"settings of yours, without the loom server: {', '.join(rep.foreign)}",
                "; ".join(f"add what loom ai init --client {key[rel]} prints" for rel in rep.foreign),
            )
        )
    if not has_sdk():
        items.append(
            Item("mcp", WARN, QUILT, "the MCP SDK is not installed, so loom mcp cannot start", reinstall_hint())
        )
    return items or [Item("mcp", OK, QUILT, ", ".join(rep.current))]


def check_ai_files(root: Path) -> Item:
    """The mode files and the orientation against what `loom upgrade` would write, by its own dry run; the permission files are the item above, and the skills, made whole from the modes at every upgrade, are no file of the author's to fall behind. A `.loom/agents/instructions` that is not a directory of the quilt's own (`blocker`) warns, since loom writes nothing there."""
    from loom.ai.layout import CLAUDE_SETTINGS, CODEX_RULES, blocker, read_versions, sha, tracked_docs, upgrade_layer
    from loom.ai.skills import is_skill

    why = blocker(root, AI, folder=True)
    if why:
        return Item(
            "ai files",
            WARN,
            QUILT,
            f"{why}, so loom writes nothing of the agent layer there",
            f"make {AI} a directory of the quilt's own",
        )
    if not (root / AI).is_dir():
        return Item("ai files", OK, QUILT, f"no {AI}/ (loom ai init writes it)")
    rep = upgrade_layer(root, write=False)
    stale = [rel for rel in rep.written if rel not in (CLAUDE_SETTINGS, CODEX_RULES) and not is_skill(rel)]
    shipped, recorded = tracked_docs(), read_versions(root)

    def unseen(rel: str) -> bool:
        """An edited file whose record predates what ships now, with that version not yet beside it; once `loom upgrade` has put it there, merging is the author's."""
        new = root / f"{rel}.new"
        if recorded.get(Path(rel).name) == sha(shipped[rel]):
            return False
        return not new.is_file() or new.read_text(encoding="utf-8") != shipped[rel]

    unseen_files = [rel for rel in rep.kept if unseen(rel)]
    if not stale and not unseen_files:
        kept = f", {len(rep.kept)} edited" if rep.kept else ""
        return Item("ai files", OK, QUILT, f"current{kept}")
    said = []
    if stale:
        said.append(f"older than this loom: {', '.join(stale)}")
    if unseen_files:
        said.append(f"edited, with a newer version shipped: {', '.join(unseen_files)}")
    return Item(
        "ai files", WARN, QUILT, "; ".join(said), "loom upgrade (an edited file gets the new version beside it)"
    )


def check_macro_blocks(quilt: Any) -> Item:
    """Every live document that carries loom's macro block carries this loom's, and one that loads loom.sty finds it (`loom:macros-missing`). Each gets the patch that puts this loom's block in place, in the JSON, since loom never edits a document (P7). A `loom.sty` a person keeps is theirs, and not checked."""
    from loom.reshape.ids import unified_diff
    from loom.reshape.linearize import loom_macro_block, to_canon
    from loom.scan.preamble import loom_sty_missing
    from loom.scan.scan import scan
    from loom.scan.source import MACRO_BLOCK

    current = loom_macro_block()
    patches: dict[str, str] = {}
    unfound: list[str] = []
    result = scan(quilt)
    for m in result.masters:
        text = (quilt.root / m).read_text(encoding="utf-8", errors="replace")
        block = MACRO_BLOCK.search(text)
        if block and block.group(0).rstrip("\n") != current.rstrip("\n"):
            patches[m] = unified_diff(text, text[: block.start()] + current + text[block.end() :], m)
        elif m in result.closures and loom_sty_missing(result.closures[m], quilt.root, result.base_of(m)):
            unfound.append(m)
            if to_canon(text) != text:
                patches[m] = unified_diff(text, to_canon(text), m)
    if not patches and not unfound:
        return Item("macro block", OK, QUILT, "current")
    if unfound:
        return Item(
            "macro block",
            WARN,
            QUILT,
            f"{', '.join(sorted(unfound))} {'loads' if len(unfound) == 1 else 'load'} loom, but no loom.sty sits beside {'it' if len(unfound) == 1 else 'them'} or on the TeX path",
            "keep loom.sty beside the document, or apply the patch `loom doctor --json` gives as this item's patch: loom never edits a document",
            extra={"patch": "".join(patches[m] for m in sorted(patches))},
        )
    return Item(
        "macro block",
        WARN,
        QUILT,
        f"older than this loom's in {', '.join(sorted(patches))}",
        "apply the patch `loom doctor --json` gives as this item's patch: loom never edits a document",
        extra={"patch": "".join(patches[m] for m in sorted(patches))},
    )


def check_gitignore(root: Path) -> Item:
    """The ignore lines loom relies on (`loom.gitignore`): `.loom/.gitignore` as this loom writes it, and the client lines in the root `.gitignore` where the agent layer is; `loom upgrade` writes both."""
    from loom.gitignore import loom_ignore_current
    from loom.gitignore import missing as lacking

    if not loom_ignore_current(root):
        return Item(".gitignore", WARN, QUILT, f"{LOOM_GITIGNORE} is missing or not this loom's", "loom upgrade")
    missing = lacking(root) if (root / AI).is_dir() else []
    if not missing:
        return Item(".gitignore", OK, QUILT, "has loom's lines")
    return Item(".gitignore", WARN, QUILT, f"lacks {', '.join(missing)}", "loom upgrade")


def check_config(quilt: Any) -> Item:
    """What `loom lint` reports of `config.toml` itself: unknown tables and keys, values out of range."""
    w = quilt.config.warnings
    if not w:
        return Item("config", OK, QUILT, "config.toml read cleanly")
    more = f" (and {len(w) - 1} more)" if len(w) > 1 else ""
    return Item("config", WARN, QUILT, f"{w[0]}{more}", "loom lint")


def check_writes(quilt: Any) -> Item:
    """The writes loom could neither finish nor undo (`writes.left_acts`), each with the id `loom doctor --settle` takes: what the person settles as it stands, in the viewer or here (`settling`)."""
    from loom.writes import left_acts

    acts = left_acts(quilt.root, quilt.history_dir)
    if not acts:
        return Item("writes", OK, QUILT, "nothing loom wrote is left unsettled")
    said = "; ".join(
        f"{act_id}: {kind}{' on ' + ', '.join(files) if files else ''}" for act_id, kind, files, _, _ in acts
    )
    return Item(
        "writes",
        WARN,
        QUILT,
        f"loom could neither finish nor undo {len(acts)} write{'s' if len(acts) > 1 else ''}: {said}",
        "settle each as it stands in the viewer's Problems, or with loom doctor --settle ID in a terminal of your own",
        extra={
            "left": [{"act": act_id, "kind": kind, "files": files, "why": why} for act_id, kind, files, why, _ in acts]
        },
    )


def check_unpacked() -> Item:
    """What the machine's one folder for a tool TeX unpacks holds (`machine.unpacked`): its size and how many copies, one for each `biber` that ever ran here (a TeX Live year, loom's own TeX beside the person's). Nothing prunes it."""
    from loom.lifetimes import readable, size_of
    from loom.machine import UNPACKED, data_dir

    where = data_dir() / UNPACKED
    copies = sorted(where.glob("par-*/cache-*")) if where.is_dir() else []
    if not copies:
        return Item(
            "unpacked", OK, OPTIONAL, "nothing unpacked yet", "", {"path": None, "copies": 0, "bytes": 0}, shown=True
        )
    size = size_of(where)
    said = f"{len(copies)} unpacked {'copy' if len(copies) == 1 else 'copies'} of biber, {readable(size)}, in {where}"
    return Item("unpacked", OK, OPTIONAL, said, "", {"copies": len(copies), "bytes": size}, shown=True)


def check_app() -> Item:
    """Whether loom's home page runs on this machine (`loom app`), and at what address."""
    from loom.app.registry import home_url

    url = home_url()
    return Item(
        "app", OK, OPTIONAL, f"the home page at {url}" if url else "not running", "", {"url": url or None}, shown=True
    )


def check_server(root: Path) -> Item:
    """Whether the quilt's server runs, and at what address; else the port it keeps on the home's list, if it is there."""
    from loom.app.registry import port_of
    from loom.render.serve import open_url

    url = open_url(root)
    if url:
        return Item("server", OK, QUILT, f"running at {url}", "", {"url": url}, shown=True)
    port = port_of(root)
    said = f"not running; it keeps http://127.0.0.1:{port}/" if port else "not running"
    return Item("server", OK, QUILT, said, "", {"url": None, "port": port}, shown=True)


def check_lean(root: Path) -> Item:
    """Lean for this quilt on this machine: whether formalization is on here, and once it is, whether the project is made, its toolchain installed and Mathlib fetched, whether loom can check Lean fenced here, and when loom last checked it, with how many results' records no longer stand.

    A warning where on and something the check needs is missing, or the last check was refused; Lean's own errors are the Lean's, said and not warned of. Off, it says only whether the quilt carries a project, which loom runs nothing of here.
    """
    from loom import fence
    from loom.evidence.log import replay
    from loom.evidence.status import files_unchanged
    from loom.formal import install, switch
    from loom.paths import LAKE_PACKAGES

    proj = install.project(root)
    made = (proj / "lakefile.toml").is_file()
    on = switch.is_on(root)
    extra: dict[str, Any] = {"on": on, "project": install.LEAN if made else None}
    if not on:
        if not made:
            return Item("lean", OK, QUILT, "formalization is off here", "", extra)
        said = f"formalization is off here; the quilt has a Lean project in {install.LEAN}/, of which loom runs nothing until you turn it on"
        return Item("lean", OK, QUILT, said, "", extra, shown=True)
    if not made:
        return Item("lean", WARN, QUILT, f"on, but the quilt has no Lean project in {install.LEAN}/", "loom formal on makes it", extra)  # fmt: skip
    try:
        toolchain = install.toolchain_of(proj)
    except install.Refused as exc:
        return Item("lean", WARN, QUILT, f"on, but {exc}", "fix the project's lean-toolchain", extra)
    extra["toolchain"] = toolchain
    try:
        manifest = json.loads((proj / "lake-manifest.json").read_text(encoding="utf-8"))
        packages = [p for p in manifest.get("packages", []) if isinstance(p, dict)]
    except (OSError, ValueError, AttributeError):
        packages = []
    extra["mathlib"] = next((str(p.get("inputRev")) for p in packages if p.get("name") == "mathlib"), None)
    missing = [str(p.get("name")) for p in packages if not (proj / LAKE_PACKAGES / str(p.get("name"))).is_dir()]
    if not (install.toolchain_folder(toolchain) / "bin" / "lake").is_file():
        return Item("lean", WARN, QUILT, f"on, but the toolchain {toolchain} is not installed here", "loom formal on installs it", extra)  # fmt: skip
    if missing:
        return Item("lean", WARN, QUILT, f"on, but {', '.join(missing)} is not fetched into the project", "loom formal on fetches it", extra)  # fmt: skip
    why = fence.lean_state()
    extra["fence"] = why
    if why is not None:
        return Item("lean", WARN, QUILT, f"on, but loom cannot check Lean here: the fence is not up ({why})", "run loom outside an agent's sandboxed shell", extra)  # fmt: skip
    have = f"on: the project in {install.LEAN}/, {toolchain}" + (f", Mathlib {extra['mathlib']}" if extra["mathlib"] else "")
    last = switch.last_check(root)
    extra["last"] = last
    if last is None:
        return Item("lean", OK, QUILT, f"{have}; not checked yet on this machine", "", extra, shown=True)
    when = last["at"].replace("T", " ").removesuffix("Z") + " UTC"
    if "refused" in last:
        return Item("lean", WARN, QUILT, f"{have}; the last check, {when}, was refused: {last['refused']}", "fix what it says, then loom formal check", extra)  # fmt: skip
    came = f"{last.get('written', 0)} recorded, {last.get('unchanged', 0)} as before"
    if last.get("errors"):
        came += f", {last['errors']} of Lean's errors"
    latest: dict[tuple[str, str], Any] = {}
    for r in replay(root).of_kind("lean"):
        if r.on is not None:
            latest[r.on.key] = r
    stands = files_unchanged(root)
    gone = sum(1 for r in latest.values() if not stands(r))
    extra["stale"] = gone
    tail = f"; {gone} of {len(latest)} results' Lean changed since, which loom checks again while it serves" if gone else ""
    return Item("lean", OK, QUILT, f"{have}; last checked {when} ({came}){tail}", "", extra, shown=True)


def check_sizes(root: Path) -> list[Item]:
    """What `.loom/` holds, by kind, in the units a person reads, the scratch and the write journal on their own; and each session whose scratch is over `lifetimes.LARGE_SCRATCH`, with the day it is removed, which is the whole of that limit."""
    import datetime

    from loom.lifetimes import KEEP_DAYS, LARGE_SCRATCH, readable, scratches, size_of, sizes
    from loom.paths import AGENTS, JOURNAL, KINDS, LOCAL, SCRATCH

    held = sizes(root)
    said = []
    for kind in KINDS:
        line = f"{Path(kind).name} {readable(held[kind])}"
        if kind == AGENTS:
            line += f" (scratch {readable(held[SCRATCH])})"
        elif kind == LOCAL:
            line += f" (the write journal {readable(size_of(root / JOURNAL))})"
        said.append(line)
    items = [Item("size", OK, QUILT, ", ".join(said), "", {"sizes": held}, shown=True)]
    large = [s for s in scratches(root) if s.size > LARGE_SCRATCH]
    if large:

        def day(t: float) -> str:
            return datetime.datetime.fromtimestamp(t).date().isoformat()

        items.append(
            Item(
                "scratch",
                WARN,
                QUILT,
                "; ".join(f"{s.session} holds {readable(s.size)}, removed on {day(s.expires)}" for s in large),
                f"each scratch is removed {KEEP_DAYS} days after its session last wrote; delete what you no longer need from {SCRATCH}/ before then",
                {"large": [{"session": s.session, "bytes": s.size, "expires": day(s.expires)} for s in large]},
            )
        )
    return items


def run_doctor(quilt_path: str | None = None, strict: bool = False) -> Report:
    """Check the machine, and the quilt when there is one.

    Parameters
    ----------
    quilt_path : str, optional
        The quilt to check; default the one found from the current directory, and no quilt section when there is none.
    strict : bool, default False
        Warnings count against the exit code, as failures do (2).

    Returns
    -------
    Report
        Every item in order, machine first; `exit_code` is what `loom doctor` exits with.
    """
    from loom.scan.quilt import LayoutError, NoQuiltError, SettingError, find_quilt

    report = Report(sys.version.split()[0], __version__, strict=strict)
    quilt, bad_quilt, bad_layout, bad_setting = None, None, None, None
    try:
        quilt = find_quilt(Path(quilt_path).expanduser() if quilt_path else None)
    except LayoutError as exc:
        bad_layout = str(exc)
    except SettingError as exc:
        bad_setting = str(exc)
    except NoQuiltError as exc:
        # not being in a quilt is normal here; a quilt that cannot be read is not
        if quilt_path or not str(exc).startswith("not inside a quilt"):
            bad_quilt = str(exc)
    report.items += [check_tex(), check_fence(), *check_tools()]
    report.items += [check_author(quilt), check_bundle(), check_unpacked(), check_app()]
    if bad_quilt is not None:
        # a path with no quilt at it has no config.toml to fix
        none_there = bool(quilt_path) and bad_quilt.startswith("not inside a quilt")
        report.items.append(
            Item(
                "quilt",
                FAIL,
                QUILT,
                bad_quilt,
                f"loom init {quilt_path} makes a quilt there, or give --quilt a quilt's root"
                if none_there
                else "fix config.toml: every command but init and doctor refuses until it reads",
            )
        )
    if bad_layout is not None:
        report.items.append(
            Item(
                "format",
                FAIL,
                QUILT,
                bad_layout,
                "open it with the loom that made it; every command but doctor refuses",
            )
        )
    if bad_setting is not None:
        report.items.append(
            Item(
                "paths",
                FAIL,
                QUILT,
                bad_setting,
                "move what it names elsewhere and set it there; every command but doctor refuses until then",
            )
        )
    if quilt is not None:
        report.quilt = quilt.root
        root = quilt.root
        report.items += [
            check_engine(quilt),
            check_permissions(root),
            *check_mcp(root),
            check_ai_files(root),
            check_macro_blocks(quilt),
            check_gitignore(root),
            check_config(quilt),
            check_server(root),
            check_lean(root),
            check_writes(quilt),
            *check_sizes(root),
        ]
    return report
