// Round six's data (`docs/design/mockups/library-round-6/`), answering the reads of `docs/specs/library-views.md` as the backend will, so each view is built and tested before its backend exists. The 300 works come from the prototype's own generator and seed, so the list is the one the author marked; Smith 2024, Okafor 2022, Arden 2024 and 2025, Jones, Ostrander, Lindqvist and the dropped scan are its fixed works. Writes change the data in memory and raise the generation, as the publisher will. Written from the spec, before any read exists: where a backend answer differs, the backend's is right and this is corrected.

import type { CheckRow, Note, DigestMark, LeanStatus, NodeAnswer, OutlineItem, Paper, Place, Section, Work, WorkAnswer } from '../types';
import { ask, review6, type ReviewFixture } from './review6';
import { notes6 } from './notes6';
import { paperUrl } from './paper';

// ---- the prototype's generator, as it wrote it, so the same seed gives the same 300 works ----

let seed = 20261120;
const rnd = () => (seed = (seed * 48271) % 2147483647) / 2147483647;
const pick = <T>(a: T[]): T => a[Math.floor(rnd() * a.length)];
const SUR = ['Abara', 'Aldane', 'Anwar', 'Baird', 'Balogun', 'Barrow', 'Bellamy', 'Brandt', 'Castell', 'Corvin', 'Dalgaard', 'Deveraux', 'Ebner', 'Ekwueme', 'Farrow', 'Fenwick', 'Galloway', 'Gerritsen', 'Haddad', 'Hollis', 'Ibarra', 'Isaksen', 'Jansen', 'Kamara', 'Kessler', 'Lindqvist', 'Lowell', 'Marchetti', 'Mensah', 'Nakagawa', 'Novak', 'Oduya', 'Okonkwo', 'Petrakis', 'Quayle', 'Ravel', 'Rossi', 'Sandoval', 'Sato', 'Takeda', 'Teller', 'Ueda', 'Valdez', 'Varga', 'Wexford', 'Whitlock', 'Yilmaz', 'Zeller', 'Amsel', 'Brook', 'Carrow', 'Dimas', 'Esterly', 'Fiala', 'Grove', 'Hart', 'Ivers', 'Juhl', 'Kovač', 'Larue', 'Moreau', 'Nyberg', 'Orsini', 'Pell', 'Rhee', 'Soler', 'Tamm', 'Udall', 'Vane', 'Wirth'];
const ADJ = ['Balanced', 'Bounded', 'Finite', 'Graded', 'Weighted', 'Tame', 'Saturated', 'Median', 'Dual', 'Stable', 'Rigid', 'Twisted', 'Cyclic', 'Planar', 'Acyclic', 'Admissible', 'Compact', 'Signed', 'Integral', 'Generic'];
const NOUN = ['weightings', 'quivers', 'widget categories', 'gadget towers', 'cycle lattices', 'divergence maps', 'flow polytopes', 'covering numbers', 'median orders', 'boundary classes', 'extension problems', 'exchange graphs', 'spanning forests', 'height functions', 'lattice points', 'gadget sheaves', 'widget complexes', 'orientation signs', 'support sets', 'cut spaces'];
const OBJ = ['finite quivers', 'widgets', 'gadgets', 'weighting lattices', 'directed graphs', 'admissible spheres', 'cycle spaces', 'compact sets', 'towers of gadgets', 'acyclic quivers', 'planar quivers', 'bounded widgets'];
const lc = (s: string) => s[0].toLowerCase() + s.slice(1);
function genTitle(): string {
	const p = rnd();
	if (p < 0.25) return `${pick(ADJ)} ${pick(NOUN)} of ${pick(OBJ)}`;
	if (p < 0.42) return `On the ${pick(NOUN)} of ${pick(OBJ)}`;
	if (p < 0.56) return `A note on ${lc(pick(ADJ))} ${pick(NOUN)}`;
	if (p < 0.7) {
		const a = pick(NOUN);
		return `${a[0].toUpperCase() + a.slice(1)} and ${pick(NOUN)}`;
	}
	if (p < 0.84) return `Counting ${pick(NOUN)} in ${pick(OBJ)}`;
	return `${pick(ADJ)} ${pick(NOUN)} and ${lc(pick(ADJ))} ${pick(NOUN)}`;
}

interface Proto {
	id: string;
	title: string;
	authors: string[];
	year: number | '';
	holds: 'PDF and TeX' | 'PDF' | 'no document';
	dig: string;
	used: string;
	v2?: true;
}

