"""Wall time of each named step of one `build()`, unprofiled.

    python parts.py QUILT [--cache-git] [--reuse] [--no-tex]
    python parts.py QUILT --save REL [--n N] [--records] [--no-tex]

With `--save`, as `loom serve` builds: a warm-up build, then N saves, each a word never written before at the start of the second line of a proof in REL (the middle one of those over 400 characters, read from the published manifest), each followed by the build a save starts, all in one process, so what one build keeps in memory the next finds; `--records` follows each with a records-only build from that build's scan, as an annotation through the viewer starts. Pins come from `PIN_CODE` and `PIN_SNIP` (`probe.pin_code`).
"""

from __future__ import annotations

import collections
import functools
import json
import os
import random
import string
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import probe  # noqa: E402

TIMES: dict[str, list[float]] = collections.defaultdict(list)
DEPTH = threading.local()


def timed(mod, name, label=None):  # type: ignore[no-untyped-def]
    f = getattr(mod, name)
    label = label or f"{mod.__name__.split('.')[-1]}.{name}"

    @functools.wraps(f)
    def w(*a, **kw):  # type: ignore[no-untyped-def]
        t = time.perf_counter()
        try:
            return f(*a, **kw)
        finally:
            TIMES[label].append(time.perf_counter() - t)

    setattr(mod, name, w)
    return w


def a_proof(q: Path, rel: str) -> tuple[int, int]:
    from loom.paths import SITE

    keys = json.loads((q / SITE / "manifest.json").read_text())["keys"].values()
    proofs = [k["src"] for k in keys if k.get("file") == rel and k.get("kind") == "proof" and k["src"][1] - k["src"][0] > 400]
    return proofs[len(proofs) // 2]


def save(q: Path, rel: str, span: tuple[int, int]) -> None:
    p = q / rel
    text = p.read_text(encoding="utf-8")
    at = text.index("\n", span[0], span[1]) + 1
    word = "".join(random.choices(string.ascii_lowercase, k=11))
    p.write_text(f"{text[:at]}Bench {word}. {text[at:]}", encoding="utf-8")


def show(title: str, total: float) -> None:
    print(f"{title}: total {total:.2f}s load={os.getloadavg()[0]:.2f}")
    stages, last = probe.stage_summary()
    if last:
        stages.append((last[0], last[1], time.perf_counter() - probe.T0 - last[1]))
    print("  stages: " + ", ".join(f"{name} {took:.2f}s" for name, _, took in stages))
    probe.STAGES.clear()
    for k, v in sorted(TIMES.items(), key=lambda kv: -sum(kv[1])):
        print(f"  {sum(v):7.2f}s  x{len(v):<4d} {k}")


def main() -> None:
    q = Path(sys.argv[1]).resolve()
    tex = "--no-tex" not in sys.argv
    probe.cache_git()
    import loom.adopt as AD
    import loom.config_edit as CE
    import loom.draft_lifecycle as DL
    import loom.files as FI
    import loom.records.store as RS
    import loom.render.attach as AT
    import loom.render.build as B
    import loom.render.changes as CH
    import loom.render.compiles as CO
    import loom.render.fragments as FR
    import loom.render.fromhtml as FH
    import loom.render.incoming as IN
    import loom.render.pending as PE
    import loom.render.review_compare as RC
    import loom.render.threads as TH
    import loom.review_queue as RQ
    import loom.scan.owners as OW
    import loom.scan.scan as SC
    import loom.section_drafts as SD
    from loom.scan.quilt import load_quilt

    for mod, name in [
        (B, "scan"), (B, "freeze_moved"), (B, "gone_annotations"), (B, "_marks_by_node"), (B, "load_history"), (B, "load_canon"),
        (B, "build_manifest"), (B, "attach_versions"), (B, "publish"), (B, "_attach_spans"), (B, "_write_source"), (B, "_write_transcripts"),
        (B, "read_index"), (B, "write_index"), (B, "_input_hash"), (B, "read_numbers"), (B, "read_cite_labels"),
        (SC, "landmark_documents"), (FH, "page_for"), (RS.Records, "apply"), (RS.Records, "resolved"), (RS.Records, "__init__"),
        (DL, "attach_closed"), (SD, "attach_context"), (RC, "attach_comparisons"), (IN, "attach_incoming"), (IN, "attach_adoptions"),
        (PE, "attach_pending"), (RQ, "rows_for"), (FI, "attach_files"), (OW, "stamped"), (AD, "_flat_shape"), (CO, "compile_problems"),
        (CE, "published"), (TH, "last_active"), (CH, "preview_html"), (CH, "_shaped"),
        (FR.FragmentRenderer, "prepare"), (FR._Previews, "make"),
    ]:
        timed(mod, name)
    AT.ATTACH = tuple(timed(sys.modules[f.__module__], f.__name__, f"attach:{f.__module__.split('.')[-1]}") for f in AT.ATTACH)
    B.ATTACH = AT.ATTACH
    quilt = load_quilt(q)
    if "--save" not in sys.argv:
        reuse = None
        if "--reuse" in sys.argv:
            reuse = SC.scan(quilt)
            TIMES.clear()
        t = time.perf_counter()
        r = B.build(quilt, reuse=reuse, progress=probe.told, tex=tex)
        show(f"rendered={len(r.rendered)} skipped={len(r.skipped)}", time.perf_counter() - t)
        print("  subprocesses:", probe.proc_summary(probe.PROCS))
        return
    rel = sys.argv[sys.argv.index("--save") + 1]
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 2
    t = time.perf_counter()
    report = B.build(quilt, progress=probe.told, tex=tex)
    print(f"warm-up build {time.perf_counter() - t:.2f}s")
    probe.STAGES.clear()
    span = a_proof(q, rel)
    for i in range(n):
        TIMES.clear()
        probe.STAGES.clear()
        save(q, rel, span)
        p0 = len(probe.PROCS)
        t = time.perf_counter()
        report = B.build(load_quilt(q), progress=probe.told, tex=tex)
        show(f"save {i} rendered={len(report.rendered)}", time.perf_counter() - t)
        print("  subprocesses:", probe.proc_summary(probe.PROCS[p0:]))
        if "--records" in sys.argv:
            TIMES.clear()
            t = time.perf_counter()
            B.build(load_quilt(q), reuse=report.result, progress=probe.told, tex=tex)
            show(f"records-only after save {i}", time.perf_counter() - t)
        report = report.kept()


if __name__ == "__main__":
    main()
