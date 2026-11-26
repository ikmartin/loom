// Which quilt this viewer shows, as what it keeps per quilt in this browser is keyed (the layout, the tree's open folders): the digest the publisher gives at `GET /_api` (`quilt`), so two quilts of one name served on one port keep apart, as Keep's undo does; where no publisher gives one, a static site or an older loom, the quilt's name.

import { capabilities, onCapabilities } from '$lib/write';

class Served {
	/** The publisher's digest; null where none is given; undefined until `/_api` has answered. */
	digest = $state<string | null | undefined>(undefined);
}

export const served = new Served();

if (typeof window !== 'undefined') {
	onCapabilities((c) => (served.digest = c?.quilt ?? null));
	void capabilities().then((c) => (served.digest = c?.quilt ?? null));
}

/** The key what is kept for quilt `name` is kept under: the digest, else the name; '' until `/_api` has answered, when nothing is to be read or written yet. */
export function keptUnder(name: string): string {
	return served.digest === undefined ? '' : (served.digest ?? name);
}
