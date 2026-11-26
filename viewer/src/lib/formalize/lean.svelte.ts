// Lean on this computer, as Settings › Lean and the Web's Check again share it: `formal-state` read when either is drawn and every second and a half while an install or a check runs, the switch (`formal-enable`, the person's alone) and Check again (`formal-check`). A refusal is said in the viewer's words (`library/said.ts`).

import { said } from '$lib/library/said';
import { can, write, type WriteResult } from '$lib/write';
import { running, type LeanState } from './said';

/** How often the state is asked again while something runs, in milliseconds. */
const POLL = 1500;

class Lean {
	/** Whether the publisher serves `formal-state`; null until asked. */
	served = $state<boolean | null>(null);
	/** The state as last read; null before the first read, or where it is not served. */
	state = $state<LeanState | null>(null);
	/** A press waiting for loom's answer. */
	busy = $state(false);
	/** The last refusal, in the viewer's words; '' for none. */
	refused = $state('');
	/** How many presses loom has answered, so a switch the person flipped and loom refused is drawn again as the state says. */
	answers = $state(0);
	#timer: ReturnType<typeof setTimeout> | null = null;

	/** Ask whether it is served, then read the state. */
	async load(): Promise<void> {
		this.served = await can('formal-state');
		if (this.served) await this.read();
	}

	/** Read the state, and again shortly while something runs. */
	async read(): Promise<void> {
		const res = (await write('formal-state', {})) as WriteResult & LeanState;
		if (!res.ok) return;
		this.state = { on: res.on, project: res.project, fence: res.fence, job: res.job };
		if (this.#timer) clearTimeout(this.#timer);
		this.#timer = running(this.state) ? setTimeout(() => void this.read(), POLL) : null;
	}

	/** Turn Lean on, which starts the install, or off. */
	enable(on: boolean): Promise<void> {
		return this.#ask('formal-enable', { on });
	}

	/** Have loom check the Lean again. */
	check(): Promise<void> {
		return this.#ask('formal-check', {});
	}

	async #ask(endpoint: string, body: Record<string, unknown>): Promise<void> {
		this.busy = true;
		this.refused = '';
		const res = await write(endpoint, body);
		if (!res.ok && res.error) this.refused = said(res.error);
		this.busy = false;
		await this.read();
		this.answers++;
	}
}

export const lean = new Lean();
