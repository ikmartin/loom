// Whether the publisher waits on a quilt an earlier loom made (`write-api.md` §1, "A quilt an earlier loom made"): `GET /_api`'s `format.found` below `format.reads`. Judged on every probe, so a quilt served later on the same port is judged afresh.

import type { Capabilities } from '$lib/write';

class Upgrade {
	/** True while the quilt is in an earlier layout and the publisher serves nothing but the upgrade. */
	waiting = $state(false);
}

export const upgrade = new Upgrade();

/** Take a probe's answer. */
export function judgeFormat(caps: Capabilities | null): void {
	upgrade.waiting = !!caps?.format && caps.format.found < caps.format.reads;
}
