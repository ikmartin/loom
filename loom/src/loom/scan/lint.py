"""Lint: the checks that turn scan facts into diagnostics.

Everything here reads the scan result and emits; nothing is stored. `[lint] disable` silences publisher codes only.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from loom.paths import COPIES
from loom.scan.diagnostics import LATEX, MODEL, can_disable
from loom.scan.directives import KNOWN_KEYS, REGION_KEYS
from loom.scan.edges import EdgeResult
from loom.scan.graph import Graph
from loom.scan.macros import LOOM_MACROS
from loom.scan.model import Diagnostic, Fix, Location
from loom.scan.nodes import Assembly, NodeRec
from loom.scan.preamble import LOOM_PACKAGE, loom_sty_missing
from loom.scan.scan import ScanResult

if TYPE_CHECKING:
    from loom.files import Drawn, Link

COMMON_THEOREM_ENVS = {
    "theorem",
    "thm",
    "lemma",
    "lem",
    "proposition",
    "prop",
    "corollary",
    "cor",
    "definition",
    "defn",
    "def",
    "remark",
    "rmk",
    "rem",
    "example",
    "exmp",
    "conjecture",
    "conj",
    "claim",
    "question",
    "notation",
    "construction",
    "convention",
    "assumption",
    "hypothesis",
    "axiom",
    "postulate",
    "fact",
    "observation",
    "setting",
    "condition",
    "problem",
    "exercise",
}


def _derived_in_person_document(result: ScanResult, edges: EdgeResult) -> list[Diagnostic]:
    """`loom:derived-id-in-person-document`: a person's document defines or cites an agent document's derived id.

    A person's document reaching a derived node defines it; a node that document reaches referring to one cites it. The derived node itself is reported once, not again for each reference it makes.
    """
    nodes = result.assembly.nodes

    def owned(key: str) -> bool:
        n = nodes.get(key)
        return n is not None and any(result.document_role(m) == "person" for m in n.reached_by)

    out: list[Diagnostic] = []
    for key, n in nodes.items():
        if n.derived_of and owned(key):
            out.append(
                Diagnostic(
                    "warning",
                    "loom:derived-id-in-person-document",
                    f"{key} is an agent document's id, and {', '.join(m for m in n.reached_by if result.document_role(m) == 'person')} defines it; a person's document names the plain id, {n.derived_of}",
                    [_loc(result, n)],
                    [key],
                )
            )
    for e in edges.edges:
        target = nodes.get(e.to)
        source = nodes.get(e.src)
        if target and target.derived_of and source and not source.derived_of and owned(e.src):
            out.append(
                Diagnostic(
                    "warning",
                    "loom:derived-id-in-person-document",
                    f"{e.src} cites {e.to}, an agent document's id; a person's document cites the plain id, {target.derived_of}",
                    [Location(e.file, e.line)],
                    [e.src],
                )
            )
    return out


def _agent_documents(result: ScanResult) -> list[Diagnostic]:
    """`loom:agent-document-unrecorded` and `loom:plain-id-in-agent-document`: every agent document was made by a step, and defines derived ids only.

    A document put in `.loom/agents/copies/` by hand has no record of where it came from, so it can be neither adopted nor refreshed; a plain id defined in an agent document writes into the person's id space from a file no adoption reads.
    """
    record = result.history
    recorded = set(record.copies(result.masters)) if record is not None else set()
    agents = {m for m in result.masters if result.document_role(m) == "agent"}
    source = result.default_master or "DOC"
    out: list[Diagnostic] = []
    for m in sorted(result.masters):
        if result.document_role(m) != "agent" or m in recorded:
            continue
        out.append(
            Diagnostic(
                "warning",
                "loom:agent-document-unrecorded",
                f"{m} is in {COPIES}/ but no step made it, so it can be neither adopted nor refreshed; an agent document starts as a copy of one of the person's, and a document of the agent's own goes anywhere else the quilt lets it write",
                [Location(m, 1)],
                fixes=[
                    Fix("copy the document it works from, NAME being a new file", f"loom draft {source} --ai NAME.tex")
                ],
            )
        )
    for key, n in sorted(result.assembly.nodes.items()):
        if not n.id or n.derived_of or n.file not in agents:
            continue
        out.append(
            Diagnostic(
                "warning",
                "loom:plain-id-in-agent-document",
                f"{n.id} is defined in {n.file}, an agent document, where every id is derived; a new node there takes a fresh id with -ai after it",
                [_loc(result, n)],
                [key],
                fixes=[Fix("take a fresh id, and add -ai to it", "loom id --next")],
            )
        )
    return out


def _agent_permissions(result: ScanResult) -> list[Diagnostic]:
    """`loom:agent-permissions-stale`: Claude Code's permission file is not what `[agents] deny` and this loom make it, so the boundary it enforces is an older one."""
    from loom.ai.layout import CLAUDE_SETTINGS, permissions_stale

    if not permissions_stale(result.quilt.root, result.quilt.config):
        return []
    return [
        Diagnostic(
            "warning",
            "loom:agent-permissions-stale",
            f"{CLAUDE_SETTINGS} is not what [agents] deny and this loom make it, so Claude Code holds agents to an older boundary; loom's own commands already hold them to this one",
            [Location(CLAUDE_SETTINGS, 1)],
            fixes=[
                Fix("rewrite it, in a terminal of your own", "loom upgrade", {"endpoint": "agents-update", "body": {}})
            ],
        )
    ]