const FIXED: Proto[] = [
	{ id: 'arden24', title: 'Cycle spaces of finite quivers', authors: ['Arden'], year: 2024, holds: 'PDF and TeX', dig: '5 of 18 · 3 compared', used: 'main.tex' },
	{ id: 'arden25', title: 'Cycle spaces of finite quivers', v2: true, authors: ['Arden'], year: 2025, holds: 'PDF', dig: '1 · 0 compared', used: 'main.tex' },
	{ id: 'halberd', title: 'Gadget towers', authors: ['Halberd', 'Ravel'], year: 2021, holds: 'PDF and TeX', dig: '', used: '' },
	{ id: 'jones', title: 'Covering estimates', authors: ['Jones'], year: 2019, holds: 'no document', dig: '', used: '' },
	{ id: 'okafor', title: 'Median orders on weighting lattices', authors: ['Okafor'], year: 2022, holds: 'PDF', dig: '', used: 'main.tex' },
	{ id: 'ostrander', title: 'Widget categories and their duals', authors: ['Ostrander'], year: 2020, holds: 'no document', dig: '', used: '' },
	{ id: 'smith', title: 'Widgets and their bounds', authors: ['Smith'], year: 2024, holds: 'PDF and TeX', dig: '11 of 62 · 2 compared', used: 'bounds.tex' },
	{ id: 'vance', title: 'Infinite quivers: a survey', authors: ['Vance', 'Whitlock', 'Ibarra'], year: 2023, holds: 'PDF', dig: '3 · 0 compared', used: 'main.tex' },
	{ id: 'lindqvist', title: 'Height functions on weighting lattices', authors: ['Lindqvist', 'Ueda'], year: 2017, holds: 'no document', dig: '', used: 'main.tex' },
	{ id: 'noid', title: 'scan-2024-11-03.pdf', authors: [], year: '', holds: 'PDF', dig: '', used: '' }
];

const PROTOS: Proto[] = [...FIXED];
{
	const seen = new Set(PROTOS.map((w) => w.title));
	let k = 0;
	while (PROTOS.length < 300) {
		const t = genTitle();
		if (seen.has(t)) continue;
		seen.add(t);
		const na = rnd() < 0.04 ? 0 : rnd() < 0.45 ? 1 : rnd() < 0.75 ? 2 : 3 + Math.floor(rnd() * 2);
		const au: string[] = [];
		while (au.length < na) {
			const s = pick(SUR);
			if (!au.includes(s)) au.push(s);
		}
		const r = rnd();
		const holds = r < 0.6 ? 'PDF' : r < 0.8 ? 'PDF and TeX' : 'no document';
		let dig = '';
		if (holds !== 'no document' && rnd() < 0.09) {
			const d = 1 + Math.floor(rnd() * 9);
			const c = Math.floor(rnd() * (d + 1));
			dig = holds === 'PDF and TeX' ? `${d} of ${d + 5 + Math.floor(rnd() * 30)} · ${c} compared` : `${d} · ${c} compared`;
		}
		PROTOS.push({ id: 'g' + k++, title: t, authors: na ? au : [], year: na ? 1979 + Math.floor(rnd() * 47) : '', holds, dig, used: rnd() < 0.03 ? 'main.tex' : '' });
	}
}

// ---- ids: opaque, as the node store mints them, and never drawn ----

const b36 = (n: number) => n.toString(36).toUpperCase().padStart(4, '0');
export const REF: Record<string, string> = {};
PROTOS.forEach((w, i) => (REF[w.id] = `tq-${b36(100 + i)}-ref`));
const PROTO_OF: Record<string, Proto> = Object.fromEntries(PROTOS.map((w) => [REF[w.id], w]));

/** The stored PDF's hash: a fixed one for each work that holds one. */
const hashOf = (id: string) => 'sha256:' + Array.from({ length: 64 }, (_, i) => '0123456789abcdef'[(id.charCodeAt(i % id.length) + i * 7) % 16]).join('');

/** How long each stored PDF is: Smith 2024's 31 pages, every other 24. */
const PAGES_OF: Record<string, number> = {};
const pagesOf = (id: string) => (id === 'smith' ? 31 : 24);

/** A stand-in paper as long as the work says (`paper.ts`). */
export function fixturePdfUrl(hash: string): string {
	return paperUrl(PAGES_OF[hash] ?? 24);
}

const auShort = (a: string[]) => (!a.length ? '' : a.length === 1 ? a[0] : a.length === 2 ? `${a[0]} and ${a[1]}` : `${a[0]} et al.`);
const shortOf = (w: Proto) => (w.authors.length ? `${auShort(w.authors)} ${w.year}` : w.title);

