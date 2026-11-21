// The column's message: one line in its foot saying what was just done (a work added, a place marked, a work deleted), with `undo` where the act can be taken back. Any view posts it; a new one replaces the last, and it goes by itself after a while or when dismissed. Folded, the column shows a dot for it.

/** How long a message stays before it goes by itself. */
export const MESSAGE_FOR = 7000;

export interface Said {
	text: string;
	/** Takes the act back; absent where it cannot be. */
	undo?: () => void | Promise<void>;
}

class ColumnMessage {
	said = $state<Said | null>(null);
	#timer: ReturnType<typeof setTimeout> | null = null;

	/** Says `text` in the column's foot, with `undo` offered when given. */
	post(text: string, undo?: Said['undo']): void {
		this.clear();
		this.said = { text, undo };
		this.#timer = setTimeout(() => this.clear(), MESSAGE_FOR);
	}

	/** Takes the message down. */
	clear(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
		this.said = null;
	}

	/** Runs the message's undo once and takes the message down. */
	async undo(): Promise<void> {
		const undo = this.said?.undo;
		this.clear();
		await undo?.();
	}
}

export const message = new ColumnMessage();
