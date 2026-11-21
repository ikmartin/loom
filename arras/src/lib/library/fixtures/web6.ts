// The Web's part of round six's fixture: the prototype's web of results, main.tex's and bounds.tex's with the library's they rest on, answered as `web-list`, `web-group`, `web-search`, `web-focus` and `web-graph` will answer them. Status is given as the evidence lane's fields, which the viewer only draws. Written from the spec (`docs/specs/library-views.md` §5) until those reads are served.

import type { Lean, Paper, Row, WebFocus, WebGraph, WebList, WebScope, WebSearch, WebSection } from '../types';

const MAIN = 'drafting/main.tex';
const BOUNDS = 'drafting/bounds.tex';

/** A result as round six has it: `st` its status in the prototype's own words, `s` and `p` what its statement and its proof use. */
interface N {
	name: string;
	title?: string;
	src: string;
	st: 'formal' | 'leanq' | 'unformal' | 'checked' | 'unchecked' | 'stub' | 'assumed';
	s?: string[];
	p?: string[];
	ex?: string;
	body?: string;
	rel?: string[];
	/** A result of a draft with no label, which a Lean statement could not name. */
	nolabel?: true;
}

/** By result: a draft's results by label, the library's by node. */
const W: Record<string, N> = {
	'def:quiver': { name: 'Definition 2.1', title: 'Quiver', src: MAIN, st: 'formal', ex: 'A quiver Q is a quadruple (V, A, s, t) with V and A finite sets …' },
	'def:divergence': { name: 'Definition 2.2', title: 'Divergence', src: MAIN, st: 'formal', s: ['def:quiver'], ex: 'The divergence of a weighting w at a vertex v is …' },
	'prop:saturated': { name: 'Proposition 2.6', src: MAIN, st: 'formal', s: ['def:quiver'], p: ['def:divergence'], rel: [], ex: '𝒵(Q) is saturated in W(Q).' },
	'thm:rank': { name: 'Theorem 3.1', title: 'Rank', src: MAIN, st: 'formal', s: ['def:quiver', 'tq-0201'], p: ['tq-0203', 'prop:saturated'], rel: ['tq-0203'], ex: 'rank 𝒵(Q) = |A(Q)| − |V(Q)| + c', body: 'Let \\(Q\\) be a quiver whose underlying graph has \\(c\\) connected components. Then \\[\\operatorname{rank} \\mathcal{Z}(Q) = |A(Q)| - |V(Q)| + c.\\]' },
	'lem:forest': { name: 'Lemma 3.3', src: MAIN, st: 'leanq', s: ['def:divergence'], p: ['prop:saturated'], ex: 'A balanced weighting supported on a forest is zero; on a cycle …' },
	'thm:count': { name: 'Theorem 3.4', title: 'Bounded balanced weightings', src: MAIN, st: 'unformal', s: ['def:quiver', 'def:height'], p: ['thm:rank', 'lem:forest', 'lem:interval', 'lem:boxes', 'tq-020E', 'tq-020G', 'tq-02D4', 'tq-04A1', 'tq-05A1'], ex: 'The number of balanced weightings of height at most h is a polynomial in h …', body: 'The number of balanced weightings of \\(Q\\) of height at most \\(h\\) is a polynomial in \\(h\\) of degree \\(|A(Q)| - |V(Q)| + c\\).' },
	'conv:finite': { name: 'Convention 1.1', src: MAIN, st: 'unformal', ex: 'Every quiver in this paper is finite: both V(Q) and A(Q) are finite sets.' },
	'def:box': { name: 'Definition 2.4', title: 'Box', src: MAIN, st: 'unformal', s: ['def:quiver'], ex: 'A box is a product of intervals of weightings.' },
	'def:height': { name: 'Definition 3.2', title: 'Height', src: MAIN, st: 'unformal', ex: 'The height of a weighting w is the largest |w(a)|.', nolabel: true },
	'lem:interval': { name: 'Lemma 3.10', src: MAIN, st: 'unformal', s: ['def:box'], p: ['def:height'], ex: 'Each interval of balanced weightings is a box.' },
	'lem:boxes': { name: 'Lemma 3.11', src: MAIN, st: 'unformal', s: ['def:height'], ex: 'The boxes of height at most h number polynomially many in h.' },
	'def:connected': { name: 'Definition 3.7', title: 'Connected', src: MAIN, st: 'leanq', ex: 'A quiver is connected if its underlying graph is.' },
	'prop:tree': { name: 'Proposition 3.8', src: MAIN, st: 'leanq', s: ['def:connected'], ex: 'A connected quiver with c = 1 …' },
	'lem:bridge': { name: 'Lemma 3.9', src: MAIN, st: 'leanq', s: ['def:connected'], ex: 'Removing a bridge disconnects …' },
	'cor:cycle': { name: 'Corollary 3.5', src: MAIN, st: 'leanq', s: ['def:connected'], p: ['thm:rank'], ex: 'A connected quiver has a nonzero balanced weighting iff …' },
	'tq-020E': { name: 'Lemma 5.7', src: 'arden24', st: 'unchecked', ex: 'An exchange preserves balance.' },
	'tq-02D4': { name: 'Definition 4.1', title: 'Exchange', src: 'arden24', st: 'checked', ex: 'An exchange between two weightings is …' },
	'tq-0201': { name: 'Definition 1.2', title: 'Cycle space', src: 'arden24', st: 'checked', ex: 'The cycle space of Q is the kernel 𝒵(Q) of the divergence map …' },
	'tq-0203': { name: 'Proposition 2.1', src: 'arden24', st: 'assumed', s: ['tq-0201'], ex: 'The image of the divergence map … has rank |V(Q)| − c.' },
	'tq-020G': { name: 'Lemma 5.9', title: 'Exchange bound', src: 'arden24', st: 'unchecked', p: ['tq-00K9'], ex: 'If w ⪯ w′ differ on one cycle, then ‖w − w′‖ ≤ …' },
	'tq-05A1': { name: 'Theorem 5.1', title: 'Extension criterion', src: 'arden25', st: 'unchecked', ex: 'A weighting of a full subquiver extends iff …' },
	'tq-04A1': { name: 'Theorem 2.3', src: 'okafor', st: 'stub' },
	'tq-00K9': { name: 'Theorem 4.1', title: 'Covering bound', src: 'smith', st: 'stub' },
	'tq-00A4': { name: 'Definition 2.1', title: 'Widget', src: 'smith', st: 'checked', ex: 'A widget is a compact set W ⊂ ℝⁿ whose boundary lies in 𝒲.' },
	'tq-00K1': { name: 'Definition 3.1', title: 'Radius', src: 'smith', st: 'unchecked', ex: 'The radius of a bounded set S is inf{r ≥ 0 : S ⊂ B(0, r)}.' },
	'tq-00K3': { name: 'Lemma 3.2', title: 'Test lemma', src: 'smith', st: 'unchecked', s: ['tq-00A4'], ex: 'diam W < ∞, and |x| ≤ diam W + |x₀|.' },
	'tq-00K5': { name: 'Proposition 3.4', title: 'Test proposition', src: 'smith', st: 'leanq', s: ['tq-00A4'], p: ['tq-00K3', 'tq-00B7'], ex: 'W lies in a ball about the origin.' },
	'tq-00B7': { name: 'Lemma 2.1', src: 'jones', st: 'stub' },
	'thm:radius': { name: 'Theorem 1', title: 'Bounded widgets', src: BOUNDS, st: 'unformal', p: ['tq-00K5'], ex: 'Every widget of type k has radius at most …' }
};

