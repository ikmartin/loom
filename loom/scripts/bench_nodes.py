#!/usr/bin/env python3
"""Measure the library's node store at the size of a large quilt: a store of 5,000 nodes made in a temporary folder, the index built cold, each question it answers, the update after one file changes and after none, a full check, and the memory and disk it takes.

The store is synthetic and reproducible: 250 works, each a reference, its macros, twelve statements and six proofs, with edges inside a work, citations and stubs across works, anchors, and words drawn from a fixed vocabulary. HOME and the XDG directories point into the temporary folder, which is removed at the end unless `--keep` is given.

    uv run python scripts/bench_nodes.py [--works N] [--repeat N] [--keep]

Each time is the median of `--repeat` runs, in milliseconds; memory is the process's peak resident size and the Python heap's peak while the index is built.
"""

from __future__ import annotations

import argparse
import os
import random
import resource
import shutil
import statistics
import sys
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loom.library.ids import mint_proof
from loom.library.node import Node, file_name, node_bytes
from loom.scan.labels import base36_encode

PREFIX = "tq"
TAXA = ("definition", "lemma", "proposition", "theorem", "corollary", "remark", "example", "lemma")
WORDS = (
    "compact set bounded closed open measure integral sequence converges uniformly continuous function space norm "
    "operator linear bounded spectrum eigenvalue Hilbert Banach manifold smooth curvature geodesic metric complete "
    "separable dense subset group ring module ideal field extension algebraic prime finite infinite countable "
    "partition cover widget boundary interior estimate inequality triangle diameter radius ball sphere torus "
    "homotopy homology cohomology sheaf scheme variety morphism functor category limit colimit adjoint natural "
    "transformation isomorphism embedding immersion fibration bundle section connection holonomy flow vector "
    "tangent cotangent differential form exact closed harmonic Laplacian elliptic parabolic hyperbolic regularity "
    "Sobolev weak solution existence uniqueness stability perturbation small large positive negative constant "
    "random variable expectation variance martingale Brownian motion stopping time filtration probability graph "
    "vertex edge path cycle tree planar coloring matching flow cut chromatic polynomial generating series"
).split()


def stem(n: int) -> str:
    return f"{PREFIX}-{base36_encode(n)}"


def sentence(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(n)).capitalize() + "."


def make_store(folder: Path, works: int, rng: random.Random) -> int:
    """Write the synthetic store into `folder` and return how many nodes it holds."""
    folder.mkdir(parents=True, exist_ok=True)
    counter = iter(range(1, 36**4))
    refs = [stem(next(counter)) for _ in range(works)]
    nodes: list[Node] = []
    statements: dict[str, list[str]] = {}
    for i, ref in enumerate(refs):
        key = f"Auth{i:03d}{2000 + i % 25}"
        entry = (
            f"@article{{{key},\n  author = {{Author{i}, A. and Coauthor{i % 37}, B.}},\n"
            f"  title  = {{{sentence(rng, 6)[:-1]}}},\n  year   = {{{2000 + i % 25}}},\n}}\n"
        )
        nodes.append(Node(id=f"{ref}-ref", taxon="reference", body=entry))
        nodes.append(
            Node(
                id=f"{ref}-macros",
                taxon="macros",
                body="\\usepackage{amssymb}\n\\newcommand{\\Wid}{\\mathcal{W}}\n\\DeclareMathOperator{\\diam}{diam}\n",
            )
        )
        statements[ref] = [stem(next(counter)) for _ in range(12)]
    for i, ref in enumerate(refs):
        own = statements[ref]
        for k, sid in enumerate(own):
            other = refs[(i + 1 + k) % len(refs)]
            stub = k == 11 and i % 2 == 0
            earlier = own[:k]
            uses = sorted(rng.sample(earlier, min(len(earlier), rng.randint(0, 2))))
            body = (
                ""
                if stub
                else " ".join(
                    [sentence(rng, rng.randint(8, 20)) for _ in range(rng.randint(2, 5))]
                    + [f"By \\ref{{{u}}}." for u in uses]
                    + [f"\\begin{{equation}}\\label{{{sid}-eq00}} x \\le \\diam W \\end{{equation}}"]
                )
                + ("\n" if not stub else "")
            )
            nodes.append(
                Node(
                    id=sid,
                    taxon=TAXA[k % len(TAXA)],
                    number=f"{1 + k // 4}.{1 + k % 4}",
                    title=sentence(rng, 2)[:-1] if k % 3 == 0 else None,
                    source=f"{ref}-ref",
                    label=f"lem:{k}" if not stub else None,
                    pages=str(3 + k),
                    uses=tuple(uses) if not stub else (),
                    body=body,
                )
            )
            if k % 2 == 0 and not stub:
                cited = statements[other][rng.randint(0, 11)]
                proof_uses = sorted({*uses, cited})
                nodes.append(
                    Node(
                        id=mint_proof(sid, []),
                        taxon="proof",
                        source=f"{ref}-ref",
                        pages=f"{3 + k}-{4 + k}",
                        uses=tuple(proof_uses),
                        mentions=(f"{other}-ref",),
                        body=" ".join(sentence(rng, rng.randint(10, 30)) for _ in range(rng.randint(3, 8)))
                        + f" The estimate of \\ref{{{cited}}} and \\eqref{{{sid}-eq00}} give it; compare \\cite{{{other}-ref}}.\n",
                    )
                )
    for node in nodes:
        (folder / file_name(node.id)).write_bytes(node_bytes(node))
    return len(nodes)


