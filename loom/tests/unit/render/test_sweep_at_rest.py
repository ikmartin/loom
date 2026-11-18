"""The server's sweep: once at rest after a build that succeeded, never after one that failed, and nothing removed when a build began while it looked."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from loom import lifetimes
from loom.lifetimes import DAY
from loom.paths import CACHE
from loom.render.serve import ServeSession
from tests.unit._quilts import demo

OLD = time.time() - 2 * DAY


def _plant(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    os.utime(path, (OLD, OLD))
    return path


def test_the_server_sweeps_once_at_rest_and_not_after_a_build_that_failed(
    tmp_path: Path, serve: Callable[..., ServeSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    q = demo(tmp_path)
    s = serve(q, watch=False)
    planted = _plant(q / CACHE / "blocks/snippets/0123.html")
    from loom.render import serve as serve_mod

    def broken(*_a: object, **_k: object) -> None:
        raise RuntimeError("the build broke")

    with monkeypatch.context() as m:
        m.setattr(serve_mod, "build", broken)
        with pytest.raises(RuntimeError):
            s.rebuild()
    s.sweep()
    assert planted.is_file()
    s.rebuild()
    s.sweep()
    assert not planted.exists()


def test_the_server_removes_nothing_when_a_build_began_while_it_looked(
    tmp_path: Path, serve: Callable[..., ServeSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the sweep found is judged against the build it followed; one that began since names what it names, so nothing found is removed."""
    q = demo(tmp_path)
    s = serve(q, watch=False)
    planted = _plant(q / CACHE / "blocks/snippets/0123.html")
    real = lifetimes.condemn

    def looking(root: Path, result: object, **kw: object) -> lifetimes.Doomed:
        doomed = real(root, result, **kw)  # type: ignore[arg-type]
        s.rebuild()  # a save arrives while the sweep looks
        return doomed

    monkeypatch.setattr(lifetimes, "condemn", looking)
    s.sweep()
    assert planted.is_file()


def test_the_server_sweeps_nothing_in_the_cache_after_another_process_built(
    tmp_path: Path, serve: Callable[..., ServeSession]
) -> None:
    """Another process built one key at another state of the quilt after the server's build, so the index on disk is not the server's: the server, at rest, leaves the cache and stays due, and sweeps after its own next build. A forced build of one key at the same state writes the same index, and does not stop it."""
    from loom.scan.quilt import load_quilt
    from loom.scan.scan import scan
    from tests.helpers import ok

    q = demo(tmp_path)
    s = serve(q, watch=False)
    planted = _plant(q / CACHE / "blocks/snippets/0123.html")
    result = scan(load_quilt(q))
    key = next(k for k, n in result.nodes.items() if n.kind == "environment")
    ok("build", "--force", "--keys", key, cwd=q)
    source = q / result.nodes[key].file
    source.write_text(source.read_text(encoding="utf-8") + "\n% another state\n", encoding="utf-8")
    ok("build", "--keys", key, cwd=q)
    s.sweep()
    assert planted.is_file() and s._sweep_due
    s.rebuild()
    s.sweep()
    assert not planted.exists()
