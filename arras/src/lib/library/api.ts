// The client of the library's reads and writes (`docs/specs/library-views.md`): one function a read and a write, each answered as `{ok, value}` or `{ok: false, error}`. Where they go is the source's: the publisher, or round six's fixture until a read exists (`source.ts`). Every read carries the generation it last saw for the same question, so a publisher whose library has not changed answers `unchanged` and does no other work.

import { can, capabilities, forgetCapabilities, write } from '$lib/write';
import { base } from '$app/paths';
import { store } from '$lib/manifest/client.svelte';
import { fetchFragment } from '$lib/fragments/fetch';
import { discardChanges, keepChanges, type ChangeAnswer } from '$lib/review/history.svelte';
import type { DigestDone, DigestScope, DigestScopes, FindAnswer, Gen, NodeAnswer, PlacesAnswer, ReviewBody, ReviewCounts, ReviewKind, ReviewList, WorkAnswer, WorksAnswer, WriteDone } from './types';

export interface ApiError {
	code: string;
	message: string;
}

export type Answer<T> = { ok: true; value: T } | { ok: false; error: ApiError };

/** Where reads and writes go: the publisher's write API, or a fixture that answers as it will. */
export interface Source {
	call<T extends Gen>(name: string, body: Record<string, unknown>): Promise<Answer<T>>;
	/** The address of a stored PDF by its hash. */
	pdfUrl(hash: string): string;
	/** The address of a work's first page as a picture, or null where there is none to ask for. */
	thumbUrl(hash: string): string | null;
	/** The address of a node drawn by TeX with its work's macros, or null where there is none to ask for. */
	drawnUrl(node: string, macros: string | null): string | null;
	/** Hands one dropped file to the intake (`library-receive`, the one write whose body is the file's bytes). */
	receive(file: File): Promise<Answer<{ incoming: string; name: string; size: number }>>;
	/** Whether this source answers the read or write `name`: the publisher's capabilities say, the fixture answers all it holds. */
	serves(name: string): Promise<boolean>;
	/** A fragment of the build, by its path, as HTML; null where it cannot be read. */
	fragment(path: string): Promise<string | null>;
}

const hex = (hash: string) => hash.replace(/^sha256:/, '');

/** The publisher: `POST /_api/<name>` with the token, a refused token probed again once, as `write()` does; bytes at their content addresses. */
export const server: Source = {
	async call<T extends Gen>(name: string, body: Record<string, unknown>): Promise<Answer<T>> {
		try {
			const send = async () => {
				const caps = await capabilities();
				return fetch(`${base}/_api/${name}`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json', ...(caps?.token ? { 'X-Loom-Token': caps.token } : {}) },
					body: JSON.stringify(body)
				});
			};
			let res = await send();
			if (res.status === 403) {
				forgetCapabilities();
				res = await send();
			}
			const payload = (await res.json().catch(() => ({}))) as T & { error?: ApiError };
			if (res.ok && !payload.error) return { ok: true, value: payload };
			return { ok: false, error: payload.error ?? { code: res.status === 404 ? 'not-served' : 'failed', message: `the publisher answered ${res.status}` } };
		} catch (err) {
			return { ok: false, error: { code: 'unreachable', message: (err as Error).message } };
		}
	},
	async receive(file: File) {
		try {
			const send = async () => {
				const caps = await capabilities();
				return fetch(`${base}/_api/library-receive?name=${encodeURIComponent(file.name)}`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/octet-stream', ...(caps?.token ? { 'X-Loom-Token': caps.token } : {}) },
					body: file
				});
			};
			let res = await send();
			if (res.status === 403) {
				forgetCapabilities();
				res = await send();
			}
			const payload = (await res.json().catch(() => ({}))) as { incoming: string; name: string; size: number; error?: ApiError };
			if (res.ok && !payload.error) return { ok: true as const, value: payload };
			return { ok: false as const, error: payload.error ?? { code: 'failed', message: `the publisher answered ${res.status}` } };
		} catch (err) {
			return { ok: false as const, error: { code: 'unreachable', message: (err as Error).message } };
		}
	},
	serves: (name) => can(name),
	fragment: (path) => fetchFragment(path, store.hash).catch(() => null),
	pdfUrl: (hash) => `${base}/_api/library/pdf/${hex(hash)}`,
	drawnUrl: (node, macros) => `${base}/_api/library/drawn/${hex(node)}-${macros ? hex(macros) : 'none'}.svg`,
	thumbUrl: (hash) => `${base}/_api/library/thumb/${hex(hash)}.png`
};

let source: Source = server;
let chosen: Promise<unknown> = Promise.resolve();

/** Points every read and write at `next`: the fixture in development and in the suites, the publisher otherwise. */
export function useSource(next: Source): void {
	source = next;
}

/** Holds every read and write until `choice` settles, so none goes to the publisher while the fixture is still being chosen. */
export function waitForSource(choice: Promise<unknown>): void {
	chosen = choice;
}

