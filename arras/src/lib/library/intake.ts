// What a dropped file, a chosen one or a pasted identifier goes through (`docs/specs/library-views.md` §3.5): each file is received, then all are taken in together, a file dropped on a work's row named for that work. The column's message says what happened to the whole drop: one work by its name, several by their count with each that was not added named, and `undo` taking back every work the drop added. On a quilt that has not said whether loom may use the network, the take is made without it, and each work it added by an identifier loom found asks in its row whether to look it up this once. Nothing here changes view: a view that lists works lights the row just added.

import { message } from '$lib/shell/message.svelte';
import { library as words } from '$lib/words/library';
import { asking, lastAdded } from './added.svelte';
import * as api from './api';
import { said as sentence } from './said';

/** Says what one drop did, refusals of files the intake never received among it. */
function tell(rows: api.TakeRow[], refused: string[]): void {
	const added = rows.filter((r) => r.state === 'added' && r.ref);
	if (added.length) lastAdded.ref = added[added.length - 1].ref!;
	for (const r of added) if (r.unconfirmed && r.identifier) asking.add(r.ref!);
	const undo = added.length ? () => undoAll(added) : undefined;
	if (rows.length === 1 && !refused.length) {
		const r = rows[0];
		if (r.state === 'added') return message.post(words.add.added(r.title ?? r.name, r.short ?? '', words.add.foundBy[r.found_by ?? 'none'] ?? '', !!r.tex), undo);
		if (r.state === 'here') return message.post(words.add.here(r.name, r.short ?? ''));
		if (r.state === 'cannot') return message.post(words.add.cannot(r.name, r.why ?? ''));
		return message.post(words.add.many(0, [words.add.question(r.name)]));
	}
	const others = [
		...rows.flatMap((r) => (r.state === 'here' ? [words.add.hereShort(r.name, r.short ?? '')] : r.state === 'cannot' ? [words.add.cannotShort(r.name, r.why ?? '')] : r.state === 'question' ? [words.add.question(r.name)] : [])),
		...refused
	];
	if (rows.length || refused.length) message.post(words.add.many(added.length, others), undo);
}

/** Takes back every work one drop added, the last first; says the first that could not be. */
async function undoAll(rows: api.TakeRow[]): Promise<api.Answer<unknown>> {
	for (const r of [...rows].reverse()) {
		const done = await api.undoTake(r.id, r.act);
		if (!done.ok) return { ok: false, error: { code: done.error.code, message: sentence(done.error) } };
	}
	return { ok: true, value: null };
}

/** Takes `items` in; where the quilt has not said whether loom may use the network, takes them without it. */
async function take(items: Parameters<typeof api.take>[0]): Promise<api.Answer<{ rows: api.TakeRow[] }>> {
	const done = await api.take(items);
	if (done.ok || done.error.code !== 'network-unasked') return done;
	return api.take(items, false);
}

/** Takes in files the person dropped or chose; `onto` is the work whose row they were dropped on. */
export async function addFiles(files: File[], onto?: string): Promise<void> {
	const items: { incoming: string; for?: string }[] = [];
	const refused: string[] = [];
	for (const file of files) {
		const got = await api.receive(file);
		if (!got.ok) refused.push(words.add.cannotShort(file.name, sentence(got.error)));
		else items.push({ incoming: got.value.incoming, ...(onto ? { for: onto } : {}) });
	}
	if (!items.length) return tell([], refused);
	const done = await take(items);
	if (!done.ok) return message.post(sentence(done.error));
	tell(done.value.rows, refused);
}

/** Takes in a pasted arXiv number, DOI or BibTeX. */
export async function addText(text: string): Promise<void> {
	if (!text.trim()) return;
	const done = await take([{ text: text.trim() }]);
	if (!done.ok) return message.post(sentence(done.error));
	tell(done.value.rows, []);
}
