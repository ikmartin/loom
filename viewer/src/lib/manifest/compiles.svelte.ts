// How each document's compile stands (plan 0.29.1), as the publisher's stream says it, keyed by document path. Empty where no stream runs, as on a static host: nothing there compiles.

import { docs } from '$lib/words/docs';

/** How a document's last compile ended: `ok`; `errors`, a PDF made though LaTeX reported errors; `failed`, no PDF, so the one before stays. */
export interface CompileLast {
	result: 'ok' | 'errors' | 'failed';
	ended: string;
	error: string | null;
	/** The line of the log TeX stopped at: `l.12 \hlind`. */
	at: string | null;
}

export interface Compile {
	state: 'queued' | 'compiling' | 'idle';
	/** Asked for again while compiling, so it runs once more. */
	again: boolean;
	last: CompileLast | null;
}

class Compiles {
	all = $state.raw<Record<string, Compile>>({});

	/** Take what the stream said, as one JSON object; anything else is left as it was. */
	take(data: string): void {
		try {
			const got = JSON.parse(data) as unknown;
			if (got && typeof got === 'object' && !Array.isArray(got)) this.all = got as Record<string, Compile>;
		} catch {
			// a garbled event is no news
		}
	}
}

export const compiles = new Compiles();

/** What a document's compile says to a reader in a word, or '' when there is nothing to say: compiling, waiting, or how the last run went wrong. */
export function compileWord(c: Compile | undefined): string {
	if (!c) return '';
	if (c.state === 'compiling') return 'compiling';
	if (c.state === 'queued') return 'waiting to compile';
	if (c.last?.result === 'failed') return 'did not compile';
	if (c.last?.result === 'errors') return 'compiled with errors';
	return '';
}

/** What a document's `view PDF` says beside it: how its compile stands (`compileWord`), or `not compiled yet` where there is no PDF and nothing under way; '' when the PDF is there and there is nothing to say. */
export function pdfWord(pdf: boolean, c: Compile | undefined): string {
	return compileWord(c) || (pdf ? '' : 'not compiled yet');
}

/**
 * The `view PDF` line of a document's *view* menu: its word (`pdfWord`); where there is no PDF to open, why, which greys it; and the last compile's error, as the line's title where it does open.
 *
 * Opens wherever a PDF is there, a failed compile's last one and one compiled with errors included.
 */
export function pdfLine(pdf: boolean, c: Compile | undefined): { word: string; off?: string; about?: string } {
	const why = compileError(c) || undefined;
	return { word: pdfWord(pdf, c), ...(pdf ? { about: why } : { off: why ?? 'There is no compiled PDF to open yet' }) };
}

/** The line of its file TeX stopped at, from the log's `l.12 \hlind`; '' where unknown. */
export const stoppedAt = (c: Compile | undefined): string => /^l\.(\d+)/.exec(c?.last?.at ?? '')?.[1] ?? '';

/** The last run's error in the person's words (`docs.texError`) and the line TeX stopped at, never the log's command, for a title or a line under the paper. */
export function compileError(c: Compile | undefined): string {
	const l = c?.last;
	if (!l || l.result === 'ok') return '';
	return docs.compileError(docs.texError(l.error ?? ''), stoppedAt(c));
}

/**
 * Whether a document is being typeset for the first time, its page not come yet: its text is not TeX's (`fromTex`), and its first compile this server runs is under way, or a compile has just ended well and the manifest that carries its page is still to come (`generated`, the manifest's time, before the run ended).
 *
 * A document TeX gives no page, as a beamer talk, keeps its text as its source between compiles, since a later compile under way has a `last` and one long published has ended by `generated`.
 */
export function typesettingFirst(c: Compile | undefined, generated: string, fromTex: boolean): boolean {
	if (fromTex || !c) return false;
	if (c.state !== 'idle') return !c.last;
	return !!c.last && c.last.result !== 'failed' && c.last.ended > generated;
}
