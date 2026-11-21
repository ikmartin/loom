"""The diagnostic code table (docs/specs/diagnostics.md): each code's severity, its class, and whether `[lint] disable` can silence it.

Reserved codes have no namespace and cannot be silenced; loom codes are namespaced and can be, except those marked fixed. Every code emitted anywhere must appear here with a class; the coverage and registry tests check both.

A class says what kind of problem a code reports: `LATEX`, a problem in a document's LaTeX that an author would recognise, a failed compile among them, and what else the person is to be shown with no other place to say it; `MODEL`, loom's model of the quilt, the hygiene of keys, links, copies and records an agent keeps; `INTERNAL`, loom's own difficulty or the integrity of its records. The viewer shows a person `LATEX` alone; `loom lint` shows every class. An entry is its code's plainest instance: `VARIES` names the codes whose emitter grades each instance, and `scan.owners.stamped` makes whatever a digest holds `INTERNAL`.
"""

from __future__ import annotations

from typing import Any, NamedTuple

#: The three classes, in the order a reader is shown them.
LATEX, MODEL, INTERNAL = "latex", "model", "internal"
CLASSES = (LATEX, MODEL, INTERNAL)


class Code(NamedTuple):
    severity: str
    cls: str
    fixed: bool = False


RESERVED: dict[str, Code] = {
    "duplicate-id": Code("error", LATEX),
    "dangling-link": Code("error", LATEX),
    "missing-include": Code("error", LATEX),
    "double-inclusion": Code("error", LATEX),
    "inclusion-cycle": Code("error", LATEX),
    "unreachable": Code("info", MODEL),
}

LOOM: dict[str, Code] = {
    "loom:environment-spans-files": Code("warning", MODEL),
    "loom:line-anchoring": Code("warning", MODEL, fixed=True),
    "loom:unknown-environment": Code("warning", MODEL),
    "loom:unattached-proof": Code("warning", MODEL),
    "loom:multi-target-proof": Code("warning", MODEL),
    "loom:reference-to-loose": Code("error", LATEX),
    "loom:duplicate-label": Code("error", LATEX),
    "loom:macros-unloaded": Code("error", MODEL),
    "loom:macros-missing": Code("error", MODEL),
    "loom:macro-shadowed": Code("warning", MODEL),
    "loom:taxon-conflict": Code("warning", MODEL),
    "loom:prefix-is-citekey": Code("warning", MODEL),
    "loom:unknown-directive": Code("warning", MODEL),
    "loom:invalid-name": Code("warning", MODEL),
    "loom:unknown-config-key": Code("warning", MODEL),
    "loom:unlabelled-node": Code("info", MODEL),
    "loom:positional-proof-key": Code("info", MODEL),
    "loom:unexpected-proof": Code("info", MODEL),
    "loom:missing-proof": Code("warning", MODEL),
    "loom:needs-classification": Code("warning", MODEL),
    "loom:misplaced-basis": Code("warning", MODEL),
    "loom:equation-in-proof-referenced": Code("warning", MODEL),
    "loom:uses-missing": Code("info", MODEL),
    "loom:uses-unused": Code("info", MODEL),
    "loom:see-redundant": Code("info", MODEL),
    "loom:dependency-cycle": Code("warning", LATEX),
    "loom:snippet-failed": Code("warning", INTERNAL),
    "loom:closure-failed": Code("error", INTERNAL),
    "loom:atomize-target-exists": Code("warning", MODEL, fixed=True),
    "loom:import-outside-tree": Code("warning", MODEL),
    "loom:retired-ledger-key": Code("info", MODEL),
    "loom:detached-annotation": Code("info", MODEL),
    "loom:previous-key-match": Code("info", MODEL),
    "loom:unmatched-postnote": Code("warning", INTERNAL),
    "loom:cites-proposed-node": Code("warning", MODEL),
    "loom:undigested-citekey": Code("info", INTERNAL),
    "loom:postnote-from-another-version": Code("info", INTERNAL),
    "loom:version-mismatch": Code("warning", INTERNAL),
    "loom:unresolved-work": Code("info", INTERNAL),
    "loom:unverified-locators": Code("warning", INTERNAL),
    "loom:missing-package": Code("warning", INTERNAL),
    "loom:digest-without-bib": Code("warning", INTERNAL),
    "loom:interface-version": Code("error", INTERNAL, fixed=True),
    "loom:non-utf8-source": Code("warning", LATEX),
    "loom:unknown-theoremstyle": Code("warning", INTERNAL),
    "loom:taxon-name-macro": Code("info", INTERNAL),
    "loom:citekey-slug-collision": Code("warning", MODEL),
    "loom:main-not-found": Code("warning", MODEL),
    "loom:main-unset": Code("info", MODEL),
    "loom:foreign-annotations": Code("warning", INTERNAL),
    "loom:repeated-id": Code("warning", INTERNAL),
    "loom:annotation-types": Code("warning", INTERNAL),
    # a document's last compile, read from its log: TeX's word, which no setting silences
    "loom:compile-failed": Code("error", LATEX, fixed=True),
    "loom:compile-errors": Code("error", LATEX, fixed=True),
    # the workbench and the record (docs/specs/diagnostics.md §3)
    "loom:superseded-file": Code("info", MODEL),
    "loom:history-missing": Code("error", INTERNAL),
    "loom:history-edited": Code("error", INTERNAL),
    "loom:history-corrupt": Code("error", INTERNAL),
    "loom:history-interrupted": Code("warning", INTERNAL),
    "loom:dangling-ancestry": Code("warning", INTERNAL),
    "loom:id-reused": Code("warning", MODEL),
    "loom:node-recovered": Code("info", MODEL),
    "loom:no-live-document": Code("info", MODEL),
    "loom:document-gone": Code("warning", MODEL),
    # the documents an agent edits
    "loom:derived-id-in-person-document": Code("warning", MODEL),
    "loom:agent-document-unrecorded": Code("warning", MODEL),
    "loom:plain-id-in-agent-document": Code("warning", MODEL),
    # the agents' boundary: the permission file Claude Code reads lags `[agents] deny`
    "loom:agent-permissions-stale": Code("warning", INTERNAL),
    # the viewer's front door: `[quilt] home` names no file the viewer shows
    "loom:home-missing": Code("warning", MODEL),
    # a link in a shown Markdown file that its page leaves going nowhere: to a file or a place that is not there, the person's to see and put right by hand, as a reference to nothing in a document is; to a work by an id loom no longer gives it, an agent's to mend with `loom link`
    "loom:link-target-missing": Code("warning", LATEX),
    "loom:link-place-missing": Code("warning", LATEX),
    "loom:link-work-unknown": Code("warning", MODEL),
    # the one door (docs/design/writes.md, "Recovery"): a write to the person's file recovery could neither finish nor undo, which the person has no other place to be told of
    "loom:write-left": Code("warning", LATEX),
    # a warning and never an error, because loom cannot fetch without consent
    "loom:no-readable-copy": Code("warning", INTERNAL),
    # the library's nodes (docs/specs/nodes.md §11): a file of loom's records failing one of the eleven checks, a code each
    "loom:node-unreadable": Code("error", INTERNAL),
    "loom:node-schema": Code("error", INTERNAL),
    "loom:node-id": Code("error", INTERNAL),
    "loom:node-taxon": Code("error", INTERNAL),
    "loom:node-key": Code("error", INTERNAL),
    "loom:node-parent": Code("error", INTERNAL),
    "loom:node-edge": Code("error", INTERNAL),
    "loom:node-body-ref": Code("error", INTERNAL),
    "loom:node-bibtex": Code("error", INTERNAL),
    "loom:node-macros": Code("error", INTERNAL),
    "loom:node-incomplete": Code("error", INTERNAL),
    # a line of the tag log that is neither a tag nor an untag, skipped as `loom:foreign-annotations` skips one of the annotation log
    "loom:foreign-tags": Code("warning", INTERNAL),
    # a line of the library's log that is no act on a work, skipped as above
    "loom:foreign-library-acts": Code("warning", INTERNAL),
}

