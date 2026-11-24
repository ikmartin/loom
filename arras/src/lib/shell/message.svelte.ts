// The column's message: one line in its foot saying what was just done (a work added, a place marked, a work deleted), with `undo` where the act can be taken back. Any view posts it. There is one message at a time: a new one replaces the last, and with it the last one's undo. It goes by itself after a while, but not while the pointer or the keyboard is on it, and not while its undo is being answered; an undo that fails says so in its place. Folded, the column shows a button for it that opens the column.

/** How long a message stays before it goes by itself, once nothing holds it. */
export const MESSAGE_FOR = 7000;

import { said } from '$lib/library/said';
import { frame } from '$lib/words/frame';

/** What an undo may answer: nothing, or the publisher's answer, whose `ok: false` is said to the person in the viewer's words (`said`). */
export type Undone = void | { ok: boolean; error?: { code?: string; message: string; status?: number } };

export interface Said {
	text: string;
	/** Takes the act back; absent where it cannot be. */
	undo?: () => Undone | Promise<Undone>;
	/** The answers to a question the message asks, each a button; a message that asks one stays until it is answered or closed. */
	choices?: { label: string; act: () => unknown }[];
	/** Run when the person closes the message without answering it. */
	ondismiss?: () => void;
}

class ColumnMessage {
	said = $state<Said | null>(null);
	/** An undo is being answered. */
	undoing = $state(false);
	#timer: ReturnType<typeof setTimeout> | null = null;
	#held = 0;

	/** Says `text` in the column's foot, with `undo` offered when given. A message posted while none shows starts with nothing holding it, since its box is new under the pointer and the keyboard; one that replaces a message on screen keeps the holds on that box. */
	post(text: string, undo?: Said['undo'], ask?: Pick<Said, 'choices' | 'ondismiss'>): void {
		this.#stop();
		if (!this.said) this.#held = 0;
		this.undoing = false;
		this.said = { text, undo, ...ask };
		this.#start();
	}

	/** The person closed the message: what it asked is put off, and it goes. */
	dismiss(): void {
		const put = this.said?.ondismiss;
		this.clear();
		put?.();
	}

	/** Takes the message down, and with its box every hold on it: a box taken from under the pointer or the keyboard is told of no leaving. */
	clear(): void {
		this.#stop();
		this.#held = 0;
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

	/** The message's box went away (the column folded under the pointer, or the view changed): whatever held it lets go, and the message goes after the usual while. */
	drop(): void {
		this.#held = 0;
		if (this.said && !this.undoing && !this.#timer) this.#start();
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
			if (answer && answer.ok === false) why = said({ code: answer.error?.code ?? 'failed', message: '', status: answer.error?.status });
		} catch {
			why = frame.errors.failed;
		}
		if (why === null) this.clear();
		else this.post(failed(why));
	}

	#start(): void {
		if (this.#held || this.said?.choices?.length) return;
		this.#timer = setTimeout(() => this.clear(), MESSAGE_FOR);
	}

	#stop(): void {
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = null;
	}
}

export const message = new ColumnMessage();
