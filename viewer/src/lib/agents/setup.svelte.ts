// Setting an agent's app up from the viewer (specs/write-api.md, `agents-setup`), and what the card says after: the steps to connect, and how long it has waited for the app's first conversation. Kept here rather than in a card, so the chip's panel and Settings › Agents show one state.

import { landed } from '$lib/manifest/updating.svelte';
import { write } from '$lib/write';
import { agents as words } from '$lib/words/agents';

/** The two apps the card offers, by the key `agents-setup` takes; the app as a person names it; the names its conversations give loom (`client.name`, else its title); and the application `open` starts, where loom starts one. */
export const OFFERED = [
	{ key: 'claude-code', app: 'Claude Code', short: 'Claude', clients: ['claude-code', 'Claude Code'], open: 'Claude' },
	{ key: 'codex', app: 'Codex', short: 'Codex', clients: ['codex-mcp-client', 'codex', 'Codex'], open: '' }
] as const;

export type Offered = (typeof OFFERED)[number];

/** What `agents-setup` answered, in the parts the card says. */
export interface SetupAnswer {
	written?: string[];
	merged?: string[];
	foreign?: string[];
	tracked?: string[];
	variant?: string;
}

class Setup {
	/** When each app was set up or opened from here, by key: the card waits for its first conversation from then. */
	since = $state<Record<string, number>>({});
	/** What the last set-up of each app answered, by key. */
	said = $state<Record<string, SetupAnswer>>({});
	busy = $state('');
	error = $state<Record<string, string>>({});

	/** Set the quilt up for `app`, then fetch the manifest that says so. */
	async run(app: string): Promise<void> {
		this.busy = app;
		this.error = { ...this.error, [app]: '' };
		const answer = await write('agents-setup', { app });
		if (answer.ok) {
			this.said = { ...this.said, [app]: answer as unknown as SetupAnswer };
			this.waitFor(app);
			await landed();
		} else {
			this.error = { ...this.error, [app]: answer.error?.message ?? words.setup.failed };
		}
		this.busy = '';
	}

	/** Start waiting for `app`'s first conversation now. */
	waitFor(app: string): void {
		this.since = { ...this.since, [app]: Date.now() };
	}
}

export const setup = new Setup();

/** A short account of what loom wrote: the files, with the skills counted rather than listed, and loom's own folder named once. */
export function wroteWords(said: SetupAnswer): string {
	const files = said.written ?? [];
	const skills = files.filter((f) => /\/skills\/loom-[^/]+\/SKILL\.md$/.test(f));
	const rest = files.filter((f) => !skills.includes(f) && !f.startsWith('.loom/'));
	const layer = files.some((f) => f.startsWith('.loom/'));
	return words.setup.wrote([...rest, ...(skills.length ? [words.setup.skills(skills.length)] : []), ...(layer ? [words.setup.layer] : [])]);
}
