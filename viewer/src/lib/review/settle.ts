// Settling a write loom could neither finish nor undo, as it stands (`loom:write-left`, docs/design/writes.md "Settling as it stands"): which notice offers it, the preview drawn from `write-settle-preview`'s fields, and what is said after, all in the viewer's words. Loom's `said` and `result` are its terminal's sentences and are never shown. Pure, so the unit tests hold it.

import type { Diagnostic } from '$lib/manifest/types';
import { frame } from '$lib/words/frame';
import { review } from '$lib/words/review';

const words = review.settle;

/** The settling endpoints: the preview, a read, and the act. */
export const PREVIEW = 'write-settle-preview';
export const SETTLE = 'write-settle';

/** One suggested edit the write wrote or undid, as the preview gives it; `id` is loom's and is never shown. */
export interface SettleEdit {
	id: string;
	words: string;
	outcome: string;
	why: string;
}

/** `write-settle-preview`'s answer, and `write-settle`'s as done (docs/specs/write-api.md). */
export interface SettleAnswer {
	act: string;
	kind: string;
	files: string[];
	edits: SettleEdit[];
	history: string;
}

/** The preview as the person reads it: each part a sentence of the viewer's, '' or empty where it says nothing. */
export interface Drawn {
	lead: string;
	filesHead: string;
	files: string[];
	editsHead: string;
	edits: string[];
	history: string;
	nothing: string;
}

/** The act a notice offers to settle: the id its fix carries for `write-settle`, '' where it carries none. */
export function settleAct(d: Pick<Diagnostic, 'fixes'>): string {
	const act = (d.fixes ?? []).find((f) => f.act?.endpoint === SETTLE)?.act;
	const id = act?.body?.act;
	return typeof id === 'string' ? id : '';
}

/** Draw the preview: every file, each to stay as it is, every suggested edit and what it becomes, and the version, in the viewer's words. A preview of nothing says that only the notice goes. */
export function drawPreview(p: Pick<SettleAnswer, 'kind' | 'files' | 'edits' | 'history'>): Drawn {
	const files = p.files ?? [];
	const edits = p.edits ?? [];
	const history = words.history[p.history] ?? '';
	return {
		lead: words.lead(p.kind),
		filesHead: files.length ? words.files(files.length) : '',
		files: [...files],
		editsHead: edits.length ? words.edits(edits.length) : '',
		edits: edits.map((e) => words.edit(e.words, e.outcome, e.why)),
		history,
		nothing: !files.length && !edits.length && !history ? words.nothing : ''
	};
}

/** What is said once it is settled, from the answer's fields. */
export function doneSays(a: Pick<SettleAnswer, 'edits' | 'history'>): string {
	return words.done((a.edits ?? []).map((e) => e.outcome), a.history);
}

/** Why a preview or a settling was refused, by loom's code: settling's own word, else the frame's, else a plain sentence; never loom's message. */
export function refusedSays(code: string | undefined): string {
	if (code === 'unreachable') return frame.errors.unreachable;
	return words.refused[code ?? ''] ?? frame.refused[code ?? ''] ?? frame.errors.failed;
}
