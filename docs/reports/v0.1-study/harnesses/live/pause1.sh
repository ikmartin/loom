#!/bin/zsh -f
. ${SCRATCH:?}/study/live/env.sh
uv tool install --force ${SCRATCH:?}/study/live/loom-v2 2>&1 | tail -3
${SCRATCH:?}/study/live/uv/bin/loom --version
sleep 8
${SCRATCH:?}/study/live/hcmd.sh '[["eval","document.body.innerText.match(/restart[^\\n]{0,160}|out of step[^\\n]{0,160}|newer[^\\n]{0,160}/gi)"],["shot","'"${SCRATCH:?}"'/study/live/shots/09a-viewer-after-loom-replaced.png"]]'
tail -5 ${SCRATCH:?}/study/live/logs/serve-agent.log