export const pdfUrl = (hash: string) => source.pdfUrl(hash);
export const thumbUrl = (hash: string) => source.thumbUrl(hash);
export const receive = async (file: File) => {
	await chosen;
	return source.receive(file);
};
export const drawnUrl = (node: string, macros: string | null) => source.drawnUrl(node, macros);
export const serves = async (name: string): Promise<boolean> => {
	await chosen;
	return source.serves(name);
};
export const fragment = async (path: string): Promise<string | null> => {
	await chosen;
	return source.fragment(path);
};
export const call = async <T extends Gen>(name: string, body: Record<string, unknown>): Promise<Answer<T>> => {
	await chosen;
	return source.call<T>(name, body);
};

// ---- the reads, each taking the generation held for the same question ----

const since = (s?: number) => (s === undefined ? {} : { since: s });
export const works = (doc?: string, s?: number) => call<WorksAnswer>('library-works', { ...(doc ? { doc } : {}), ...since(s) });
export const work = (ref: string, s?: number) => call<WorkAnswer>('library-work', { ref, ...since(s) });
export const digestScopes = (target: { ref: string } | { all: true }, s?: number) => call<DigestScopes>('library-digest-scopes', { ...target, ...since(s) });
export const places = (target: { ref: string; pages: number[] } | { node: string }, s?: number) => call<PlacesAnswer>('library-places', { ...target, ...since(s) });
export const node = (target: { node: string; brief?: boolean } | { ref: string; item: string }, s?: number) => call<NodeAnswer>('library-node', { ...target, ...since(s) });
export const find = (ref: string, q: string) => call<FindAnswer>('library-find', { ref, q });
export const reviewCounts = (doc?: string, s?: number) => call<ReviewCounts>('review-counts', { ...(doc ? { doc } : {}), ...since(s) });
export const reviewList = (kind: ReviewKind | 'all' | 'agents', doc?: string, s?: number) => call<ReviewList>('review-list', { kind, ...(doc ? { doc } : {}), ...since(s) });
export const reviewRow = (row: string, s?: number) => call<ReviewBody>('review-row', { row, ...since(s) });

// ---- the writes ----

export const digest = (refs: string[] | 'all', scope: DigestScope, chosen?: string[]) => call<DigestDone>('library-digest', { refs, scope, ...(chosen ? { chosen } : {}) });
export const check = (node: string, hash: string) => call<WriteDone>('library-check', { node, hash });
export const remove = (ref: string) => call<WriteDone & { undo: string }>('library-delete', { ref });
export const restore = (undo: string) => call<WriteDone & { ref: string }>('library-restore', { undo });
export const lookUp = (ref: string) => call<WriteDone>('library-look-up', { ref });
export const take = (items: ({ incoming: string; for?: string } | { text: string })[]) => call<WriteDone & { rows: TakeRow[] }>('library-take', { items });
export const undoTake = (id: string, act?: string) => call<WriteDone>('library-undo', { id, ...(act ? { act } : {}) });
export const answer = (task: string, choice: number | null, words: string) => call<WriteDone>('review-answer', { task, ...(choice === null ? {} : { choice }), words });
export const takeCorrection = (correction: string) => call<WriteDone>('library-correction-take', { correction });
export const declineCorrection = (correction: string) => call<WriteDone>('library-correction-decline', { correction });
export const withdraw = (task: string) => call<WriteDone>('review-task-delete', { task });
/** Asks an agent (`review-task`): an `asked` line of the asks log (`evidence.md` §4.1), `fields` those of its `what`, `from` the drafts it is asked for. */
export const ask = (what: string, on: Record<string, unknown>, fields: Record<string, unknown>, from: string[], words = '') => call<WriteDone & { task: string }>('review-task', { what, on, ...fields, from, words });

/** A write that is built today: to the publisher through `write()`, which names the reviewer and the session, or, for keep and discard, through the history that offers their undo; to the fixture as any other. */
async function built(name: string, body: Record<string, unknown>, send: () => Promise<{ ok: boolean; error?: ApiError }>): Promise<Answer<WriteDone>> {
	await chosen;
	if (source !== server) return source.call<WriteDone>(name, body);
	const done = await send();
	return done.ok ? { ok: true, value: { gen: 0 } } : { ok: false, error: done.error ?? { code: 'failed', message: name } };
}
/** Keep and discard answer `ok` with each change refused listed apart; one change refused is this act refused. */
const one = async (sent: Promise<ChangeAnswer>) => {
	const res = await sent;
	const no = res.refused?.[0];
	return no ? { ok: false, error: { code: no.code ?? 'refused', message: no.why } } : res;
};
export const keep = (change: string) => built('change-keep', { changes: [change] }, () => one(keepChanges({ changes: [change] })));
export const discard = (change: string) => built('change-discard', { changes: [change] }, () => one(discardChanges({ changes: [change] })));
export const accept = (key: string) => built('review-accept', { keys: [key] }, () => write('review-accept', { keys: [key] }));

/** A row the intake answers with (`write-api.md` §6), with what the message needs (§3.5 of the views' spec). */
export interface TakeRow {
	id: string;
	item: number;
	name: string;
	state: 'added' | 'here' | 'question' | 'cannot';
	act?: string;
	ref?: string;
	short?: string;
	title?: string;
	found_by?: 'arxiv' | 'doi' | 'isbn' | 'entry' | 'row' | 'none';
	tex?: boolean;
	unconfirmed?: boolean;
	why?: string;
}