function digestedOf(dig: string): Work['digested'] {
	const m = dig.match(/^(\d+)(?: of (\d+))? · (\d+) compared/);
	return m ? { statements: +m[1], of: m[2] ? +m[2] : null, compared: +m[3], stubs: 0 } : null;
}

function workOf(w: Proto, i: number): Work {
	const pdf = w.holds === 'no document' ? null : hashOf(w.id);
	if (pdf) PAGES_OF[pdf] = pagesOf(w.id);
	return {
		ref: REF[w.id],
		short: shortOf(w),
		title: w.title,
		authors: w.authors,
		year: String(w.year),
		holds: { pdf, tex: w.holds === 'PDF and TeX' },
		digested: digestedOf(w.dig),
		used_in: w.used ? [`drafting/${w.used}`] : [],
		link: w.authors.length ? `https://arxiv.org/abs/2${String(1000 + i).slice(1)}.0${String(1000 + i * 7).slice(-4)}` : null,
		version: w.v2 ? 2 : null,
		lookup: null,
		cited_as: null
	};
}

// ---- Smith 2024: a work with its TeX source, 62 results in the paper's order ----

type Mk = Paper | '';
interface Res {
	num: string;
	tax: string;
	title?: string;
	p: Mk;
	l?: LeanStatus;
	node?: string;
	page?: number;
}

const SECS: Record<string, [string, string, number][]> = {
	smith: [['1', 'Introduction', 1], ['2', 'Widgets', 3], ['3', 'Bounds', 12], ['4', 'Covering', 13], ['5', 'Covering numbers', 18], ['6', 'Thin widgets', 22], ['7', 'Duality', 26], ['A', 'The boundary class', 29]],
	arden24: [['1', 'Introduction', 1], ['2', 'The image of the divergence map', 1], ['3', 'Heights', 6], ['4', 'Exchanges', 11], ['5', 'Bounds', 16]],
	okafor: [['1', 'Introduction', 1], ['2', 'Median orders', 4], ['3', 'Counting', 9], ['4', 'One cycle', 14]]
};

const SMITH: Res[] = (() => {
	const counts: [string, number][] = [['1', 4], ['2', 6], ['3', 9], ['4', 9], ['5', 10], ['6', 11], ['7', 9], ['A', 5]];
	const tax = ['Definition', 'Lemma', 'Proposition', 'Theorem', 'Remark', 'Corollary', 'Example', 'Lemma', 'Lemma'];
	const out: Res[] = [];
	let t = 0;
	for (const [s, n] of counts)
		for (let i = 1; i <= n; i++) {
			const num = `${s}.${i}`;
			if (num === '3.3') continue;
			out.push({ num, tax: tax[t++ % tax.length], p: '' });
		}
	const set = (num: string, o: Partial<Res>) => Object.assign(out.find((x) => x.num === num)!, o);
	set('2.1', { tax: 'Definition', title: 'Widget', p: 'matches', node: 'tq-00A4' });
	set('2.2', { tax: 'Example' });
	set('3.1', { tax: 'Definition', title: 'Radius', p: 'unchecked', node: 'tq-00K1' });
	set('3.2', { tax: 'Lemma', title: 'Test lemma', p: 'unchecked', node: 'tq-00K3' });
	set('3.4', { tax: 'Proposition', title: 'Test proposition', p: 'matches', l: { lean: 'unattested', role: 'proved' }, node: 'tq-00K5' });
	set('4.1', { tax: 'Theorem', title: 'Covering bound', p: 'stub', node: 'tq-00K9' });
	for (const n of ['5.2', '5.3', '5.4', '6.1', '6.2', '6.3', '6.5']) set(n, { p: 'unchecked', node: 'tq-01' + n.replace('.', '') });
	const page: Record<string, number> = { '1': 1, '2': 3, '3': 12, '4': 13, '5': 18, '6': 22, '7': 26, A: 29 };
	for (const r of out) r.page = page[r.num.split('.')[0]] + (r.num === '3.4' || r.num === '3.5' ? 1 : 0);
	return out;
})();

