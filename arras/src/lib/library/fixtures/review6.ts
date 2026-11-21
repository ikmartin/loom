// Review's part of round six's fixture: the rows the prototype draws, 29 waiting for the person and 6 for an agent, answered as `review-counts`, `review-list` and `review-row` will answer them, and changed by Review's writes. A work's digested results to check are read from the Library's part, so a yes given in either view leaves both. Written from the spec (`docs/specs/library-views.md` §4) until the evidence lane serves these reads.

import type { AcceptedChangedRow, AttestRow, AttestedChangedRow, CheckRow, CitedRow, EditRow, FetchRow, QuestionRow, ReviewBody, ReviewCounts, ReviewGroup, ReviewKind, ReviewList, ReviewRow, TaskRow } from '../types';

const MAIN = 'drafting/main.tex';
const BOUNDS = 'drafting/bounds.tex';

/** The kinds in the order the list draws them under Everything: by who is waiting. */
export const LIST_ORDER: ReviewKind[] = ['questions', 'fetch', 'cited', 'check', 'attest', 'accepted-changed', 'attested-changed', 'edits'];

/** What Review holds: its rows (a work's results to check are added from the Library's part as asked), the tasks, the rows' bodies and the fragments they draw. */
export interface ReviewFixture {
	rows: ReviewRow[];
	tasks: TaskRow[];
	bodies: Record<string, Record<string, unknown>>;
	fragments: Record<string, string>;
	seq: number;
}

/** Inline mathematics, as a fragment holds it. */
const m = (tex: string) => `<span class="math">\\(${tex}\\)</span>`;
/** A change's old and new words, marked as a pending change's are. */
const ch = (n: string, old: string, now: string) => [old && `<span class="change" data-change="${n}" data-side="old">${old}</span>`, now && `<span class="change" data-change="${n}" data-side="new">${now}</span>`].filter(Boolean).join(' ');
const p = (html: string) => `<p>${html}</p>`;

const ACCEPTED: [string, string, string, string][] = [
	[MAIN, 'lem:forest', 'Lemma 3.3', p(`(i) <em>if</em> ${m('\\operatorname{supp} w')} <em>is</em> ${ch('a', 'a tree', 'a forest')}, <em>then</em> ${m('w = 0')};`)],
	[MAIN, 'thm:count', 'Theorem 3.4', p(`The number of balanced weightings of ${m('Q')} of height ${ch('b', 'at most', 'less than')} ${m('h')} is a polynomial in ${m('h')}.`)],
	[MAIN, 'rem:sharp', 'Remark 3.6', p(`The bound of Theorem 3.4 is ${ch('c', 'sharp', 'sharp for quivers with one cycle')}.`)],
	[MAIN, 'def:divergence', 'Definition 2.2', p(`The divergence of a weighting ${m('w')} at a vertex ${m('v')} is the weight arriving at ${m('v')} less the weight leaving it${ch('d', '', `, so that ${m('\\partial w \\in \\mathbb{Z}^V')}`)}.`)],
	[BOUNDS, 'thm:radius', 'Theorem 1', p(`Every widget of type ${m('k')} has radius at most ${ch('e', m('k'), m('2k'))}.`)],
	[BOUNDS, 'lem:thin', 'Lemma 2', p(`${ch('f', 'Let', 'Suppose')} ${m('W')} is thin.`)]
];

