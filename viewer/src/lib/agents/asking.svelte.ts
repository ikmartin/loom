// The one "Ask your agent" box of the page, which the selection's chip and the toolbars open: kept here, and the box mounted once at the column's foot, since a chip that asks goes away as the box opens.

import type { Place } from './ask';

export const asking = $state<{ open: boolean; places: Place[] }>({ open: false, places: [] });

/** Open the box about `places`, the first chosen. */
export function askAbout(places: Place[]): void {
	if (!places.length) return;
	asking.places = places;
	asking.open = true;
}
