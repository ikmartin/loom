"""What `.loom/` keeps and for how long: the sweep after a build, the scratch's and the saved previews' expiry, one `biber` for the machine, and the sizes `loom doctor` reports."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import replace
from pathlib import Path

import pytest

from loom import lifetimes
from loom.lifetimes import DAY, FRESH, KEEP_DAYS, built, condemn, drop_preview, sweep
from loom.paths import (
    ADOPTION_PREVIEWS,
    AGENTS,
    CACHE,
    INCORPORATION_PREVIEWS,
    LIBRARY,
    LOCAL,
    RECORDS,
    SCRATCH,
    SESSIONS,
    document_build,
)
from loom.scan.quilt import load_quilt
from loom.scan.scan import scan
from tests.helpers import flat, ok, run
from tests.unit._quilts import demo

#: Two days ago: older than `FRESH`, younger than `KEEP_DAYS`.
OLD = time.time() - 2 * DAY


def _plant(path: Path, data: bytes = b"x", when: float = OLD) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.utime(path, (when, when))
    return path


def _age(folder: Path, when: float = OLD) -> None:
    """Every file and folder under `folder` written at `when`, so only what names it can keep it."""
    for p in [*folder.rglob("*"), folder]:
        os.utime(p, (when, when), follow_symlinks=False)


def _age_folders(folder: Path, when: float = OLD) -> None:
    """Every folder under `folder` last written at `when`, as a folder nobody has added to since is."""
    for p in [*folder.rglob("*"), folder]:
        if p.is_dir() and not p.is_symlink():
            os.utime(p, (when, when))


def _files(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() or p.is_symlink()}


# ---- the sweep after a build ------------------------------------------------------------------------------------------


def test_a_build_removes_what_it_does_not_name_keeps_what_it_does_and_touches_no_other_kind(tmp_path: Path) -> None:
    """A file of each folder under `cache/` that nothing names, and the compile folder of a document that is gone, are removed by the next build; every file the build names is still there, and so is a file in every other kind."""
    q = demo(tmp_path)
    ok("build", cwd=q)
    cache = q / CACHE
    _age(cache)
    result = scan(load_quilt(q))
    master = result.masters[0]
    key = next(k for k, n in result.nodes.items() if n.kind == "environment")
    from loom.tex.bundle import bundle_filename

    closure = bundle_filename(key).removesuffix(".tex")
    unnamed = [
        "stray.txt",
        "site/fragments/nodes/planted.html",
        "site/source/planted.tex",
        "site/svg/0123456789abcdef.svg",
        "site/compare/0123.html",
        "site/draft-previews/0123/paper.pdf",
        "site/incorporation-review/" + "0" * 64 + "-1-0.html",
        "site/elsewhere/x.json",
        "blocks/snippets/0123.html",
        "blocks/snippets/pictures/0123.svg",
        "blocks/previews/0123.html",
        "blocks/spans/0123.json",
        f"{document_build('gone/paper.tex').removeprefix(CACHE + '/')}/paper.pdf",
        f"{document_build('gone/paper.tex').removeprefix(CACHE + '/')}/html/paper.html",
        "closures/no-such-key.tex",
        "closures/no-such-key/no-such-key.pdf",
        "crops/0123456789abcdef-p1-0123456789abcdef.png",
        "marks/boxes/0123456789abcdef/0001.xml",
        "marks/refound/0123.json",
        "library/boxes/doi/no-such-work/0001.xml",
        "library/resolve/0123.json",
    ]
    long_ago = time.time() - (KEEP_DAYS + 1) * DAY
    for rel in unnamed:
        _plant(cache / rel, when=long_ago if rel.startswith(("site/compare", "site/draft-previews")) else OLD)
    token = "1" * 64
    kept = [
        "site/compare/recent.html",
        f"site/incorporation-review/{token}-1-0.html",
        f"{document_build(master).removeprefix(CACHE + '/')}/planted.log",
        f"closures/{closure}.tex",
        f"closures/{closure}/{closure}.pdf",
    ]
    for rel in kept:
        _plant(cache / rel)
    _plant(q / INCORPORATION_PREVIEWS / f"{token}.json", b"{}")
    elsewhere = [f"{kind}/planted.txt" for kind in (RECORDS, LIBRARY, AGENTS, LOCAL)] + [f"{SESSIONS}/s-x/planted.txt"]
    for rel in elsewhere:
        _plant(q / rel)
    _age_folders(cache)
    before = _files(cache)

    ok("build", cwd=q)

    after = _files(cache)
    assert not [rel for rel in unnamed if rel in after]
    assert not (cache / document_build("gone/paper.tex").removeprefix(CACHE + "/")).exists()
    assert not (cache / "closures/no-such-key").exists() and not (cache / "site/elsewhere").exists()
    assert all(rel in after for rel in kept)
    assert all((q / rel).is_file() for rel in elsewhere)
    named = built(q)
    # every file the build names is there, and every file that was there and is named still is
    on_disk = {rel for rel in named if not rel.startswith("@") and (cache / rel).is_file()}
    assert {rel for rel in before if rel in named} <= on_disk
    assert {"index.json", "site/manifest.json"} <= on_disk
    assert any(rel.startswith("site/fragments/") for rel in on_disk)


def test_a_build_that_fails_sweeps_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    planted = _plant(q / CACHE / "blocks/snippets/0123.html")
    from loom.render import build as build_mod

    def broken(*_a: object, **_k: object) -> None:
        raise RuntimeError("the publish broke")

    monkeypatch.setattr(build_mod, "publish", broken)
    with pytest.raises(RuntimeError):
        ok("build", cwd=q)
    assert planted.is_file()


def test_a_build_of_some_keys_sweeps_nothing(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    planted = _plant(q / CACHE / "blocks/snippets/0123.html")
    key = next(k for k, n in scan(load_quilt(q)).nodes.items() if n.kind == "environment")
    ok("build", "--keys", key, cwd=q)
    assert planted.is_file()


def test_a_file_just_written_stays_though_nothing_names_it(tmp_path: Path) -> None:
    """Whatever wrote it, a build in another process or a step a viewer is about to fetch, may not have named it yet."""
    q = demo(tmp_path)
    ok("build", cwd=q)
    fresh = _plant(q / CACHE / "blocks/snippets/fresh.html", when=time.time())
    result = scan(load_quilt(q))
    sweep(q, result)
    assert fresh.is_file()
    sweep(q, result, now=time.time() + FRESH + 1)
    assert not fresh.exists()


def test_the_sweep_follows_no_link_and_removes_nothing_through_a_cache_that_is_one(tmp_path: Path) -> None:
    """A link under the cache is removed itself, never what it points at; a cache folder that is a link is not swept at all."""
    q = demo(tmp_path)
    ok("build", cwd=q)
    result = scan(load_quilt(q))
    target = _plant(q / RECORDS / "kept.txt")
    outside = _plant(tmp_path / "outside" / "file.txt")
    link = q / CACHE / "blocks/snippets/link.html"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    folder_link = q / CACHE / "blocks/elsewhere"
    folder_link.symlink_to(outside.parent, target_is_directory=True)
    for p in (link, folder_link):
        os.utime(p, (OLD, OLD), follow_symlinks=False)
    sweep(q, result)
    assert not link.is_symlink() and not folder_link.is_symlink()
    assert target.is_file() and outside.is_file()

    # a cache that leads out of the quilt
    away = tmp_path / "away"
    (q / CACHE).rename(away)
    (q / CACHE).symlink_to(away, target_is_directory=True)
    stray = _plant(away / "blocks/snippets/0123.html")
    sweep(q, result, now=time.time() + DAY)
    assert stray.is_file()


# ---- the scratch and the saved previews -------------------------------------------------------------------------------


def _session(q: Path, sid: str, when: float) -> Path:
    """A session that last wrote at `when`: its run log and a file in its scratch."""
    _plant(q / SESSIONS / sid / "run.log", b"loom status\n", when)
    scratch = _plant(q / SCRATCH / sid / "work" / "big.aux", b"aux", when)
    _age(q / SESSIONS / sid, when)
    _age(q / SCRATCH / sid, when)
    return scratch


def test_a_scratch_is_kept_thirteen_days_after_its_session_last_wrote_and_removed_at_fifteen(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    result = scan(load_quilt(q))
    now = time.time()
    _session(q, "s-old", now - 20 * DAY)
    sweep(q, result, now=now - 7 * DAY)  # thirteen days after
    assert (q / SCRATCH / "s-old").is_dir()
    sweep(q, result, now=now - 5 * DAY)  # fifteen days after
    assert not (q / SCRATCH / "s-old").exists()
    assert (q / SESSIONS / "s-old" / "run.log").is_file()


def test_a_session_still_writing_keeps_an_old_scratch(tmp_path: Path) -> None:
    """Its run log, or any file in its session's directory, is a write of the session's."""
    q = demo(tmp_path)
    ok("build", cwd=q)
    result = scan(load_quilt(q))
    now = time.time()
    _session(q, "s-busy", now - 30 * DAY)
    _plant(q / SESSIONS / "s-busy" / "notes.md", b"still here", now - DAY)
    _session(q, "s-scratching", now - 30 * DAY)
    _plant(q / SCRATCH / "s-scratching" / "today.tex", b"%", now - DAY)
    sweep(q, result, now=now)
    assert (q / SCRATCH / "s-busy" / "work" / "big.aux").is_file()
    assert (q / SCRATCH / "s-scratching" / "work" / "big.aux").is_file()


def test_a_result_with_no_session_goes_fourteen_days_after_it_was_written(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    result = scan(load_quilt(q))
    now = time.time()
    old = _plant(q / SCRATCH / "none" / "old-result.txt", b"x", now - 15 * DAY)
    young = _plant(q / SCRATCH / "none" / "young-result.txt", b"x", now - 13 * DAY)
    os.utime(q / SCRATCH / "none", (now - 15 * DAY, now - 15 * DAY))
    sweep(q, result, now=now)
    assert not old.exists() and young.is_file() and (q / SCRATCH / "none").is_dir()


def test_removing_a_scratch_removes_a_link_in_it_and_not_what_it_points_at(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    now = time.time()
    _session(q, "s-linked", now - 20 * DAY)
    target = _plant(tmp_path / "theirs" / "keep.txt")
    link = q / SCRATCH / "s-linked" / "theirs"
    link.symlink_to(target.parent, target_is_directory=True)
    os.utime(link, (now - 20 * DAY, now - 20 * DAY), follow_symlinks=False)
    os.utime(q / SCRATCH / "s-linked", (now - 20 * DAY, now - 20 * DAY))
    sweep(q, scan(load_quilt(q)), now=now)
    assert not (q / SCRATCH / "s-linked").exists() and target.is_file()


def test_a_saved_preview_goes_when_applied_or_fourteen_days_after_it_was_written(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    now = time.time()
    old = _plant(q / ADOPTION_PREVIEWS / f"{'a' * 64}.json", b"{}", now - 15 * DAY)
    young = _plant(q / INCORPORATION_PREVIEWS / f"{'b' * 64}.json", b"{}", now - 13 * DAY)
    applied = _plant(q / ADOPTION_PREVIEWS / f"{'c' * 64}.json", b"{}", now)
    sweep(q, scan(load_quilt(q)), now=now)
    assert not old.exists() and young.is_file()
    drop_preview(q, ADOPTION_PREVIEWS, "c" * 64)
    drop_preview(q, ADOPTION_PREVIEWS, "../" + "b" * 61)  # not a token: nothing
    assert not applied.exists() and young.is_file()


def test_nothing_is_found_before_a_build_has_said_what_it_names(tmp_path: Path) -> None:
    q = demo(tmp_path)
    stray = _plant(q / CACHE / "blocks/snippets/0123.html")
    assert condemn(q, scan(load_quilt(q)), now=time.time() + DAY).paths == []
    assert stray.is_file()


# ---- one biber for the machine ----------------------------------------------------------------------------------------


def test_a_tex_run_unpacks_biber_in_the_machines_place_whatever_tmpdir_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.machine import UNPACKED, data_dir
    from loom.tex.runner import tex_env

    monkeypatch.setenv("TMPDIR", str(tmp_path / "an-agents-scratch"))
    monkeypatch.setenv("PAR_GLOBAL_TMPDIR", str(tmp_path / "elsewhere"))
    env = tex_env()
    assert env["PAR_GLOBAL_TMPDIR"] == str(data_dir() / UNPACKED)
    assert (data_dir() / UNPACKED).is_dir()
    assert env["TMPDIR"] == str(tmp_path / "an-agents-scratch")


def test_a_compile_starts_latexmk_with_the_machines_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from loom.machine import UNPACKED, data_dir
    from loom.tex import runner

    seen: list[dict[str, str]] = []
    real = runner.subprocess.Popen

    def popen(argv: list[str], *a: object, **kw: object) -> object:
        if Path(argv[0]).name == "latexmk":
            seen.append(dict(kw.get("env") or {}))  # type: ignore[call-overload]
        return real(argv, *a, **kw)  # type: ignore[call-overload]

    monkeypatch.setattr(runner.subprocess, "Popen", popen)
    monkeypatch.setenv("TMPDIR", str(tmp_path / "an-agents-scratch"))
    q = demo(tmp_path)
    run("compile", cwd=q)
    assert seen and all(e.get("PAR_GLOBAL_TMPDIR") == str(data_dir() / UNPACKED) for e in seen)


def test_no_agent_is_granted_the_machines_folder() -> None:
    """A folder whose contents the person's own `loom` runs is no place of an agent's: a sandboxed agent's `biber` unpacks its own copy where its temporary folder is."""
    from loom.ai.layout import codex_rules, permissions_json
    from loom.machine import UNPACKED
    from loom.scan.quilt import QuiltConfig

    for shell in (False, True):
        said = permissions_json(QuiltConfig(), shell=shell)
        assert "sandbox" not in json.loads(said) and UNPACKED not in said
    assert UNPACKED not in codex_rules()