const EDITS: { change: string; type: 'suggested' | 'edit'; doc: string; key: string; where: string; html: string; broke?: { line: number; error: string } }[] = [
	// keyed as the static suite's main.tex keys its proof, so see it lands on a block that is there
	{ change: 'c-1a2b3c4d', type: 'suggested', doc: MAIN, key: 'sy-0002/proof', where: 'proof of Theorem 3.1', html: p(`Since ${m('\\mathcal{Z}(Q) = \\ker \\partial')}, ${ch('g', 'the rank of the kernel is the rank of the source less the rank of the image', `by rank–nullity, ${m('\\operatorname{rank} \\mathcal{Z}(Q) = |A(Q)| - \\operatorname{rank} \\partial')}`)}, and Proposition 2.1 gives ${m('\\operatorname{rank} \\partial')}.`) },
	{ change: 'c-2b3c4d5e', type: 'suggested', doc: BOUNDS, key: 'thm:radius', where: 'Theorem 1', html: p(`The bound follows from ${ch('h', '[Smi24]', '[Smi24, Proposition 3.4]')}.`) },
	{ change: 'c-3c4d5e6f', type: 'suggested', doc: MAIN, key: 'def:divergence', where: 'Definition 2.2', html: p(`the weight arriving at ${m('v')} less the weight ${ch('i', 'leaving at', 'leaving')} it.`) },
	{ change: 'c-4d5e6f70', type: 'edit', doc: BOUNDS, key: 'lem:thin', where: 'Lemma 2', html: p(`${ch('j', 'Let', 'Suppose')} ${m('W')} is thin ${ch('k', '', 'and its boundary lies in \\Wid')}.`), broke: { line: 14, error: 'Undefined control sequence' } },
	{ change: 'c-5e6f7081', type: 'suggested', doc: MAIN, key: 'sec:open', where: 'Section 4, second paragraph', html: p(`…${ch('l', '', ' The case of infinite quivers is open; see the survey [4].')}`) }
];