#: The codes whose severity differs by instance, each set by its emitter: the first four an error of class `LATEX` where a document's compile reads the instance, and `loom:environment-spans-files` where a document is never closed, else a warning of class `MODEL` (an info for a reference between two files no document reads); the compile codes a warning when a file the document reads changed after its log; `loom:no-readable-copy` and `loom:annotation-types` an info in their milder case; `loom:document-gone` of class `LATEX` where annotations are on the document, which the person is shown nowhere else.
VARIES = frozenset(
    {
        "duplicate-id",
        "loom:duplicate-label",
        "dangling-link",
        "loom:reference-to-loose",
        "loom:environment-spans-files",
        "loom:compile-failed",
        "loom:compile-errors",
        "loom:no-readable-copy",
        "loom:annotation-types",
        "loom:document-gone",
    }
)


#: The codes a gate refuses to bring in, by code and not by grade: those that were errors wherever loom raised them before its model was graded by what TeX does. Adopting an agent's copy and linearizing a document will not go ahead over a new one, at any grade but info, so that a regrade changes what a person and an agent are told and never what loom lets through. A code added since is in no gate until one is meant to refuse it.
GATED = frozenset(
    {
        "duplicate-id",
        "dangling-link",
        "missing-include",
        "double-inclusion",
        "inclusion-cycle",
        "loom:environment-spans-files",
        "loom:line-anchoring",
        "loom:unknown-environment",
        "loom:unattached-proof",
        "loom:reference-to-loose",
        "loom:duplicate-label",
        "loom:macros-unloaded",
        "loom:macros-missing",
        "loom:closure-failed",
        "loom:atomize-target-exists",
        "loom:interface-version",
        "loom:citekey-slug-collision",
        "loom:history-missing",
        "loom:history-edited",
        "loom:history-corrupt",
        "loom:id-reused",
        "loom:derived-id-in-person-document",
        "loom:agent-document-unrecorded",
        "loom:plain-id-in-agent-document",
    }
)


def gates(d: Any) -> bool:
    """Whether a gate refuses to bring in diagnostic `d` (`GATED`): its code is one, and it is no info, as a reference between two files no document reads is."""
    return d.code in GATED and d.severity != "info"


def registered(name: str) -> Code | None:
    """The registry's entry for a code, None for one it does not hold."""
    return RESERVED.get(name) or LOOM.get(name)


def class_of(name: str) -> str:
    """A code's class; one the registry does not hold, which only another publisher's can be, is the person's LaTeX, so a viewer that shows a person that class alone still shows it."""
    found = registered(name)
    return found.cls if found is not None else LATEX


def unclassed() -> list[str]:
    """The registered codes with no class among `CLASSES`, which the registry test requires to be none."""
    return sorted(c for c, entry in {**RESERVED, **LOOM}.items() if entry.cls not in CLASSES)


def can_disable(name: str) -> bool:
    return name in LOOM and not LOOM[name].fixed


def all_codes() -> list[str]:
    return sorted(RESERVED) + sorted(LOOM)
