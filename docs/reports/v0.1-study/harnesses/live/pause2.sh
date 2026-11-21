#!/bin/zsh -f
. ${SCRATCH:?}/study/live/env.sh
kill $(cat ${SCRATCH:?}/study/live/serve-agent.pid); sleep 3
${SCRATCH:?}/study/live/hcmd.sh '[["wait","3000"],["eval","document.body.innerText.slice(0,300)"],["eval","document.body.innerText.match(/(lost|disconnect|not running|stopped|offline|reconnect)[^\\n]{0,120}/gi)"],["shot","'"${SCRATCH:?}"'/study/live/shots/09b-viewer-after-serve-stopped.png"]]'
