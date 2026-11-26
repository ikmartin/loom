#!/bin/sh
# Regenerate docs/specs/fixture/ from loom's build of the synthetic quilt (docs/specs/fixture.md §2), then vendor it into loom/tests/fixture and viewer/tests/fixture.
# Runs the real TeX toolchain in an isolated environment so nothing outside the quilt and TeX Live can be read. Timestamps are fixed through LOOM_FIXED_TIME.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
WS=$(cd "$HERE/../../.." && pwd)
LOOM="$WS/loom"
SRC="$LOOM/tests/quilts/synthetic"
OUT="$HERE/../fixture"
export LOOM_FIXED_TIME="2026-09-16T00:00:00Z"
TMP=$(mktemp -d)
EMPTY=$(mktemp -d)
cp -R "$SRC" "$TMP/synthetic"
Q="$TMP/synthetic"
mkdir -p "$EMPTY/.config/loom"
printf '[author]\nname = "The synthetic quilt"\n' > "$EMPTY/.config/loom/config.toml"
TEXBIN=$(dirname "$(command -v latexmk)")
POPPLER=$(dirname "$(command -v pdftotext)")
run() { env -i PATH="$TEXBIN:$POPPLER:/usr/bin:/bin:$LOOM/.venv/bin" HOME="$EMPTY" TEXMFHOME="$EMPTY" TEXMFLOCAL="$EMPTY" TEXMFVAR="$EMPTY/var" TEXMFCONFIG="$EMPTY/config" LOOM_FIXED_TIME="$LOOM_FIXED_TIME" "$@"; }
run "$LOOM/.venv/bin/loom" compile drafting/main.tex --html --quilt "$Q"
run "$LOOM/.venv/bin/loom" compile drafting/talk.tex --html --quilt "$Q"
# the agent's copy is a document like any other, and `loom serve` compiles it too
run "$LOOM/.venv/bin/loom" compile .loom/agents/copies/aidoc.tex --html --quilt "$Q"
run "$LOOM/.venv/bin/loom" build --quilt "$Q" || true   # exit 1 is expected: the synthetic quilt carries intentional errors
rm -rf "$OUT"
mkdir -p "$OUT"
cp "$Q/.loom/cache/site/manifest.json" "$OUT/"
cp -R "$Q/.loom/cache/site/fragments" "$OUT/fragments"
[ -d "$Q/.loom/cache/site/svg" ] && cp -R "$Q/.loom/cache/site/svg" "$OUT/svg"
[ -d "$Q/.loom/cache/site/diffs" ] && cp -R "$Q/.loom/cache/site/diffs" "$OUT/diffs"
[ -d "$Q/.loom/cache/site/source" ] && cp -R "$Q/.loom/cache/site/source" "$OUT/source"
[ -d "$Q/.loom/cache/site/transcripts" ] && cp -R "$Q/.loom/cache/site/transcripts" "$OUT/transcripts"
[ -d "$Q/.loom/cache/site/files" ] && cp -R "$Q/.loom/cache/site/files" "$OUT/files"
[ -d "$Q/.loom/cache/site/changes" ] && cp -R "$Q/.loom/cache/site/changes" "$OUT/changes"
VERSION=$(cd "$LOOM" && .venv/bin/loom --version | awk '{print $2}')
printf 'loom %s\ngenerated %s\n' "$VERSION" "$LOOM_FIXED_TIME" > "$OUT/VERSION"
for dest in "$LOOM/tests/fixture" "$WS/viewer/tests/fixture"; do
  rm -rf "$dest"; mkdir -p "$dest"; cp -R "$OUT"/. "$dest"/
done
python3 "$HERE/validate-dialect.py" "$OUT/fragments"
echo "fixture refreshed: $(find "$OUT/fragments" -name '*.html' | wc -l | tr -d ' ') fragments, loom $VERSION"
rm -rf "$TMP" "$EMPTY"
