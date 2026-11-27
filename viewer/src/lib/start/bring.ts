// Bringing a paper into an empty quilt from its page (`docs/specs/write-api.md` §2): a drop's files sent one at a time into a drop outside the quilt (`paper-receive`), then brought in (`paper-import`), or a file chosen in the system's dialog and brought in (`paper-choose`); and where the page says a refusal.

import { base } from '$app/paths';
import { capabilities, forgetCapabilities, write } from '$lib/write';
import type { Dropped } from './drop';

/** What loom answers once something is brought in, or asks first. */
export interface Brought {
	/** The paper's drafted document, once it came in. */
	document?: string;
	typeset?: boolean;
	untypeset?: string;
	/** Whether the drafted document does not typeset as the paper did. */
	differs?: boolean;
	/** How many PDFs came into the library. */
	read?: number;
	/** The one question, where several files could be the paper, with the drop that waits for its answer. */
	question?: { choices: string[] };
	drop?: string;
	/** The person cancelled the file dialog. */
	cancelled?: boolean;
}

/** An answer, or loom's refusal by its code. */
export type Answer<T> = { ok: true; value: T } | { ok: false; code: string; message: string };

/** Send one dropped file's bytes into a drop, joining `drop` when given. */
async function receive(file: Blob, path: string, drop: string): Promise<Answer<{ drop: string }>> {
	try {
		const query = new URLSearchParams({ path, ...(drop ? { drop } : {}) });
		const send = async () => {
			const caps = await capabilities();
			return fetch(`${base}/_api/paper-receive?${query}`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/octet-stream', ...(caps?.token ? { 'X-Loom-Token': caps.token } : {}) },
				body: file
			});
		};
		let res = await send();
		// a server started again under the page has another token: asked again once
		if (res.status === 403) {
			forgetCapabilities();
			res = await send();
		}
		const said = (await res.json().catch(() => ({}))) as { drop: string; error?: { code?: string; message?: string } };
		if (res.ok) return { ok: true, value: said };
		return { ok: false, code: said.error?.code ?? (res.status === 413 ? 'too-large' : 'failed'), message: said.error?.message ?? '' };
	} catch (err) {
		return { ok: false, code: 'unreachable', message: (err as Error).message };
	}
}

/** One of the JSON endpoints, its answer as `Brought`. */
async function ask(endpoint: string, body: Record<string, unknown>): Promise<Answer<Brought>> {
	const r = await write(endpoint, body);
	if (r.ok) return { ok: true, value: r as Brought };
	return { ok: false, code: r.error?.code ?? 'failed', message: r.error?.message ?? '' };
}

/**
 * Send a drop's files, then bring them in.
 *
 * Parameters
 * ----------
 * files : Dropped[]
 *     What was dropped, each file by its path within it.
 *
 * Returns
 * -------
 * Answer
 *     What `paper-import` answered, or the first refusal.
 */
export async function bringDrop(files: Dropped[]): Promise<Answer<Brought>> {
	let drop = '';
	for (const f of files) {
		const r = await receive(f.file, f.path, drop);
		if (!r.ok) return r;
		drop = r.value.drop;
	}
	return answer(drop);
}

/**
 * Bring in what waits in `drop`, the paper `main` names where several could be.
 *
 * Parameters
 * ----------
 * drop : str
 *     The drop, as loom named it.
 * main : str, optional
 *     The person's answer to the question.
 *
 * Returns
 * -------
 * Answer
 */
export function answer(drop: string, main?: string): Promise<Answer<Brought>> {
	return ask('paper-import', { drop, ...(main ? { main } : {}) });
}

/**
 * Show the system's file dialog, then bring in what the person chose.
 *
 * Returns
 * -------
 * Answer
 *     `cancelled` when they cancelled.
 */
export function choose(): Promise<Answer<Brought>> {
	return ask('paper-choose', {});
}

/** How a refusal is said on the page: one of loom's known refusals, or loom's own line, '' when it gave none worth showing. */
export type Said = { refused: 'noPaper' | 'badArchive' | 'tooLarge' | 'noDialog' } | { failed: string };

/**
 * How the page says a refusal.
 *
 * Parameters
 * ----------
 * code : str
 *     Loom's code.
 * message : str, default ''
 *     Loom's words, kept for an import that failed.
 *
 * Returns
 * -------
 * Said
 */
export function saidOf(code: string, message = ''): Said {
	switch (code) {
		case 'no-paper':
			return { refused: 'noPaper' };
		case 'bad-archive':
			return { refused: 'badArchive' };
		case 'too-large':
			return { refused: 'tooLarge' };
		case 'no-dialog':
			return { refused: 'noDialog' };
		default:
			return { failed: code === 'cannot-import' || code === 'cannot-read' ? droppedPaths(message) : '' };
	}
}

/** What loom said of an import, the drop's own paths written as the person dropped them: the drop's folder in loom's folder for the machine, whose name may hold a space ("Application Support"), from the path's first slash to the drop's own files. */
export function droppedPaths(said: string): string {
	return said.replace(/(?<=^|[\s'"(])\/[^'"\n]*?\/app\/incoming\/[0-9a-f]+\/(?:files|unpacked)\//g, '');
}
