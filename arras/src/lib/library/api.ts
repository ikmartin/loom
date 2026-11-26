// The client of the library's reads and writes (`docs/specs/library-views.md`): one function a read and a write, each answered as `{ok, value}` or `{ok: false, error}`. Where they go is the source's: the publisher, or round six's fixture until a read exists (`source.ts`). Every read carries the generation it last saw for the same question, so a publisher whose library has not changed answers `unchanged` and does no other work.

import { can, capabilities, forgetCapabilities } from '$lib/write';
import { base } from '$app/paths';
import { libraryPdfUrl } from '$lib/paths';
import { store } from '$lib/manifest/client.svelte';
import { fetchFragment } from '$lib/fragments/fetch';
import { library as libraryWords } from '$lib/words/library';
import { library as generation } from './gen.svelte';
import type { FormalMarks, FormalPlan, NotesAnswer, DigestDone, DigestScope, DigestScopes, FindAnswer, Gen, NodeAnswer, PlacesAnswer, ReviewBody, ReviewCounts, ReviewKind, ReviewList, WebFocus, WebGraph, WebGroupAnswer, WebList, WebScope, WebSearch, WorkAnswer, WorksAnswer, WriteDone } from './types';

export interface ApiError {
	code: string;
	/** Loom's own words, for the command line: never drawn (`said`). */
	message: string;
	/** The HTTP status of loom's refusal; absent where nothing answered. */
	status?: number;
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
			// an answer that is not loom's JSON is a host that serves no write API: the read is not served here
			const payload = (await res.json().catch(() => null)) as (T & { error?: ApiError }) | null;
			if (!payload || payload.error?.code === 'unknown-endpoint') return { ok: false, error: { code: 'not-served', message: '' } };
			if (res.ok && !payload.error) return { ok: true, value: payload };
			return { ok: false, error: { ...(payload.error ?? { code: 'failed', message: '' }), status: res.status } };
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
			return { ok: false as const, error: { ...(payload.error ?? { code: 'failed', message: '' }), status: res.status } };
		} catch (err) {
			return { ok: false as const, error: { code: 'unreachable', message: (err as Error).message } };
		}
	},
	serves: (name) => can(name),
	fragment: (path) => fetchFragment(path, store.hash).catch(() => null),
	pdfUrl: (hash) => libraryPdfUrl(hash),
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
	const answer = await source.call<T>(name, body);
	// the library's generation, which every library read and write answers with: a write's change is on screen at once, and the stream's event for the same generation then changes nothing. Review's and the Web's reads count their own, so only the library's are heard
	if (answer.ok && name.startsWith('library-') && typeof answer.value.gen === 'number') generation.heard(answer.value.gen);
	return answer;
};

// ---- the reads, each taking the generation held for the same question ----