const ARDEN: Res[] = [
	['1.1', 'Definition', 'Quiver', 'matches'], ['1.2', 'Definition', 'Cycle space', 'matches'], ['1.3', 'Remark', '', ''], ['2.1', 'Proposition', '', 'matches', 'assumed'], ['2.2', 'Lemma', '', ''], ['2.3', 'Corollary', '', ''], ['3.1', 'Definition', 'Height', ''], ['3.2', 'Lemma', '', ''], ['3.3', 'Proposition', '', ''], ['4.1', 'Theorem', '', ''], ['4.2', 'Lemma', '', ''], ['4.3', 'Example', '', ''], ['5.1', 'Definition', '', ''], ['5.4', 'Lemma', '', ''], ['5.7', 'Lemma', '', 'unchecked'], ['5.8', 'Remark', '', ''], ['5.9', 'Lemma', 'Exchange bound', 'unchecked'], ['5.10', 'Corollary', '', '']
].map(([num, tax, title, p, l], i) => ({ num, tax, title: title || undefined, p: (p || '') as Mk, l: l ? ({ lean: 'formalized', role: 'assumed' } as LeanStatus) : undefined, node: p ? `tq-02${b36(i).slice(2)}` : undefined, page: 1 + Number(num.split('.')[0]) * 3 }));

/** A statement's text as a node's body holds it: LaTeX, pointing at other nodes by id. */
const BODY: Record<string, { body: string; how?: 'extracted' | 'transcribed'; uses?: string[] }> = {
	'tq-00A4': { body: String.raw`A \emph{widget} is a compact set $W \subset \mathbb{R}^n$ whose boundary lies in $\Wid$.` },
	'tq-00K1': { body: String.raw`The \emph{radius} of a bounded set $S \subset \mathbb{R}^n$ is $\rad S = \inf\{r \ge 0 : S \subset B(0,r)\}$.` },
	'tq-00K3': {
		body: String.raw`Let $W$ be a widget (Definition~\ref{tq-00A4}). Then
\begin{enumerate}
\item $\diam W < \infty$; and
\item for every $x_0 \in W$, each point $x$ of $W$ satisfies
\begin{equation}\label{tq-00K3-eq00}
  |x| \le \diam W + |x_0| .
\end{equation}
\end{enumerate}`,
		uses: ['tq-00A4']
	},
	'tq-00K5': { body: String.raw`Let $W$ be a widget as in Definition~\ref{tq-00A4}. Then $W$ lies in a ball about the origin.`, uses: ['tq-00A4', 'tq-00B7'] },
	'tq-0152': { body: String.raw`If $W$ is a widget and $r > 0$, then $N(W, r)$ is finite.` },
	'tq-0153': { body: String.raw`$N(W, r)$ is non-increasing in $r$.` },
	'tq-0154': { body: String.raw`For a widget $W \subset \mathbb{R}^n$, $N(W, r) \le (1 + 2 \diam W / r)^n$.` },
	'tq-0161': { body: String.raw`A widget is \emph{thin} if its boundary class $\Wid$ contains no sphere.` },
	'tq-0162': { body: String.raw`The union of two thin widgets is a thin widget.` },
	'tq-0163': { body: String.raw`The intersection of thin widgets need not be thin.` },
	'tq-0165': { body: String.raw`Every thin widget lies in a ball of radius $\diam W$.` }
};
const SMITH_MACROS = String.raw`\usepackage{amssymb}
\newcommand{\Wid}{\mathcal{W}}
\DeclareMathOperator{\diam}{diam}
\DeclareMathOperator{\rad}{rad}`;

// ---- the data, changed by writes ----

export interface Fixture {
	gen: number;
	works: Work[];
	/** Each work's results and their marks, by the prototype's id. */
	results: Record<string, Res[]>;
	marks: Record<string, DigestMark[]>;
	overlayPlaced: Record<string, Place[]>;
	deleted: Record<string, { work: Work; at: number }>;
	/** Review's rows and the tasks waiting for an agent (`review6.ts`). */
	review: ReviewFixture;
	/** Transcribed results the person has found match their paper. */
	checked: string[];
	/** The notes tab's notes (`notes6.ts`). */
	notes: Note[];
	/** Whether the quilt has said loom may use the network: `asked` it may, `off` it may not, and `unasked` refuses a take that does not go without it. */
	network: 'asked' | 'off' | 'unasked';
	/** The work each taken row added, by the row's id, which `library-undo` takes back out. */
	taken: Record<string, string>;
	/** The intake's questions waiting on the person, by id: the file's name and the works it may be. */
	questions: Record<string, { name: string; candidates: string[] }>;
}

