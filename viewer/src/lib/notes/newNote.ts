// New note, from a selection's actions or an item's toolbar: the publisher runs the person's own command with the link (`new-note`, specs/write-api.md), or writes a Markdown note and opens it, and the toast says which.
import { refusalOf } from '$lib/library/said';
import { say } from '$lib/review/toasts.svelte';
import { notes as words } from '$lib/words/notes';
import { write, type WriteResult } from '$lib/write';

export interface NoteRequest {
	/** A `quilt:` link to the place, with its words where there are some (`quoteLink`). */
	link: string;
	/** The words selected; '' for a whole item. */
	quote?: string;
	/** A name for the place, as a reader names it. */
	title: string;
}

/** Ask for a new note on a place and say how it went; the answer, for a caller that wants it. */
export async function newNote(req: NoteRequest): Promise<WriteResult & { how?: string; path?: string; said?: string }> {
	const res: WriteResult & { how?: string; path?: string; said?: string } = await write('new-note', { link: req.link, quote: req.quote ?? '', title: req.title });
	if (!res.ok) say({ title: words.made.failed, lines: [refusalOf(res.error, words.made.noAnswer)] });
	else if (res.how === 'wrote') say({ title: words.made.wrote(res.path ?? ''), words: req.quote || undefined, lines: [words.made.wroteLine] });
	else say({ title: words.made.ran, words: req.quote || undefined, lines: [res.said?.trim() || words.made.ranLine] });
	return res;
}