def _home(result: ScanResult) -> list[Diagnostic]:
    """`loom:home-missing`: `[quilt] home` names no file the viewer shows, so the viewer opens as if it were unset."""
    from loom.files import Shown

    named = result.quilt.config.home
    root = result.quilt.root
    if not named or ((root / named).is_file() and Shown.of(result.quilt).is_shown(named)):
        return []
    why = "is hidden from the viewer" if (root / named).is_file() else "does not exist"
    return [
        Diagnostic(
            "warning",
            "loom:home-missing",
            f"[quilt] home names {named}, which {why}, so the viewer opens on README.md or the default document instead",
            [Location("config.toml", 1)],
            fixes=[Fix("name a file the viewer shows, or remove the line", "edit config.toml")],
        )
    ]


def _person_pages(result: ScanResult) -> bool:
    """Whether the quilt shows a Markdown file, notebook or HTML page of the person's: one beyond the README.md and the agents' instruction files loom writes at its root.

    `loom:no-live-document`'s advice to begin a document is for a quilt with nothing in it; a quilt of lessons or notes is being worked on in its files.
    """
    from loom.ai.layout import ROOT_FILES
    from loom.files import SUFFIX_KINDS, Shown

    loom_wrote = {"README.md", *ROOT_FILES}
    pages = {"markdown", "notebook", "html"}
    return any(
        p not in loom_wrote and SUFFIX_KINDS.get(PurePosixPath(p).suffix.lower()) in pages
        for p in Shown.of(result.quilt).walk()
    )


def _writes_left(result: ScanResult) -> list[Diagnostic]:
    """`loom:write-left`: a write the journal records on the person's files that recovery could neither finish nor undo, one per act at its first file, saying only what was checked and what makes it go, in plain words; a record recovery cannot trust is said with no file.

    Each carries the fix that settles it as it stands (`settling`): `act` the endpoint a viewer offers as its control, after showing `write-settle-preview`'s words, and the command an agent or installer reads; the act's id is in those alone, never in the words.
    """
    from loom.writes import left_acts

    out = []
    for act_id, kind, files, why, settles in left_acts(result.quilt.root, result.quilt.history_dir):
        fix = [
            Fix(
                "settle it as it stands",
                f"loom doctor --settle {act_id}",
                {"endpoint": "write-settle", "body": {"act": act_id}},
            )
        ]
        if not files:
            out.append(
                Diagnostic("warning", "loom:write-left", f"{why[0].upper()}{why[1:]}.", [], fixes=fix, owner="person")
            )
            continue
        # the wording is the author's to judge (handover): no command, no id; what settles it is the verdict's own (`writes._judge`)
        goes = settles
        if kind == "a Keep":
            goes += " Until it is settled, loom will not keep again the suggestions this act records."
        out.append(
            Diagnostic(
                "warning",
                "loom:write-left",
                f"The journal records {kind} on {', '.join(files)} that loom could neither finish nor undo: {why}. {goes}",
                [Location(files[0], 1)],
                fixes=fix,
                owner="person",
            )
        )
    return out