def test_a_tex_run_starts_when_the_machines_folder_cannot_be_made(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from loom.machine import UNPACKED, data_dir
    from loom.tex.runner import tex_env

    place = data_dir()
    place.parent.mkdir(parents=True, exist_ok=True)
    place.write_text("not a folder")  # so nothing can be made under it
    env = tex_env()
    assert env["PAR_GLOBAL_TMPDIR"] == str(place / UNPACKED) and not (place / UNPACKED).exists()


# ---- sizes ------------------------------------------------------------------------------------------------------------


def test_doctor_reports_the_size_of_each_kind_and_the_scratch(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    _plant(q / SCRATCH / "s-small" / "a.txt", b"x" * 2000, time.time())
    out = flat(ok("doctor", cwd=q).stdout)
    assert re.search(r"ok size records \S+ \S?B, library \S+ \S?B, agents \S+ \S?B \(scratch 2\.0 KB\), local", out)
    assert re.search(r"local \S+ \S?B \(the write journal \S+ \S?B\), cache \S+ \S?B", out)


def test_doctor_reports_a_scratch_over_500_mb_with_the_day_it_goes_and_removes_nothing(tmp_path: Path) -> None:
    """The report is the whole of the limit: a sparse file stands in for 600 MB of disk."""
    import datetime

    q = demo(tmp_path)
    big = q / SCRATCH / "s-large" / "big.bin"
    big.parent.mkdir(parents=True)
    with big.open("wb") as f:
        f.truncate(600 * 1000**2)
    last = time.time() - DAY
    os.utime(big, (last, last))
    os.utime(big.parent, (last, last))
    got = json.loads(run("doctor", "--json", cwd=q).stdout)
    item = next(i for i in got["items"] if i["name"] == "scratch")
    expires = datetime.datetime.fromtimestamp(last + KEEP_DAYS * DAY).date().isoformat()
    assert item["status"] == "warn" and "s-large holds 600 MB" in item["detail"] and expires in item["detail"]
    assert item["large"] == [{"session": "s-large", "bytes": 600 * 1000**2, "expires": expires}]
    assert big.is_file()


def test_a_file_that_cannot_be_removed_stops_nothing(tmp_path: Path) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    stuck = _plant(q / CACHE / "blocks/snippets/stuck/0123.html")
    loose = _plant(q / CACHE / "blocks/previews/0123.html")
    _age_folders(q / CACHE)
    stuck.parent.chmod(0o555)
    try:
        swept = sweep(q, scan(load_quilt(q)))
    finally:
        stuck.parent.chmod(0o755)
    assert stuck.is_file() and not loose.exists()
    assert swept.failed >= 1 and swept.files >= 1


def test_a_diff_the_manifest_names_is_kept_by_its_name_and_one_it_does_not_goes(tmp_path: Path) -> None:
    """The records write each stale acceptance's diff into the site beside the publish; the build names it, so it is kept for that and not for having just been written."""
    from loom.scan.quilt import save_author

    q = demo(tmp_path)
    save_author("The loom demo")  # the reviewer whose acceptance the demo ships stale
    ok("build", cwd=q)
    manifest = json.loads((q / CACHE / "site/manifest.json").read_text(encoding="utf-8"))
    named = [
        c["diff"]
        for k in manifest["keys"].values()
        for c in (k.get("acceptance") or {}).get("causes", [])
        if c.get("diff")
    ]
    assert named, "the demo has a stale acceptance whose cause carries a diff"
    stale = _plant(q / CACHE / "site/diffs/gone-key-dependency-changed.diff")
    sweep(q, scan(load_quilt(q)), now=time.time() + FRESH + 60)
    assert all((q / CACHE / "site" / rel).is_file() for rel in named)
    assert not stale.exists()


# ---- no setting points where loom removes files -----------------------------------------------------------------------


def _setting(q: Path, key: str, value: str) -> None:
    """`[quilt] key = value` in `q`'s config, replacing the line that sets it if there is one."""
    text = (q / "config.toml").read_text(encoding="utf-8")
    line = f'{key} = "{value}"'
    text, n = re.subn(rf"(?m)^{key}\s*=.*$", line, text, count=1)
    if not n:
        text = text.replace("[quilt]\n", f"[quilt]\n{line}\n", 1)
    (q / "config.toml").write_text(text, encoding="utf-8")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("history", ".loom/cache/history"),
        ("research_state", ".loom/local/state.md"),
        ("main", ".loom/agents/scratch/s-1/main.tex"),
        ("home", ".loom/cache/../cache/front.md"),
    ],
)
def test_a_path_setting_inside_a_folder_loom_removes_from_is_refused(tmp_path: Path, key: str, value: str) -> None:
    from loom.scan.quilt import SettingError

    q = demo(tmp_path)
    _setting(q, key, value)
    with pytest.raises(
        SettingError, match=rf"\[quilt\] {key} is {re.escape(value)}, inside \.loom/.*where loom removes files"
    ):
        load_quilt(q)
    assert run("build", cwd=q).exit_code == 2


