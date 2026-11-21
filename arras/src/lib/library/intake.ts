// What a dropped file, a chosen one or a pasted identifier goes through (`docs/specs/library-views.md` §3.5): each file is received, then all are taken in together, a file dropped on a work's row named for that work; the column's message says what happened to the last, with `undo` where it was added. Nothing here changes view: a view that lists works lights the row just added.

import { message } from '$lib/shell/message.svelte';
import { library as words } from '$lib/words/library';
import { lastAdded } from './added.svelte';
import * as api from './api';

function said(row: api.TakeRow): void {
	if (row.state === 'added' && row.ref) {
		lastAdded.ref = row.ref;
		const how = words.add.foundBy[row.found_by ?? 'none'] ?? '';
		message.post(words.add.added(row.title ?? row.name, row.short ?? '', how, !!row.tex), () => api.undoTake(row.id, row.act));
	} else if (row.state === 'here') message.post(words.add.here(row.name, row.short ?? ''));
	else if (row.state === 'cannot') message.post(words.add.cannot(row.name, row.why ?? ''));
}

/** Takes in files the person dropped or chose; `onto` is the work whose row they were dropped on. */
export async function addFiles(files: File[], onto?: string): Promise<void> {
	const items: { incoming: string; for?: string }[] = [];
	for (const file of files) {
		const got = await api.receive(file);
		if (!got.ok) {
			message.post(words.add.cannot(file.name, got.error.message));
			continue;
		}
		items.push({ incoming: got.value.incoming, ...(onto ? { for: onto } : {}) });
	}
	if (!items.length) return;
	const done = await api.take(items);
	if (!done.ok) return message.post(done.error.message);
	const rows = done.value.rows;
	if (rows.length) said(rows[rows.length - 1]);
}

/** Takes in a pasted arXiv number, DOI or BibTeX. */
export async function addText(text: string): Promise<void> {
	if (!text.trim()) return;
	const done = await api.take([{ text: text.trim() }]);
	if (!done.ok) return message.post(done.error.message);
	const rows = done.value.rows;
	if (rows.length) said(rows[rows.length - 1]);
}
