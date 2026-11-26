// The person's own annotation writes in this page's life, each kept with the write that undoes it and the write that does it again: Undo and Redo on the toolbar, ⌘Z and ⇧⌘Z. A new annotation or reply is undone by deleting it and done again by restoring what the delete took out; a delete by restoring and deleting again; an edit by an edit back to its type, look and words before; a resolve by reopening. Every annotation write in the viewer goes through here, so there is one record of what can be undone.
//
// Keep and Discard of pending changes go through here too, from the document and from Review alike, and are shown so from loom's answer, which comes once it has recorded them, while the page updates (`acted.svelte.ts`). A suggestion loom wrote in when it was kept is undone by `change-undo`, which takes its words out of the file, the text they replaced back, and opens it again; one kept that loom did not write, its words being in already, is not undone. A Keep step names the quilt the server says it serves, and none is made where the server has said none; it is kept in the tab's session storage under that quilt, so a reload still offers its undo in that quilt and no other; loom says, when it is pressed, whether it still can be. A step loom says can no longer be undone leaves the history. A discarded suggestion is undone by `change-discard` with `undo`, which opens it again. A discarded edit in the file has the person's words written back, a version kept first, and comes back from that version in History rather than from here; an edit in the file kept only moved the person's look, and is not undone here either. Neither enters the history.
//
// A delete also stands at the foot of the window (`DeletedBar`) while it is done, since its mark goes with the annotation; its Undo there undoes that delete, wherever it is in the history.

import { store } from '$lib/manifest/client.svelte';
import type { Annotation, Look } from '$lib/manifest/types';
import { capabilities, onCapabilities, write, type Capabilities, type WriteResult } from '$lib/write';
import { plain, typeById } from './annotating.svelte';
import { mark, prune, unmark } from './acted.svelte';
import { changesIn, pending } from './changes';
import { say } from './toasts.svelte';

type Events = Record<string, unknown>[];

/** What a step's undo or redo answers: loom's answer, and whether the step can never be taken again, so it leaves the history. */
type StepResult = WriteResult & { final?: boolean };

interface Step {
	/** What it did, as a reader names it: `delete`, `edit`, `resolve`, `new annotation`. */
	label: string;
	undo: () => Promise<StepResult>;
	redo: () => Promise<StepResult>;
	/** For a delete, the annotation and the words naming what went, so the foot of the window can offer it. */
	deleted?: { id: string; said: string };
	/** For the Keep of suggestions, their ids, kept in the tab's session storage so a reload keeps the step. */
	keeps?: string[];
	/** For the Keep of suggestions, the quilt it was made in, which its undo names so that no other quilt's server does it. */
	quilt?: string;
}

/** A delete held at the foot of the window while it stands. */
export interface Deletion {
	id: string;
	said: string;
}

/** The steps are kept raw, never proxied, so a step is the same object in every list that holds it. */
class History {
	done = $state.raw<Step[]>([]);
	undone = $state.raw<Step[]>([]);
	busy = $state(false);
	deletions = $state.raw<Deletion[]>([]);
}

export const history = new History();

async function run(endpoint: string, body: Record<string, unknown>): Promise<WriteResult> {
	const res = await write(endpoint, body);
	if (res.ok) void store.refresh();
	return res;
}

function push(step: Step): void {
	history.done = [...history.done, step];
	history.undone = [];
	if (step.deleted) history.deletions = [...history.deletions, step.deleted];
	save();
}

/** Where the Keep steps still to be undone are kept for this tab: by quilt, the ids of each, oldest first. */
const KEEPS = 'viewer.keeps';

/** The quilt the server says it serves (`GET /_api`'s `quilt`), once it has answered; steps are kept and offered only under it. */
let serving: string | undefined;

function stored(): Record<string, string[][]> {
	try {
		const all: unknown = JSON.parse(globalThis.sessionStorage?.getItem(KEEPS) ?? '{}');
		return all && typeof all === 'object' && !Array.isArray(all) ? (all as Record<string, string[][]>) : {};
	} catch {
		return {};
	}
}

/** Keep this tab's Keep steps still to be undone, under the quilt being served; a browser that cannot store them loses them on a reload. */
function save(): void {
	if (!serving) return;
	try {
		const all = stored();
		all[serving] = history.done.filter((s) => s.keeps).map((s) => s.keeps as string[]);
		globalThis.sessionStorage?.setItem(KEEPS, JSON.stringify(all));
	} catch {
		// storage refused: the history still holds them until the page goes
	}
}