def test_the_reviewers_history_in_the_cache_is_refused_and_kept(tmp_path: Path) -> None:
    """A history moved into `.loom/cache/`, the one ignored folder, so as not to commit it: the build refuses and nothing of it goes, and doctor names the setting and still runs."""
    q = demo(tmp_path)
    ok("build", cwd=q)
    (q / RECORDS / "history").rename(q / CACHE / "history")
    _setting(q, "history", ".loom/cache/history")
    before = _files(q / CACHE / "history")
    _age(q / CACHE)
    r = run("build", cwd=q)
    assert r.exit_code == 2 and "[quilt] history is .loom/cache/history, inside .loom/cache/" in flat(r.output)
    assert _files(q / CACHE / "history") == before
    got = json.loads(run("doctor", "--json", cwd=q).stdout)
    item = next(i for i in got["items"] if i["name"] == "paths")
    assert item["status"] == "fail" and "where loom removes files" in item["detail"]
    assert any(i["name"] == "tex" for i in got["items"])


def test_a_setting_reached_through_a_link_and_the_sync_directory_are_refused(tmp_path: Path) -> None:
    from loom.paths import SOURCE_SYNC
    from loom.scan.quilt import SettingError

    q = demo(tmp_path)
    (q / CACHE / "kept").mkdir(parents=True)
    (q / "hist").symlink_to(q / CACHE / "kept", target_is_directory=True)
    config = (q / "config.toml").read_text(encoding="utf-8")
    (q / "config.toml").write_text(config.replace("[quilt]\n", '[quilt]\nhistory = "hist"\n', 1), encoding="utf-8")
    with pytest.raises(SettingError, match="history is hist, inside .loom/cache/"):
        load_quilt(q)
    (q / "config.toml").write_text(config, encoding="utf-8")
    (q / SOURCE_SYNC).write_text(json.dumps({"directory": ".loom/local/overleaf"}), encoding="utf-8")
    with pytest.raises(SettingError, match="the sync directory is .loom/local/overleaf, inside .loom/local/"):
        load_quilt(q)


