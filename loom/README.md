# loom

A tool for atomized mathematical development. loom turns a LaTeX paper into a *quilt*: every theorem-like environment and section carries a permanent id as an ordinary `\label`, dependencies are read from the `\ref` and `\uses` you already write, acceptances are recorded with content hashes so you are told exactly what went stale and why, review comments are anchored to quoted text, and the whole is published to loom's viewer. The paper compiles exactly as before, with plain `pdflatex`, from the same files, on Overleaf.

Status: alpha. The design, the interface specification and the example quilts live in [the repository](https://github.com/ikmartin/loom) beside it.

## Install

```
curl -LsSf https://github.com/ikmartin/loom/releases/latest/download/install.sh | sh
```

installs loom with its own TeX, Ghostscript and poppler, for this user, with no password; the same line updates it. Loom uses its own TeX first; `use = "mine"` under `[tex]` in `~/.config/loom/config.toml` keeps yours, and then you need TeX Live with `latexmk`, `make4ht` and `dvisvgm`, and poppler and Ghostscript for figures and page text. git is optional.

For development, from a clone:

```
git clone https://github.com/ikmartin/loom
cd loom/loom
uv sync
uv run loom doctor
```

`loom doctor` names anything missing and how to get it. The viewer ships inside this repository as a built bundle, so `loom serve` needs no Node. An agent attaches to a quilt through `loom mcp`, and the MCP SDK it needs installs with loom.

## Quickstart

```
loom doctor                 # names every missing tool and how to install it
loom init demo --demo       # a small quilt with a landmark, acceptances, annotations, and an agent's run
cd demo
loom check                  # lint plus a compile of the master
loom serve                  # http://127.0.0.1:8791, re-renders whenever a file changes
```

Then, on your own paper:

```
loom init mypaper --from ~/papers/draft.tex     # the paper as received kept as a landmark, and the working document drafted from it
cd mypaper
loom status                                     # every key, its state, and its open annotations
loom atomize draft/draft.tex --to draft/spine.tex --sections  # one file per node, a spine of \input lines
loom stamp draft/spine.tex -m "Submitted"       # a landmark, and a record of what every key was
loom accept rl-0004 --proofs                    # record what you have checked; later edits show up as stale
loom annotate rl-0004/proof "Why closed?" --quote "the diagonal is closed"
loom library add ~/papers/manolache.pdf         # a paper you read or cite, kept in the quilt's library
loom ai init                                    # the optional AI layer: orientation, rules, modes, permissions, and what starts the loom MCP server
```

Every command is described in [docs/cli-reference.md](docs/cli-reference.md), generated from the command tree. `loom <command> --help` says the same.

## What a quilt is

An ordinary LaTeX project loom can read: the documents you are working on, laid out as you like, and three macros from `loom.sty` that print nothing (`\uses`, `\incomplete`, `\nest`). Each document compiles with plain `pdflatex` from its own directory, and on Overleaf. Loom changes a file of yours only when you ask it to, and keeps what it replaces first (`docs/design/writes.md`). Everything loom keeps lies in `.loom/`, in a folder for each kind: `records/` (the acceptance ledger, the history of every key with its landmarks, the annotations and the suggested edits), `library/` (the works you read and cite, a file each, and the documents you gave them), `agents/` (what agents are told, their sessions, copies and scratch), `local/` (this machine's state) and `cache/` (everything derived), beside `format`, the layout's number.

## Layout of this repository

- `src/loom/scan/` reads a quilt (files, macros, environments, sections, ids, edges, lint, hashing).
- `src/loom/records/` holds the acceptance ledger, snapshots, annotations, and the computed states.
- `src/loom/history/` holds the history: the ledger of steps, the versions of every key, and the checks over them.
- `src/loom/render/` publishes the build directory the viewer reads (fragments, manifest, threads, serve).
- `src/loom/tex/` wraps latexmk, reads `.aux` files, builds bundles, and runs the identity test.
- `src/loom/reshape/` is `id`, `import`, `atomize`, `linearize` and `deloom`; `src/loom/library/` is the library, its nodes, the intake and gathering; `src/loom/ai/` is the AI layer.
- `src/loom/assets/` ships `loom.sty`, the demo quilt, the AI-layer templates, and the built viewer.

## Development

- `uv run pytest` runs the unit tier against a fake TeX toolchain in seconds; `uv run pytest -m tex` runs the TeX tier against your real TeX Live in an isolated environment; `LOOM_PAPER_FIXTURES=... uv run pytest -m paper` runs the paper tier.
- `uv run ruff check src tests` and `uv run mypy` must be clean.
- `scripts/vendor_viewer.py ../viewer/build` refreshes the vendored viewer after building it; `scripts/gen_cli_reference.py` regenerates `docs/cli-reference.md` (a test fails when it is stale).
- `docs/RELEASE.md` is the release checklist; it stops before publishing.

## License

GPL-3.0-or-later. Files under `src/loom/assets/` (`loom.sty`, the demo quilt, the AI-layer templates) are MIT so they can travel with your paper. See `LICENSE` and `NOTICE`.