const SHORT: Record<string, [string, string]> = { arden24: ['Arden 2024', 'Cycle spaces of finite quivers'], arden25: ['Arden 2025', 'Cycle spaces of finite quivers'], okafor: ['Okafor 2022', 'Median orders on weighting lattices'], smith: ['Smith 2024', 'Widgets and their bounds'], jones: ['Jones 2019', 'Covering estimates'] };

const own = (id: string) => W[id].src.endsWith('.tex');
/** A work's reference: the Library's for round six's works, its own key for a work of the large web. */
const refOf = (refs: Record<string, string>, w: string) => refs[w] ?? `${w}-ref`;

/** Grows the web to the size a reviewer measured: sixty works of eighty results each that Theorem 3.4 rests on, 5,140 results in a draft and what it rests on. Once, for `?web=large`. */
export function growWeb(): void {
	if (SHORT.syn0) return;
	for (let g = 0; g < 60; g++) {
		SHORT[`syn${g}`] = [`Author ${g} ${2000 + (g % 25)}`, `A paper of the large web, ${g + 1}`];
		for (let i = 1; i <= 80; i++) {
			const id = `syn${g}-${i}`;
			W[id] = { name: `Lemma ${Math.ceil(i / 10)}.${i}`, src: `syn${g}`, st: i % 5 ? 'checked' : 'unchecked', ex: `A result of the large web, ${g}.${i}: a weighting of height at most $h$ is a polynomial in $h$.` };
			W['thm:count'].p!.push(id);
		}
	}
	for (let i = 0; i < 325; i++) {
		W[`own:${i}`] = { name: `Lemma 9.${i + 1}`, src: MAIN, st: 'unformal', ex: 'A lemma of the large draft.' };
	}
}
const uses = (id: string) => [...(W[id].s ?? []), ...(W[id].p ?? [])];
const usedBy = (id: string) => Object.keys(W).filter((k) => uses(k).includes(id));

