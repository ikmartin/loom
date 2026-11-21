# source me: TinyTeX first, every TeX directory removed from the ordinary PATH
S=${SCRATCH:?}/study/tinytex
TTBIN=$S/tt/TinyTeX/bin/universal-darwin
REST=$(printf '%s' "$PATH" | tr ':' '\n' | grep -v -E '^/usr/local/texlive|^/Library/TeX|TinyTeX' | paste -sd: -)
export PATH="$TTBIN:$REST"
export XDG_CONFIG_HOME=$S/xdg
unset INFOPATH
LOOM=$HOME/dev/loom-arras/.claude/worktrees/v01-study/loom/.venv/bin/loom
