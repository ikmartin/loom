// The client of the library's reads and writes (`docs/specs/library-views.md`): one function a read and a write, each answered as `{ok, value}` or `{ok: false, error}`. Where they go is the source's: the publisher, or round six's fixture until a read exists (`source.ts`). Every read carries the generation it last saw for the same question, so a publisher whose library has not changed answers `unchanged` and does no other work.

import { capabilities, forgetCapabilities } from '$lib/write';
import { base } from '$app/paths';
import type { DigestDone, DigestScope, DigestScopes, FindAnswer, Gen, NodeAnswer, PlacesAnswer, WorkAnswer, WorksAnswer, WriteDone } from './types';

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

// ---- the writes ----

export const digest = (refs: string[] | 'all', scope: DigestScope, chosen?: string[]) => call<DigestDone>('library-digest', { refs, scope, ...(chosen ? { chosen } : {}) });
export const check = (node: string, hash: string) => call<WriteDone>('library-check', { node, hash });
export const remove = (ref: string) => call<WriteDone & { undo: string }>('library-delete', { ref });
export const restore = (undo: string) => call<WriteDone & { ref: string }>('library-restore', { undo });
export const lookUp = (ref: string) => call<WriteDone>('library-look-up', { ref });
export const take = (items: ({ incoming: string; for?: string } | { text: string })[]) => call<WriteDone & { rows: TakeRow[] }>('library-take', { items });
export const undoTake = (id: string, act?: string) => call<WriteDone>('library-undo', { id, ...(act ? { act } : {}) });

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
