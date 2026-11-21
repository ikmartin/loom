# source me: TinyTeX and the system directories only, as on a Mac with no Homebrew and no MacTeX
S=${SCRATCH:?}/study/tinytex
TTBIN=$S/tt/TinyTeX/bin/universal-darwin
export PATH="$TTBIN:/usr/bin:/bin:/usr/sbin:/sbin"
export XDG_CONFIG_HOME=$S/xdg
unset INFOPATH
LOOM=$HOME/dev/loom-arras/.claude/worktrees/v01-study/loom/.venv/bin/loom
unset LIBGS