/** Review as round six draws it; `refs` are the Library's ids for the works it names. */
export function review6(refs: Record<string, string>): ReviewFixture {
	const fragments: Record<string, string> = {};
	const bodies: Record<string, Record<string, unknown>> = {};
	const rows: ReviewRow[] = [];

	const questions: QuestionRow[] = [
		{ row: 'questions:t-2026-11-21-w2c6ga', kind: 'questions', docs: [MAIN], task: 't-2026-11-21-w2c6ga', by: 'Claude Code', on: { digesting: 'Okafor 2022', ref: refs.okafor, short: 'Okafor 2022', page: 7 }, text: 'your mark on page 7 takes in Remark 2.5 and Proposition 2.6. Digest both, or only the proposition?', choices: ['both', 'only the proposition'] },
		{ row: 'questions:t-2026-11-21-k4dq2m', kind: 'questions', docs: [MAIN], task: 't-2026-11-21-k4dq2m', by: 'Claude Code', on: { doc: MAIN, key: 'thm:count', name: 'Theorem 3.4' }, text: 'should the count include the zero weighting?', choices: ['yes', 'no'] }
	];
	const fetch: FetchRow[] = [
		{ row: 'fetch:t-2026-11-21-pq0d4n', kind: 'fetch', docs: [BOUNDS], task: 't-2026-11-21-pq0d4n', ref: refs.jones, short: 'Jones 2019', title: 'Covering estimates', link: 'https://doi.org/10.1000/example.2019.17', by: 'Claude Code' },
		{ row: 'fetch:t-2026-11-21-r8ms1v', kind: 'fetch', docs: [BOUNDS], task: 't-2026-11-21-r8ms1v', ref: refs.ostrander, short: 'Ostrander 2020', title: 'Widget categories and their duals', link: 'https://doi.org/10.1000/example.2020.4', by: 'Claude Code' },
		{ row: 'fetch:t-2026-11-21-h2zk7c', kind: 'fetch', docs: [MAIN], task: 't-2026-11-21-h2zk7c', ref: refs.lindqvist, short: 'Lindqvist and Ueda 2017', title: 'Height functions on weighting lattices', link: 'https://doi.org/10.1000/example.2017.31', by: 'Claude Code' }
	];
	const cited: CitedRow[] = [
		{ row: `cited:${refs.okafor}`, kind: 'cited', docs: [MAIN], ref: refs.okafor, short: 'Okafor 2022', holds: { pdf: true, tex: false }, stubs: [{ node: 'tq-04A1', name: 'Theorem 2.3', rests: { docs: [MAIN] }, not_in_source: false, marked: false }, { node: 'tq-04A2', name: 'Corollary 4.2', rests: { docs: [MAIN] }, not_in_source: false, marked: false }] },
		{ row: `cited:${refs.arden25}`, kind: 'cited', docs: [MAIN], ref: refs.arden25, short: 'Arden 2025', holds: { pdf: true, tex: false }, stubs: [{ node: 'tq-04B1', name: 'Theorem 6.2', rests: { docs: [MAIN] }, not_in_source: false, marked: false }] },
		{ row: `cited:${refs.smith}`, kind: 'cited', docs: [BOUNDS], ref: refs.smith, short: 'Smith 2024', holds: { pdf: true, tex: true }, stubs: [{ node: 'tq-04C1', name: 'Lemma 8.2', rests: { docs: [BOUNDS] }, not_in_source: true, marked: false }] },
		{ row: 'cited:m-2026-11-21-oka22', kind: 'cited', docs: [MAIN], citation: 'm-2026-11-21-oka22', doc: MAIN, key: 'thm:count/proof', where: 'the proof of Theorem 3.4', ref: refs.okafor, short: 'Okafor 2022', citekey: 'Oka22' }
	];
	const checks: CheckRow[] = [
		{ row: `check:${refs.arden25}`, kind: 'check', docs: [MAIN], ref: refs.arden25, short: 'Arden 2025', pdf: null, nodes: [{ node: 'tq-05A1', name: 'Theorem 5.1', number: '5.1', title: 'Extension criterion', rests: { docs: [MAIN] }, how: 'transcribed' }] },
		{ row: `check:${refs.vance}`, kind: 'check', docs: [MAIN], ref: refs.vance, short: 'Vance et al. 2023', pdf: null, nodes: ['Theorem 1.4', 'Lemma 2.2', 'Proposition 3.1'].map((name, i) => ({ node: `tq-05B${i}`, name, number: name.split(' ')[1], rests: { docs: [] }, how: 'transcribed' as const })) },
		{ row: 'check:ev-2026-11-21-c8vz2a', kind: 'check', docs: [MAIN], correction: 'ev-2026-11-21-c8vz2a', node: 'tq-0201', name: 'Definition 1.2', ref: refs.arden24, short: 'Arden 2024', by: 'Claude Code' }
	];
	bodies['check:ev-2026-11-21-c8vz2a'] = {
		compared_at: '2026-11-18T15:20:00Z',
		runs: [
			['=', String.raw`The \emph{cycle space} of a quiver $Q$ is the kernel`],
			['-', 'of the divergence map'],
			['+', String.raw`$\mathcal{Z}(Q)$ of the divergence map $\partial\colon \mathbb{Z}^{A(Q)} \to \mathbb{Z}^{V(Q)}$`],
			['=', '.']
		]
	};
	// what `locate…` opens on each cited result: the draft's sentence citing it, and what loom found of its name in the paper
	const cite = (key: string, html: string) => {
		fragments[`fixture/cites/${key}.html`] = html;
		return `fixture/cites/${key}.html`;
	};
	const c = (n: string, label: string) => `<span class="cite"><a>[${n}, ${label}]</a></span>`;
	bodies[`cited:${refs.okafor}#tq-04A1`] = { cite: { doc: MAIN, key: 'sec:intro', where: 'main.tex, Section 1', fragment: cite('t23', p(`…the counting argument of Section 3 is an adaptation of the median-order technique of ${c('2', 'Theorem 2.3')}.`)), nth: 0 }, find: { query: 'Theorem 2.3', hits: [{ page: 1, rects: [[72, 236, 180, 250]] }, { page: 2, rects: [[72, 410, 180, 424]] }], pages: 24 } };
	bodies[`cited:${refs.okafor}#tq-04A2`] = { cite: { doc: MAIN, key: 'thm:count/proof', where: 'main.tex, proof of Theorem 3.4', fragment: cite('c42', p(`…and the count is a polynomial, as in ${c('2', 'Corollary 4.2')}.`)), nth: 0 }, find: { query: 'Corollary 4.2', hits: [{ page: 1, rects: [[72, 520, 190, 534]] }], pages: 24 } };
	bodies[`cited:${refs.arden25}#tq-04B1`] = { cite: { doc: MAIN, key: 'sec:intro', where: 'main.tex, Section 1', fragment: cite('t62', p(`The extension criterion ${c('3', 'Theorem 6.2')} appears only in the second arXiv version of that paper.`)), nth: 0 }, find: { query: 'Theorem 6.2', hits: [], pages: 31 } };
	bodies[`cited:${refs.smith}#tq-04C1`] = { cite: { doc: BOUNDS, key: 'thm:radius/proof', where: 'bounds.tex, proof of Theorem 1', fragment: cite('l82', p(`…by the thinness bound ${c('Smi24', 'Lemma 8.2')}, applied to each widget.`)), nth: 0 }, find: { query: 'Lemma 8.2', hits: [{ page: 2, rects: [[72, 610, 160, 624]] }], pages: 31 } };
	bodies['cited:m-2026-11-21-oka22'] = { cite: { doc: MAIN, key: 'thm:count/proof', where: 'main.tex, proof of Theorem 3.4', fragment: cite('bare', p(`Each interval ${m('[u, v]')} is a box <span class="cite"><a>[2]</a></span>, so the count over intervals is a sum of products.`)), nth: 0 } };
	// the Lean kinds: what the agent wrote of its formalization, what loom observed, and the person's last word
	const frag = (key: string, html: string) => {
		fragments[`fixture/lean/${key}.html`] = html;
		return { fragment: `fixture/lean/${key}.html` };
	};
	bodies['attest:lem:forest'] = {
		observation: 'ev-2026-11-21-l3an9e',
		statement: frag('lem-forest', p(`<b>Lemma 3.3.</b> <em>Let ${m('w')} be a balanced weighting of a quiver ${m('Q')}. Then (i) if ${m('\\operatorname{supp} w')} is a forest, then ${m('w = 0')}; and (ii) if the underlying graph of ${m('Q')} is a cycle, then ${m('w(a) = \\varepsilon(a)\\, w(a_0)')} for every arrow ${m('a')}, where ${m('\\varepsilon(a) = \\pm 1')} as ${m('a')} agrees with the orientation of ${m('a_0')} round the cycle.</em>`)),
		parts: [
			{ part: '(i)', draft: String.raw`if $\operatorname{supp} w$ is a forest, then $w = 0$;`, lean: "theorem Weighting.IsBalanced.eq_zero_of_isForest\n    {Q : Quiver'} {w : Q.Weighting}\n    (hw : w.IsBalanced)\n    (hF : (Q.restrict (Function.support w)).IsForest) :\n    w = 0", reading: String.raw`If $w$ is balanced and the arrows where $w$ is not zero form a forest, then $w$ is zero on every arrow.`, by: 'Claude Code' },
			{ part: '(ii)', draft: String.raw`if the underlying graph of $Q$ is a cycle, then $w(a) = \varepsilon(a)\, w(a_0)$ for every arrow $a$.`, lean: "theorem Weighting.IsBalanced.eq_cycleSign_mul\n    {Q : Quiver'} {w : Q.Weighting}\n    (hw : w.IsBalanced) (hC : Q.underlying.IsCycle)\n    (a₀ : Q.Arrow) :\n    ∀ a, w a = Q.cycleSign a₀ a * w a₀", reading: String.raw`If the underlying graph of $Q$ is a single cycle, then for any arrow $a_0$, each arrow carries $\pm$ the weight of $a_0$, the sign saying whether it points the same way round the cycle.`, by: 'Claude Code' }
		],
		notation: [
			{ part: 'ε', draft: String.raw`$\varepsilon(a) = \pm 1$ as $a$ agrees with the orientation of $a_0$ round the cycle`, lean: "def Quiver'.cycleSign (Q : Quiver')\n    (a₀ a : Q.Arrow) : ℤ", reading: String.raw`$+1$ if $a$ and $a_0$ run the same way round the cycle, $-1$ otherwise.`, from: 'statement' },
			{ part: 'supp', lean: 'Function.support w     -- Mathlib', reading: String.raw`The arrows on which $w$ is not zero, as Mathlib defines the support of a function.`, from: 'macros' }
		],
		uses_attested: [{ result: 'def:quiver', name: 'Definition 2.1', title: 'Quiver', at: '2026-11-12T10:40:00Z' }, { result: 'def:balanced', name: 'Definition 2.3', title: 'Balanced', at: '2026-11-12T10:40:00Z' }],
		supporting: ['Weighting.exists_leaf_of_isForest', 'Weighting.IsBalanced.restrict', "Quiver'.cycleSign_mul_self"],
		difference: { by: 'Claude Code', text: 'One difference. The draft fixes no a₀ in (ii); Lean takes a₀ as given. The statement holds for every choice of a₀, so the two say the same if (ii) is read “for any arrow a₀”.' }
	};
	bodies['attest:tq-00K5'] = {
		observation: 'ev-2026-11-21-k5ob2q',
		statement: frag('smith-34', p(`<b>Proposition 3.4.</b> <em>Let ${m('W')} be a widget as in Definition 2.1. Then ${m('W')} lies in a ball about the origin.</em>`)),
		parts: [{ part: '', draft: String.raw`Let $W$ be a widget as in Definition 2.1. Then $W$ lies in a ball about the origin.`, lean: 'theorem Smith.widget_bounded (W : Widget) :\n    ∃ r, W.carrier ⊆ Metric.ball 0 r', reading: String.raw`Every widget is contained in some ball centred at the origin.`, by: 'Claude Code' }],
		notation: [],
		uses_attested: [],
		supporting: []
	};
	bodies['attested-changed:cor:cycle'] = {
		observation: 'ev-2026-11-20-c35obs',
		at: '2026-11-20T16:02:00Z',
		then: frag('cor-then', p(`<b>Corollary 3.5.</b> <em>A connected quiver has a nonzero balanced weighting if and only if its underlying graph has a cycle.</em>`)),
		now: frag('cor-now', p(`<b>Corollary 3.5.</b> <em>A connected quiver has a nonzero balanced weighting if and only if its underlying graph has a cycle${ch('m', '', ' of length at least 2')}.</em>`)),
		lean: 'theorem Showcase.exists_ne_zero_balanced_iff\n    (Q : Quiver\') (hQ : Q.Connected) :\n    (∃ w : Q.Weighting, w.IsBalanced ∧ w ≠ 0)\n      ↔ Q.underlying.HasCycle',
		resting: []
	};
	bodies['attested-changed:def:connected'] = {
		observation: 'ev-2026-11-12-d37obs',
		at: '2026-11-12T10:40:00Z',
		then: frag('def-then', p(`<b>Definition 3.7.</b> A quiver is <em>connected</em> if its underlying graph is connected.`)),
		now: frag('def-now', p(`<b>Definition 3.7.</b> A quiver is <em>connected</em> if its underlying graph is connected${ch('n', '', ' after its loops are removed')}.`)),
		lean: "def Quiver'.Connected (Q : Quiver') : Prop :=\n  Q.underlying.Connected",
		resting: [
			{ result: 'prop:tree', name: 'Proposition 3.8', statement: frag('p38', p(`<b>Proposition 3.8.</b> <em>A connected quiver whose underlying graph is a tree has no nonzero balanced weighting.</em>`)), lean: 'theorem Showcase.balanced_eq_zero_of_isTree …', attested_again: false },
			{ result: 'lem:bridge', name: 'Lemma 3.9', statement: frag('l39', p(`<b>Lemma 3.9.</b> <em>Removing a bridge from a connected quiver leaves two connected quivers.</em>`)), lean: 'theorem Showcase.connected_of_removeBridge …', attested_again: false }
		]
	};
	const attest: AttestRow[] = [
		{ row: 'attest:lem:forest', kind: 'attest', docs: [MAIN], result: 'lem:forest', name: 'Lemma 3.3', source: { doc: MAIN }, what: 'statement and proof', paper: null },
		{ row: 'attest:tq-00K5', kind: 'attest', docs: [BOUNDS], result: 'tq-00K5', name: 'Proposition 3.4', source: { ref: refs.smith, short: 'Smith 2024' }, what: 'statement only', paper: 'matches' }
	];
	const accepted: AcceptedChangedRow[] = ACCEPTED.map(([doc, key, name, html]) => {
		const row = `accepted-changed:${key}`;
		fragments[`fixture/accepted/${key}.html`] = html;
		bodies[row] = { statement: { fragment: `fixture/accepted/${key}.html` } };
		return { row, kind: 'accepted-changed', docs: [doc], key, name, doc };
	});
	const attested: AttestedChangedRow[] = [
		{ row: 'attested-changed:cor:cycle', kind: 'attested-changed', docs: [MAIN], result: 'cor:cycle', name: 'Corollary 3.5', doc: MAIN, attested_at: '2026-11-20T16:02:00Z', changed: 'statement', resting: 0 },
		{ row: 'attested-changed:def:connected', kind: 'attested-changed', docs: [MAIN], result: 'def:connected', name: 'Definition 3.7', title: 'Connected', doc: MAIN, attested_at: '2026-11-12T10:40:00Z', changed: 'used', resting: 2 }
	];
	const edits: EditRow[] = EDITS.map((e) => {
		const row = `edits:${e.change}`;
		fragments[`fixture/edits/${e.change}.html`] = e.html;
		bodies[row] = { statement: { fragment: `fixture/edits/${e.change}.html` } };
		return { row, kind: 'edits', docs: [e.doc], change: e.change, type: e.type, doc: e.doc, key: e.key, where: e.where, by: 'Claude Code', broke: e.broke ?? null };
	});
	rows.push(...questions, ...fetch, ...cited, ...checks, ...attest, ...accepted, ...attested, ...edits);

	const tasks: TaskRow[] = [
		{ row: 'agents:t-2026-11-21-dg01', kind: 'agents', docs: [MAIN], task: 't-2026-11-21-dg01', what: 'digest', on: { ref: refs.okafor, short: 'Okafor 2022', scope: 'marked', count: 2 }, working: { by: 'Claude Code' }, asked_at: '2026-11-21T08:10:00Z' },
		{ row: 'agents:t-2026-11-21-tr02', kind: 'agents', docs: [BOUNDS], task: 't-2026-11-21-tr02', what: 'transcribe', on: {}, text: 'Transcribe the second proof of Proposition 3.4 of Smith 2024, from Halberd and Ravel 2021, pages 22–23', working: null, asked_at: '2026-11-21T08:20:00Z' },
		{ row: 'agents:t-2026-11-21-as03', kind: 'agents', docs: [MAIN], task: 't-2026-11-21-as03', what: 'ask', on: { doc: MAIN, key: 'thm:count/proof', name: 'proof of Theorem 3.4' }, text: 'does the count need the median order?', working: null, asked_at: '2026-11-21T08:30:00Z' },
		{ row: 'agents:t-2026-11-21-dg04', kind: 'agents', docs: [MAIN], task: 't-2026-11-21-dg04', what: 'digest', on: { ref: refs.vance, short: 'Vance et al. 2023', scope: 'all' }, working: null, asked_at: '2026-11-21T08:40:00Z' },
		{ row: 'agents:t-2026-11-21-7h3qfw', kind: 'agents', docs: [MAIN], task: 't-2026-11-21-7h3qfw', what: 'read', on: { ref: refs.okafor, short: 'Okafor 2022', names: ['Theorem 2.3'] }, working: null, asked_at: '2026-11-21T09:00:00Z' },
		{ row: 'agents:t-2026-11-21-mc06', kind: 'agents', docs: [BOUNDS], task: 't-2026-11-21-mc06', what: 'macros', on: {}, text: 'Check the macros of Smith 2024 against its preamble', working: null, asked_at: '2026-11-21T09:10:00Z' }
	];
	return { rows, tasks, bodies, fragments, seq: 0 };
}

