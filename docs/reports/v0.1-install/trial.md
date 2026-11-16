# v0.1 Install: the trial of decision 7

Done 2026-11-14 on an Apple M2, macOS 26.5.2, with other sessions loading the machine (one-minute load 7 to 35). The question: what a Mac without Homebrew uses for the pictures, figures and page text loom needs beyond TeX. Everything ran under the scratch directory `$T` (`/private/tmp/claude-501/-Users-isaac-dev-loom-arras--claude-worktrees-clever-rosalind-146ec5/29da6cdd-3817-4039-9259-8ec986afc480/scratchpad/trial`), as the person (`$T/scripts/p`: `env -i`, `HOME`, `TMPDIR` and biber's unpack directory in scratch, PATH = TinyTeX 2026 + `/usr/bin:/bin:/usr/sbin:/sbin`). Nothing was installed outside scratch and nothing ran with sudo.

**A trap in the harness, found and fixed.** This session's own shell exports `LIBGS=/opt/homebrew/lib/libgs.dylib`, and TinyTeX's dvisvgm uses it; the first "bare" builds therefore drew with Homebrew's Ghostscript. Every number below is from the corrected harness, where `LIBGS` names nothing unless a case gives it one. The study's TinyTeX report (`v0.1-study/raw/tinytex.md`, TTX-5) had the same exposure; its "bare" findings agree with these, so it seems to have been set differently there.

## Findings

| need | without Homebrew | with loom shipping Ghostscript and poppler |
|---|---|---|
| xy diagrams (man12, acgs) | drawn with **no arrows at all**, and no warning: 598 SVG paths in man12's 51 pictures | every arrow: 1,462 paths in the same 51 pictures |
| xy diagrams, xy kept off its PostScript driver (no Ghostscript) | complete, drawn with xy's own fonts; see below | not needed |
| EPS figures in the PDF (pdflatex) | `fig-eps-converted-to.pdf not found`; latexmk exits 12 | converted by `repstopdf` |
| EPS figures in the HTML (acgs's twelve `pspdftex` figures) | blank pictures | drawn, once loom's HTML makes its pictures with dvisvgm (below) |
| PDF figures in the HTML (showcase `quiver.pdf`) | a broken image link, no warning | an SVG by `pdftocairo` |
| `dvisvgm --pdf` as the fallback for PDF figures | refuses: needs Ghostscript older than 10.01 or `mutool` | not used: `pdftocairo` comes first |
| page text and word boxes of a dropped PDF | none: "pdftotext is not installed" | `pdftotext -layout` and `-bbox-layout`, the same program records were made with |
| the identity test at import | skipped, silently, without pdftotext | runs |
| TikZ and quiver (relloc) | complete | the same |

Two gaps found on the way, neither about Homebrew:

- **acgs's figures are missing in every build**, with Homebrew or without. TeX4ht turns a `picture` environment into a PNG with `dvipng`, which loom's TeX lacked, so the page named PNGs that were never made. With `dvipng` installed it is no better: in a paper that loads `pstricks`, `dvipng` hands Ghostscript 10 PostScript it rejects, and every figure comes out blank, on the author's own TeX Live 2024 with Homebrew's Ghostscript as on loom's. Loom's HTML now makes these pictures as SVG through dvisvgm, as its diagram runs already did, and acgs's figures draw (`$T/shots/e89053ee035ade1a.svg.png`). `dvipng` stays in the seed for a configuration that asks for PNG.
- **The end-to-end run found two more causes of empty figures, both fixed on the branch.** The import copied only the PDF twin of a figure named without an extension, which pdflatex reads, while the DVI that TeX4ht draws from reads the EPS; it now brings in every form the paper ships. And a paper that loads `pstricks` needs `pst-tools.pro`, a PostScript header that `dvipng` names only in make4ht's own output ("Cannot find PostScript file pst-tools.pro"); loom now reads that output after every HTML run and fetches the package.
- **Nothing tells the person a picture is wrong.** Missing arrows, blank figures and a broken figure link all build with exit 0 and no diagnostic. The diagnostic belongs in `render/fragments.py` and `render/assets.py` (Speed's); the reserved prefix is `loom:tex-`.

### xy without Ghostscript

TeX4ht's `xy.4ht` loads `\xyoption{dvips}\xyoption{ps}` unconditionally, which makes xy draw lines and arrow tips as PostScript specials, which dvisvgm ignores without Ghostscript. A copy of `xy.4ht` without that line, placed where the run finds it first, makes xy draw with its own fonts. On a test diagram (two straight arrows, a diagonal, a curve, a dashed arrow) the result is indistinguishable from the Ghostscript drawing (`$T/xy/png2/*.png`). On man12 at full scale, with no Ghostscript, all 51 pictures draw with every arrow (839 paths and 2,169 glyph uses, against 598 and 1,472 bare), and the commutative square of `man-002H` is indistinguishable from the Ghostscript drawing (`$T/shots/cmp/man12-{gs,nodriver,bare}.png`). This is a fallback loom can apply in `tex/tex4ht.py` whenever no Ghostscript is found; pstricks and EPS have no such route.

### Host programs on a Mac with no Command Line Tools

Checked by whether `/usr/bin/X` links `libxcselect` (the stub that offers to install the tools): `perl`, `curl`, `tar`, `shasum`, `codesign`, `open`, `osascript`, `unzip` are real, so latexmk, tlmgr, epstopdf and the install script run. `git`, `python3`, `make`, `clang` are stubs. **There is no `timeout`, `xz` or `pkgutil` on the path** (the last is in `/usr/sbin`); macOS's `tar` reads `.tar.xz` itself.

**git is a problem now.** Every `loom init --from` and `loom import` runs `git -C <quilt> rev-list --all` (`scan/alloc.py`), twice; on a clean Mac each call opens Apple's "install the command line developer tools" dialog. The same stub is reached from `scan/quilt.py` (the author name, on the serve path), `cli/quilt.py`, `ai/clients.py`, `adopt.py` and `sync.py`, and doctor's own probe of `git --version`. Doctor now recognises the stub without running it (`xcode-select -p` fails) and says so. The other call sites are not this workstream's files.

## The candidates

| candidate | gives | size (arm64) | licence | relocates | notes |
|---|---|---|---|---|---|
| conda-forge `ghostscript` 10.08.0: `bin/gs` and `lib/libgs.10.dylib` | `gs` for `repstopdf`; `LIBGS` for dvisvgm | 49 MB on disk, 23 MB as `.tar.xz` | AGPL-3.0-only | yes: both are self-contained, init files compiled in; ran from a moved copy with the original hidden; signatures intact | osx-64 package exists for Intel Macs |
| conda-forge `poppler` 26.11.0: `pdftotext`, `pdfinfo`, `pdftocairo` with their 51 libraries | page text and word boxes, rotation, PDF figures, crops | 74 MB on disk (ICU's data is 34 MB of it), 20 MB as `.tar.xz` | GPL-2.0-or-later; libraries LGPL, MPL, MIT, Unicode | yes, same test; `pdftocairo` warns once that fontconfig has no configuration, harmless for embedded fonts, cured by shipping a two-line `fonts.conf` | osx-64 exists |
| both together, one archive | all of the above | 117 MB on disk, **43 MB download** | as above | yes | built by micromamba (static, 15 MB, BSD-3) in the release workflow; the person never runs it |
| `pypdfium2` 5.15.2 wheel | page text with character boxes, rendering to bitmaps; no SVG, no PostScript | 7.4 MB installed | Apache-2.0 / BSD-3 | a wheel | against `pdftotext -bbox-layout` on the showcase's four PDFs: 95% of words the same, 81-84% of word boxes overlapping by more than half. Not a drop-in: records already rest on poppler's geometry, and the change is in `refs/pages.py`, `records/marks.py`, `records/crops.py` and `tex/identity.py` (2-4 days, other workstreams' files) |
| conda-forge `mupdf` for `dvisvgm --pdf` | a second route for PDF figures | 482 MB environment | AGPL-3.0 | not tried | not needed while `pdftocairo` is shipped |
| MacTeX's Ghostscript package | `gs` | not measured | AGPL | not tried | not needed: the conda-forge build relocated |

## Recommendation

Ship one per-architecture archive of conda-forge Ghostscript and poppler beside loom's TeX (`<data>/loom/tools/{bin,lib}`), 43 MB, built in the release workflow and installed by the same "Repair TeX" step as loom's TeX; loom puts `tools/bin` on its path and gives dvisvgm `LIBGS`. It changes no file another workstream owns, keeps every word box records rest on, and makes all three papers and the showcase draw as they do on the author's machine. Also apply the xy fallback when no Ghostscript is found, so that a person whose tools archive failed still gets arrows. pypdfium2 stays the fallback for page text if the archive cannot be shipped.

The licences need the author's word: Ghostscript is AGPL-3.0 and poppler GPL; shipping their unmodified binaries beside loom (itself GPL-3.0-or-later) is distribution, which needs their licence texts in the archive and a pointer to their sources (the conda-forge feedstocks name them). Total first download on a Mac: about 58 MB of TeX and 43 MB of tools, plus uv and a managed Python (about 25 MB).

## What only a clean Mac can show

That a Mac with no Command Line Tools runs latexmk and tlmgr through `/usr/bin/perl`; that no dialog opens during install, import or serve once the git call sites are guarded; that binaries fetched by `curl` carry no quarantine (here they carry only `com.apple.provenance`); first-run times; an Intel Mac with the osx-64 archive.
