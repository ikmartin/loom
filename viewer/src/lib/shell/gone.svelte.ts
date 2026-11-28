// Whether the loom serving this quilt has stopped, and where loom's home page is. The stream dropping says only that the server may be gone, since the browser reconnects by itself and a server restarted after an update drops it too; so the page asks `GET /_api` a few seconds later, and again every few seconds while nothing answers, and says the server stopped only while that ask finds nothing there (`Stopped.svelte`). The home page's address is the one the server's `/_api` last gave, while a home ran (`docs/specs/write-api.md` §1). The column's Your quilts (`column/YourQuilts.svelte`) goes there too, and shows only on a page a quilt's server answered for.

import { base } from '$app/paths';
import type { Capabilities } from '$lib/write';

/** How long after the stream drops the page first asks whether the server is there. */
const GRACE = 3000;
/** How often it asks again while nothing answers. */
const AGAIN = 3000;

class Stopped {
	/** True while nothing answers where the quilt's server was. */
	on = $state(false);
	/** The home page's address, as the server last gave it; '' where no home ran. */
	home = $state('');
	/** A quilt's server answered the probe: this page is served by loom, not published. Kept once seen, so a probe that later finds nothing does not take the column's Your quilts away. */
	served = $state(false);
	#timer: ReturnType<typeof setTimeout> | null = null;

	/** The stream dropped: ask, after a grace, whether the server is there. */
	dropped(): void {
		if (this.#timer) return;
		this.#timer = setTimeout(() => void this.#ask(), GRACE);
	}

	/** The stream is open again: the server is there. */
	back(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		this.on = false;
	}

	async #ask(): Promise<void> {
		this.#timer = null;
		const there = await answers();
		this.on = !there;
		if (!there) this.#timer = setTimeout(() => void this.#ask(), AGAIN);
	}
}

export const stopped = new Stopped();

/** Whether anything answers `GET /_api` where the page was served from. */
async function answers(): Promise<boolean> {
	try {
		const res = await fetch(`${base}/_api`, { cache: 'no-store' });
		await res.arrayBuffer();
		return true;
	} catch {
		return false;
	}
}

/** Take a probe's answer: a quilt's server says it serves the page, and names the home page's address while a home runs. */
export function judgeStopped(caps: Capabilities | null): void {
	if (caps && caps.home !== true) stopped.served = true;
	if (typeof caps?.home === 'string') stopped.home = caps.home;
}