export function round6(): Fixture {
	const works = PROTOS.map(workOf);
	const smithRef = REF.smith;
	const okaforRef = REF.okafor;
	const results: Record<string, Res[]> = { [smithRef]: SMITH.map((r) => ({ ...r })), [REF.arden24]: ARDEN.map((r) => ({ ...r })) };
	const marks: Record<string, DigestMark[]> = { [okaforRef]: [{ mark: 'a-2026-11-20-okf6', page: 6, words: 'Lemma 2.4. Let ⪯ be a median order…' }] };
	const review = review6(REF);
	// a transcribed result's row is beside its work's stored paper, as a digested one's is
	for (const r of review.rows) if (r.kind === 'check' && 'nodes' in r && r.pdf === null) r.pdf = works.find((w) => w.ref === r.ref)?.holds.pdf ?? null;
	return { gen: 1, works, results, marks, overlayPlaced: {}, deleted: {}, review, checked: [], notes: notes6(REF), network: 'asked', taken: {}, questions: {} };
}

const protoOf = (ref: string) => PROTO_OF[ref];

/** The id of a survey's item: its label where it has one, else `i` and its place among the source's results. */
const itemOf = (r: Res, i: number) => (r.node === 'tq-00K3' ? 'lem:test' : r.node === 'tq-00K5' ? 'prop:test' : `i${i}`);

export function outlineOf(f: Fixture, ref: string): WorkAnswer['outline'] {
	const w = protoOf(ref);
	if (!w || w.holds === 'no document') return null;
	const list = f.results[ref];
	const secs = SECS[w.id];
	if (w.holds === 'PDF and TeX' && list && secs) {
		const sections: Section[] = secs.map(([n, t, p]) => ({ section: 's' + n, number: n, title: t, page: p, level: 1 }));
		const items: OutlineItem[] = list.map((r, i) => ({
			item: itemOf(r, i),
			node: r.node && r.p ? r.node : null,
			name: `${r.tax} ${r.num}`,
			...(r.title ? { title: r.title } : {}),
			taxon: r.tax.toLowerCase(),
			section: 's' + r.num.split('.')[0],
			page: r.page ?? null,
			paper: r.p || null,
			lean: r.l ?? null
		}));
		return { from: 'tex', state: 'ready', sections, items };
	}
	return { from: 'pdf', state: 'ready', sections: [], items: [] };
}

export function workAnswer(f: Fixture, ref: string): WorkAnswer | null {
	const row = f.works.find((w) => w.ref === ref);
	const w = protoOf(ref);
	if (!row || !w) return null;
	const key = w.authors.length ? `${w.authors[0].slice(0, 3)}${String(w.year).slice(2)}` : 'X';
	const entry = `@article{${key},\n  author = {${w.authors.join(' and ')}},\n  title  = {${w.title}},\n  year   = {${w.year}},\n}`;
	const unplaced = w.id === 'okafor' ? [{ node: 'tq-00C2', name: 'Theorem 2.3', paper: 'stub' as const }, { node: 'tq-00C3', name: 'Corollary 4.2', paper: 'stub' as const }] : [];
	return {
		gen: f.gen,
		ref,
		short: row.short,
		title: row.title,
		authors: row.authors,
		year: row.year,
		holds: { pdf: row.holds.pdf, pages: row.holds.pdf ? (PAGES_OF[row.holds.pdf] ?? 24) : null, tex: row.holds.tex },
		entry,
		link: row.link,
		outline: outlineOf(f, ref),
		marks: f.marks[ref] ?? [],
		unplaced
	};
}

/** The counts of a work's `digest…` menu, as round six draws them. */
export function scopesOf(f: Fixture, ref: string) {
	const w = protoOf(ref);
	const list = f.results[ref];
	const notYet = list ? list.filter((r) => !r.p || r.p === 'stub').length : null;
	const used = w?.id === 'smith' ? 2 : w?.id === 'okafor' ? 2 : w?.id === 'arden24' ? 1 : w?.used ? 1 : 0;
	return { gen: f.gen, tex: w?.holds === 'PDF and TeX', pdf: w?.holds !== 'no document', used, marked: (f.marks[ref] ?? []).length, all: w?.holds === 'PDF and TeX' ? notYet ?? 20 : 24 };
}