/** Follow the quilt the server says it serves: when it is another than the one the Keep steps were made in, as when the stream comes back from another quilt on the same port, those steps go from the history; and the steps this tab kept in the quilt now served come back. */
function follow(caps: Capabilities | null): void {
	const now = caps?.quilt;
	if (now === serving) return;
	if (serving !== undefined) {
		history.done = history.done.filter((s) => !s.keeps);
		history.undone = history.undone.filter((s) => !s.keeps);
	}
	serving = now;
	if (!now) return;
	const mine = stored()[now];
	if (!Array.isArray(mine)) return;
	const steps = mine.filter((ids) => Array.isArray(ids) && ids.length > 0 && ids.every((i) => typeof i === 'string')).map((ids) => kept(ids, now));
	if (steps.length) history.done = [...steps, ...history.done];
}

/** Ask which quilt is served, and keep asking with the stream: the history follows it (`follow`). */
async function load(): Promise<void> {
	try {
		onCapabilities(follow);
		follow(await capabilities());
	} catch {
		// no publisher to ask: nothing is kept, and nothing offered
	}
}

/** The id loom gave a new annotation or reply: the first word of its answer. */
function idOf(res: WriteResult): string {
	return (res.result ?? '').split(/\s+/)[0] ?? '';
}

/** A new annotation or reply `id`: undone by deleting it, done again by restoring exactly what the delete took out. */
function created(id: string, label: string): Step {
	let removed: Events = [];
	return {
		label,
		undo: async () => {
			const res = await run('delete', { annotation: id });
			if (res.ok) removed = res.removed ?? [];
			return res;
		},
		redo: () => run('restore', { events: removed })
	};
}

/**
 * Write a new annotation, kept so it can be undone.
 *
 * Parameters
 * ----------
 * body : object
 *     What `annotate` takes.
 *
 * Returns
 * -------
 * WriteResult
 *     loom's answer; `result` begins with the new annotation's id.
 */
export async function annotate(body: Record<string, unknown>): Promise<WriteResult> {
	const res = await run('annotate', body);
	const id = res.ok ? idOf(res) : '';
	if (id) push(created(id, 'new annotation'));
	return res;
}

/** Reply to annotation `id`, kept so it can be undone. */
export async function reply(id: string, message: string): Promise<WriteResult> {
	const res = await run('reply', { annotation: id, message });
	const made = res.ok ? idOf(res) : '';
	if (made) push(created(made, 'reply'));
	return res;
}

/** What puts `a` back as it stands now, for the fields `change` touches: its words, where a mark on a page stands, its type, and its look, as its type's when it is drawn so, else its own. */
function before(a: Annotation, change: Record<string, unknown>, types: Parameters<typeof typeById>[0]): Record<string, unknown> {
	const back: Record<string, unknown> = {};
	if ('message' in change) back.message = a.body ?? plain(a.body_html);
	if ('type' in change) back.type = a.type;
	if ('rects' in change) back.rects = a.rects ?? [];
	if ('strokes' in change) back.strokes = a.strokes ?? [];
	if ('type' in change || 'look' in change) {
		const t = typeById(types, a.type)?.look;
		back.look = t && sameLook(t, a.look) ? null : { ...a.look };
	}
	return back;
}

/** Whether two looks draw alike. */
export function sameLook(x: Partial<Look>, y: Partial<Look>): boolean {
	return x.color === y.color && x.style === y.style && x.weight === y.weight && x.opacity === y.opacity;
}

/** Edit annotation `a` (`message`, `type`, `look`, a null look dropping its own), kept so it can be undone by an edit back. */
export async function edit(a: Annotation, change: Record<string, unknown>): Promise<WriteResult> {
	const back = before(a, change, store.manifest);
	const res = await run('edit', { annotation: a.id, ...change });
	if (res.ok) push({ label: 'edit', undo: () => run('edit', { annotation: a.id, ...back }), redo: () => run('edit', { annotation: a.id, ...change }) });
	return res;
}

/** Resolve annotation `id`, or with `reopen` open it again, kept so it can be undone by the other. */
export async function resolve(id: string, reopen = false): Promise<WriteResult> {
	const there = () => run('resolve', { annotation: id, ...(reopen ? { undo: true } : {}) });
	const back = () => run('resolve', { annotation: id, ...(reopen ? {} : { undo: true }) });
	const res = await there();
	if (res.ok) push({ label: reopen ? 'reopen' : 'resolve', undo: back, redo: there });
	return res;
}

