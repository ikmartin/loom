// Round six's fixture and the client against what loom sends, in both directions, so neither can wander from the backend: every generated sample of Review's, the Web's and the Library's reads and writes (`docs/specs/fixture/views/`, made by `scripts/regen views` from `evidence.md` §6 to §8 and by `scripts/regen views-library` from `write-api.md` §2 and §6) passes through the client as a served answer would, the client sending exactly the sample's request; and every answer the fixture gives the same read or write has the sample's fields and types. A field one side fills and the other's answers leave null or empty is checked by nothing, so each is named, with the sample or the fixture's answer that would check it (`AWAITING_SAMPLES`, `NOT_ANSWERED`).
import { readdirSync, readFileSync } from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { forgetCapabilities } from '$lib/write';
import * as api from '../api';
import { fixtureSource } from './source';

// the samples are generated (`scripts/regen views`) and committed on library-web; on a branch that has not taken them yet, this check needs them copied in
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

/** Fields whose shape is a union the specs name: an ask's place by its `what`, a row's body by its kind, what changed under an attestation, a result's source (`{doc}` for a draft's, `{ref, short}` for a work's); and a node's `points`, keyed by the ids its body names; compared as objects only. */
const VARIANT = new Set(['on', 'body', 'changed', 'target', 'source', 'points']);

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

/** What tells a list's items apart: a row's kind, a section's head, an intake row's state; a node's place, which the digest adds to the places, is tagged apart and so meets none of loom's yet. */
const tag = (x: unknown): string | undefined => (x as { kind?: string })?.kind ?? (x as { head?: string })?.head ?? (x as { state?: string })?.state ?? (x && typeof x === 'object' && 'node' in x && 'rects' in x ? "a node's place" : undefined);

/** The sample's items an item is compared with, merged into one: each field the first value of theirs that is not null, an array's items gathered from all, so a field one item leaves null is checked against another that fills it. */
function merged(items: unknown[]): unknown {
	if (!items.every((x) => x && typeof x === 'object' && !Array.isArray(x))) return items[0];
	const out: Record<string, unknown> = {};
	for (const x of items as Record<string, unknown>[])
		for (const [k, v] of Object.entries(x)) {
			if (Array.isArray(v) && Array.isArray(out[k])) out[k] = [...(out[k] as unknown[]), ...v];
			else if (v !== null && v !== undefined && (out[k] === null || out[k] === undefined)) out[k] = v;
			else if (!(k in out)) out[k] = v;
		}
	return out;
}

