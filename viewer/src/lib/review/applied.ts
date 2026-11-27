// The undo of Apply on an agent's copy, offered where it was applied: the version Apply kept of the document is restored (`history-restore`), in the quilt it was applied in, which loom refuses in any other; loom then offers the changes it took in the copy again.

import { said } from '$lib/library/said';
import { landed } from '$lib/manifest/updating.svelte';
import { review as words } from '$lib/words/review';
import { can, capabilities, write } from '$lib/write';

/** What the undo puts back: the version Apply kept of `document`, in the quilt it was applied in. */
export interface Applied {
	document: string;
	version: string;
	quilt: string;
}

/** What a copy's bar says after an act: its words, whether loom refused it, and the undo it offers beside them. */
export interface Answer {
	text: string;
	refused: boolean;
	undo?: Applied;
}

/** Refusals after which pressing Undo again may work: the file moved in the instant loom wrote, or loom was not reached. */
const AGAIN = new Set(['changed', 'unreachable']);

/** The undo of an Apply into `document` that kept it as `version`, in the quilt served now; undefined where none can be offered: no version kept, no quilt named, or no restore served. */
export async function undoOf(document: string, version: string | undefined): Promise<Applied | undefined> {
	if (!version || !(await can('history-restore'))) return undefined;
	const quilt = (await capabilities())?.quilt;
	return quilt ? { document, version, quilt } : undefined;
}

/**
 * Undo an Apply: put its document back as the version it kept holds it, its text now kept as a version first.
 *
 * Parameters
 * ----------
 * a : Applied
 *     What `undoOf` gave for that Apply.
 *
 * Returns
 * -------
 * Answer
 *     What to say, in the viewer's words; it offers the undo again only after a refusal that pressing again may get past.
 */
export async function undoApplied(a: Applied): Promise<Answer> {
	const done = await write('history-restore', { document: a.document, version: a.version, quilt: a.quilt });
	if (done.ok) {
		await landed();
		return { text: words.applied.undone(a.document), refused: false };
	}
	const code = done.error?.code ?? 'failed';
	const why = words.applied.why[code] ?? said({ code, message: '' });
	return { text: words.applied.notUndone(why), refused: true, ...(AGAIN.has(code) ? { undo: a } : {}) };
}
