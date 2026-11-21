// What a Review row says before it opens: its first line, its quiet line at the right, its two marks, and whether it opens; and a task's sentence from what was asked and of what. Pure, so the phrases are held by unit tests; every word is `$lib/words/review`'s.

import type { MarkKind } from '$lib/marks/Mark.svelte';
import { paperMark } from '$lib/marks/marks';
import type { ReviewRow, TaskRow } from '$lib/library/types';
import { review as words } from '$lib/words/review';

/** A row's first line. An agent's question is drawn with the agent's name apart (`question`), so it has none here. */
export function line(r: ReviewRow): string {
	switch (r.kind) {
		case 'accepted-changed':
			return words.at(words.file(r.doc), r.name);
		case 'questions':
			return '';
		case 'attested-changed':
			return words.at(words.file(r.doc), r.title ? `${r.name}, ${r.title}` : r.name);
		case 'cited':
			return r.citation !== undefined ? words.cited.namesNone(r.doc, r.where, r.short) : words.at(r.short, words.results(r.stubs.map((s) => s.name)));
		case 'check':
			return r.correction !== undefined ? words.at(r.short, words.check.correction(r.name)) : words.at(r.short, words.results(r.nodes.map((n) => n.name)));
		case 'attest':
			return words.at('doc' in r.source ? words.file(r.source.doc) : r.source.short, r.title ? `${r.name}, ${r.title}` : r.name);
		case 'fetch':
			return words.at(r.short, r.title);
		case 'edits':
			return words.at(words.file(r.doc), r.where);
	}
}

/** An agent's question: the agent's name, then where it asked and what. */
export function question(r: Extract<ReviewRow, { kind: 'questions' }>): { by: string; rest: string } {
	const o = r.on;
	const where = o.digesting ? words.questions.digesting(o.digesting) : o.doc && o.name ? words.questions.onResult(o.doc, o.name) : o.short && o.page ? words.questions.onPage(o.short, o.page) : words.questions.on(o.short ?? o.name ?? (o.doc ? words.file(o.doc) : ''));
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
			return r.changed === 'statement' ? words.attested.statement(words.day(r.attested_at)) : words.attested.used(r.resting);
		case 'edits':
			return r.broke ? words.edits.broke(r.doc, r.broke.line) : words.edits.by(r.by);
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
const OPENS = new Set<ReviewRow['kind']>(['questions', 'accepted-changed', 'edits', 'check', 'cited']);
export const opens = (r: ReviewRow): boolean => OPENS.has(r.kind);

/** A task's sentence, from what was asked and of what; an ask of a kind loom does not make here is drawn with the words it carries. */
export function task(t: TaskRow): string {
	const o = t.on;
	const short = o.short ?? '';
	switch (t.what) {
		case 'digest':
			return o.scope === 'marked' ? words.agents.digestMarked(o.count ?? 0, short) : o.scope === 'all' ? words.agents.digestAll(short) : o.scope === 'uses' ? words.agents.digestUses(short) : words.agents.digestChosen(o.count ?? 0, short);
		case 'read':
			return words.agents.read(o.names ?? [], short);
		case 'ask':
			return o.doc ? words.agents.askResult(o.doc, o.name ?? '', t.text ?? '') : words.agents.askPage(short, o.page ?? 1, t.text ?? '');
		case 'correct':
			return words.agents.correct(o.name ?? '', short, t.text ?? '');
		case 'restate':
			return words.agents.restate(o.name ?? '', o.doc ?? '');
		case 'which-result':
			return words.agents.whichResult(short, o.where ?? '');
		case 'formalize':
			return words.agents.formalize(o.name ?? '', o.doc ?? '');
		default:
			return t.text ?? '';
	}
}

/** The cited results the rows hold, which `ask an agent to read all` asks for. */
export const stubsOf = (rows: (ReviewRow | TaskRow)[]) => rows.flatMap((r) => (r.kind === 'cited' && r.citation === undefined ? r.stubs.map((s) => ({ node: s.node, docs: s.rests.docs })) : []));
