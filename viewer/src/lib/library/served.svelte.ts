// Which of the library views' reads and writes the source serves, asked once each: a control whose read or write is not served is left out, so nothing offers what cannot work. The publisher's capabilities say; round six's fixture serves all it holds.

import { SvelteMap } from 'svelte/reactivity';
import * as api from './api';

class Served {
	#known = new SvelteMap<string, boolean>();
	#asked = new Set<string>();

	/** Whether `name` is served: true once the source says so, false while it is unknown or not served. */
	has(name: string): boolean {
		if (!this.#asked.has(name)) {
			this.#asked.add(name);
			// asked outside the read that called it, so a component drawing this answer never writes state while it draws
			queueMicrotask(() => void api.serves(name).then((yes) => this.#known.set(name, yes)));
		}
		return this.#known.get(name) ?? false;
	}

	/** Forgets every answer, for a source that changed under the page. */
	forget(): void {
		this.#known.clear();
		this.#asked.clear();
	}
}

export const served = new Served();