def lint(result: ScanResult, edges: EdgeResult, graph: Graph) -> list[Diagnostic]:
    asm = result.assembly
    files = result.files
    diags: list[Diagnostic] = list(result.diagnostics) + list(edges.diagnostics)
    config_lines = (
        (result.quilt.root / "config.toml").read_text(encoding="utf-8", errors="replace").splitlines()
        if (result.quilt.root / "config.toml").is_file()
        else []
    )
    for w in result.quilt.config.warnings:
        # at the line of the table the warning names, where there is one
        named = re.search(r"\[([A-Za-z0-9_-]+)\]|key ([A-Za-z0-9_-]+)\.|: ([A-Za-z0-9_-]+)\.[A-Za-z0-9_-]+ ", w)
        table = next((g for g in named.groups() if g), None) if named else None
        line = next(
            (
                i
                for i, text in enumerate(config_lines, 1)
                if table and re.match(rf"\s*\[\s*{re.escape(table)}\s*\]", text)
            ),
            1,
        )
        diags.append(Diagnostic("warning", "loom:unknown-config-key", w, [Location("config.toml", line)]))
    from loom.history.checks import quick_checks
    from loom.history.ledger import load_history

    diags.extend(quick_checks(result, load_history(result.quilt.history_dir)))
    if not any(result.document_role(m) == "person" for m in result.masters):
        # every view that is about nodes is empty until a document is begun; the viewer shows that, and this says how to begin one
        if result.canon_files:
            newest = result.canon_files[-1]
            diags.append(
                Diagnostic(
                    "info",
                    "loom:no-live-document",
                    "the quilt holds no LaTeX document, so it defines no nodes",
                    [],
                    fixes=[
                        Fix(
                            f"start from the newest landmark, {Path(newest).stem}",
                            f"loom history restore {Path(newest).stem} --to FILE",
                        )
                    ],
                )
            )
        elif not _person_pages(result):
            diags.append(
                Diagnostic(
                    "info",
                    "loom:no-live-document",
                    "the quilt holds no LaTeX document; write one anywhere in it with \\documentclass, or begin from a paper",
                    [],
                    fixes=[
                        Fix("bring in a paper you are writing", "loom import FILE"),
                        Fix("file a paper you are reading", "loom library add FILE"),
                    ],
                )
            )
    diags.extend(_derived_in_person_document(result, edges))
    diags.extend(_agent_documents(result))
    diags.extend(_agent_permissions(result))
    diags.extend(_home(result))
    diags.extend(_writes_left(result))
    for path, directives in asm.directives.items():
        for d in directives:
            if d.key == "basis" and not any(
                n.kind == "environment" and n.file == path and any(a <= d.offset < b for a, b in n.own)
                for n in asm.nodes.values()
            ):
                diags.append(
                    Diagnostic(
                        "warning",
                        "loom:misplaced-basis",
                        "% !LOOM basis belongs inside one theorem-like block",
                        [Location(path, d.line)],
                    )
                )
    # The basis is inferred during every live scan; an unresolved basis is a review task, not a proof waiver.
    for key, n in asm.nodes.items():
        if n.kind != "environment" or n.conflict_of:
            continue
        if n.basis == "unclassified" and n.reached_by:
            diags.append(
                Diagnostic(
                    "warning",
                    "loom:needs-classification",
                    f"{key} needs classification: {n.basis_reason}",
                    [_loc(result, n)],
                    [key],
                )
            )
        if n.basis == "local-proof" and not n.proofs and not n.inline_proof and not n.incomplete:
            diags.append(
                Diagnostic("warning", "loom:missing-proof", f"{key} ({n.taxon}) has no proof", [_loc(result, n)], [key])
            )
        if n.basis in ("expository", "assumption", "open-claim") and n.proofs:
            diags.append(
                Diagnostic("info", "loom:unexpected-proof", f"{key} ({n.taxon}) has a proof", [_loc(result, n)], [key])
            )
    # references to loose nodes; equations in proofs referenced from elsewhere. A master reaches what it reads by `\externaldocument` as well as what it includes.
    external = result.external_reach
    for e in edges.edges:
        if e.via == "nested":
            continue
        target = asm.nodes.get(e.to)
        source = asm.nodes.get(e.src)
        if target is None or source is None:
            continue
        src_masters = set(source.reached_by)
        loose_to_loose = not src_masters and not target.reached_by and target.file != source.file
        reach = src_masters.union(*(external.get(m, ()) for m in src_masters))
        if (src_masters and not (reach & set(target.reached_by))) or loose_to_loose:
            # a reference the document's compile reads prints ?? there; `\uses` prints nothing, and two loose files meet no TeX
            read = any(m in result.masters for m in src_masters)
            sev = ("error" if e.via != "uses" else "warning") if read else "info"
            diags.append(
                Diagnostic(
                    sev,
                    "loom:reference-to-loose",
                    f"{e.src} refers to {e.to}, which its master does not reach",
                    [Location(e.file, e.line)],
                    [e.src, e.to],
                    class_=LATEX if sev == "error" else MODEL,
                )
            )
        if (
            target.kind == "proof"
            and e.label
            and target.of
            and e.src != target.key
            and not e.src.startswith(target.key)
        ):
            region = asm.regions.get(f"{target.key}#{e.label}")
            if region is not None:
                diags.append(
                    Diagnostic(
                        "warning",
                        "loom:equation-in-proof-referenced",
                        f"{e.src} references {e.label}, which lies inside the proof {target.key}",
                        [Location(e.file, e.line)],
                        [e.src, target.key],
                    )
                )
    # uses vs refs in proofs
    for key, n in asm.nodes.items():
        if n.kind != "proof":
            continue
        refs = [asm.labels.get(x) for x in edges.refs_in.get(key, [])]
        ref_keys = {_stmt(asm, r) for r in refs if r}
        uses = edges.uses_in.get(key, [])
        use_keys = {_stmt(asm, asm.labels.get(u)) for u in uses if asm.labels.get(u)}
        for rk in sorted(k for k in ref_keys - use_keys if k):
            if rk != n.of:
                diags.append(
                    Diagnostic(
                        "info",
                        "loom:uses-missing",
                        f"{key} references {rk} but its \\uses does not list it",
                        [_loc(result, n)],
                        [key],
                        fixes=[Fix("list it", f"add {rk} to the \\uses of {key}")],
                    )
                )
        for uk in sorted(k for k in use_keys - ref_keys if k):
            if True:
                diags.append(
                    Diagnostic(
                        "info",
                        "loom:uses-unused",
                        f"{key} lists {uk} in \\uses but never references it",
                        [_loc(result, n)],
                        [key],
                    )
                )
    # directives
    for path, ds in asm.directives.items():
        for d in ds:
            if (
                d.form == "unknown"
                or (d.form == "kv" and d.key not in KNOWN_KEYS)
                or (d.form in ("begin", "end") and d.key not in REGION_KEYS)
            ):
                diags.append(
                    Diagnostic(
                        "warning", "loom:unknown-directive", f"unknown directive {d.key}", [Location(path, d.line)]
                    )
                )
    for path, ds in asm.directives.items():
        owners: set[str] = set()
        for d in ds:
            if d.form != "kv" or d.key != "name":
                continue
            owner = next(
                (
                    n
                    for n in asm.nodes.values()
                    if n.file == path
                    and n.kind in ("environment", "section", "proof")
                    and any(a <= d.offset < b for a, b in n.own)
                ),
                None,
            )
            problem = (
                "name belongs inside a node"
                if owner is None
                else "name must not be empty"
                if not d.value
                else "multiple names in this node; the last one is used"
                if owner.key in owners
                else ""
            )
            if owner:
                owners.add(owner.key)
            if problem:
                diags.append(Diagnostic("warning", "loom:invalid-name", problem, [Location(path, d.line)]))
    # theorem-like environments the preamble does not declare
    for path, fe in asm.envs.items():
        seen: set[str] = set()
        for env in fe.all_envs():
            if env.name in result.taxa or env.name in seen or env.is_proof:
                continue
            if env.name in COMMON_THEOREM_ENVS:
                seen.add(env.name)
                diags.append(
                    Diagnostic(
                        "warning",
                        "loom:unknown-environment",
                        f"environment {env.name} looks theorem-like but no master declares it; add % !LOOM environment: {env.name} = Name, plain",
                        [Location(path, files[path].line_of(env.start))],
                    )
                )
    # loom macros without loom.sty, a loom.sty found nowhere, and shadowed macros
    for master, closure in result.closures.items():
        exp = result.expansions[master]
        base = result.base_of(master)
        if master in result.files and loom_sty_missing(closure, result.quilt.root, base):
            src = result.files[master]
            named = LOOM_PACKAGE.search(src.clean)
            diags.append(
                Diagnostic(
                    "error",
                    "loom:macros-missing",
                    f"{master} loads loom, but no loom.sty sits beside it or on the TeX path, so it does not compile; keep loom.sty in {base or 'the quilt root'}/, or put loom's macro block in place of \\usepackage{{loom}}, the patch `loom doctor --json` gives",
                    [Location(master, src.line_of(named.start()) if named else 1)],
                )
            )
        used = sorted({m for m in LOOM_MACROS if re.search(r"\\" + m + r"(?![A-Za-z@])", exp.text)})
        if used and not closure.loads_loom:
            names = ", ".join("\\" + m for m in used)
            diags.append(
                Diagnostic(
                    "error",
                    "loom:macros-unloaded",
                    f"{master} uses {names} but loads neither loom.sty nor loom's macro block",
                    [Location(master, 1)],
                )
            )
        for frag in closure.fragments:
            if frag.file.endswith("loom.sty"):
                continue
            # the macro block, blanked in the clean text as a comment is, defines the three by design; anything else shadows them
            text = frag.src.clean[frag.start : frag.end]
            for m in sorted(LOOM_MACROS):
                if re.search(r"\\(?:new|renew|provide)command\s*\{?\\" + m + r"\b", text):
                    diags.append(
                        Diagnostic(
                            "warning",
                            "loom:macro-shadowed",
                            f"{frag.file} defines \\{m}, which loom.sty also provides",
                            [Location(frag.file, 1)],
                        )
                    )
    # loose files
    for path, src in files.items():
        if src.ignored or path in result.masters:
            continue
        if not any(path in e.reached for e in result.expansions.values()):
            node_keys = [k for k, n in asm.nodes.items() if n.file == path and n.kind in ("environment", "section")]
            # the line names the file from the directory the default document compiles from (P12)
            base = result.base_of(result.default_master) if result.default_master else ""
            stem = (path.removeprefix(f"{base}/") if base else path).removesuffix(".tex")
            diags.append(
                Diagnostic(
                    "info",
                    "unreachable",
                    f"no master reaches {path}",
                    [Location(path, 1)],
                    node_keys,
                    fixes=[Fix("read it, or let it go", f"\\input{{{stem}}} in a document, or remove {path}")],
                )
            )
    # dependency cycles
    for cyc in graph.cycles():
        diags.append(
            Diagnostic(
                "warning",
                "loom:dependency-cycle",
                "statement dependencies form a cycle: " + " -> ".join(cyc + cyc[:1]),
                [],
                cyc,
            )
        )
    disabled = set(result.quilt.config.lint_disable)
    diags = [d for d in diags if not (d.code in disabled and can_disable(d.code))]
    diags.sort(
        key=lambda d: (
            {"error": 0, "warning": 1, "info": 2}[d.severity],
            d.code,
            d.locations[0].file if d.locations else "",
            d.locations[0].line if d.locations else 0,
        )
    )
    return diags


