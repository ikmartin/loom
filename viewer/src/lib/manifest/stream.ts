// The publisher's word that a new manifest exists, where it offers one: the viewer fetches it at once, and its poll only stands by. Detected like the write API, never assumed, so a corpus on a static host polls as it always has.
//
// The stream says nothing of what changed in the manifest, so what the viewer does with a new one is what it does after a poll (spec README, viewer obligation 3). It also says how each document's compile stands and which agents are connected, which no manifest carries, the library's generation, which the library's views read by, and how the publisher's builds ended, which clears the page's mark that it is updating (`updating.svelte.ts`) and the blocks a save drew from source (`fragments/drafts.svelte.ts`). While it is down, who is connected is not known.

import { base } from '$app/paths';
import { capabilities, forgetCapabilities } from '$lib/write';
import { store } from './client.svelte';
import { compiles } from './compiles.svelte';
import { library } from '$lib/library/gen.svelte';
import { presence } from '$lib/agents/presence.svelte';
import { updating, type Built } from './updating.svelte';
import { stopped } from '$lib/shell/gone.svelte';
import { drafts } from '$lib/fragments/drafts.svelte';

/** How often to poll while the stream is open, as a net under it; while it is down, the poll is what tells. */
const NET = 5000;
const UNASSISTED = 1000;

let source: EventSource | null = null;
/** The stream dropped: the publisher may come back as another one, restarted with other code and another token. */
let dropped = false;

/** Listen to the publisher's stream, if it offers one. */
export async function listen(): Promise<void> {
	if (source) return;
	if (typeof EventSource === 'undefined') return updating.none();
	const caps = await capabilities();
	presence.probed(caps);
	if (source) return;
	if (!caps?.stream) return updating.none();
	source = new EventSource(base + '/_api/stream');
	source.addEventListener('manifest', () => void store.refresh());
	source.addEventListener('compiles', (e) => compiles.take((e as MessageEvent<string>).data));
	// the library's generation, raised whenever anything the views read changes (`docs/specs/library-views.md` §2): a view asks again for what it shows
	source.addEventListener('library', (e) => {
		try {
			const { gen } = JSON.parse((e as MessageEvent<string>).data) as { gen?: number };
			if (typeof gen === 'number') library.heard(gen);
		} catch {
			// a malformed event says nothing; the next one will
		}
	});
	// a save's changed blocks as source, before its build runs TeX (a demonstration): drawn in place until that build's publication is fetched
	source.addEventListener('drafted', (e) => drafts.take((e as MessageEvent<string>).data));
	source.addEventListener('connected', (e) => presence.take((e as MessageEvent<string>).data));
	// how the builds ended, on opening and after each: what a write's answer waits on
	source.addEventListener('built', (e) => {
		try {
			const b = JSON.parse((e as MessageEvent<string>).data) as Built;
			if (typeof b?.server === 'number' && typeof b.published === 'number' && typeof b.failed === 'number') {
				void updating.heard(b);
				void drafts.heard(b);
			}
		} catch {
			// a malformed event says nothing; the next one will
		}
	});
	updating.listen();
	source.onopen = () => {
		updating.up();
		stopped.back();
		store.pace(NET);
		// back after a drop: ask again what the publisher is, so a restart under this page is noticed
		if (dropped) {
			dropped = false;
			forgetCapabilities();
			void capabilities();
		}
	};
	// the browser reconnects by itself; until it does, the poll is back at its own pace
	// and whether the server is still there is asked a moment later (`shell/gone.svelte.ts`)
	source.onerror = () => {
		dropped = true;
		stopped.dropped();
		updating.down();
		presence.lost();
		store.pace(UNASSISTED);
	};
}
