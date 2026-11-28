// "Ask your agent" (Attach C5): a request for the person to paste into their agent's conversation, naming the place as a reader names it, with its `quilt:` link, which `loom link` and every loom tool resolve, where that link holds no key loom minted (a document or a file by its path; any link with Settings › Show ids on), the words selected as the reader sees them, and the mode to work in. The viewer sends nothing and starts no agent; a request is what the person copies.

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

/** A key loom mints: a result's, a proof's, a work's, an annotation's or a session's, which no reader is shown unless Show ids is on. */
const MINTED = /^[A-Za-z][A-Za-z0-9]*-[0-9A-Z]{4}\b/;

/** A place's link with no key loom minted in it: a document or a file by its path, with a page or a heading kept; '' for a thing only a key names, which the request names in words alone. */
export function plainLink(href: string): string {
	const body = href.slice(href.indexOf(':') + 1);
	const cut = body.indexOf('#');
	const head = cut < 0 ? body : body.slice(0, cut);
	if (!head.includes('.') || MINTED.test(head)) return '';
	return cut >= 0 && MINTED.test(body.slice(cut + 1)) ? href.slice(0, href.indexOf(':') + 1) + head : href;
}

/**
 * The request: the place and the mode in one sentence, then the person's own words after a blank line.
 *
 * With no mode it asks the agent to look; with one, to work in that mode, which a loom agent reads with `loom_ai_mode` and Claude Code also offers as the skill `/loom-<mode>`. The place is named as the reader names it, with its link only where the link holds no key loom minted (`plainLink`), unless `ids`, Settings › Show ids, is on.
 */
export function request(place: Place, mode = '', said = '', ids = false): string {
	const own = said.trim();
	const lead = words.ask.request(mode, place.name, ids ? place.href : plainLink(place.href), place.words?.trim() ? quote(place.words) : '');
	return own ? `${lead}\n\n${own}` : lead;
}