/** A result's two statuses, as the evidence lane's status gives them: `lean` its status's word (`evidence.md` §8). */
function status(n: N): { paper: Paper | null; lean: Lean } {
	if (n.src.endsWith('.tex')) return { paper: null, lean: n.st === 'formal' ? 'formalized' : n.st === 'leanq' ? 'unattested' : 'none' };
	if (n.st === 'assumed') return { paper: 'matches', lean: 'formalized' };
	if (n.st === 'leanq') return { paper: 'matches', lean: 'unattested' };
	return { paper: n.st === 'checked' ? 'matches' : (n.st as Paper), lean: 'none' };
}

/** A result as a list sends it (`ROW`): its title null where it has none. */
export function rowOf(id: string, refs: Record<string, string>): Row {
	const n = W[id];
	const source = own(id) ? { doc: n.src } : { ref: refOf(refs, n.src), short: SHORT[n.src][0] };
	return { result: id, name: n.name, title: n.title ?? null, taxon: n.name.split(' ')[0].toLowerCase(), source, ...status(n) };
}

/** Number order, read naturally: 3.2 before 3.10. */
const num = (id: string) => (W[id].name.split(' ')[1] ?? '').split('.').map((x) => (Number.isNaN(+x) ? x.charCodeAt(0) + 1000 : +x));
const byNum = (a: string, b: string) => {
	const [x, y] = [num(a), num(b)];
	return x[0] - y[0] || (x[1] ?? 0) - (y[1] ?? 0);
};

function closure(ids: string[]): Set<string> {
	const seen = new Set(ids);
	const q = [...ids];
	while (q.length) for (const u of uses(q.pop()!)) if (!seen.has(u)) (seen.add(u), q.push(u));
	return seen;
}

/** Each draft's closure, computed once a read, since the web does not change under a read. */
const closures = new Map<string, Set<string>>();

export function inScope(id: string, scope: WebScope, doc = MAIN): boolean {
	if (scope === 'all') return true;
	if (scope === 'library') return !own(id);
	if (scope === 'draft') return W[id].src === doc;
	let c = closures.get(doc);
	if (!c) {
		c = closure(Object.keys(W).filter((k) => W[k].src === doc));
		closures.set(doc, c);
		queueMicrotask(() => closures.delete(doc));
	}
	return c.has(id);
}

/** The order of the list by status: not read, not compared, Lean accepted and not attested, not formalized, matches the paper, assumed, formalized. */
const RANK: Record<N['st'], number> = { stub: 0, unchecked: 1, leanq: 2, unformal: 3, checked: 4, assumed: 5, formal: 6 };