#: An address with a scheme: another site's, an application's, or one of the two link forms.
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def markdown_links(result: ScanResult, drawn: Drawn | None = None) -> list[Diagnostic]:
    """`loom:link-target-missing`, `loom:link-place-missing` and `loom:link-work-unknown`: each link or source in a shown Markdown file that its page leaves reaching nothing, on the line that wrote it.

    Parameters
    ----------
    result : ScanResult
        The quilt as scanned.
    drawn : Drawn, optional
        The pages' links as a build drew them (`files.attach_files`); drawn here when not given.

    Returns
    -------
    list of Diagnostic
        One warning per link, `[lint] disable` applied.

    Notes
    -----
    Read off the page's own drawing (`files.render_file_markdown`), so a link in code is none, and judged by the resolver every `quilt:` and `cited:` link answers to (`links.resolve`), so lint and the page agree on what a link reaches. Kept out of `lint`, which every command's scan runs, because it draws every Markdown file: `loom lint`, a build and an agent's first look add it. In the research state a link whose result is gone since the page was written through loom goes nowhere too, as its page says (`pages.published`).
    """
    from urllib.parse import unquote

    from loom.files import drawn_links, headings_of
    from loom.links import LinkError, resolve
    from loom.records.annotations import load_records

    drawn = drawn if drawn is not None else drawn_links(result)
    root = result.quilt.root
    records = load_records(root)[0] if any(drawn.links.values()) else []
    state = result.quilt.config.research_state
    recorded = _written_links(result) if state in drawn.links else {}
    out: list[Diagnostic] = []
    for rel, found in sorted(drawn.links.items()):
        for link in found:
            href = link.drawn
            try:
                if href.startswith(("quilt:", "cited:")):
                    target = resolve(result, root, href, records)
                    if rel == state and target.kind == "node" and target.key not in result.nodes:
                        if recorded.get(unquote(href)):
                            named = unquote(href[len("quilt:") :].split("#", 1)[0])
                            raise LinkError(f"{href}: {named} was a result when the page was written, and is gone")
                elif href.startswith("#"):
                    place = unquote(href[1:])
                    if place and place not in headings_of(root, rel, "markdown"):
                        raise LinkError(f"{href}: {rel} has no heading {place}", "place")
                elif href and not href.startswith(("/", "?")) and not _SCHEME.match(href):
                    raise LinkError(f"{href}: {_unreached(root, rel, link, drawn.kinds)}")
            except LinkError as exc:
                why = str(exc).removeprefix(f"{href}: ")
                if exc.part != "work":
                    why = _as_seen(root, href, why)
                out.append(
                    Diagnostic(
                        "warning",
                        "loom:link-work-unknown"
                        if exc.part == "work"
                        else "loom:link-place-missing"
                        if exc.part == "place"
                        else "loom:link-target-missing",
                        f"a link goes nowhere: {why}",
                        [Location(rel, link.line)],
                        fixes=[Fix("link the work as it is named now", "loom link WORK")] if exc.part == "work" else [],
                    )
                )
    disabled = set(result.quilt.config.lint_disable)
    return [d for d in out if not (d.code in disabled and can_disable(d.code))]


