"""A fake of loom's own TeX for the unit tier: kpsewhich, tlmgr, latexmk and pdftex in one script, over a package database of a few packages.

The installation's root is two directories above the script (`<root>/bin/<platform>/<tool>`). `have.txt` there lists the files installed; `tlpkg/texlive.tlpdb` the installed packages, `tlpkg/texlive.tlpdb.main.fake` the repository's. tlmgr logs each run to `tlmgr.log` and installs a package by adding its files; `FAKE_TLMGR_HANG=1` makes it hang. latexmk fails on the first `\\usepackage` whose file is not installed, as LaTeX does under -halt-on-error. Never install this on a real PATH.
"""

import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = Path(sys.argv[0]).name


def have() -> set[str]:
    f = ROOT / "have.txt"
    return set(f.read_text().split()) if f.is_file() else set()


def repository() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    name = ""
    for line in (ROOT / "tlpkg" / "texlive.tlpdb.main.fake").read_text().splitlines():
        if line.startswith("name "):
            name = line[5:]
            out[name] = []
        elif line.startswith(" "):
            out[name].append(line.strip().rsplit("/", 1)[-1])
    return out


def tlmgr(args: list[str]) -> int:
    with (ROOT / "tlmgr.log").open("a") as log:
        log.write(" ".join(args) + "\n")
    if os.environ.get("FAKE_TLMGR_HANG"):
        time.sleep(600)
    if "install" not in args:
        return 0
    wanted = args[args.index("install") + 1 :]
    repo = repository()
    files = have()
    local = ROOT / "tlpkg" / "texlive.tlpdb"
    for n, pkg in enumerate(wanted, 1):
        if pkg not in repo:
            print(f"tlmgr install: package {pkg} not present in repository.")
            continue
        files.update(repo[pkg])
        with local.open("a") as db:
            db.write(f"name {pkg}\n")
        print(f"[{n}/{len(wanted)}, ??:??/??:??] install: {pkg} [1k]")
    (ROOT / "have.txt").write_text("\n".join(sorted(files)) + "\n")
    return 0


def kpsewhich(args: list[str]) -> int:
    files = have()
    for a in args:
        if not a.startswith("-") and a in files:
            print(ROOT / "texmf-dist" / a)
    return 0


def latexmk(args: list[str]) -> int:
    outdir = Path(next(a.split("=", 1)[1] for a in args if a.startswith("-outdir=")))
    tex = Path(args[-1])
    stem = tex.stem
    text = tex.read_text()
    files = have()
    for m in re.finditer(r"\\usepackage\{([^}]+)\}", text):
        name = m.group(1)
        if f"{name}.sty" not in files and not Path(f"{name}.sty").is_file():
            (outdir / f"{stem}.log").write_text(f"! LaTeX Error: File `{name}.sty' not found.\n")
            print("Latexmk: Errors, so I did not complete making targets")
            return 12
    (outdir / f"{stem}.log").write_text("This is the fake pdfTeX\n")
    (outdir / f"{stem}.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if "--version" in args or "-v" in args:
        print("pdfTeX 3.141592653-2.6-1.40.29 (TeX Live 2026)")
        return 0
    if TOOL == "tlmgr":
        return tlmgr(args)
    if TOOL == "kpsewhich":
        return kpsewhich(args)
    if TOOL == "latexmk":
        return latexmk(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