/** The rows a draft concerns, all when `doc` is none. */
const forDoc = <T extends { docs: string[] }>(rows: T[], doc?: string) => (doc ? rows.filter((r) => r.docs.includes(doc)) : rows);

/** `review-counts`, over the rows as `extra` (the Library's results to check) completes them: the kinds for one draft where `doc` names one, the drafts always each. */
export function counts(r: ReviewFixture, extra: ReviewRow[], doc?: string): Omit<ReviewCounts, 'gen'> {
	const all = [...extra, ...r.rows];
	const here = forDoc(all, doc);
	const kinds: Partial<Record<ReviewKind, number>> = {};
	for (const k of LIST_ORDER) kinds[k] = here.filter((x) => x.kind === k).length;
	const docs = [...new Set(all.flatMap((x) => x.docs))].sort((a, b) => (a === MAIN ? -1 : b === MAIN ? 1 : a.localeCompare(b)));
	return { everything: here.length, kinds, agents: forDoc(r.tasks, doc).length, drafts: docs.map((d) => ({ doc: d, n: all.filter((x) => x.docs.includes(d)).length })) };
}

/** `review-list`: a kind's group, or every kind's in the list's order with the tasks' group last. */
export function list(r: ReviewFixture, extra: ReviewRow[], kind: ReviewKind | 'all' | 'agents', doc?: string): Omit<ReviewList, 'gen'> {
	const all = [...r.rows];
	// a work's results to check stand before the works held only as a PDF and the corrections, in paper order, as the Library's results do
	const firstCheck = all.findIndex((x) => x.kind === 'check');
	all.splice(firstCheck < 0 ? all.length : firstCheck, 0, ...extra);
	const group = (k: ReviewKind | 'agents'): ReviewGroup => ({ kind: k, rows: k === 'agents' ? forDoc(r.tasks, doc) : forDoc(all.filter((x) => x.kind === k), doc) });
	if (kind === 'all') return { groups: [...LIST_ORDER.map(group), group('agents')] };
	return { groups: [group(kind)] };
}