/** Where `got` differs from `want` in fields and types: an object's keys (less the transport's), each value's type, null standing for any type, and an array's items each against the sample's items of the same `kind`, merged (`merged`). */
function differences(got: unknown, want: unknown, at = ''): string[] {
	if (want === null || got === null) return [];
	if (kindOf(got) !== kindOf(want)) return [`${at || '.'}: ${kindOf(got)} where loom sends ${kindOf(want)}`];
	if (Array.isArray(got)) {
		const items = want as unknown[];
		if (!items.length) return [];
		return got.flatMap((g, i) => {
			// an item tagged (`tag`) against the sample's items of the same tag; an untagged one against the sample's items with the same fields where there are some (a folded group sends no rows), else all of them
			const keys = (x: unknown) => (x && typeof x === 'object' ? Object.keys(x).sort().join() : '');
			const same = items.filter((w) => keys(w) === keys(g));
			const pool = tag(g) === undefined ? (same.length ? same : items) : items.filter((w) => tag(w) === tag(g));
			return pool.length ? differences(g, merged(pool), `${at}[${i}]`) : [];
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

/** The fields a value fills, each by its path with an array's items as `[]`, or `[kind]` by their tag (`.works[].lookup.identifier`, `.groups[].rows[cited].stubs`): not null, a list not empty, and a variant (`VARIANT`) as itself, since its fields are compared by none. */
function filled(v: unknown, at = '', out = new Set<string>()): Set<string> {
	if (Array.isArray(v))
		for (const x of v) {
			const t = tag(x);
			if (t !== undefined) out.add(`${at}[${t}]`);
			filled(x, `${at}[${t ?? ''}]`, out);
		}
	else if (v && typeof v === 'object')
		for (const [k, x] of Object.entries(v)) {
			if (TRANSPORT.has(k) || x === null || x === undefined || (Array.isArray(x) && !x.length)) continue;
			out.add(`${at}.${k}`);
			if (!VARIANT.has(k)) filled(x, `${at}.${k}`, out);
		}
	return out;
}

/** The fields the fixture fills that loom's samples send only as null, so the check above cannot see their shape: the outermost of each, where loom fills what holds it. */
function unchecked(fixture: Set<string>, loom: Set<string>): string[] {
	const parent = (p: string) => (/\[[^\]]+\]$/.test(p) ? p.replace(/\[[^\]]+\]$/, '') : p.replace(/\.[^.[\]]+$/, '')).replace(/\[\]$/, '');
	return [...fixture].filter((p) => !loom.has(p) && (parent(p) === '' || loom.has(parent(p)))).sort();
}

describe('the shape check itself', () => {
	it('finds a missing field, a field loom does not send, and a type that differs; null is any type', () => {
		expect(differences({ a: 1, b: 'x' }, { a: 1, c: 2 })).toEqual(['.c: missing', '.b: not sent by loom']);
		expect(differences({ a: '1' }, { a: 1 })).toEqual(['.a: string where loom sends number']);
		expect(differences({ a: null, b: [{ kind: 'x', n: 1 }] }, { a: 'y', b: [{ kind: 'x', n: 2 }] })).toEqual([]);
		expect(differences({ b: [{ kind: 'x', n: '1' }] }, { b: [{ kind: 'x', n: 2 }] })).toEqual(['.b[0].n: string where loom sends number']);
	});
	it("checks a list's item against every sample item like it, so a field the first leaves null is checked where another fills it", () => {
		const loom = { works: [{ ref: 'a', lookup: null }, { ref: 'b', lookup: { state: 'unconfirmed', identifier: 'arxiv:1' } }] };
		expect(differences({ works: [{ ref: 'c', lookup: { state: 'unconfirmed', id: 'arxiv:1' } }] }, loom)).toEqual(['.works[0].lookup.identifier: missing', '.works[0].lookup.id: not sent by loom']);
	});
	it('names a field the fixture fills that every sample of loom leaves null', () => {
		const loom = filled({ works: [{ ref: 'a', digested: null, lookup: { state: 'x' }, used_in: [] }] });
		expect(unchecked(filled({ works: [{ ref: 'b', digested: { statements: 1 }, lookup: { state: 'y' }, used_in: ['main.tex'] }] }), loom)).toEqual(['.works[].digested', '.works[].used_in']);
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
	'web-graph': (r) => api.webGraph({ scope: r.scope as never, doc: r.doc as string | undefined }, r.result as string),
	'library-works': (r) => api.works(r.doc as string | undefined, r.since as number | undefined),
	'library-places': (r) => (r.node ? api.places({ node: r.node as string }) : api.places({ ref: r.ref as string, ...(r.pages ? { pages: r.pages as number[] } : {}) }, r.since as number | undefined)),
	'library-work': (r) => api.work(r.ref as string),
	'library-digest-scopes': (r) => api.digestScopes(r.all ? { all: true } : { ref: r.ref as string }),
	'library-node': (r) => api.node(r.node ? { node: r.node as string, ...(r.brief ? { brief: true } : {}) } : { ref: r.ref as string, item: r.item as string }),
	'library-find': (r) => api.find(r.ref as string, r.q as string),
	'library-digest': (r) => api.digest(r.refs as string[] | 'all', r.scope as never, r.chosen as string[] | undefined),
	'library-receive': (r) => api.receive(new File([new Uint8Array(r.size as number)], r.name as string)),
	'library-take': (r) => api.take(r.items as never, r.online as false | undefined),
	'library-answer': (r) => api.answerDrop(r.question as string, r.same as string | null, r.online as boolean | undefined),
	'library-undo': (r) => api.undoTake(r.id as string, r.act as string | undefined),
	'library-unfile': (r) => api.unfile(r.ref as string, r.which as 'pdf' | 'tex' | undefined),
	'library-look-up': (r) => api.lookUp(r.ref as string, r.online === true),
	'library-entry': (r) => api.entry(r.ref as string, r.bibtex as string),
	'library-delete': (r) => api.remove(r.ref as string),
	'library-restore': (r) => api.restore(r.undo as string)
};

describe('every generated sample passes through the client as a served answer would', () => {
	let sent: { url: string; body: unknown }[] = [];
	let answer: Sample['answer'] = {};
	beforeEach(() => {
		forgetCapabilities();
		sent = [];
		vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
			if (!init) return Response.json({ write_api: 1, capabilities: Object.keys(CALLS), token: 't' });
			// a received file is its bytes, its name in the address: the request a sample records is its name and size
			sent.push({ url, body: init.body instanceof File || init.body instanceof Blob ? { name: new URL(url, 'http://x').searchParams.get('name'), size: (init.body as Blob).size } : JSON.parse(String(init.body)) });
			const { status, ...rest } = answer;
			return Response.json(rest, { status: status ?? 200 });
		});
	});
	afterEach(() => vi.unstubAllGlobals());

	it("finds Review's and the Web's seventeen samples and the Library's", () => {
		expect(samples.filter((s) => !s.endpoint.startsWith('library-')).length).toBe(17);
		expect(samples.filter((s) => s.endpoint.startsWith('library-')).length).toBeGreaterThan(20);
		for (const s of samples) expect(CALLS, s.endpoint).toHaveProperty([s.endpoint]);
	});

	for (const s of samples) {
		it(`${s.name}: the client sends the sample's request and takes its answer`, async () => {
			answer = s.answer;
			const got = await CALLS[s.endpoint](s.request);
			expect(sent).toHaveLength(1);
			expect(sent[0].url.replace(/\?.*$/, '')).toBe(`/_api/${s.endpoint}`);
			expect(sent[0].body).toEqual(s.request);
			// a refusal keeps loom's code and HTTP status, which tell loom's own failures from the transport's
			if (s.answer.status) expect(got).toEqual({ ok: false, error: { ...s.answer.error, status: s.answer.status } });
			else expect(got).toEqual({ ok: true, value: s.answer });
		});
	}
});

// ---- round six's fixture against each sample ----

/** The Library's samples whose state round six's fixture does not model, each with why; they are said here rather than passed. */
const NOT_MODELLED: Record<string, string> = {
	'library-entry.key-taken': 'the fixture keeps no entries whose keys could collide',
	'library-undo.waits-again': 'the fixture files no document under a work, so no filing is undone',
	'library-digest.no-reviewer': 'the fixture always knows its reviewer, so an ask is never refused for want of one',
};

/** The fixture a sample is asked of: on a quilt that has not said whether loom may use the network, or has it off, where the sample's refusal needs one. */
const fixtureFor = (s: Sample) => fixtureSource(undefined, s.name.endsWith('network-unasked') ? { network: 'unasked' } : s.name.endsWith('offline') ? { network: 'off' } : {});

/** A sample's request with the fixture's own ids where it names one, so the fixture answers what loom answered; some first make what the request names (a delete before a restore, a take before an undo). */
async function adapted(s: Sample, f: ReturnType<typeof fixtureSource>): Promise<Record<string, unknown>> {
	const r = { ...s.request };
	const review = f.data.review;
	const question = review.rows.find((x) => x.kind === 'questions');
	const task = review.tasks[0];
	// a work holding a PDF, one found by an identifier and not yet looked up, and one stating none
	const held = f.data.works.find((w) => w.holds.pdf)!.ref;
	const unlooked = f.data.works.find((w) => !w.lookup)!.ref;
	// a work held with its source, one held only as a PDF, and one holding neither
	const source = f.data.works.find((w) => w.holds.tex && w.holds.pdf)!.ref;
	const pdfOnly = f.data.works.find((w) => w.holds.pdf && !w.holds.tex)!.ref;
	const neither = f.data.works.find((w) => !w.holds.pdf && !w.holds.tex)!.ref;
	// its outline, and the first of its results digested, with its page
	const read = await f.call<{ gen: number; outline: { items: { item: string | null; node: string | null; page: number | null }[] } }>('library-work', { ref: source });
	const outline = read.ok ? read.value.outline.items : [];
	const digested = outline.find((i) => i.node);
	switch (s.endpoint) {
		case 'review-row':
			// the sample names its row's kind after the read's name, where it is not a question's
			return { row: (s.name.includes('.') ? review.rows.find((x) => x.kind === s.name.split('.')[1]) : question)?.row };
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
		case 'library-works':
			// a work found by an identifier and not looked up, so the list holds one whose `lookup` is filled, as loom's does
			await f.call('library-take', { items: [{ text: '2209.01234v2' }], online: false });
			return r.doc ? { ...r, doc: 'drafting/main.tex' } : r.since !== undefined ? { since: f.data.gen } : r;
		case 'library-take': {
			// a question made as the answer's is, by a file named by an arXiv number a work states
			if (!s.name.endsWith('.question')) return r;
			const got = await f.receive(new File([new Uint8Array(8)], '2000.01000v2.pdf'));
			return { items: [{ incoming: got.ok ? got.value.incoming : '' }] };
		}
		case 'web-search':
			return { ...r, q: 'polynomial' };
		case 'library-delete':
		case 'library-unfile':
		case 'library-entry':
			return { ...r, ref: held };
		case 'library-look-up':
			return { ...r, ref: unlooked };
		case 'library-answer': {
			// a question made first, by a file named by an arXiv number a work states; answered with no work, with its candidate, or with a work it is not
			const got = await f.receive(new File([new Uint8Array(8)], '2000.01000v2.pdf'));
			const took = got.ok ? await f.call<{ gen: number; rows: { question?: string; candidates?: { ref: string }[] }[] }>('library-take', { items: [{ incoming: got.value.incoming }] }) : null;
			const row = took?.ok ? took.value.rows[0] : {};
			const candidate = row.candidates?.[0]?.ref ?? '';
			const other = f.data.works.find((w) => w.ref !== candidate)!.ref;
			return { ...r, question: row.question ?? '', same: s.name.endsWith('.same') ? candidate : r.same === null ? null : other };
		}
		case 'library-work':
		case 'library-digest-scopes':
		case 'library-find':
			return r.all ? r : { ...r, ref: s.name.endsWith('.no-document') ? neither : s.name.endsWith('.pdf') ? pdfOnly : source };
		case 'library-digest':
			return { ...r, refs: [s.name.endsWith('.no-document') ? neither : source] };
		case 'library-node': {
			// a digested result of the work held with its source, or one of its results not yet digested
			if (s.answer.status) return r;
			if (r.item) return { ref: source, item: outline.find((i) => i.item && !i.node)?.item ?? '' };
			return { ...r, node: digested?.node ?? '' };
		}
		case 'library-places': {
			// a node's place, alone or on the pages asked for, where the sample asks for one
			if (r.node) return { node: digested?.node ?? '' };
			if (r.pages && s.name.endsWith('.nodes')) return { ref: source, pages: [digested?.page ?? 1] };
			// a work with a mark to digest on its pages, which is an annotation placed; one holding no PDF for the refusal
			if (s.answer.status) return { ref: f.data.works.find((w) => !w.holds.pdf)!.ref };
			const [ref, marks] = Object.entries(f.data.marks).find(([, ms]) => ms.length)!;
			return { ref, ...(r.pages ? { pages: [marks[0].page] } : {}), ...(r.since !== undefined ? { since: f.data.gen } : {}) };
		}
		case 'library-restore': {
			const del = await f.call<{ gen: number; undo: string }>('library-delete', { ref: held });
			return { undo: del.ok ? del.value.undo : '' };
		}
		case 'library-undo': {
			if (s.answer.status) return r;
			const took = await f.call<{ gen: number; rows: { id: string; act?: string }[] }>('library-take', { items: [{ text: '2209.01234v2' }], online: false });
			const row = took.ok ? took.value.rows[0] : { id: '' };
			return { id: row.id, ...(row.act ? { act: row.act } : {}) };
		}
		default:
			return r;
	}
}

/** The fields the fixture fills that no sample of loom's fills yet, so their shape is unchecked, each with the sample that would check it; those samples are loom's generators' (`scripts/regen views`, `views-library`). A field the fixture fills that is not listed fails the check below, and so does a listed one a sample now fills. */
const AWAITING_SAMPLES: Record<string, string> = {
	'library-answer .row.authors': 'a work of its own naming its authors',
	'library-node .title': 'a digested result with a title, which none of the showcase\'s Arden 2024 has',
	'library-work .outline.items[].lean.role': 'a work\'s result that a Lean record states',
	'library-work .outline.items[].title': 'a work\'s result with a title, which none of the showcase\'s Arden 2024 has',
	'library-works .works[].cited_as': 'a work a compiled document cites',
	'library-works .works[].digested': 'a digested work',
	'library-works .works[].version': 'a version of a work',
	'review-list .groups[agents].rows[agents].marks': 'an ask to digest marked places',
	'review-list .groups[agents].rows[agents].ref': 'an ask to digest a work',
	'review-list .groups[agents].rows[agents].scope': 'an ask to digest a work',
	'review-list .groups[agents].rows[agents].text': 'an ask in the person\'s words',
	'review-list .groups[agents].rows[agents].working': 'an ask an agent is working on',
	'review-list .groups[attest].rows[attest].paper': 'a library node to attest',
	'review-list .groups[attest].rows[attest].reading': 'a result to attest that the person has read',
	'review-list .groups[attested-changed].rows[attested-changed].resting': 'a changed definition that results rest on',
	'review-list .groups[check]': 'digested results to check',
	'review-list .groups[cited]': 'cited results to digest',
	'review-list .groups[edits].rows[edits].broke': 'an edit made in place that broke its compile',
	'review-list .groups[questions].rows[questions].under.ref': 'a question asked while digesting a work',
	'review-row .row.under.ref': 'a question asked while digesting a work',
	'web-focus .more.proofs': 'a result in focus with a proof',
	'web-focus .rests_on': 'a result in focus that rests on another',
	'web-focus .uses.proof': 'a result in focus whose proof uses another',
	'web-focus .uses.statement': 'a result in focus whose statement uses another',
	'web-graph .columns.back': 'a graph with results behind the focus',
	'web-graph .columns.uses': 'a graph whose focus uses another result',
	'web-list .sections[library].groups': "the library's results in the Web, which the node store adds"
};

/** The fields loom's samples fill that no answer of the fixture fills, so loom's shape there is checked against nothing, each with why. A field loom fills and the fixture leaves that is not listed fails the check below, and so does a listed one the fixture now fills. */
const NOT_ANSWERED: Record<string, string> = {
	'library-node .lean': "the fixture answers null for a result no Lean record names, where loom answers {lean: 'none'}",
	'library-node .macros': "the fixture's first digested result of a work held with its source is Arden 2024's, whose work has no macros node in round six",
	'library-node .proofs': "the fixture's first digested result of a work held with its source has no proof in round six",
	"library-places .places[a node's place].lean": "the fixture answers null for a result no Lean record names, where loom answers {lean: 'none'}",
	'library-take .rows[cannot]': "the fixture's intake refuses nothing it is given",
	'library-take .rows[here]': "the fixture's intake never meets a file it holds",
	'web-focus .used_by.rows': "the fixture's result in focus, Theorem 3.4, is used by none",
	'web-graph .columns.used_by': "the fixture's result in focus, Theorem 3.4, is used by none"
};

describe("round six's fixture answers with loom's fields and types", () => {
	/** By endpoint, the fields loom's samples fill and the fields the fixture's answers fill. */
	const loomFills = new Map<string, Set<string>>();
	const fixtureFills = new Map<string, Set<string>>();
	for (const s of samples) if (!s.answer.status && !NOT_MODELLED[s.name]) filled(s.answer, '', loomFills.get(s.endpoint) ?? loomFills.set(s.endpoint, new Set()).get(s.endpoint));
	for (const s of samples) {
		if (NOT_MODELLED[s.name]) {
			it.skip(`${s.name}: ${NOT_MODELLED[s.name]}`, () => {});
			continue;
		}
		it(`${s.name}`, async () => {
			const f = fixtureFor(s);
			const request = await adapted(s, f);
			// a received file is the fixture's `receive`, the one request that is not JSON
			const ask = () => (s.endpoint === 'library-receive' ? f.receive(new File([new Uint8Array(Number(request.size))], String(request.name))) : f.call(s.endpoint, request));
			// a refusal is tried as the sample tried it: the same request twice where the first closes what it names
			if (s.answer.status) await ask();
			const got = await ask();
			if (s.answer.status) {
				expect(got.ok).toBe(false);
				expect(!got.ok && got.error.code).toBe(s.answer.error?.code);
				return;
			}
			expect(got.ok, JSON.stringify(got)).toBe(true);
			expect(differences(got.ok ? got.value : null, s.answer)).toEqual([]);
			if (got.ok) filled(got.value, '', fixtureFills.get(s.endpoint) ?? fixtureFills.set(s.endpoint, new Set()).get(s.endpoint));
		});
	}
	it('fills no field that every sample of loom leaves null, but those that wait on samples', () => {
		const blind = [...fixtureFills].flatMap(([endpoint, got]) => unchecked(got, loomFills.get(endpoint) ?? new Set()).map((p) => `${endpoint} ${p}`));
		expect(blind).toEqual(Object.keys(AWAITING_SAMPLES).sort());
	});
	it("leaves null no field loom's samples fill, but those it does not model", () => {
		const blind = [...loomFills].flatMap(([endpoint, sent]) => unchecked(sent, fixtureFills.get(endpoint) ?? new Set()).map((p) => `${endpoint} ${p}`));
		expect(blind).toEqual(Object.keys(NOT_ANSWERED).sort());
	});
});
