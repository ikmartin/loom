// Round six's fixture and the client against what loom sends, in both directions, so neither can wander from the backend: every generated sample of Review's and the Web's reads and writes (`docs/specs/fixture/views/`, made by `scripts/regen views` from `evidence.md` §6 to §8) passes through the client as a served answer would, the client sending exactly the sample's request; and every answer the fixture gives the same read or write has the sample's fields and types.
import { readdirSync, readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { forgetCapabilities } from '$lib/write';
import * as api from '../api';
import { fixtureSource } from './source';

const DIR = new URL('../../../../../docs/specs/fixture/views/', import.meta.url);

interface Sample {
	name: string;
	endpoint: string;
	request: Record<string, unknown>;
	answer: Record<string, unknown> & { status?: number; error?: { code: string } };
}

const samples: Sample[] = readdirSync(DIR)
	.filter((f) => f.endsWith('.json'))
	.sort()
	.map((f) => ({ name: f.replace(/\.json$/, ''), ...(JSON.parse(readFileSync(new URL(f, DIR), 'utf8')) as Omit<Sample, 'name'>) }));

/** The transport's fields, which the views' spec adds to every answer and request (`gen`, `since`), and the publisher's `ok` and `result`, which the client does not read. */
const TRANSPORT = new Set(['ok', 'gen', 'unchanged', 'since', 'result']);

/** Fields whose shape is a union the specs name: an ask's place by its `what`, a row's body by its kind, what changed under an attestation, a result's source (`{doc}` for a draft's, `{ref, short}` for a work's); compared as objects only. */
const VARIANT = new Set(['on', 'body', 'changed', 'target', 'source']);

/** The fields an ask to an agent carries beyond the row's own, by its `what` (`evidence.md` §4.1). */
const ASK_FIELDS: Record<string, string[]> = {
	read: ['nodes', 'marks', 'words'],
	digest: ['ref', 'scope', 'nodes', 'marks', 'words'],
	ask: ['text', 'quote', 'words'],
	correct: ['text', 'words'],
	restate: ['target', 'differs', 'words'],
	'which-result': ['cites', 'words'],
	formalize: ['target', 'state', 'prove', 'assume', 'words']
};
const AGENT_ROW = ['row', 'kind', 'docs', 'task', 'what', 'on', 'working', 'asked_at'];

const kindOf = (v: unknown) => (v === null ? 'null' : Array.isArray(v) ? 'array' : typeof v);

/** Where `got` differs from `want` in fields and types: an object's keys (less the transport's), each value's type, null standing for any type, and an array's items each against the sample's item of the same `kind`, else its first. */
function differences(got: unknown, want: unknown, at = ''): string[] {
	if (want === null || got === null) return [];
	if (kindOf(got) !== kindOf(want)) return [`${at || '.'}: ${kindOf(got)} where loom sends ${kindOf(want)}`];
	if (Array.isArray(got)) {
		const items = want as unknown[];
		if (!items.length) return [];
		return got.flatMap((g, i) => {
			// an item tagged by its kind, or a section by its head, against the sample's item of the same; an untagged one against the sample's item with the same fields where there is one (a folded group sends no rows), else its first
			const tag = (x: unknown) => (x as { kind?: string })?.kind ?? (x as { head?: string })?.head;
			const keys = (x: unknown) => (x && typeof x === 'object' ? Object.keys(x).sort().join() : '');
			const match = tag(g) === undefined ? (items.find((w) => keys(w) === keys(g)) ?? items[0]) : items.find((w) => tag(w) === tag(g));
			return match === undefined ? [] : differences(g, match, `${at}[${i}]`);
		});
	}
	if (typeof got !== 'object') return [];
	const g = got as Record<string, unknown>;
	const w = want as Record<string, unknown>;
	if (g.kind === 'agents' && w.kind === 'agents' && 'row' in w) return agentRow(g, w, at);
	const out: string[] = [];
	for (const k of Object.keys(w)) if (!TRANSPORT.has(k) && !(k in g)) out.push(`${at}.${k}: missing`);
	for (const k of Object.keys(g)) if (!TRANSPORT.has(k) && !(k in w)) out.push(`${at}.${k}: not sent by loom`);
	for (const k of Object.keys(w)) {
		if (!(k in g) || TRANSPORT.has(k)) continue;
		if (VARIANT.has(k)) {
			if (g[k] !== null && w[k] !== null && kindOf(g[k]) !== kindOf(w[k])) out.push(`${at}.${k}: ${kindOf(g[k])} where loom sends ${kindOf(w[k])}`);
			continue;
		}
		out.push(...differences(g[k], w[k], `${at}.${k}`));
	}
	return out;
}

/** An agents row: the row's own fields as the sample has them, and beyond them only the fields its `what` carries. */
function agentRow(g: Record<string, unknown>, w: Record<string, unknown>, at: string): string[] {
	const out: string[] = [];
	for (const k of AGENT_ROW) if (!(k in g)) out.push(`${at}.${k}: missing`);
	// a kind of ask loom does not make here (round six lists some) carries its words alone
	const own = ASK_FIELDS[String(g.what)] ?? ['words'];
	for (const k of Object.keys(g)) if (!AGENT_ROW.includes(k) && !own.includes(k) && !TRANSPORT.has(k)) out.push(`${at}.${k}: not an ask's field for ${String(g.what)}`);
	for (const k of AGENT_ROW) if (k in g && k in w && !VARIANT.has(k)) out.push(...differences(g[k], w[k], `${at}.${k}`));
	return out;
}

describe('the shape check itself', () => {
	it('finds a missing field, a field loom does not send, and a type that differs; null is any type', () => {
		expect(differences({ a: 1, b: 'x' }, { a: 1, c: 2 })).toEqual(['.c: missing', '.b: not sent by loom']);
		expect(differences({ a: '1' }, { a: 1 })).toEqual(['.a: string where loom sends number']);
		expect(differences({ a: null, b: [{ kind: 'x', n: 1 }] }, { a: 'y', b: [{ kind: 'x', n: 2 }] })).toEqual([]);
		expect(differences({ b: [{ kind: 'x', n: '1' }] }, { b: [{ kind: 'x', n: 2 }] })).toEqual(['.b[0].n: string where loom sends number']);
	});
});

// ---- the client against each sample ----

/** The call the views make for a sample's request, through the client's own functions. */
const CALLS: Record<string, (r: Record<string, unknown>) => Promise<api.Answer<unknown>>> = {
	'review-counts': () => api.reviewCounts(),
	'review-list': (r) => api.reviewList((r.kind as never) ?? 'all', r.doc as string | undefined),
	'review-row': (r) => api.reviewRow(r.row as string),
	'review-answer': (r) => api.answer(r.question as string, (r.choice as number | undefined) ?? null, (r.text as string | undefined) ?? ''),
	'review-task': (r) => api.ask(r.kind as string, r.on as Record<string, unknown>, (r.text as string | undefined) ?? '', r.docs as string[] | undefined),
	'review-task-delete': (r) => api.withdraw(r.task as string),
	'web-list': (r) => api.webList({ scope: r.scope as never, doc: r.doc as string | undefined }, (r.sort as never) ?? 'document', (r.open as string[]) ?? [], (r.offset as number) ?? 0),
	'web-group': (r) => api.webGroup({ scope: r.scope as never, doc: r.doc as string | undefined }, r.group as string),
	'web-search': (r) => api.webSearch({ scope: r.scope as never, doc: r.doc as string | undefined }, r.q as string),
	'web-focus': (r) => api.webFocus({ scope: r.scope as never, doc: r.doc as string | undefined }, r.result as string, r.more === true),
	'web-graph': (r) => api.webGraph({ scope: r.scope as never, doc: r.doc as string | undefined }, r.result as string)
};

describe('every generated sample passes through the client as a served answer would', () => {
	let sent: { url: string; body: unknown }[] = [];
	let answer: Sample['answer'] = {};
	beforeEach(() => {
		forgetCapabilities();
		sent = [];
		vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
			if (!init) return Response.json({ write_api: 1, capabilities: Object.keys(CALLS), token: 't' });
			sent.push({ url, body: JSON.parse(String(init.body)) });
			const { status, ...rest } = answer;
			return Response.json(rest, { status: status ?? 200 });
		});
	});
	afterEach(() => vi.unstubAllGlobals());

	it('finds the fifteen samples', () => {
		expect(samples.length).toBe(15);
		for (const s of samples) expect(CALLS, s.endpoint).toHaveProperty([s.endpoint]);
	});

	for (const s of samples) {
		it(`${s.name}: the client sends the sample's request and takes its answer`, async () => {
			answer = s.answer;
			const got = await CALLS[s.endpoint](s.request);
			expect(sent).toHaveLength(1);
			expect(sent[0].url).toBe(`/_api/${s.endpoint}`);
			expect(sent[0].body).toEqual(s.request);
			if (s.answer.status) expect(got).toEqual({ ok: false, error: s.answer.error });
			else expect(got).toEqual({ ok: true, value: s.answer });
		});
	}
});

