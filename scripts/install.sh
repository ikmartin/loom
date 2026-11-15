#!/bin/sh
# Install or update loom, for this user only, with no password:
#
#   curl -LsSf https://github.com/ikmartin/loom-arras/releases/latest/download/install.sh | sh
#
# It installs uv (which installs Python programs) and a Python of its own, then loom from the release's wheel, then loom's own TeX with Ghostscript and poppler beside it. It touches no shell file and nothing outside the person's home. Running it again updates loom and keeps loom's TeX when it is current.
#
# To try a build before it is released, name local files or URLs:
#   LOOM_WHEEL         the wheel to install, instead of the release's
#   LOOM_TEX_ARCHIVE   loom's TeX, instead of the archive this loom names (a `.sha256` beside a local file is checked)
#   LOOM_TOOLS_ARCHIVE Ghostscript and poppler, likewise
#   LOOM_RELEASE_URL   where the release's files are, instead of the latest GitHub release
#   LOOM_UV            a uv to use, instead of installing one

set -eu

RELEASE="${LOOM_RELEASE_URL:-https://github.com/ikmartin/loom-arras/releases/latest/download}"
case "$(uname -s)" in
  Darwin) DATA="$HOME/Library/Application Support/loom" ;;
  *) DATA="${XDG_DATA_HOME:-$HOME/.local/share}/loom" ;;
esac

say() { printf 'loom: %s\n' "$*"; }
fail() { printf 'loom: %s\n' "$*" >&2; exit 1; }

# fetch SOURCE DEST: a URL downloaded or a local file copied
fetch() {
  case "$1" in
    https://* | http://*) curl -fsSL --retry 3 -o "$2" "$1" || fail "could not download $1" ;;
    *) [ -f "$1" ] || fail "$1 is not a file"; cp "$1" "$2" ;;
  esac
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/loom-install.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT INT TERM
mkdir -p "$DATA"

# 1. uv, in loom's own directory, so no shell file is edited
if [ -n "${LOOM_UV:-}" ]; then
  UV="$LOOM_UV"
else
  UV="$DATA/uv/uv"
  if [ ! -x "$UV" ]; then
    say "installing uv, which installs Python programs (about 20 MB)"
    fetch https://astral.sh/uv/install.sh "$WORK/uv-install.sh"
    UV_UNMANAGED_INSTALL="$DATA/uv" INSTALLER_NO_MODIFY_PATH=1 sh "$WORK/uv-install.sh" >"$WORK/uv.log" 2>&1 \
      || { cat "$WORK/uv.log" >&2; fail "uv did not install"; }
  fi
fi
[ -x "$UV" ] || fail "no uv at $UV"

# 2. the wheel: named, or the release's, checked against the release's checksum
if [ -n "${LOOM_WHEEL:-}" ]; then
  WHEEL="$WORK/$(basename "$LOOM_WHEEL")"
  fetch "$LOOM_WHEEL" "$WHEEL"
else
  fetch "$RELEASE/loom-release.txt" "$WORK/loom-release.txt"
  NAME="$(sed -n 's/^wheel \([^ ]*\) .*/\1/p' "$WORK/loom-release.txt")"
  SUM="$(sed -n 's/^wheel [^ ]* \([0-9a-f]*\)$/\1/p' "$WORK/loom-release.txt")"
  [ -n "$NAME" ] && [ -n "$SUM" ] || fail "the release names no wheel"
  WHEEL="$WORK/$NAME"
  fetch "$RELEASE/$NAME" "$WHEEL"
  [ "$(shasum -a 256 "$WHEEL" | cut -d' ' -f1)" = "$SUM" ] || fail "$NAME does not have the checksum the release gives; nothing was installed"
fi

# 3. loom, with a Python uv manages, so no other Python on the machine is used or changed
say "installing loom $(basename "$WHEEL" | cut -d- -f2)"
"$UV" tool install --quiet --force --managed-python --python 3.13 "$WHEEL" \
  || fail "uv could not install $(basename "$WHEEL")"
LOOM="$("$UV" tool dir --bin)/loom"
[ -x "$LOOM" ] || fail "loom was installed but $LOOM is not there"

# 4. loom's own TeX, Ghostscript and poppler: installed when absent, repaired when broken, kept when current
say "setting up TeX for reading papers (the first time, about 100 MB)"
"$LOOM" doctor --repair --json >"$WORK/doctor.json" 2>"$WORK/repair.log" || true
sed 's/^/loom: /' "$WORK/repair.log"
PY="$("$UV" tool dir)/loomtex/bin/python"
"$PY" - "$WORK/doctor.json" <<'EOF'
import json, sys
data = json.load(open(sys.argv[1]))
items = {i["name"]: i for i in data["items"]}
print(f"loom: loom {data['loom']} is installed; TeX: {items['tex']['detail']}")
for i in data["items"]:
    if i["status"] == "fail":
        print(f"loom: {i['name']}: {i['detail']}" + (f" ({i['remedy']})" if i["remedy"] else ""))
sys.exit(1 if items["tex"]["status"] == "fail" else 0)
EOF
say "if loom is open in your browser, it will ask to be restarted"
