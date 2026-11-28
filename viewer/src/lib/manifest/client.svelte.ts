// The manifest store: one loaded manifest, its hash, and a poll that re-fetches with If-None-Match, which the publisher's stream, where it offers one, makes only a fallback (stream.ts). Re-rendering follows the hash; nothing else ever triggers it (spec README, viewer obligation 3).
import { dataUrl } from '$lib/paths';
import { loadManifest, type Loaded } from './loader';
import { untrack } from 'svelte';
import type { AdoptionReview, Diagnostic, Macro, Manifest, PendingChange } from './types';

/** A plain manifest as JSON with each adoption's choices left out, to tell a manifest that changed only in them; the choices are taken off and put back rather than copied, since a copy of every contribution costs more than the writing. */
function contentOf(m: Manifest): string {
	const adopts = (m.contributions ?? []).filter((c) => c.kind === 'adopt');
	const choices = adopts.map((c) => c.choices);
	for (const c of adopts) (c as { choices?: unknown }).choices = undefined;
	try {
		return JSON.stringify(m);
	} finally {
		adopts.forEach((c, i) => (c.choices = choices[i]));
	}
}

class ManifestStore {
	/** Replaced whole on every change, never written into: a 10 MB manifest held as deep state gave every object read through it a proxy and a signal, which a republish paid for again in garbage collection. */
	manifest = $state.raw<Manifest | null>(null);
	hash = $state<string>('');
	/** The corpus's macros as text: equal across manifests that did not change them, so what depends on it does not run again on every rebuild. */
	#macroKey = $derived(JSON.stringify(this.manifest?.macros.default ?? []));
	/** The corpus's macros, read so that an effect follows a change of them rather than every new manifest. */
	get macros(): Macro[] {
		void this.#macroKey;
		return untrack(() => this.manifest?.macros.default ?? []);
	}
	problem = $state<Diagnostic | null>(null);
	loading = $state(true);
	polls = $state(0);
	#etag: string | null = null;
	#timer: ReturnType<typeof setInterval> | null = null;
	/** The manifest to poll. Follows the configured data root unless a host sets it outright. */
	url = '';

	get manifestUrl(): string {
		return this.url || dataUrl('manifest.json');
	}

	/** Apply the server acknowledgement immediately, as a new manifest holding the new choices; late polls cannot regress its revision. */
	setAdoption(copy: string, fingerprint: string, choices: AdoptionReview['choices']): void {
		const m = this.manifest;
		if (!m?.contributions) return;
		let changed = false;
		const contributions = m.contributions.map((c) => {
			if (c.kind !== 'adopt' || c.copy !== copy || c.fingerprint !== fingerprint || (c.choices?.revision ?? 0) > (choices.revision ?? 0)) return c;
			changed = true;
			return { ...c, choices };
		});
		if (changed) this.manifest = { ...m, contributions };
	}

	/** Pending changes an act made pending again before a publication lists them (an undone Keep), put into every manifest held that does not list them, until `release`, or with no `until`, until a manifest that lists them or a later one is loaded. */
	#held: { row: PendingChange; until: boolean }[] = [];

	/**
	 * Show `rows` in the manifest's pending changes at once, before the publication that lists them lands.
	 *
	 * Parameters
	 * ----------
	 * rows : PendingChange[]
	 *     The rows as the manifest last listed them; one the manifest lists already is left out.
	 * until : Promise, optional
	 *     Resolves once the manifest held carries the act, when the rows go; without it, they go at the next manifest loaded.
	 */
	hold(rows: PendingChange[], until?: Promise<unknown>): void {
		if (!rows.length) return;
		const ids = new Set(rows.map((r) => r.id));
		this.#held = [...this.#held.filter((h) => !ids.has(h.row.id)), ...rows.map((row) => ({ row, until: !!until }))];
		if (this.manifest) this.manifest = this.#withHeld(this.manifest);
		const go = () => this.#release(ids);
		until?.then(go, go);
	}

	/** `m` with the held rows it does not list added at the end; a row it lists is no longer held. */
	#withHeld(m: Manifest): Manifest {
		if (!this.#held.length) return m;
		const listed = new Set((m.changes ?? []).map((c) => c?.id));
		this.#held = this.#held.filter((h) => !listed.has(h.row.id));
		return this.#held.length ? { ...m, changes: [...(m.changes ?? []), ...this.#held.map((h) => h.row)] } : m;
	}

