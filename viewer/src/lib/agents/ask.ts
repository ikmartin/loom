// "Ask your agent" (Attach C5): a request for the person to paste into their agent's conversation, naming the place as a reader names it, its `quilt:` link, which `loom link` and every loom tool resolve, the words selected, and the mode to work in. The viewer sends nothing and starts no agent; a request is what the person copies.

import { agents as words } from '$lib/words/agents';

/** What a request is about: a document, a result in one or on its own, or words selected in either. */
export interface Place {
	/** As a reader names it: "main.tex, Theorem 3.1". */
	name: string;
	/** Its link: `quilt:KEY`, `quilt:DOC`, or `quilt:DOC#KEY`. */
	href: string;
	/** The words selected there, if the request is about them. */
	words?: string;
	/** What the choice between places calls it: "the document", "Theorem 3.1, where you are reading". */
	label?: string;
}

/** The longest selection a request quotes whole; a longer one is cut at a word, with an ellipsis. */
const QUOTED = 600;

function quote(words: string): string {
	const w = words.replace(/\s+/g, ' ').trim();
	if (w.length <= QUOTED) return w;
	const cut = w.slice(0, QUOTED);
	return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), QUOTED - 40))}…`;
}

/**
 * The request: the place and the mode in one sentence, then the person's own words after a blank line.
 *
 * With no mode it asks the agent to look; with one, to work in that mode, which a loom agent reads with `loom_ai_mode` and Claude Code also offers as the skill `/loom-<mode>`.
 */
export function request(place: Place, mode = '', said = ''): string {
	const own = said.trim();
	const lead = words.ask.request(mode, place.name, place.href, place.words?.trim() ? quote(place.words) : '');
	return own ? `${lead}\n\n${own}` : lead;
}