def _unreached(root: Path, rel: str, link: Link, kinds: dict[str, str]) -> str:
    """Why the page left a relative address of `rel` as written: what it names is missing, hidden, a folder, outside the quilt, a LaTeX file, or no image."""
    import posixpath
    from urllib.parse import unquote

    path = unquote(link.drawn.split("#", 1)[0].split("?", 1)[0])
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(rel), path))
    if joined == ".." or joined.startswith("../"):
        return f"{path} leads out of the quilt"
    if joined in kinds:
        return (
            f"{joined} is not an image"
            if link.src
            else f"{joined} is a LaTeX file, which the viewer does not open by its path"
        )
    if (root / joined).is_dir():
        return f"{joined} is a folder, which the viewer does not open"
    if (root / joined).exists():
        return f"{joined} is hidden from the viewer"
    return f"{joined} does not exist"


def _as_seen(root: Path, href: str, why: str) -> str:
    """Why a link a person is shown goes nowhere, as they would say it: what is not there, never loom's rule for writing a link nor a command.

    The resolver's sentences are an agent's when a link it posts is refused (`links.resolve`); this rewords the few that state a rule or name a key, and keeps the rest as they are.
    """
    from urllib.parse import unquote

    key, _, place = href.partition(":")[2].partition("#")
    key, place = unquote(key), unquote(place)
    if href.startswith("cited:"):
        page = re.search(r"[?&#]page=([^&#]*)", href)
        return f"there is no page {unquote(page.group(1))}" if page and why.startswith("page must be") else why
    if not href.startswith("quilt:"):
        return why
    if not key:
        return "it names nothing"
    missing = re.fullmatch(r"no key (.+) in this quilt", why)
    if missing and missing.group(1) == key and PurePosixPath(key).suffix and not (root / key).exists():
        return f"{key} does not exist"  # a file's path, written as a link, names no key either
    if missing:
        return f"nothing in the quilt is named {missing.group(1)}"
    if key.endswith(".tex") and ("file the documents include" in why or why.startswith("a LaTeX file")):
        return f"{key} is a LaTeX file, which the viewer does not open by its path"
    if why.endswith("is linked whole") or why.startswith(("a place in a PDF is", "a place in a text file is")):
        return f"{'the research state' if key == 'state' else key} has no place {place}"
    return why


def _written_links(result: ScanResult) -> dict[str, bool]:
    """The research state's links that named a result when it was last written through loom, by their address decoded: what `pages.published` reads to say a result has gone since."""
    from urllib.parse import unquote

    from loom.pages import state_page, writes

    done = writes(result.quilt.root, result.quilt.history_dir, state_page(result.quilt.config))
    links = (done[-1].get("links") or {}) if done else {}
    return {unquote(href): bool(entry.get("hash")) for href, entry in links.items()}


def _stmt(asm: Assembly, key: str | None) -> str | None:
    if key is None:
        return None
    region = asm.regions.get(key)
    if region is not None:
        key = region.container
    n = asm.nodes.get(key)
    if n is not None and n.kind == "proof" and n.of:
        return n.of
    return key


def _loc(result: ScanResult, n: NodeRec) -> Location:
    return Location(n.file, result.files[n.file].line_of(n.start))