/** A node beside its page, or an item of a survey not yet digested. */
export function nodeAnswer(f: Fixture, args: { node?: string; ref?: string; item?: string; brief?: boolean }): NodeAnswer | null {
	for (const [ref, list] of Object.entries(f.results)) {
		const i = list.findIndex((r, k) => (args.node ? r.node === args.node && !!r.p : ref === args.ref && itemOf(r, k) === args.item));
		if (i < 0) continue;
		const r = list[i];
		const row = f.works.find((w) => w.ref === ref)!;
		const work = { ref, short: row.short, pdf: row.holds.pdf };
		const base = { gen: f.gen, name: `${r.tax} ${r.num}`, ...(r.title ? { title: r.title } : {}), taxon: r.tax.toLowerCase(), work, pages: String(r.page ?? '') };
		if (!r.p || (!args.node && !r.p)) return { ...base, digested: null, paper: null };
		const b = r.node ? BODY[r.node] : undefined;
		const uses = (b?.uses ?? []).map((u) => (u === 'tq-00B7' ? { result: u, name: 'Lemma 2.1', title: null, taxon: 'lemma', source: { ref: REF.jones, short: 'Jones 2019' }, paper: 'stub' as const, reading: 'stub' as const, lean: null } : { result: u, name: 'Definition 2.1', title: 'Widget', taxon: 'definition', source: null, paper: 'matches' as const, reading: 'matches' as const, lean: null }));
		return {
			...base,
			node: r.node,
			hash: hashOf(r.node! + r.p),
			digested: r.p === 'stub' ? null : { how: b?.how ?? 'extracted', by: 'loom', at: '2026-11-20T14:02:11Z' },
			paper: r.p,
			lean: r.l ?? null,
			...(b ? { body: b.body } : {}),
			macros: ref === REF.smith ? { node: 'tq-00A1-macros', hash: hashOf('macros'), body: SMITH_MACROS } : null,
			points: { 'tq-00A4': { name: 'Definition 2.1', number: '2.1', paper: 'matches' }, 'tq-00K3-eq00': { number: '3.3' }, 'tq-00B7': { name: 'Lemma 2.1', work: 'Jones 2019', paper: 'stub' } },
			...(args.brief ? {} : { uses, mentions: [], proofs: r.node === 'tq-00K3' ? [{ node: 'tq-00K3-proof00', source: null, pages: '12-13', pointer: false }] : [], used_by: { docs: ref === REF.smith ? ['drafting/bounds.tex'] : [], nodes: 1 } })
		};
	}
	return args.node ? transcribedAnswer(f, args.node) : null;
}

/** Results an agent transcribed from works held only as a PDF, which Review asks the person to check: by node, with the work, page and body. */
const TRANSCRIBED: Record<string, { ref: string; tax: string; num: string; title?: string; page: number; body: string; stub?: true; lacks?: string[] }> = {
	'tq-04A1': { ref: 'okafor', tax: 'Theorem', num: '2.3', page: 0, body: '', stub: true },
	'tq-05A1': { ref: 'arden25', tax: 'Theorem', num: '5.1', title: 'Extension criterion', page: 2, body: String.raw`Let $Q' \subset Q$ be a full subquiver. A weighting $w'$ of $Q'$ extends to a balanced weighting of $Q$ if and only if, for every connected component $K$ of $Q \setminus Q'$, the divergence of $w'$ sums to zero over the vertices of $Q'$ adjacent to $K$.`, lacks: ['sums', 'adjacent'] },
	'tq-05B0': { ref: 'vance', tax: 'Theorem', num: '1.4', page: 1, body: String.raw`Every locally finite quiver with finitely many ends has a balanced weighting of finite height.` },
	'tq-05B1': { ref: 'vance', tax: 'Lemma', num: '2.2', page: 2, body: String.raw`The cycle space of an infinite quiver is generated by its finite cycles and its double rays.` },
	'tq-05B2': { ref: 'vance', tax: 'Proposition', num: '3.1', page: 3, body: String.raw`A balanced weighting of a one-ended quiver is determined by its values on any cofinite subquiver.` }
};

/** A transcribed result's answer, as `nodeAnswer` gives a node of a work with its source. */
function transcribedAnswer(f: Fixture, node: string): NodeAnswer | null {
	const t = TRANSCRIBED[node];
	const row = t && f.works.find((w) => w.ref === REF[t.ref]);
	if (!t || !row) return null;
	const done = f.checked.includes(node);
	if (t.stub) return { gen: f.gen, node, hash: hashOf(node), name: `${t.tax} ${t.num}`, taxon: t.tax.toLowerCase(), work: { ref: row.ref, short: row.short, pdf: row.holds.pdf }, pages: '', digested: null, paper: 'stub', lean: null, macros: null, points: {} };
	return {
		gen: f.gen,
		node,
		hash: hashOf(node + (done ? 'matches' : 'unchecked')),
		name: `${t.tax} ${t.num}`,
		...(t.title ? { title: t.title } : {}),
		taxon: t.tax.toLowerCase(),
		work: { ref: row.ref, short: row.short, pdf: row.holds.pdf },
		pages: String(t.page),
		digested: { how: 'transcribed', by: 'Claude Code', at: '2026-11-20T14:02:11Z' },
		paper: done ? 'matches' : 'unchecked',
		lean: null,
		body: t.body,
		macros: null,
		points: {}
	};
}