/** Delete annotation `id` and its replies, kept so it can be undone; '' when it is done, else loom's refusal in its words. */
export async function remove(id: string, said: string): Promise<string> {
	let removed: Events = [];
	const del = async () => {
		const res = await run('delete', { annotation: id });
		if (res.ok) removed = res.removed ?? [];
		return res;
	};
	const res = await del();
	if (!res.ok) return res.error?.message ?? 'the publisher refused it';
	push({ label: 'delete', undo: () => run('restore', { events: removed }), redo: del, deleted: { id, said } });
	return '';
}

/** What `change-keep`, `change-discard` and `change-undo` answer: the changes done, by id, and each refused with why. */
export type ChangeAnswer = WriteResult & { done?: string[]; refused?: { id: string; why: string; code?: string }[] };

/** Which changes an act takes: some by id, or every one, of one document or of the whole quilt. */
export type Which = { changes: string[] } | { all: true; document?: string };

/** The ids `which` names, as the manifest lists them now. */
function idsOf(which: Which): string[] {
	if ('changes' in which) return which.changes;
	const m = store.manifest;
	return (which.document ? changesIn(m, which.document) : pending(m)).filter((c) => c.state === 'ready').map((c) => c.id);
}

/** Act on `which`, each change loom did shown so from its answer, which comes once it is recorded, until the manifest no longer lists it; nothing is shown done before, and what loom refuses stays pending. `suggested` is which of the changes done were suggestions, as the manifest had them. */
async function act(endpoint: 'change-keep' | 'change-discard', which: Which, extra: Record<string, unknown> = {}): Promise<{ res: ChangeAnswer; done: string[]; suggested: string[] }> {
	const asked = idsOf(which);
	const kinds = new Map(pending(store.manifest).map((c) => [c.id, c.kind]));
	const res = (await write(endpoint, { ...which, ...extra })) as ChangeAnswer;
	const done = res.ok ? (Array.isArray(res.done) ? res.done : asked.filter((id) => !(res.refused ?? []).some((r) => r.id === id))) : [];
	mark(done, endpoint === 'change-keep' ? 'kept' : 'discarded');
	if (res.ok) {
		await store.refresh();
		prune(store.manifest);
	}
	return { res, done, suggested: done.filter((id) => kinds.get(id) === 'suggested') };
}

/** The refusals after which a change's undo or redo can never succeed: it is not kept, loom wrote nothing to undo, its words changed where they were written, or the quilt has no such suggestion. A file that moved while loom worked (`changed`) may succeed when pressed again. */
const FINAL = new Set(['not-kept', 'not-written', 'changed-since', 'not-open', 'no-such-change', 'other-quilt']);

/** `res` as a step of the history takes it: loom having done none of the changes it was asked for is a refusal, with the first one's why, and final when every refusal is; when it did some, those refused are said under `title`. */
function asStep(res: ChangeAnswer, title: string): StepResult & ChangeAnswer {
	const refused = res.refused ?? [];
	// the request refused whole, as a suggestion this quilt does not have is: final when its code is
	if (!res.ok) return { ...res, final: FINAL.has(res.error?.code ?? '') };
	if (!refused.length) return res;
	if (!(res.done ?? []).length) {
		const final = refused.every((r) => FINAL.has(r.code ?? ''));
		return { ...res, ok: false, final, error: { code: refused[0].code ?? 'refused', message: refused[0].why } };
	}
	say({ title, lines: refused.slice(0, 3).map((r) => r.why) });
	return res;
}

/** The Keep of suggestions `ids`, which loom wrote in: undone by `change-undo`, which takes their words out again and opens them, and done again by keeping them again. */
function kept(ids: string[], quilt: string): Step {
	const step: Step = {
		label: ids.length === 1 ? 'keep' : `keep of ${ids.length} suggestions`,
		keeps: ids,
		quilt,
		undo: async () => {
			const res = asStep((await run('change-undo', { changes: step.keeps, quilt: step.quilt })) as ChangeAnswer, 'Not all undone');
			if (res.ok) {
				step.keeps = res.done ?? step.keeps;
				unmark(step.keeps ?? []);
			}
			return res;
		},
		redo: async () => {
			const { res, done } = await act('change-keep', { changes: step.keeps ?? [] });
			const again = asStep({ ...res, done }, 'Not all kept again');
			if (again.ok && done.length) step.keeps = done;
			return again;
		}
	};
	return step;
}