/** `web-list`. */
export function webList(refs: Record<string, string>, a: { scope: WebScope; doc?: string; sort: string; open?: string[]; offset?: number }): Omit<WebList, 'gen'> {
	const doc = a.doc ?? MAIN;
	const ids = Object.keys(W)
		.filter((k) => inScope(k, a.scope, doc))
		.sort(byNum);
	const row = (k: string) => rowOf(k, refs);
	if (a.sort === 'status') {
		const all = [...ids].sort((x, y) => RANK[W[x].st] - RANK[W[y].st] || byNum(x, y));
		const at = a.offset ?? 0;
		return { count: all.length, rows: all.slice(at, at + 200).map(row), more: Math.max(0, all.length - at - 200) };
	}
	const open = new Set(a.open ?? []);
	// open groups under what a draft rests on carry their rows for the first three only; the rest are read as they come into view
	const works = (list: string[], openAll: boolean) =>
		[...new Set(list.filter((k) => !own(k)).map((k) => W[k].src))].sort().map((w, i) => {
			const ks = list.filter((k) => W[k].src === w);
			return { group: refOf(refs, w), short: SHORT[w][0], title: SHORT[w][1], n: ks.length, ...((openAll && i < 3) || open.has(refOf(refs, w)) ? { rows: ks.map(row) } : {}) };
		});
	const sections: WebSection[] = [];
	if (a.scope === 'draft' || a.scope === 'deps') sections.push({ head: 'draft', doc, rows: ids.filter((k) => W[k].src === doc).map(row) });
	if (a.scope === 'deps') sections.push({ head: 'uses', doc, groups: works(ids, true) });
	if (a.scope === 'all') {
		const docs = [...new Set(ids.filter(own).map((k) => W[k].src))].sort((x, y) => (x === MAIN ? -1 : y === MAIN ? 1 : x.localeCompare(y)));
		sections.push({ head: 'drafts', groups: docs.map((d) => ({ group: d, n: ids.filter((k) => W[k].src === d).length, ...(open.has(d) ? { rows: ids.filter((k) => W[k].src === d).map(row) } : {}) })) });
	}
	if (a.scope === 'all' || a.scope === 'library') sections.push({ head: 'library', groups: works(ids, false) });
	return { count: ids.length, sections, ...(a.scope === 'all' || a.scope === 'library' ? { undigested: 295 } : {}) };
}

/** `web-group`: a group's rows, by the document or the work's reference, and how many it holds. */
export function webGroup(refs: Record<string, string>, a: { scope: WebScope; doc?: string; group: string }): { group: string; n: number; rows: Row[] } {
	const work = Object.keys(SHORT).find((w) => refOf(refs, w) === a.group);
	const rows = Object.keys(W)
		.filter((k) => inScope(k, a.scope, a.doc) && (W[k].src === a.group || W[k].src === work))
		.sort(byNum)
		.map((k) => rowOf(k, refs));
	return { group: a.group, n: rows.length, rows };
}

const words = (id: string) => (W[id].body ?? W[id].ex ?? '').replace(/\\[()[\]]/g, '');

/** `web-search`: a hit on the name or title before one in the words. */
export function webSearch(refs: Record<string, string>, a: { scope: WebScope; doc?: string; q: string }): Omit<WebSearch, 'gen'> {
	const q = a.q.trim().toLowerCase();
	const ids = Object.keys(W).filter((k) => inScope(k, a.scope, a.doc));
	const named = (k: string) => `${W[k].name} ${W[k].title ?? ''} ${own(k) ? W[k].src : SHORT[W[k].src].join(' ')}`.toLowerCase().includes(q);
	const said = (k: string) => words(k).toLowerCase().includes(q);
	const hits = [...ids.filter(named).sort(byNum), ...ids.filter((k) => !named(k) && said(k)).sort(byNum)].slice(0, 50).map((k) => {
		const w = words(k);
		const i = w.toLowerCase().indexOf(q);
		return { row: rowOf(k, refs), ...(i < 0 ? { snippet: null } : { snippet: { before: (i > 40 ? '…' : '') + w.slice(Math.max(0, i - 40), i), match: w.slice(i, i + q.length), after: w.slice(i + q.length, i + q.length + 70) + (w.length > i + q.length + 70 ? '…' : '') } }) };
	});
	return { count: hits.length, hits };
}

