// What a Review row says before it opens: its first line, its quiet line at the right, its two marks, and whether it opens; and a task's sentence from what was asked and of what. Pure, so the phrases are held by unit tests; every word is `$lib/words/review`'s.

import type { MarkKind } from '$lib/marks/Mark.svelte';
import { paperMark } from '$lib/marks/marks';
import type { AskedOn, ReviewGroup, ReviewKind, ReviewRow, TaskRow } from '$lib/library/types';
import { review as words } from '$lib/words/review';

/** The names of what a row names by id (`names.svelte.ts`): undefined while unread, or for what nothing names. */
export interface Names {
	work(ref: string): { short: string; title: string } | undefined;
	node(id: string): { name: string; short: string } | undefined;
	result(label: string): string | undefined;
}

const short = (n: Names, ref?: string) => (ref ? n.work(ref)?.short : undefined) ?? words.someWork;
const result = (n: Names, label?: string) => (label ? n.result(label) : undefined) ?? words.someResult;
/** The draft result an ask's place names, by its label or its block. */
const placed = (n: Names, on: AskedOn) => result(n, on.label ?? on.block?.key);

/** Names in the paper's order, their numbers read naturally (5.7 before 5.9 before 5.10), as a row names its results. */
export function inPaperOrder(names: string[]): string[] {
	const num = (n: string) => (/(\S+)$/.exec(n)?.[1] ?? '').split('.').map((x) => (Number.isNaN(+x) ? x.charCodeAt(0) + 1000 : +x));
	return [...names].sort((a, b) => {
		const [x, y] = [num(a), num(b)];
		for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) - (y[i] ?? 0);
		return 0;
	});
}

/** A row's first line. An agent's question is drawn with the agent's name apart (`question`), so it has none here. */
export function line(r: ReviewRow, n: Names): string {
	switch (r.kind) {
		case 'accepted-changed':
			return words.at(words.file(r.doc), r.name);
		case 'questions':
			return '';
		case 'attested-changed':
			return words.at(words.file(r.doc), r.name);
		case 'cited':
			return r.citation !== undefined ? words.cited.namesNone(r.doc, r.where, r.short) : words.at(r.short, words.results(inPaperOrder(r.stubs.map((s) => s.name))));
		case 'check':
			return r.correction !== undefined ? words.at(r.short, words.check.correction(r.name)) : words.at(r.short, words.results(inPaperOrder(r.nodes.map((n) => n.name))));
		case 'attest':
			return words.at('doc' in r.source ? words.file(r.source.doc) : r.source.short, r.name);
		case 'fetch': {
			const w = n.work(r.ref);
			return w ? words.at(w.short, w.title) : words.someWork;
		}
		case 'edits':
			return words.at(words.file(r.doc), r.where);
	}
}

/** An agent's question: the agent's name, then where it asked and what. */
export function question(r: Extract<ReviewRow, { kind: 'questions' }>, n: Names): { by: string; rest: string } {
	const o = r.on;
	const node = o.node ? n.node(o.node) : undefined;
	// where the agent was when it asked: the work it was digesting, where its session was digesting one; else the question's own place
	const where = r.under?.what === 'digest' && r.under.ref ? words.questions.digesting(short(n, r.under.ref)) : o.ref ? (o.page ? words.questions.onPage(short(n, o.ref), o.page) : words.questions.on(short(n, o.ref))) : o.label || o.block ? words.questions.onResult(r.docs[0] ?? '', placed(n, o)) : o.node ? words.questions.on(node ? words.of(node.name, node.short) : words.someResult) : words.questions.on(o.document ? words.file(o.document) : '');
	return { by: r.by, rest: words.questions.asks(where) + r.text };
}

/** A row's quiet line at the right. */
export function quiet(r: ReviewRow): string {
	switch (r.kind) {
		case 'cited': {
			if (r.citation !== undefined) return '';
			const docs = [...new Set(r.stubs.flatMap((s) => s.rests.docs))];
			const why = r.stubs.some((s) => s.not_in_source) ? words.cited.notInSource : r.holds.pdf && !r.holds.tex ? words.cited.pdfOnly : '';
			return words.quiet([why, words.rests(docs, r.stubs.filter((s) => s.rests.docs.length).length, r.stubs.length)]);
		}
		case 'check': {
			if (r.correction !== undefined) return words.edits.by(r.by);
			const docs = [...new Set(r.nodes.flatMap((n) => n.rests.docs))];
			const how = r.nodes.some((n) => n.how === 'transcribed') ? words.check.transcribed : '';
			return words.quiet([how, words.rests(docs, r.nodes.filter((n) => n.rests.docs.length).length, r.nodes.length)]);
		}
		case 'attest':
			return words.attest.what[r.what];
		case 'attested-changed':
			// results resting under it are counted; else what changed, its own text or what it uses
			return r.resting.length ? words.attested.used(r.resting.length) : r.changed === 'statement' ? words.attested.statement(words.day(r.attested_at)) : words.attested.uses;
		case 'edits':
			return r.broke ? words.edits.broke(r.doc, r.broke.line) : r.by ? words.edits.by(r.by) : '';
		default:
			return '';
	}
}

