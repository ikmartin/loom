// What Docs' additions remember while the person reads: whether the library's picker is open over Docs, and its search and sort; and whether the source serves the library's reads at all. The picker's list or thumbnails is the Library's choice, one for both.

import * as api from '$lib/library/api';

class DocsState {
	picker = $state(false);
	/** Whether the source serves the library's works list; where it does not, Docs' column offers no Library button. */
	served = $state<boolean | null>(null);
	#asked = false;

	ask(): void {
		if (this.#asked) return;
		this.#asked = true;
		void api.serves('library-works').then((yes) => (this.served = yes));
	}
	q = $state('');
	sort = $state<'title' | 'authors' | 'year'>('title');
}

export const docsState = new DocsState();