def test_the_sweep_keeps_clear_of_a_folder_that_holds_the_history_whatever_the_loader_did(tmp_path: Path) -> None:
    from loom.scan.quilt import Quilt

    q = demo(tmp_path)
    ok("build", cwd=q)
    result = scan(load_quilt(q))
    stray = _plant(q / CACHE / "blocks/snippets/0123.html")
    ledger = _plant(q / CACHE / "history/ledger.jsonl", b"{}\n")
    scratched = _plant(q / SCRATCH / "s-old/history/texts/a.md", b"x", time.time() - 30 * DAY)
    for history, kept in ((".loom/cache/history", ledger), (".loom/agents/scratch/s-old/history", scratched)):
        result.quilt = Quilt(q, replace(result.quilt.config, history=history))
        doomed = condemn(q, result, now=time.time() + 30 * DAY)
        assert kept.resolve() not in {p for p, _home in doomed.paths}
    assert stray in {p for p, _home in condemn(q, scan(load_quilt(q)), now=time.time() + DAY).paths}


# ---- removal through open folders ---------------------------------------------------------------------------------


def _race(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """A built demo with an expired scratch `s-race/d/` holding two files, and outside it a home-like folder holding a file of the second one's name: the quilt, `d`, the home, and the file there that must survive."""
    q = demo(tmp_path)
    ok("build", cwd=q)
    home = tmp_path / "home-like"
    victim = _plant(home / "b-thesis.tex", b"months of work")
    d = q / SCRATCH / "s-race" / "d"
    long_ago = time.time() - 30 * DAY
    _plant(d / "a-first.txt", when=long_ago)
    _plant(d / "b-thesis.tex", when=long_ago)
    for p in (d, d.parent):
        os.utime(p, (long_ago, long_ago))
    return q, d, home, victim


def _swap(d: Path, home: Path) -> None:
    d.rename(d.parent / "d-real")
    d.symlink_to(home, target_is_directory=True)


def test_a_folder_swapped_for_a_link_before_the_removal_is_not_entered(tmp_path: Path) -> None:
    q, d, home, victim = _race(tmp_path)
    doomed = condemn(q, scan(load_quilt(q)), now=time.time())
    _swap(d, home)
    swept = doomed.remove()
    assert victim.read_bytes() == b"months of work" and swept.failed >= 1


def test_a_folder_swapped_for_a_link_between_two_removals_in_it_is_not_entered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second name is removed in the folder the sweep opened, wherever that folder now is, and never through the link."""
    q, d, home, victim = _race(tmp_path)
    doomed = condemn(q, scan(load_quilt(q)), now=time.time())
    real = os.unlink

    def racing(path: object, *a: object, **kw: object) -> None:
        real(path, *a, **kw)  # type: ignore[arg-type]
        if str(path).endswith("a-first.txt"):
            _swap(d, home)

    monkeypatch.setattr(lifetimes.os, "unlink", racing)
    doomed.remove()
    assert victim.read_bytes() == b"months of work"


def test_what_changed_after_the_look_is_left(tmp_path: Path) -> None:
    """A file touched, or a picture a page named again, between finding what goes and removing it stays."""
    from loom.render.assets import publish_picture

    q = demo(tmp_path)
    ok("build", cwd=q)
    touched = _plant(q / CACHE / "site/compare/0123.html", when=time.time() - 20 * DAY)
    picture = _plant(tmp_path / "drawn.svg", b"<svg/>")
    reused = q / CACHE / "site" / publish_picture(picture, q / CACHE / "site/svg")
    os.utime(reused, (OLD, OLD))
    untouched = _plant(q / CACHE / "blocks/snippets/0123.html")
    doomed = condemn(q, scan(load_quilt(q)), now=time.time())
    assert {touched.resolve(), reused.resolve(), untouched.resolve()} <= {p for p, _home in doomed.paths}
    os.utime(touched)
    publish_picture(picture, q / CACHE / "site/svg")
    swept = doomed.remove()
    assert touched.is_file() and reused.is_file() and not untouched.exists() and swept.changed >= 2


def test_a_system_that_cannot_remove_through_a_folder_removes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    q = demo(tmp_path)
    ok("build", cwd=q)
    stray = _plant(q / CACHE / "blocks/snippets/0123.html")
    monkeypatch.setattr(lifetimes, "CAN_REMOVE", False)
    swept = sweep(q, scan(load_quilt(q)))
    assert (
        stray.is_file() and swept.said() == "removed nothing: this system cannot remove a file through an open folder"
    )
