// Who is connected, as the publisher's stream says it (specs/write-api.md §1): taken from `/_api` at first and from each `connected` event after, and forgotten the moment the stream drops, so that the chip never repeats what it last heard of a server that may have gone. Nothing here where no stream runs, as on a static host: no agent attaches to a page there.

import type { Connected } from './connected';

class Presence {
	/** The records, oldest first; null while not known: before the first answer, and while the stream is down. */
	records = $state.raw<Connected[] | null>(null);
	/** Whether a publisher that says who is connected stands behind the page. */
	served = $state(false);
	/** The clock the chip's "active" and "ago" are read against, moved on by `tick`. */
	now = $state(Date.now());

	/** What `/_api` said: whether the stream is served, and who was connected as it answered. */
	probed(caps: { stream?: boolean; connected?: unknown } | null): void {
		this.served = !!caps?.stream && Array.isArray(caps.connected);
		if (this.served && this.records === null) this.records = caps!.connected as Connected[];
	}

	/** Take a `connected` event, one JSON list; anything else is left as it was. */
	take(data: string): void {
		try {
			const got = JSON.parse(data) as unknown;
			if (Array.isArray(got)) this.records = got as Connected[];
		} catch {
			// a garbled event is no news
		}
	}

	/** The stream dropped: until it opens again and says, nothing is known. */
	lost(): void {
		this.records = null;
	}

	tick(): void {
		this.now = Date.now();
	}
}

export const presence = new Presence();