def timed(fn: Callable[[], Any], repeat: int) -> tuple[Timing, Any]:
    """The medians of `repeat` runs of `fn`, wall and processor time in milliseconds, and its last result."""
    walls, cpus = [], []
    result = None
    for _ in range(repeat):
        wall, cpu = time.perf_counter(), time.process_time()
        result = fn()
        walls.append((time.perf_counter() - wall) * 1000)
        cpus.append((time.process_time() - cpu) * 1000)
    return Timing(statistics.median(walls), statistics.median(cpus)), result


class Timing(tuple[float, float]):
    """Wall and processor milliseconds; processor time is what a busy machine changes least."""

    def __new__(cls, wall: float, cpu: float) -> Timing:
        return super().__new__(cls, (wall, cpu))


def peak_rss_mb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024


def write_tags(root: Path, rng: random.Random, count: int) -> None:
    """`count` tag lines on random statements, from forty tags, as the log holds them."""
    import json

    from loom.paths import LIBRARY_NODES, TAG_LOG

    names = sorted(p.name.removesuffix(".node") for p in (root / LIBRARY_NODES).glob("*.node"))
    statements = [n for n in names if n.count("-") == 1]
    (root / TAG_LOG).parent.mkdir(parents=True, exist_ok=True)
    with (root / TAG_LOG).open("w", encoding="utf-8") as fh:
        for _ in range(count):
            event = {
                "event": "tag",
                "node": rng.choice(statements),
                "tag": f"topic-{rng.randint(1, 40)}",
                "by": "Bench",
                "kind": "person",
                "at": "2026-11-21T00:00:00Z",
            }
            fh.write(json.dumps(event, sort_keys=True) + "\n")