/** A row's two marks, its paper's and its Lean's, either none. */
export function marks(r: ReviewRow): [MarkKind | null, MarkKind | null] {
	switch (r.kind) {
		case 'cited':
			return [r.citation !== undefined ? null : r.stubs.every((s) => s.marked) ? 'marked' : 'stub', null];
		case 'check':
			return ['unchecked', null];
		case 'attest':
			return [r.paper ? paperMark(r.paper) : null, 'attest'];
		case 'attested-changed':
			return [null, 'attest'];
		default:
			return [null, null];
	}
}

/** The kinds whose rows open in this build; a papers-to-fetch row never does. */
const OPENS = new Set<ReviewRow['kind']>(['questions', 'accepted-changed', 'edits', 'check', 'cited', 'attest', 'attested-changed']);
export const opens = (r: ReviewRow): boolean => OPENS.has(r.kind);

/** A task's sentence, from what was asked and of what, each named by its id; an ask of a kind loom does not make here is drawn with the words it carries. */
export function task(t: TaskRow, n: Names): string {
	const o = t.on;
	const doc = t.docs[0] ?? '';
	const nodes = (t.nodes ?? []).map((id) => n.node(id));
	const target = t.target?.node ? (n.node(t.target.node)?.name ?? words.someResult) : result(n, t.target?.label);
	switch (t.what) {
		case 'digest': {
			const of = short(n, t.ref ?? o.ref);
			const count = (t.scope === 'marked' ? t.marks : t.nodes)?.length ?? 0;
			return t.scope === 'marked' ? words.agents.digestMarked(count, of) : t.scope === 'all' ? words.agents.digestAll(of) : t.scope === 'uses' ? words.agents.digestUses(of) : words.agents.digestChosen(count, of);
		}
		case 'read':
			return words.agents.read(
				nodes.map((x) => x?.name ?? words.someResult),
				nodes.find((x) => x)?.short ?? words.someWork
			);
		case 'ask':
			return o.ref ? words.agents.askPage(short(n, o.ref), o.page ?? 1, t.text ?? '') : words.agents.askResult(doc, placed(n, o), t.text ?? '');
		case 'correct': {
			const node = o.node ? n.node(o.node) : undefined;
			return words.agents.correct(node?.name ?? words.someResult, node?.short ?? words.someWork, t.text ?? '');
		}
		case 'restate':
			return words.agents.restate(target, doc);
		case 'which-result':
			return words.agents.whichResult(short(n, t.cites), placed(n, o));
		case 'formalize':
			return words.agents.formalize(target, doc);
		default:
			return t.text ?? t.words ?? '';
	}
}

/** The kinds the viewer shows: loom's, with attested results that changed shown among the Lean statements to attest. */
export type ShownKind = Exclude<ReviewKind, 'attested-changed'> | 'agents';
export interface ShownGroup extends ReviewGroup {
	kind: ShownKind;
}

/** Loom's groups as the viewer shows them: the attested results that changed joined to the Lean statements to attest, ahead of those never attested, in the place of whichever comes first; each row keeps its own kind. */
export function joined(groups: ReviewGroup[]): ShownGroup[] {
	const changed = groups.filter((g) => g.kind === 'attested-changed').flatMap((g) => g.rows);
	const fresh = groups.filter((g) => g.kind === 'attest').flatMap((g) => g.rows);
	const out: ShownGroup[] = [];
	for (const g of groups) {
		if (g.kind !== 'attest' && g.kind !== 'attested-changed') out.push(g as ShownGroup);
		else if (!out.some((o) => o.kind === 'attest')) out.push({ kind: 'attest', rows: [...changed, ...fresh] });
	}
	return out;
}

/** The cited results the rows hold, which `ask an agent to read all` asks for. */
export const stubsOf = (rows: (ReviewRow | TaskRow)[]) => rows.flatMap((r) => (r.kind === 'cited' && r.citation === undefined ? r.stubs.map((s) => ({ node: s.node, docs: s.rests.docs })) : []));