/**
 * Keep pending changes: an edit in the file becomes what the person has kept, a suggestion is written into its file. A suggestion loom writes is kept so it can be undone.
 *
 * Parameters
 * ----------
 * which : Which
 *     Some changes by id, or every one of a document (`document`) or of the quilt.
 *
 * Returns
 * -------
 * ChangeAnswer
 *     loom's answer, with the changes done and each refused.
 */
export async function keepChanges(which: Which): Promise<ChangeAnswer> {
	// what loom will write in: a suggestion the manifest lists ready; one taken already is kept with nothing written
	const writes = new Set(pending(store.manifest).filter((c) => c.kind === 'suggested' && c.state === 'ready').map((c) => c.id));
	const { res, suggested } = await act('change-keep', which);
	const wrote = suggested.filter((id) => writes.has(id));
	if (wrote.length) {
		// a step names the quilt it was made in, so none is kept before the server has said which it serves
		if (serving === undefined) follow(await capabilities());
		if (serving) push(kept(wrote, serving));
	}
	return res;
}

/**
 * Discard pending changes: an edit in the file has the person's words written back, a version kept first; a suggestion is dropped and the text left as it is, kept so it can be undone.
 *
 * Parameters
 * ----------
 * which : Which
 *     Some changes by id, or every one of a document (`document`) or of the quilt.
 * why : str, optional
 *     Why, kept with a discarded suggestion.
 *
 * Returns
 * -------
 * ChangeAnswer
 */
export async function discardChanges(which: Which, why?: string): Promise<ChangeAnswer> {
	const { res, done, suggested } = await act('change-discard', which, why ? { why } : {});
	// an edit in the file is not undone here: the words it had are in History, kept before they were replaced
	const edits = done.length - suggested.length;
	if (edits > 0) say({ title: edits === 1 ? 'Discarded an edit' : `Discarded ${edits} edits`, lines: ['Your words are back in the file. The text it had is kept as a version in History.'] });
	if (suggested.length) {
		push({
			label: suggested.length === 1 ? 'discard' : `discard of ${suggested.length} suggestions`,
			undo: async () => {
				const back = await run('change-discard', { changes: suggested, undo: true });
				if (back.ok) unmark(suggested);
				return back;
			},
			redo: async () => (await act('change-discard', { changes: suggested })).res
		});
	}
	return res;
}

/** Take a step back or forward: '' when it is done, else loom's refusal. A delete leaves the foot of the window when undone and comes back when done again. */
async function move(from: 'done' | 'undone', step: Step): Promise<string> {
	if (history.busy) return '';
	history.busy = true;
	const res = from === 'done' ? await step.undo() : await step.redo();
	history.busy = false;
	if (!res.ok) {
		// a step loom says can never be taken leaves the history, so what is beneath it can be reached again
		if (res.final) {
			history.done = history.done.filter((s) => s !== step);
			history.undone = history.undone.filter((s) => s !== step);
			if (step.deleted) history.deletions = history.deletions.filter((d) => d !== step.deleted);
			save();
		}
		return res.error?.message ?? 'the publisher refused it';
	}
	if (from === 'done') {
		history.done = history.done.filter((s) => s !== step);
		history.undone = [...history.undone, step];
		if (step.deleted) history.deletions = history.deletions.filter((d) => d !== step.deleted);
	} else {
		history.undone = history.undone.filter((s) => s !== step);
		history.done = [...history.done, step];
		if (step.deleted) history.deletions = [...history.deletions, step.deleted];
	}
	save();
	return '';
}

/** Undo the last write still done. */
export function undo(): Promise<string> {
	const step = history.done.at(-1);
	return step ? move('done', step) : Promise.resolve('');
}

/** Do again the last write undone. */
export function redo(): Promise<string> {
	const step = history.undone.at(-1);
	return step ? move('undone', step) : Promise.resolve('');
}

/** Undo the delete of annotation `id`, wherever it stands in the history. */
export function undoDelete(id: string): Promise<string> {
	const step = history.done.find((s) => s.deleted?.id === id);
	return step ? move('done', step) : Promise.resolve('');
}

/** Stop offering the undo of a delete at the foot of the window; it can still be undone from the toolbar. */
export function forget(id: string): void {
	history.deletions = history.deletions.filter((d) => d.id !== id);
}

/** What Undo and Redo would do now, for their titles; '' when nothing. */
export function nextUndo(): string {
	return history.done.at(-1)?.label ?? '';
}
export function nextRedo(): string {
	return history.undone.at(-1)?.label ?? '';
}

void load();
