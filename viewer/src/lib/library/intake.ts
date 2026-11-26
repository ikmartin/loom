// What a dropped file, a chosen one or a pasted identifier goes through (`docs/specs/library-views.md` §3.5): each file is received, then all are taken in together, a file dropped on a work's row named for that work. The column's message says what happened to the whole drop: one work by its name, several by their count with each that was not added named, and `undo` taking back every work the drop added. On a quilt that has not said whether loom may use the network, the take is made without it, and each work it added by an identifier loom found asks in its row whether to look it up this once. A file loom has a question about ("is this one of these works?", Open 19) is asked in the column, with each work it may be and a work of its own as answers, which `library-answer` settles; one still waiting after a reload is asked again from the manifest's `arriving`, and one closed unanswered is not asked again on this page. Nothing here changes view: a view that lists works lights the row just added.

import { message } from '$lib/shell/message.svelte';
import { library as words } from '$lib/words/library';
import { asking, lastAdded } from './added.svelte';
import * as api from './api';
import { said as sentence } from './said';

/** Why a row was not added, in the viewer's words by its code. */
const whyNot = (r: api.TakeRow) => words.add.cannotWhy[r.code ?? ''] ?? words.add.cannotWhyAny;

/** Says what one drop did, refusals of files the intake never received among it; a question is asked once the message goes, or at once when it is the drop's one row. */
function tell(rows: api.TakeRow[], refused: string[]): void {
	const added = rows.filter((r) => r.state === 'added' && r.ref);
	if (added.length) lastAdded.ref = added[added.length - 1].ref!;
	for (const r of added) if (r.unconfirmed && r.identifier) asking.add(r.ref!);
	for (const r of rows) if (r.state === 'question' && r.question) waiting.set(r.question, r);
	const undo = added.length ? () => undoAll(added) : undefined;
	if (rows.length === 1 && !refused.length) {
		const r = rows[0];
		if (r.state === 'added' && r.under) return message.post(words.add.filed(r.name, r.short ?? ''), undo);
		if (r.state === 'added') return message.post(words.add.added(r.title ?? r.name, r.short ?? '', words.add.foundBy[r.found_by ?? 'none'] ?? '', !!r.tex), undo);
		if (r.state === 'here') return message.post(words.add.here(r.name, r.short ?? ''));
		if (r.state === 'cannot') return message.post(words.add.cannot(r.name, whyNot(r)));
		if (r.state === 'question') return void ask(r, true);
	}
	const others = [
		...rows.flatMap((r) => (r.state === 'here' ? [words.add.hereShort(r.name, r.short ?? '')] : r.state === 'cannot' ? [words.add.cannotShort(r.name, whyNot(r))] : r.state === 'question' ? [words.add.question(r.name)] : [])),
		...refused
	];
	if (rows.length || refused.length) message.post(words.add.many(added.length, others), undo);
}

/** The intake's questions this page knows of and has not settled, by id; and those closed unanswered, which wait in the manifest until a reload asks them again. */
const waiting = new Map<string, api.TakeRow>();
/** The questions whose works are being read before they are asked. */
const reading = new Set<string>();
const putOff = new Set<string>();

type Candidate = NonNullable<api.TakeRow['candidates']>[number];

/** A work the question names, as its button says it: its short name, which an unconfirmed work's row shows beside its identifier, and its title as well where another work asked about has the same short name. */
export function candidate(c: Candidate, all: readonly Candidate[]): string {
	const name = c.short || c.title || (c.how ? words.works.identifier(c.how) : '');
	return c.title && c.title !== name && all.some((o) => o !== c && (o.short || o.title) === name) ? words.add.candidate(name, c.title) : name;
}

/** Asks a drop's question in the column: each work it may be that the library still holds, read afresh since a question waits across deletes, and a work of its own; with none left, only whether it is a work of its own. */
async function ask(r: api.TakeRow, now = false): Promise<void> {
	const id = r.question!;
	if (reading.has(id)) return;
	reading.add(id);
	const held = await api.works();
	reading.delete(id);
	// while the works were read, the question was answered or closed, or, asked as the column fell quiet, something else was said
	if (!waiting.has(id) || putOff.has(id) || (!now && message.said)) return;
	const works = held.ok ? (r.candidates ?? []).filter((c) => held.value.works.some((w) => w.ref === c.ref)) : (r.candidates ?? []);
	const stated = (r.candidates ?? []).find((c) => c.how)?.how ?? r.document?.identifiers[0];
	if (!works.length) return message.post(words.add.asksGone(r.name, stated ? words.works.identifier(stated) : ''), undefined, { choices: [{ label: words.add.ownWork, act: () => settle(r, null) }], ondismiss: () => putOff.add(id) });
	const text = stated ? words.add.asks(r.name, words.works.identifier(stated), works.map((c) => c.short)) : words.add.asksOn(r.name, works[0]?.short ?? '');
	const choices =
		works.length === 1
			? [
					{ label: words.add.isIt, act: () => settle(r, works[0].ref) },
					{ label: words.add.notIt, act: () => settle(r, null) }
				]
			: [...works.map((c) => ({ label: candidate(c, works), act: () => settle(r, c.ref) })), { label: words.add.noneOfThem, act: () => settle(r, null) }];
	message.post(text, undefined, { choices, ondismiss: () => putOff.add(id) });
}

/** The person's answer to a question: the file filed under the work they named, or a work of its own, taken without the network where the quilt has not said whether loom may use it. */
async function settle(r: api.TakeRow, same: string | null): Promise<void> {
	const id = r.question!;
	waiting.delete(id);
	putOff.add(id);
	let done = await api.answerDrop(id, same);
	if (!done.ok && done.error.code === 'network-unasked') done = await api.answerDrop(id, same, false);
	if (!done.ok) return message.post(sentence(done.error));
	tell([done.value.row], []);
}

/**
 * Asks the next question that waits, while the column says nothing else.
 *
 * Parameters
 * ----------
 * arriving : TakeRow[], optional
 *     The manifest's `arriving`, the drops that wait on the person; a question there is asked as one a take answered is.
 */
export function askWaiting(arriving?: api.TakeRow[]): void {
	for (const r of arriving ?? []) if (r.state === 'question' && r.question && !waiting.has(r.question) && !putOff.has(r.question)) waiting.set(r.question, r);
	if (message.said) return;
	const next = [...waiting.values()].find((r) => !putOff.has(r.question!));
	if (next) void ask(next);
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
