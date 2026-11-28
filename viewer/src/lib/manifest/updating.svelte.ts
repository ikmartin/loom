// Whether the page is updating: from a write's answer, which loom sends once it has recorded the write (`docs/specs/write-api.md` §2), until the manifest this page holds carries it. The answer names the build that publishes it (`publication`) and the probe names the server that answered (`pid`); the stream's `built` event says how that server's builds ended (`stream.ts`).
//
// The mark clears once the stream says that build or a later one published and the manifest has been fetched since; once it says that build failed, the failure kept to be said (`Updating.svelte`); and, when the stream comes back from another server, once that server first publishes, since its first build reads every file as it is. While the stream is down the mark stays, since nothing says the page is current, and whoever waits on it (`landed`) is let go. Where no stream is listened to, no mark is set, since nothing could clear it.

import { store } from './client.svelte';

/** The stream's `built` event: the server's process, the last build that published and the last that failed (0 for none), and why that one failed. */
export interface Built {
	server: number;
	published: number;
	failed: number;
	why: string | null;
}

class Updating {
	/** The stream's last `built` event, or null before one is heard; a server whose first build has not ended has published nothing yet, which the page says while the quilt has no manifest (`making`). */
	built = $state.raw<Built | null>(null);
	/** Whether the publisher has said whether it builds: a `built` event heard, or no stream to hear one on (`none`). Until then a missing manifest is not yet a problem. */
	known = $state(false);
	/** The build the page waits on, of the server that named it; null while it waits on none. */
	awaited = $state.raw<{ server: number; n: number } | null>(null);
	/** Why the build a write waited on failed, to be said until it is dismissed or another write is answered; null when there is nothing to say. */
	failure = $state<string | null>(null);
	/** The stream's last `built` event. */
	#heard: Built | null = null;
	/** The highest build of the heard server whose manifest this page has fetched since it published. */
	#shown = 0;
	#listening = false;
	#down = false;
	#waiters: (() => void)[] = [];

	/** Whether the page is waiting on a publication. */
	get on(): boolean {
		return this.awaited !== null;
	}

	/** Whether the server's first build is still running: nothing of it has published or failed. */
	get making(): boolean {
		const b = this.built;
		return !!b && b.published === 0 && b.failed === 0;
	}

	/** Why the server's first build failed, '' where it said nothing; null while none has failed before one published. */
	get unmade(): string | null {
		const b = this.built;
		return b && b.published === 0 && b.failed > 0 ? (b.why ?? '') : null;
	}

	/** The publisher offers no stream, so no `built` event will say how its builds stand. */
	none(): void {
		this.known = true;
	}

	/** A stream is listened to, so a mark set will be cleared. */
	listen(): void {
		this.#listening = true;
	}

	/** The stream dropped: the mark stays, and whoever waits on it goes on. */
	down(): void {
		this.#down = true;
		this.#release();
	}

	/** The stream is open again; its `built` event follows. */
	up(): void {
		this.#down = false;
	}

	/** A write's answer: build `n` of the server `server` publishes it. An answer naming no build changes nothing. */
	expect(server: number | undefined, n: unknown): void {
		if (!this.#listening || typeof n !== 'number' || typeof server !== 'number') return;
		const a = this.awaited;
		this.awaited = a && a.server === server ? { server, n: Math.max(a.n, n) } : { server, n };
		this.failure = null;
		this.#settle();
	}

	/** The stream's `built` event, on opening and each time a build ends. */
	async heard(b: Built): Promise<void> {
		if (this.#heard?.server !== b.server) this.#shown = 0;
		this.#heard = b;
		this.built = b;
		this.known = true;
		// another server than the one that answered: its first publication carries every write on disk
		const a = this.awaited;
		if (a && a.server !== b.server) this.awaited = { server: b.server, n: 1 };
		this.#settle();
		if (b.published > this.#shown) {
			await store.refresh();
			if (this.#heard?.server === b.server) this.#shown = Math.max(this.#shown, b.published);
			this.#settle();
		}
	}

	/** Put the failure away. */
	dismiss(): void {
		this.failure = null;
	}

	/** Resolves once no publication is waited on, or the stream is down. */
	idle(): Promise<void> {
		if (!this.awaited || this.#down) return Promise.resolve();
		return new Promise((resolve) => this.#waiters.push(resolve));
	}

	#settle(): void {
		const a = this.awaited;
		const h = this.#heard;
		if (!a || !h || h.server !== a.server) return;
		if (this.#shown >= a.n) return this.#clear();
		// failed, and no later build published it: said, and the page stops waiting; a later one that did is fetched first
		if (h.failed >= a.n && h.published < a.n) {
			this.failure = h.why ?? '';
			this.#clear();
		}
	}

	#clear(): void {
		this.awaited = null;
		this.#release();
	}

	#release(): void {
		const waiting = this.#waiters;
		this.#waiters = [];
		for (const resolve of waiting) resolve();
	}
}

export const updating = new Updating();

/**
 * Fetch the manifest, and wait until it carries every write answered so far: the publication a write's answer named has landed, or its build failed, or the stream is down.
 *
 * For a caller that reads the manifest after its write, as the answer comes before the publication.
 *
 * Returns
 * -------
 * Promise<void>
 */
export async function landed(): Promise<void> {
	await store.refresh();
	await updating.idle();
}
