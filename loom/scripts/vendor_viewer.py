#!/usr/bin/env python3
"""Replace src/loom/assets/viewer with a built viewer bundle and stamp VERSION.

Usage: scripts/vendor_viewer.py ../viewer/build [--viewer-dir ../viewer] [--allow-dirty]. Refuses when the viewer has uncommitted changes unless `--allow-dirty` is given, in which case VERSION names the commit with `-dirty`. Everything in the target but README.md is removed first, so no chunk of an earlier build survives. `scripts/checks/bundle.py` at the workspace root checks the result.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / "src" / "loom" / "assets" / "viewer"
KEEP = {"README.md"}


def viewer_commit(viewer_dir: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(viewer_dir), "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def viewer_dirty(viewer_dir: Path) -> bool:
    """Whether the viewer's tracked or untracked-and-not-ignored files differ from its HEAD; the build output is ignored."""
    try:
        return bool(
            subprocess.run(
                ["git", "-C", str(viewer_dir), "status", "--porcelain", "--", "."],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("build_dir", type=Path, help="viewer build output (contains index.html)")
    ap.add_argument("--viewer-dir", type=Path, default=None, help="viewer checkout (default: parent of build_dir)")
    ap.add_argument(
        "--allow-dirty", action="store_true", help="vendor from uncommitted viewer changes, stamping VERSION -dirty"
    )
    args = ap.parse_args(argv)
    build = args.build_dir.resolve()
    viewer_dir = (args.viewer_dir or build.parent).resolve()
    if not (build / "index.html").is_file():
        print(f"error: {build} has no index.html; run `npm run build` in viewer/ first", file=sys.stderr)
        return 2
    dirty = viewer_dirty(viewer_dir)
    if dirty and not args.allow_dirty:
        print(
            f"error: {viewer_dir} has uncommitted changes, so VERSION could not name the commit this bundle is built from;"
            " commit them, or pass --allow-dirty to vendor anyway and stamp it -dirty",
            file=sys.stderr,
        )
        return 2
    for child in TARGET.iterdir():
        if child.name in KEEP:
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    shutil.copytree(build, TARGET, dirs_exist_ok=True, ignore=shutil.ignore_patterns("build"))
    commit = viewer_commit(viewer_dir) + ("-dirty" if dirty else "")
    stamp = f"viewer {commit} vendored {datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}\n"
    (TARGET / "VERSION").write_text(stamp, encoding="utf-8")
    print(f"vendored {build} -> {TARGET}\n{stamp.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