/** The work a node is of: a digested result's, or one an agent transcribed; '' for none. */
export function workOfNode(f: Fixture, node: string): string {
	const digested = Object.keys(f.results).find((r) => f.results[r].some((x) => x.node === node));
	return digested ?? (TRANSCRIBED[node] ? REF[TRANSCRIBED[node].ref] : '') ?? '';
}

/** Where each node of a work stands on the pages asked for, placed down the fixture PDF's pages a band each, and each mark to digest as the annotation it is (`library-places`, §3.3): a node's entry is what the digest will add. */
export function placesOf(f: Fixture, args: { ref?: string; node?: string; pages?: number[] }): Place[] {
	const out: Place[] = [];
	for (const [ref, list] of Object.entries(f.results)) {
		if (args.ref && ref !== args.ref) continue;
		list.forEach((r, i) => {
			if (!r.node || !r.p || r.p === 'stub') return;
			if (args.node && r.node !== args.node) return;
			// on its own page, the one the outline and the node name
			const page = r.page ?? 1;
			if (args.pages && !args.pages.includes(page)) return;
			const top = 120 + ((i * 97) % 520);
			out.push({ node: r.node, name: `${r.tax} ${r.num}`, number: r.num, page, rects: [[72, top, 540, top + 46]], paper: r.p as Paper, lean: r.l ?? null, lacks: [] });
		});
	}
	const t = args.node ? TRANSCRIBED[args.node] : undefined;
	if (t && !t.stub) out.push({ node: args.node!, name: `${t.tax} ${t.num}`, number: t.num, page: t.page, rects: [[72, 300, 540, 372]], paper: f.checked.includes(args.node!) ? 'matches' : 'unchecked', lean: null, lacks: t.lacks ?? [] });
	for (const [ref, ms] of Object.entries(f.marks)) {
		if (args.ref && ref !== args.ref) continue;
		for (const m of ms) if (!args.pages || args.pages.includes(m.page)) out.push({ annotation: m.mark, page: m.page, rects: [[70, 352, 541, 402]] });
	}
	return out;
}

/** What `library-digest` does to the fixture: results chosen, used or all become digested and not yet compared; a work held only as a PDF gets a task instead. */
export function digest(f: Fixture, refs: string[] | 'all', scope: string, chosen: string[] = []): { made: number; tasks: string[] } {
	let made = 0;
	const tasks: string[] = [];
	const targets = refs === 'all' ? f.works.map((w) => w.ref) : refs;
	for (const ref of targets) {
		const row = f.works.find((w) => w.ref === ref);
		if (!row || (!row.holds.pdf && !row.holds.tex)) continue;
		const list = f.results[ref];
		if (!row.holds.tex || !list) {
			if (refs !== 'all' || scope === 'used') tasks.push(ask(f.review, 'digest', { ref }, row.used_in, { ref, scope: (scope === 'used' ? 'uses' : scope) as 'uses' | 'marked' | 'chosen' | 'all', ...(scope === 'marked' ? { marks: (f.marks[ref] ?? []).map((m) => m.mark) } : scope === 'chosen' ? { nodes: chosen } : {}) }));
			continue;
		}
		list.forEach((r, i) => {
			const pick = scope === 'all' ? !r.p || r.p === 'stub' : scope === 'chosen' ? chosen.includes(itemOf(r, i)) || (!!r.node && chosen.includes(r.node)) : scope === 'used' ? r.p === 'stub' : false;
			if (!pick) return;
			r.p = 'unchecked';
			r.node ??= `tq-03${b36(i).slice(1)}`;
			made++;
		});
		const statements = list.filter((r) => r.p && r.p !== 'stub').length;
		row.digested = { statements, of: list.length, compared: list.filter((r) => r.p === 'matches').length, stubs: list.filter((r) => r.p === 'stub').length };
	}
	f.gen++;
	return { made, tasks };
}