const since = (s?: number) => (s === undefined ? {} : { since: s });
export const works = (doc?: string, s?: number) => call<WorksAnswer>('library-works', { ...(doc ? { doc } : {}), ...since(s) });
/** What a work's tab says when its work has left the library. */
const gone = libraryWords.works.gone;
/** A work's tab: `library-work` where it is served; else the work's row of the list, with no outline, since nothing reads a work's results yet (phase 3), so its tab still opens its paper. */
export const work = async (ref: string, s?: number): Promise<Answer<WorkAnswer>> => {
	if (await serves('library-work')) return call<WorkAnswer>('library-work', { ref, ...since(s) });
	const all = await works();
	if (!all.ok) return all;
	const w = all.value.works.find((x) => x.ref === ref);
	if (!w) return { ok: false, error: { code: 'no-such-ref', message: gone } };
	return { ok: true, value: { gen: all.value.gen, ref: w.ref, short: w.short, title: w.title, authors: w.authors, year: w.year, holds: { pdf: w.holds.pdf, pages: null, tex: w.holds.tex }, entry: '', link: w.link, outline: null, marks: [], unplaced: [] } };
};
export const digestScopes = (target: { ref: string } | { all: true }, s?: number) => call<DigestScopes>('library-digest-scopes', { ...target, ...since(s) });
export const places = (target: { ref: string; pages?: number[] } | { node: string }, s?: number) => call<PlacesAnswer>('library-places', { ...target, ...since(s) });
export const node = (target: { node: string; brief?: boolean } | { ref: string; item: string }, s?: number) => call<NodeAnswer>('library-node', { ...target, ...since(s) });
export const find = (ref: string, q: string) => call<FindAnswer>('library-find', { ref, q });
/** Where a Web read looks: its scope, and the draft where the scope names one. */
export type InScope = { scope: WebScope; doc?: string };
const scoped = (w: InScope) => ({ scope: w.scope, ...(w.doc && (w.scope === 'draft' || w.scope === 'deps') ? { doc: w.doc } : {}) });
export const webList = (w: InScope, sort: 'document' | 'status', open: string[], offset = 0, s?: number) => call<WebList>('web-list', { ...scoped(w), ...(sort === 'status' ? { sort } : {}), ...(open.length ? { open } : {}), ...(offset ? { offset } : {}), ...since(s) });
export const webGroup = (w: InScope, group: string, s?: number) => call<WebGroupAnswer>('web-group', { ...scoped(w), group, ...since(s) });
export const webSearch = (w: InScope, q: string) => call<WebSearch>('web-search', { ...scoped(w), q });
export const webFocus = (w: InScope, result: string, more: boolean, s?: number) => call<WebFocus>('web-focus', { ...scoped(w), result, ...(more ? { more: true } : {}), ...since(s) });
export const webGraph = (w: InScope, result: string, s?: number) => call<WebGraph>('web-graph', { ...scoped(w), result, ...since(s) });
export const notes = (sort: 'work' | 'date', orphaned: boolean, more?: { group?: string; offset: number }, s?: number) => call<NotesAnswer>('notes', { sort, orphaned, ...(more?.group ? { group: more.group } : {}), ...(more ? { offset: more.offset } : {}), ...since(s) });
export const deleteNote = (annotation: string) => call<WriteDone>('delete', { annotation });
export const formalMarks = (doc: string, s?: number) => call<FormalMarks>('formal-marks', { doc, ...since(s) });
export const formalPlan = (targets: string[], assume: string[]) => call<FormalPlan>('formal-plan', { targets, assume });
export const formalAsk = (targets: string[], assume: string[]) => call<WriteDone & { tasks: string[] }>('formal-ask', { targets, assume });
/** Review's counts, a draft's among them (`drafts`). */
export const reviewCounts = (s?: number) => call<ReviewCounts>('review-counts', { ...since(s) });
export const reviewList = (kind: ReviewKind | 'all' | 'agents', doc?: string, s?: number) => call<ReviewList>('review-list', { ...(kind === 'all' ? {} : { kind }), ...(doc ? { doc } : {}), ...since(s) });
export const reviewRow = (row: string, s?: number, node?: string) => call<ReviewBody>('review-row', { row, ...(node ? { node } : {}), ...since(s) });

// ---- the writes ----

