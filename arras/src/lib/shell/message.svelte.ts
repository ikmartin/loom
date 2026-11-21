// The column's message: one line in its foot saying what was just done (a work added, a place marked, a work deleted), with `undo` where the act can be taken back. Any view posts it. There is one message at a time: a new one replaces the last, and with it the last one's undo. It goes by itself after a while, but not while the pointer or the keyboard is on it, and not while its undo is being answered; an undo that fails says so in its place. Folded, the column shows a button for it that opens the column.

/** How long a message stays before it goes by itself, once nothing holds it. */
export const MESSAGE_FOR = 7000;

/** What an undo may answer: nothing, or the publisher's answer, whose `ok: false` is said to the person. */
export type Undone = void | { ok: boolean; error?: { message: string } };

export interface Said {
	text: string;
	/** Takes the act back; absent where it cannot be. */
	undo?: () => Undone | Promise<Undone>;
}

class ColumnMessage {
	said = $state<Said | null>(null);
	/** An undo is being answered. */
	undoing = $state(false);
	#timer: ReturnType<typeof setTimeout> | null = null;
	#held = 0;

	/** Says `text` in the column's foot, with `undo` offered when given. */
	post(text: string, undo?: Said['undo']): void {
		this.#stop();
		this.undoing = false;
		this.said = { text, undo };
		this.#start();
	}

	/** Takes the message down. */
	clear(): void {
		this.#stop();
		this.said = null;
		this.undoing = false;
	}

	/** The pointer or the keyboard came onto the message: it stays until they leave. */
	hold(): void {
		this.#held++;
		this.#stop();
	}

	/** The pointer or the keyboard left the message: it goes after the usual while. */
	release(): void {
		this.#held = Math.max(0, this.#held - 1);
		if (!this.#held && this.said && !this.undoing) this.#start();
	}

	/** Runs the message's undo once; the message stays while it is answered, goes when it is done, and says so when it failed. */
	async undo(failed: (why: string) => string): Promise<void> {
		const undo = this.said?.undo;
		if (!undo || this.undoing) return;
		this.undoing = true;
		this.#stop();
		let why: string | null = null;
		try {
			const answer = await undo();
			if (answer && answer.ok === false) why = answer.error?.message ?? '';
		} catch (err) {
			why = (err as Error)?.message ?? '';
		}
		if (why === null) this.clear();
		else this.post(failed(why));
	}

	#start(): void {
		if (this.#held) return;
		this.#timer = setTimeout(() => this.clear(), MESSAGE_FOR);
	}

	#stop(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
	}
}

export const message = new ColumnMessage();
