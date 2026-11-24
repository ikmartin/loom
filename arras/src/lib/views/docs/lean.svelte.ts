// The Lean marks in a draft's margin: each draft's marks (`formal-marks`), read once a draft is shown and again as the library's generation moves, and whether the person shows them, which the draft's view menu turns.

import { SvelteMap } from 'svelte/reactivity';
import * as api from '$lib/library/api';
import type { FormalMarks } from '$lib/library/types';

class LeanMarks {
	shown = $state(true);
	/** Each draft's marks as last read, by its path. */
	byDoc = new SvelteMap<string, FormalMarks>();

	async read(doc: string): Promise<void> {
		if (!(await api.serves('formal-marks'))) return;
		const held = this.byDoc.get(doc);
		const a = await api.formalMarks(doc, held?.gen);
		if (a.ok && !a.value.unchanged) this.byDoc.set(doc, a.value);
	}
}

export const leanMarks = new LeanMarks();