/** The fragments of the drafts' results, for the source's `fragment`. */
export function webFragment(path: string): string | null {
	const id = /^fixture\/web\/(.+)\.html$/.exec(path)?.[1];
	if (!id || !W[id] || !own(id)) return null;
	const n = W[id];
	const text = (n.body ?? n.ex ?? '').replace(/\\\(([^]*?)\\\)/g, '<span class="math">\\($1\\)</span>').replace(/\\\[([^]*?)\\\]/g, '<span class="math display">\\[$1\\]</span>');
	return `<p>${text}</p>`;
}

/** `web-focus`. */
export function webFocus(refs: Record<string, string>, a: { scope: WebScope; doc?: string; result: string; more?: boolean }): Omit<WebFocus, 'gen'> | null {
	const id = a.result;
	const n = W[id];
	if (!n) return null;
	const inS = (k: string) => inScope(k, a.scope, a.doc);
	const row = (k: string) => rowOf(k, refs);
	const statement = own(id) ? { fragment: `fixture/web/${id}.html` } : n.ex ? { body: n.ex, macros: null, points: {} } : null;
	const users = usedBy(id).filter(inS);
	return {
		row: row(id),
		statement,
		relative_to: n.rel ? n.rel.map(row) : null,
		rests_on: own(id) && n.st === 'unformal' ? uses(id).filter((u) => ['stub', 'unchecked'].includes(W[u].st)).map(row) : [],
		more: a.more
			? {
					proofs: own(id) ? [{ where: `${n.src.split('/').pop()}, Section 3`, uses: (n.p ?? []).map(row) }] : [{ where: { ref: refs[n.src], short: SHORT[n.src][0], pages: '4–5' }, uses: (n.p ?? []).map(row) }],
					lean: n.st === 'formal' || n.st === 'leanq' ? [own(id) ? 'Showcase.rank_cycleSpace' : 'Arden24.prop_2_1'] : [],
					record: own(id) ? (n.st === 'formal' ? [{ act: 'lean-accepted', by: 'loom', at: '2026-11-20T10:00:00Z' }, { act: 'attested', by: 'you', at: '2026-11-20T11:00:00Z' }] : []) : n.st === 'stub' ? [] : [{ act: 'verified', by: 'you', at: '2026-11-18T15:00:00Z' }]
				}
			: null,
		uses: { statement: (n.s ?? []).filter(inS).map(row), proof: (n.p ?? []).filter(inS).map(row), outside: { statement: (n.s ?? []).filter((k) => !inS(k)).length, proof: (n.p ?? []).filter((k) => !inS(k)).length } },
		used_by: { rows: users.slice(0, 50).map(row), outside: usedBy(id).length - users.length, more: Math.max(0, users.length - 50) }
	};
}

/** `web-graph`: two steps back, what it uses, what uses it, five drawn of a column of more than six. */
export function webGraph(refs: Record<string, string>, a: { scope: WebScope; doc?: string; result: string }): Omit<WebGraph, 'gen'> | null {
	const f = a.result;
	if (!W[f]) return null;
	const inS = (k: string) => inScope(k, a.scope, a.doc);
	const cap = (ids: string[]) => (ids.length > 6 ? ids.slice(0, 5) : ids);
	const l1 = uses(f).filter(inS);
	const l2 = [...new Set(l1.flatMap(uses))].filter((x) => inS(x) && !l1.includes(x) && x !== f);
	const r1 = usedBy(f).filter(inS);
	const [b, u, r] = [cap(l2), cap(l1), cap(r1)];
	const drawn = new Set([f, ...b, ...u, ...r]);
	const edges = [...drawn].flatMap((x) => uses(x).filter((y) => drawn.has(y)).map((y) => ({ from: x, to: y, proof: (W[x].p ?? []).includes(y) })));
	return { focus: rowOf(f, refs), excerpt: W[f].ex ?? '', columns: { back: b.map((k) => rowOf(k, refs)), uses: u.map((k) => rowOf(k, refs)), used_by: r.map((k) => rowOf(k, refs)) }, more: { back: l2.length - b.length, uses: l1.length - u.length, used_by: r1.length - r.length }, edges };
}

