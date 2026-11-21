// One read a view keeps on screen: its latest answer, its error, and asking again. Asked again for the same question, it sends the generation it holds as `since`, so a publisher whose library has not changed answers `unchanged` and the answer on screen stays; asked for another question, the old answer goes at once, and an answer to a question no longer asked is dropped.

import type { Answer, ApiError } from './api';
import type { Gen } from './types';

export class Read<T extends Gen> {
	// raw: an answer is replaced whole, never changed in place, and a list of thousands is not made reactive row by row
	value = $state.raw<T | null>(null);
	error = $state<ApiError | null>(null);
	busy = $state(false);
	#key: string | null = null;
	#asked = 0;

	/** Asks `run` for the question named `key`, passing the generation held when it is the same question. */
	async load(key: string, run: (since?: number) => Promise<Answer<T>>): Promise<void> {
		const same = key === this.#key;
		if (!same) {
			this.#key = key;
			this.value = null;
			this.error = null;
		}
		const asked = ++this.#asked;
		this.busy = true;
		const answer = await run(same ? this.value?.gen : undefined);
		if (asked !== this.#asked) return;
		this.busy = false;
		if (!answer.ok) {
			this.error = answer.error;
			return;
		}
		this.error = null;
		if (!answer.value.unchanged) this.value = answer.value;
	}

	/** Forgets the question and its answer. */
	clear(): void {
		this.#key = null;
		this.#asked++;
		this.value = null;
		this.error = null;
		this.busy = false;
	}
}