def phase(name: str, root: Path, repeat: int) -> dict[str, Any]:
    """One phase, run in a process of its own so that its peak memory is its own."""
    from loom.library.checks import check
    from loom.library.index import NodeIndex
    from loom.library.node import Node
    from loom.library.store import write_node
    from loom.paths import LIBRARY_NODES, NODE_INDEX

    out: dict[str, Any] = {}
    if name == "cold":
        tracemalloc.start()
        start, cpu = time.perf_counter(), time.process_time()
        with NodeIndex.open(root) as index:
            out["nodes"] = index.count()
        out["cold build ms"] = Timing((time.perf_counter() - start) * 1000, (time.process_time() - cpu) * 1000)
        out["python heap peak MB"] = tracemalloc.get_traced_memory()[1] / (1024 * 1024)
        tracemalloc.stop()
        out["index on disk MB"] = (root / NODE_INDEX).stat().st_size / (1024 * 1024)
    elif name == "questions":
        out["open, nothing changed ms"], _ = timed(lambda: NodeIndex.open(root).close(), repeat)
        with NodeIndex.open(root) as index:
            ref = index.db.execute(
                "SELECT id FROM nodes WHERE kind = 'reference' ORDER BY id LIMIT 1 OFFSET 100"
            ).fetchone()[0]
            statement = index.work(ref)[3].id
            used = index.db.execute(
                "SELECT dst FROM edges WHERE kind = 'uses' GROUP BY dst ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()[0]
            questions: dict[str, Callable[[], Any]] = {
                "node by id": lambda: index.node(statement),
                "a work's nodes in order": lambda: index.work(ref),
                "what a node uses": lambda: index.uses(statement),
                "what a node mentions": lambda: index.mentions(statement),
                "what uses a node": lambda: index.used_by(used),
                "a statement's proofs": lambda: index.proofs(statement),
                "all stubs": lambda: index.stubs(),
                "search one word": lambda: index.search("compact"),
                "search three words": lambda: index.search("compact bounded sequence"),
                "search a prefix": lambda: index.search("homo"),
                "search a number": lambda: index.search("2.3"),
                "search words in one work": lambda: index.search("compact", work=ref),
                "search words and proofs": lambda: index.search("compact bounded", proofs=True),
                "search by taxon alone": lambda: index.search(taxon="lemma", limit=500),
                "search by tag": lambda: index.search(tag="topic-7"),
                "nodes with a tag": lambda: index.tagged("topic-7"),
                "a node's tags": lambda: index.tags(statement),
                "tags in use": lambda: index.tags_in_use(),
            }
            for label, fn in questions.items():
                ms, result = timed(fn, repeat * 4)
                size = len(result) if isinstance(result, list) else 1
                out[f"{label} ms ({size})"] = ms
    elif name == "update":
        folder = root / LIBRARY_NODES
        with NodeIndex.open(root) as index:
            ref = index.db.execute(
                "SELECT id FROM nodes WHERE kind = 'reference' ORDER BY id LIMIT 1 OFFSET 50"
            ).fetchone()[0]
            target = index.work(ref)[2].id
            node = index.node(target)
            assert node is not None
            statement_path, ref_path = folder / f"{target}.node", folder / f"{ref}.node"
            counter = iter(range(10**6))

            def one_statement() -> Any:
                text = statement_path.read_text(encoding="utf-8")
                statement_path.write_text(text + f"Added {next(counter)}.\n", encoding="utf-8")
                return index.refresh()

            def one_work() -> Any:
                ref_path.write_text(ref_path.read_text(encoding="utf-8") + f"% {next(counter)}\n", encoding="utf-8")
                return index.refresh()

            out["update after one statement changes ms"], done = timed(one_statement, repeat)
            assert done.changed == 1, done
            out["update after a work's entry changes ms"], _ = timed(one_work, repeat)
            ref_path.write_text(ref_path.read_text(encoding="utf-8").split("% ")[0], encoding="utf-8")
            index.refresh()
            then = time.time() - 3600
            for p in folder.iterdir():
                os.utime(p, (then, then))
            index.refresh()
            time.sleep(2.1)
            out["update when nothing changed ms"], done = timed(index.refresh, repeat)
            out["files read when nothing changed"] = done.read
        fresh = Node(id="tq-ZZZ0", taxon="remark", source=f"{ref}", pages="9", body="A new remark on compact sets.\n")
        out["write one node (checked, locked, indexed) ms"], _ = timed(lambda: write_node(root, fresh), repeat)
    elif name == "check":
        out["check the whole store ms"], diags = timed(lambda: check(root), max(1, repeat // 2))
        out["check failures"] = len(diags)
    out["peak RSS MB"] = peak_rss_mb()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--works", type=int, default=250)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--phase", help=argparse.SUPPRESS)
    ap.add_argument("--root", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.phase:
        import json

        print(json.dumps(phase(args.phase, Path(args.root), args.repeat)))
        return
    scratch = Path(tempfile.mkdtemp(prefix="loom-bench-nodes-"))
    for var, sub in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data")):
        (scratch / sub).mkdir()
        os.environ[var] = str(scratch / sub)
    try:
        run(scratch / "q", args)
    finally:
        if args.keep:
            print(f"kept {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


def run(root: Path, args: argparse.Namespace) -> None:
    import json
    import subprocess

    from loom.paths import LIBRARY_NODES

    rng = random.Random(0)
    count = make_store(root / LIBRARY_NODES, args.works, rng)
    write_tags(root, rng, 2000)
    size = sum(p.stat().st_size for p in (root / LIBRARY_NODES).iterdir()) / (1024 * 1024)
    print(
        f"store: {count} nodes, {size:.1f} MB of files, 2000 tag lines; times are medians of {args.repeat} runs (questions of {args.repeat * 4})"
    )
    for name in ("cold", "questions", "update", "check"):
        got = subprocess.run(
            [sys.executable, __file__, "--phase", name, "--root", str(root), "--repeat", str(args.repeat)],
            capture_output=True, text=True, check=True,
        )  # fmt: skip
        print(f"\n{name}:")
        for label, value in json.loads(got.stdout).items():
            if isinstance(value, list):
                print(f"  {label:<52} {value[0]:>10.1f} {value[1]:>10.1f}")
            elif isinstance(value, float):
                print(f"  {label:<52} {value:>10.1f}")
            else:
                print(f"  {label:<52} {value:>10}")


if __name__ == "__main__":
    main()