export const digest = (refs: string[] | 'all', scope: DigestScope, chosen?: string[]) => call<DigestDone>('library-digest', { refs, scope, ...(chosen ? { chosen } : {}) });
export const check = (node: string, hash: string) => call<WriteDone>('library-check', { node, hash });
export const remove = (ref: string) => call<WriteDone & { undo: string }>('library-delete', { ref });
export const restore = (undo: string) => call<WriteDone & { ref: string }>('library-restore', { undo });
/** Looks a work up by the identifier its reference states; `once`, with the network this once, on a quilt that has not said whether loom may use it. */
export const lookUp = (ref: string, once = false) => call<WriteDone>('library-look-up', { ref, ...(once ? { online: true } : {}) });
/** Takes received files and pasted works in; `online: false` takes them without the network, each reference's details unconfirmed. */
export const take = (items: ({ incoming: string; for?: string } | { text: string })[], online?: false) => call<WriteDone & { rows: TakeRow[] }>('library-take', { items, ...(online === false ? { online } : {}) });
export const undoTake = (id: string, act?: string) => call<WriteDone>('library-undo', { id, ...(act ? { act } : {}) });
/** Answers a drop's one question (`library-answer`): `same` the work it is, or null for a work of its own, which `online` lets be looked up this once. */
export const answerDrop = (question: string, same: string | null, online?: boolean) => call<WriteDone & { row: TakeRow }>('library-answer', { question, same, ...(online === undefined ? {} : { online }) });
/** Takes a work's PDF, or with `which` its TeX source, off it, to wait again as a drop (`library-unfile`). */
export const unfile = (ref: string, which?: 'pdf' | 'tex') => call<WriteDone & { incoming: string; act: string; row: TakeRow }>('library-unfile', { ref, ...(which ? { which } : {}) });
/** Replaces a work's entry with one BibTeX entry (`library-entry`). */
export const entry = (ref: string, bibtex: string) => call<WriteDone & { ref: string }>('library-entry', { ref, bibtex });
/** Answers an agent's question (`review-answer`): one of its choices, the person's words, or both. */
export const answer = (question: string, choice: number | null, text: string) => call<WriteDone>('review-answer', { question, ...(choice === null ? {} : { choice }), ...(text ? { text } : {}) });
export const takeCorrection = (correction: string) => call<WriteDone>('library-correction-take', { correction });
export const declineCorrection = (correction: string) => call<WriteDone>('library-correction-decline', { correction });
export const attest = (result: string, observation: string) => call<WriteDone>('formal-attest', { result, observation });
export const mention = (citation: string) => call<WriteDone>('library-mention', { citation });
/** Withdraws a task (`review-task-delete`); `undo`, the column's undo of that, puts the same task back as it stood. */
export const withdraw = (task: string, undo = false) => call<WriteDone>('review-task-delete', { task, ...(undo ? { undo: true } : {}) });
/** Asks an agent (`review-task`, `evidence.md` §7): `kind` what is asked, `on` the place and what the kind needs, `text` the person's words, `docs` the person's drafts it is for (by default those that read the place). */
export const ask = (kind: string, on: Record<string, unknown>, text = '', docs?: string[]) => call<WriteDone & { task: string }>('review-task', { kind, on, ...(text ? { text } : {}), ...(docs?.length ? { docs } : {}) });

/** A row the intake answers with (`write-api.md` §6), with what the message needs (§3.5 of the views' spec). */
/** A row of the intake (`write-api.md` §6), in one of four states once taken: `added` (the work, how it was found, its `act` for an undo), `here` (the work held already, and why), `question` (the file's own words and the works it may be), `cannot` (a code and why); `received` for a drop that waits to be taken, as an unfiled document does. */
export interface TakeRow {
	id: string;
	item: number;
	name: string;
	state: 'added' | 'here' | 'question' | 'cannot' | 'received';
	act?: string;
	ref?: string;
	short?: string;
	title?: string;
	authors?: string[];
	year?: string;
	found_by?: 'arxiv' | 'doi' | 'zbl' | 'entry' | 'title' | 'none';
	/** The identifier loom found, `scheme:value` with the scheme lower-case (`arxiv:2209.01234v2`); null where none was found. On an added row. */
	identifier?: string | null;
	tex?: boolean;
	unconfirmed?: boolean;
	/** Filed under a work the library had. */
	under?: boolean;
	why?: string;
	code?: string;
	question?: string;
	document?: { name: string; kind: string; identifiers: string[] };
	/** The works it may be; `how` the identifier the file states that the work states too, null for the work it was dropped on where that states none of them. */
	candidates?: { ref: string; short: string; title: string; authors: string[]; year: string; how: string | null }[];
}