const isDef = (id: string) => /^(Definition|Convention)/.test(W[id].name);

/** `formal-marks`: each result of a draft and its Lean mark. */
export function formalMarks(doc: string): Record<string, string> {
	const mark = (n: N) => (n.st === 'formal' ? 'formalized' : n.st === 'leanq' ? 'attest' : 'not');
	return Object.fromEntries(Object.keys(W).filter((k) => W[k].src === doc).map((k) => [k, mark(W[k])]));
}

/** `formal-plan`, by round six's rules as ruled: what to state, prove and assume, what is formalized already, what stops the request, and what keeps it from reading formalized. */
export function formalPlan(refs: Record<string, string>, targets: string[], assume: string[]) {
	const tag: Record<string, string> = {};
	for (const t of targets) tag[t] = assume.includes(t) ? 'assume' : 'prove';
	const q = [...targets];
	const seen = new Set<string>();
	while (q.length) {
		const x = q.shift()!;
		if (seen.has(x)) continue;
		seen.add(x);
		const full = tag[x] === 'prove';
		for (const u of full ? uses(x) : (W[x].s ?? [])) {
			if (tag[u]) continue;
			const n = W[u];
			const t = n.st === 'formal' ? 'formalized' : own(u) && n.st === 'leanq' ? 'attest' : isDef(u) ? 'state' : own(u) ? (assume.includes(u) ? 'assume' : 'prove') : n.st === 'stub' ? 'not-read' : n.st === 'unchecked' ? 'not-checked' : 'library';
			tag[u] = t;
			if (['state', 'prove', 'assume', 'library', 'not-checked'].includes(t)) q.push(u);
		}
	}
	const ids = Object.keys(tag).filter((i) => !targets.includes(i));
	const row = (k: string) => ({ ...rowOf(k, refs), ...(own(k) ? { fragment: `fixture/web/${k}.html` } : {}) });
	const mine = (t: string) => ids.filter((i) => own(i) && tag[i] === t);
	const lib = ids.filter((i) => ['library', 'not-read', 'not-checked'].includes(tag[i]));
	const state = ids.filter((i) => tag[i] === 'state');
	const prove = [...(targets.length > 1 ? targets : []), ...mine('prove'), ...mine('assume')];
	const stops = [...targets, ...state, ...prove].filter((i, k, a) => W[i].nolabel && a.indexOf(i) === k);
	const group = (why: string, list: string[]) => (list.length ? [{ why, results: list.map(row) }] : []);
	const attest = ids.filter((i) => tag[i] === 'attest');
	return {
		targets: targets.map((t) => ({ key: t, name: W[t].name, ...(W[t].title ? { title: W[t].title } : {}), doc: W[t].src, statement: { fragment: `fixture/web/${t}.html` } })),
		state: state.map(row),
		prove: prove.map((k) => ({ ...row(k), assume: tag[k] === 'assume' })),
		assume: lib.map((k) => ({ ...row(k), why: tag[k] === 'not-read' ? 'not-read' : tag[k] === 'not-checked' ? 'not-checked' : null })),
		formalized: ids.filter((i) => tag[i] === 'formalized').map(row),
		stops: stops.map(row),
		before: [...group('not-read', lib.filter((i) => tag[i] === 'not-read')), ...group('not-checked', lib.filter((i) => tag[i] === 'not-checked')), ...group('attest', attest.filter((i) => !['def:connected', 'cor:cycle'].includes(i))), ...group('attested-changed', attest.filter((i) => ['def:connected', 'cor:cycle'].includes(i)))]
	};
}
