"""The dependency graph from the command line: `search`, `deps`, `downstream`, and the refusal of `delete`."""

from __future__ import annotations

import shutil
from pathlib import Path

from tests.helpers import json_of, ok, refused
from tests.unit._quilts import demo

SYNTHETIC = Path(__file__).resolve().parents[1] / "quilts" / "synthetic"


def test_deps_prints_see_also(tmp_path: Path) -> None:
    """`deps` reports relations in a final section marked not-a-dependency, and `--json` carries them beside the closure (plan 0.2 §2.2)."""
    q = tmp_path / "syn"
    shutil.copytree(SYNTHETIC, q)
    r = ok("deps", "sy-0008", cwd=q)
    assert "see also, not a dependency (1)" in r.output
    assert "sy-0009" in r.output.split("see also, not a dependency (1)")[1]

    payload = json_of("deps", "sy-0009", "--json", cwd=q)
    assert payload["relations"] == [{"key": "sy-0008", "kind": "see"}]  # both directions are reported
    assert all(e["key"] != "sy-0008" for e in payload["closure"])  # and a relation is not in the closure


def test_search_deps_downstream_delete(tmp_path: Path) -> None:
    q = demo(tmp_path)
    entries = json_of("search", "orbits", "--json", cwd=q)["matches"]
    assert entries[0]["key"] == "dm-0002" and "lem:orbits" in entries[0]["aliases"]
    found = ok("search", "lem:orbits", cwd=q).output.splitlines()
    assert found[0] == "1 match for 'lem:orbits'" and found[2] == "in your documents (1)"
    assert found[3].split()[-1] == "dm-0002"  # the key last on its row
    payload = json_of("deps", "dm-0003", "--json", cwd=q)
    # \cite[Proposition 3.2]{Calloway14} names a work, no node
    assert [e["key"] for e in payload["proof"]] == ["dm-0002"]
    assert payload["closure"] == [{"key": "dm-0003"}]
    dp = ok("deps", "dm-0003/proof", "--closure", cwd=q)
    assert dp.output.splitlines()[2] == "closure, dependencies first (2)"
    assert {tuple(ln.split()) for ln in dp.output.splitlines()[3:]} == {("Lemma", "dm-0002"), ("Theorem", "dm-0003")}
    up = json_of("downstream", "dm-0001", "--json", cwd=q)
    assert {x["key"] for x in up["dependents"]} == {"dm-0002/proof", "dm-0005/proof"}
    assert any(i["file"] == "drafting/main.tex" for i in up["inclusions"])
    assert "nothing was changed" in ok("downstream", "dm-0001", cwd=q).output.splitlines()[0]
    before = sorted(p.relative_to(q).as_posix() for p in q.rglob("*"))
    for name in ("delete", "rm", "remove"):
        r = refused(name, "dm-0001", cwd=q, code=2, match="loom will not delete your notes")
        assert "loom downstream dm-0001" in r.output
    assert sorted(p.relative_to(q).as_posix() for p in q.rglob("*")) == before
    refused("deps", "dm-9999", cwd=q, code=2, match="no such key: dm-9999")


def test_downstream_reports_the_ledger_and_the_annotations_it_heads(tmp_path: Path) -> None:
    """`downstream` lists a node's ledger rows and the annotations on it; `annotations: (none)` on a reviewed node would say it was never reviewed (F13)."""
    q = demo(tmp_path)
    ok("annotate", "dm-0002", "Which orbits?", "--as", "Tom", cwd=q)

    payload = json_of("downstream", "dm-0002", "--json", cwd=q)
    assert [r["key"] for r in payload["ledger"]] == ["dm-0002", "dm-0002/proof"]  # the statement and its proof
    (a,) = payload["annotations"]
    assert a["message"] == "Which orbits?" and a["target"] == "dm-0002" and a["status"] == "open" and a["type"] is None

    text = ok("downstream", "dm-0002", cwd=q).output
    assert "Which orbits?" in text
    assert "annotations:\n  (none)" not in text


def test_deps_closure_names_what_the_proof_adds_so_it_agrees_with_source(tmp_path: Path) -> None:
    """The re-grade: `deps dm-0003 --closure` said "depends on nothing" right after `deps dm-0003` listed a result, while `source dm-0003 --closure` printed more. The statement closure stays what `--closure` is; what the proofs add is listed apart, and the two together are what `source` prints."""
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from loom.tex.bundle import build_bundle

    q = demo(tmp_path)
    r = ok("deps", "dm-0003", "--closure", cwd=q)
    said = " ".join(r.stdout.split())
    assert "depends on nothing" not in said
    assert (
        "dm-0003's statement depends on no other statement; its proof adds 1, which loom source dm-0003 --closure prints with it"
        in said
    )
    payload = json_of("deps", "dm-0003", "--closure", "--json", cwd=q)
    listed = [e["key"] for e in payload["closure"] + payload["proof_closure"] if e["key"] != "dm-0003"]
    assert sorted(listed) == sorted(build_bundle(scan(load_quilt(q)), "dm-0003").closure)


def test_deps_and_downstream_say_how_in_the_readers_words(tmp_path: Path) -> None:
    """T4: `deps` said `via uses,ref` and `via postnote`, `downstream` said `via transitive`; T2: two references on one line printed as identical rows."""
    q = demo(tmp_path)
    deps = ok("deps", "dm-0003", cwd=q).stdout
    assert "listed in \\uses" in deps and "via " not in deps, deps
    proof = q / "drafting" / "nodes" / "dm-0003.tex"
    proof.write_text(
        proof.read_text().replace("By Lemma~\\ref{lem:orbits}", "By Lemma~\\ref{lem:orbits} (that is, \\ref{dm-0002})")
    )
    down = ok("downstream", "dm-0002", cwd=q).stdout
    rows = [ln for ln in down.splitlines() if "drafting/nodes/dm-0003.tex:" in ln]
    assert len(rows) == len(set(rows)) >= 2 and any("lem:orbits" in r for r in rows), down
    assert "via transitive" not in down and "transitive" not in down


def test_downstream_lists_its_dependents_in_the_order_of_their_keys(tmp_path: Path) -> None:
    """The same quilt prints the same rows whatever the process's hash seed: the graph's walk starts from a set, so the rows are sorted."""
    q = tmp_path / "q"
    shutil.copytree(Path(__file__).parents[1] / "quilts" / "synthetic", q)
    keys = [d["key"] for d in json_of("downstream", "sy-0002", "--json", cwd=q)["dependents"]]
    assert keys == ["sy-0004", "sy-0005", "sy-0009", "sy-0009/proof"]