// ---- round six's fixture against each sample ----

/** A sample's request with the fixture's own ids where it names one, so the fixture answers what loom answered. */
function adapted(s: Sample, f: ReturnType<typeof fixtureSource>): Record<string, unknown> {
	const r = { ...s.request };
	const review = f.data.review;
	const question = review.rows.find((x) => x.kind === 'questions');
	const task = review.tasks[0];
	switch (s.endpoint) {
		case 'review-row':
			return { row: question?.row };
		case 'review-answer':
			return { ...r, question: question && 'question' in question ? question.question : '' };
		case 'review-task-delete':
			return { task: task?.task };
		case 'review-task':
			return { ...r, on: { key: 'thm:count', quote: 'a polynomial in' } };
		case 'review-list':
		case 'web-list':
			return r.doc ? { ...r, doc: 'drafting/main.tex' } : r.open ? { ...r, open: ['drafting/main.tex'] } : r;
		case 'web-group':
			return { ...r, group: 'drafting/main.tex' };
		case 'web-focus':
		case 'web-graph':
			return { ...r, result: 'thm:count' };
		default:
			return r;
	}
}

describe("round six's fixture answers with loom's fields and types", () => {
	for (const s of samples) {
		it(`${s.name}`, async () => {
			const f = fixtureSource();
			// a refusal is tried as the sample tried it: the same request twice where the first closes what it names
			const request = adapted(s, f);
			if (s.answer.status) await f.call(s.endpoint, request);
			const got = await f.call(s.endpoint, request);
			if (s.answer.status) {
				expect(got.ok).toBe(false);
				expect(!got.ok && got.error.code).toBe(s.answer.error?.code);
				return;
			}
			expect(got.ok, JSON.stringify(got)).toBe(true);
			expect(differences(got.ok ? got.value : null, s.answer)).toEqual([]);
		});
	}
});