/** `review-row`: a row's body, by the row's id; for a cited result's `locate…`, by its row and its node. */
export function body(r: ReviewFixture, row: string, node?: string): Omit<ReviewBody, 'gen'> | null {
	const b = r.bodies[node ? `${row}#${node}` : row];
	return b ? { row, ...b } : null;
}

/** Takes away the row whose `field` is `value`, as acting on it closes it; false where none was there. */
export function close(r: ReviewFixture, test: (row: ReviewRow | TaskRow) => boolean): boolean {
	const i = r.rows.findIndex(test);
	if (i >= 0) {
		r.rows.splice(i, 1);
		return true;
	}
	const j = r.tasks.findIndex(test);
	if (j >= 0) {
		r.tasks.splice(j, 1);
		return true;
	}
	return false;
}

/** A task asked now, as `review-task` and `library-digest` make one. */
export function ask(r: ReviewFixture, what: string, on: TaskRow['on'], docs: string[], text?: string): string {
	const task = `t-2026-11-21-n${(++r.seq).toString().padStart(3, '0')}`;
	r.tasks.push({ row: `agents:${task}`, kind: 'agents', docs, task, what, on, ...(text ? { text } : {}), working: null, asked_at: new Date().toISOString().replace(/\.\d+Z$/, 'Z') });
	return task;
}

/** The fixture's fragment for a path, for its source's `fragment`. */
export const fragmentOf = (r: ReviewFixture, path: string): string | null => r.fragments[path] ?? null;

/** Marks the cited result `node` as placed by the person, as a mark to digest naming it does. */
export function markStub(r: ReviewFixture, node: string): void {
	for (const row of r.rows) if (row.kind === 'cited' && row.citation === undefined) for (const s of row.stubs) if (s.node === node) s.marked = true;
}

/** Records the person's attestation of `result`: a row waiting on it closes, or a result resting on a changed definition reads attested again. */
export function attest(r: ReviewFixture, result: string): boolean {
	const i = r.rows.findIndex((x) => (x.kind === 'attest' || x.kind === 'attested-changed') && x.result === result);
	if (i >= 0) {
		r.rows.splice(i, 1);
		return true;
	}
	for (const b of Object.values(r.bodies)) for (const x of (b.resting as { result: string; attested_again: boolean }[] | undefined) ?? []) if (x.result === result) return (x.attested_again = true);
	return false;
}