/** The person's yes: a node's paper mark becomes `checked`, and its work's count with it. */
export function check(f: Fixture, node: string): boolean {
	if (TRANSCRIBED[node]) {
		if (f.checked.includes(node)) return false;
		f.checked.push(node);
		for (const r of f.review.rows) if (r.kind === 'check' && r.correction === undefined) r.nodes = r.nodes.filter((n) => n.node !== node);
		f.review.rows = f.review.rows.filter((r) => !(r.kind === 'check' && r.correction === undefined && !r.nodes.length));
		f.gen++;
		return true;
	}
	for (const [ref, list] of Object.entries(f.results)) {
		const r = list.find((x) => x.node === node);
		if (!r) continue;
		r.p = 'matches';
		const row = f.works.find((w) => w.ref === ref);
		if (row?.digested) row.digested = { ...row.digested, compared: list.filter((x) => x.p === 'matches').length };
		f.gen++;
		return true;
	}
	return false;
}

/** A work the fixture's intake adds: named by an arXiv number it is round six's Gadget towers, found by that number with its TeX source; any other is a work titled by its file's name. */
export function addWork(f: Fixture, name: string, offline = false): Work {
	const arxiv = /^\d{4}\.\d{4,5}/.test(name);
	const w: Work = arxiv && offline
		? { ref: `tq-${b36(900 + f.gen)}-ref`, short: '', title: `arXiv ${name}`, authors: [], year: '', holds: { pdf: null, tex: false }, digested: null, used_in: [], link: `https://arxiv.org/abs/${name}`, version: null, lookup: { state: 'unconfirmed', identifier: `arxiv:${name}` }, cited_as: null }
		: arxiv
		? { ref: `tq-${b36(900 + f.gen)}-ref`, short: 'Halberd and Ravel 2021', title: 'Gadget towers', authors: ['Halberd', 'Ravel'], year: '2021', holds: { pdf: hashOf('halberd' + f.gen), tex: true }, digested: null, used_in: [], link: `https://arxiv.org/abs/${name}`, version: null, lookup: null, cited_as: null }
		: { ref: `tq-${b36(900 + f.gen)}-ref`, short: name, title: name, authors: [], year: '', holds: { pdf: hashOf(name + f.gen), tex: false }, digested: null, used_in: [], link: null, version: null, lookup: null, cited_as: null };
	if (w.holds.pdf) PAGES_OF[w.holds.pdf] = 24;
	f.works.push(w);
	f.gen++;
	return w;
}

/** What rests on a digested result, by its node: the draft, and the result it rests on it through where it is not used directly. */
const RESTS: Record<string, { docs: string[]; through?: string }> = { 'tq-00K3': { docs: ['drafting/bounds.tex'], through: 'Proposition 3.4' }, 'tq-020G': { docs: ['drafting/main.tex'] } };

/** Review's rows of digested results to check from the works whose TeX source loom read: a row a work, its results not yet compared in paper order. */
export function checkRows(f: Fixture): CheckRow[] {
	const rows: CheckRow[] = [];
	// round six's order: what a draft rests on first, Smith 2024 before Arden 2024
	const order = [REF.smith, REF.arden24];
	for (const w of [...f.works].sort((a, b) => (order.indexOf(a.ref) + 1 || 99) - (order.indexOf(b.ref) + 1 || 99))) {
		// what a draft rests on first, then paper order
		const all = (f.results[w.ref] ?? []).filter((r) => r.p === 'unchecked' && r.node);
		const nodes = [...all.filter((r) => RESTS[r.node!]), ...all.filter((r) => !RESTS[r.node!])];
		if (!nodes.length) continue;
		const rests = nodes.map((r) => RESTS[r.node!] ?? { docs: [] });
		rows.push({
			row: `check:${w.ref}`,
			kind: 'check',
			docs: [...new Set([...w.used_in, ...rests.flatMap((x) => x.docs)])],
			ref: w.ref,
			short: w.short,
			pdf: w.holds.pdf,
			nodes: nodes.map((r, i) => ({ node: r.node!, name: `${r.tax} ${r.num}`, number: r.num, ...(r.title ? { title: r.title } : {}), rests: rests[i], how: BODY[r.node!]?.how ?? 'extracted' }))
		});
	}
	return rows;
}

/** A work looked up: the one an arXiv number names, round six's Gadget towers. */
export function lookUp(f: Fixture, ref: string): boolean {
	const w = f.works.find((x) => x.ref === ref);
	if (!w?.lookup) return false;
	Object.assign(w, { short: 'Halberd and Ravel 2021', title: 'Gadget towers', authors: ['Halberd', 'Ravel'], year: '2021', holds: { pdf: hashOf('halberd' + ref), tex: true }, lookup: null });
	if (w.holds.pdf) PAGES_OF[w.holds.pdf] = 24;
	f.gen++;
	return true;
}