	/** Let the held rows `ids` go, taking out of the manifest held those it shows only because they were held. */
	#release(ids: Set<string>): void {
		const gone = new Set(this.#held.filter((h) => ids.has(h.row.id)).map((h) => h.row));
		if (!gone.size) return;
		this.#held = this.#held.filter((h) => !gone.has(h.row));
		const m = this.manifest;
		if (m?.changes?.some((c) => gone.has(c))) this.manifest = { ...m, changes: m.changes.filter((c) => !gone.has(c)) };
	}

	#running: Promise<void> | null = null;
	#again = false;
	/** The last manifest as text without its adoption choices (`contentOf`), kept so the one held is not written out again at the next change. */
	#content = '';

	/** Fetch the manifest if it changed. One fetch at a time: asked again while one is under way, it fetches once more after it, since what prompted the ask may be newer than the fetch in flight. */
	refresh(): Promise<void> {
		if (this.#running) {
			this.#again = true;
			return this.#running;
		}
		this.#running = (async () => {
			try {
				do {
					this.#again = false;
					await this.#load();
				} while (this.#again);
			} finally {
				this.#running = null;
			}
		})();
		return this.#running;
	}

	async #load(): Promise<void> {
		try {
			const r = await loadManifest(this.manifestUrl, this.#etag);
			this.polls += 1;
			if (r === 'unchanged') return;
			if (r.manifest === null) {
				this.problem = r.diagnostic;
				this.manifest = null;
				this.hash = '';
				return;
			}
			const loaded = r as Loaded;
			if (loaded.hash !== this.hash) {
				if (loaded.manifest.reviewer?.name === this.manifest?.reviewer?.name) {
					for (const old of this.manifest?.contributions ?? []) {
						if (old.kind !== 'adopt') continue;
						const next = loaded.manifest.contributions?.find(c => c.kind === 'adopt' && c.copy === old.copy);
						if (next?.kind === 'adopt' && next.fingerprint === old.fingerprint && (old.choices?.revision ?? 0) > (next.choices?.revision ?? 0)) next.choices = old.choices;
					}
				}
				// a manifest that differs only in adoption choices keeps the one held, with the new choices, so the comparison it shows is not mounted again
				const content = contentOf(loaded.manifest);
				if (this.manifest && content === this.#content) {
					for (const c of loaded.manifest.contributions ?? []) if (c.kind === 'adopt') this.setAdoption(c.copy, c.fingerprint, c.choices);
				} else {
					// a row held with nothing to wait on goes with the first manifest loaded after it
					this.#held = this.#held.filter((h) => h.until);
					this.manifest = this.#withHeld(loaded.manifest);
				}
				this.#content = content;
				this.hash = loaded.hash;
				this.problem = null;
			}
			this.#etag = loaded.etag;
		} catch (err) {
			this.problem = {
				severity: 'error',
				code: 'viewer:manifest-missing',
				message: `could not fetch the manifest: ${(err as Error).message}`,
				locations: [],
				keys: []
			};
		} finally {
			this.loading = false;
		}
	}

	start(intervalMs = 1000): void {
		void this.refresh();
		if (this.#timer === null && intervalMs > 0) {
			this.#poll(intervalMs);
			globalThis.document?.addEventListener('visibilitychange', this.#onVisible);
		}
	}

	/** Poll every `intervalMs` from now on: slowly while the publisher's stream says when to fetch, and as often as before when it cannot. */
	pace(intervalMs: number): void {
		if (this.#timer === null) return;
		clearInterval(this.#timer);
		this.#poll(intervalMs);
	}

	#poll(intervalMs: number): void {
		// a tab nobody is looking at has nothing to re-render, so it stops asking, and asks at once when it is looked at again
		this.#timer = setInterval(() => {
			if (globalThis.document?.visibilityState !== 'hidden') void this.refresh();
		}, intervalMs);
	}

	#onVisible = () => {
		if (document.visibilityState === 'visible') void this.refresh();
	};

	stop(): void {
		if (this.#timer !== null) {
			clearInterval(this.#timer);
			this.#timer = null;
			globalThis.document?.removeEventListener('visibilitychange', this.#onVisible);
		}
	}
}

export const store = new ManifestStore();
