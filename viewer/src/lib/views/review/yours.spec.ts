// The rows of the two kinds drawn from the manifest, and what they count: Results to accept's blocks waiting, each once, the never accepted and the accepted folded beneath and uncounted; Proposed edits' files with edits made in place, suggested edits and copies; each narrowed to a draft as it is drawn.
import { describe, expect, it } from 'vitest';
import fixture from '../../../../tests/fixture/manifest.json';
import type { Manifest, PendingChange, UnresolvedReview } from '$lib/manifest/types';
import type { ReviewList } from '$lib/library/types';
import { acceptList, acceptSections, acceptWaiting, changeGroups, changeList, changesWaiting, editRows, theirs } from './yours';

const m = fixture as unknown as Manifest;
const MAIN = 'drafting/main.tex';
const TALK = 'drafting/talk.tex';
const change = (over: Partial<PendingChange>): PendingChange => ({ id: 'c-0001', kind: 'edit', path: 'drafting/nodes/sy-0001.tex', key: 'sy-0001', documents: [MAIN], old: 'a', new: 'b', state: 'ready', ...over });

describe('the accept section', () => {
	it('counts a block changed since accepted once, however many drafts read it, and the never accepted not at all', () => {
		const waiting = new Set(m.unresolved!.filter((r) => r.cause !== 'never-accepted').map((r) => r.key));
		expect(acceptWaiting(m)).toBe(waiting.size);
		expect(acceptWaiting(m)).toBeLessThanOrEqual(acceptWaiting(m, MAIN) + acceptWaiting(m, TALK));
	});

	it('draws every document with blocks, each block once, under the first document that reads it, and counts what it draws', () => {
		const sections = acceptSections(m);
		const keys = sections.flatMap((s) => [...s.a.changed, ...s.a.taken.flatMap((t) => t.rows), ...s.a.never, ...s.a.accepted].map((b) => b.key));
		expect(new Set(keys).size).toBe(keys.length);
		expect(sections.map((s) => s.path)).toContain(TALK);
		const waiting = sections.reduce((n, s) => n + s.a.changed.length + s.a.taken.reduce((k, t) => k + t.rows.length, 0), 0);
		expect(acceptWaiting(m)).toBe(waiting);
		// a draft alone keeps every block it reads, those an earlier draft lists too
		expect(acceptSections(m, TALK).map((s) => s.path)).toEqual([TALK]);
	});

	it('lists a row for each block waiting, the changed before the taken in within a document, and counts exactly those rows', () => {
		const list = acceptList(m);
		expect(list.rows).toHaveLength(acceptWaiting(m));
		// with no adoption, each block waiting is a row
		expect(list.rows.map((r) => r.type === 'block' && r.key)).toEqual(list.waiting.map((b) => b.key));
		const keys = [...list.waiting, ...list.never, ...list.accepted].map((b) => b.key);
		expect(new Set(keys).size).toBe(keys.length);
		expect(list.waiting.every((b) => b.row.cause !== 'never-accepted')).toBe(true);
		expect(list.never.every((b) => b.row.cause === 'never-accepted')).toBe(true);
		expect(list.never.length).toBeGreaterThan(0);
		// a block names the document it is listed under, whose file names its row
		for (const b of list.waiting) expect(m.masters.some((d) => d.path === b.doc)).toBe(true);
		expect(acceptList(m, TALK).rows).toHaveLength(acceptWaiting(m, TALK));
	});

	it('names the source of a block taken in from a copy, and lists it after its document\'s changed blocks', () => {
		const taken: Manifest = { ...m, unresolved: m.unresolved!.map((r) => (r.key === 'sy-0001' ? { ...r, cause: 'adopted' as const, contribution: '.loom/copies/main-agent.tex' } : r)) };
		const rows = acceptList(taken).waiting;
		const row = rows.find((b) => b.key === 'sy-0001');
		expect(row?.taken).toBe('Taken in from the copy “main-agent”');
		const own = rows.filter((b) => b.doc === row!.doc);
		expect(own.at(-1)?.key).toBe('sy-0001');
	});

	it('draws an adoption as one row holding every block it took in, standing where its first block does, and counts it once; a block taken in from Overleaf stays a row of its own', () => {
		const COPY = '.loom/agents/copies/aidoc.tex';
		const from: Record<string, Partial<UnresolvedReview>> = {
			'sy-0002': { cause: 'adopted', contribution: COPY },
			'sy-0004': { cause: 'adopted', contribution: COPY, refusal: 'It is marked incomplete.', refusal_code: 'incomplete' },
			'sy-0005': { cause: 'incoming-pull', source_label: 'Taken in from Overleaf' },
			'drafting/talk.tex#lemma:1': { cause: 'adopted', contribution: COPY }
		};
		const x: Manifest = { ...m, unresolved: m.unresolved!.map((r) => ({ ...r, ...from[r.key] })) };
		const list = acceptList(x);
		const shown = list.rows.map((r) => (r.type === 'adoption' ? [r.name, r.doc, r.blocks.map((b) => b.key)] : r.key));
		expect(shown).toEqual(['sy-0001', 'sy-0002/proof', ['aidoc', MAIN, ['sy-0002', 'sy-0004', 'drafting/talk.tex#lemma:1']], 'sy-0005']);
		// every block the rows hold is listed once, in `waiting`, with the document that names it
		expect(list.waiting.map((b) => b.key)).toHaveLength(6);
		expect(list.waiting.find((b) => b.key === 'drafting/talk.tex#lemma:1')?.doc).toBe(TALK);
		expect(acceptWaiting(x)).toBe(4);
		// a draft draws the adoption while it reads one of its blocks, holding only those
		const talk = acceptList(x, TALK).rows;
		expect(talk.map((r) => (r.type === 'adoption' ? r.blocks.map((b) => b.key) : r.key))).toEqual(['sy-0002/proof', ['drafting/talk.tex#lemma:1', 'sy-0002']]);
		expect(acceptWaiting(x, TALK)).toBe(2);
		// two copies are two rows
		const y: Manifest = { ...x, unresolved: x.unresolved!.map((r) => (r.key === 'sy-0004' ? { ...r, contribution: '.loom/agents/copies/other.tex' } : r)) };
		expect(acceptList(y).rows.filter((r) => r.type === 'adoption').map((r) => r.type === 'adoption' && r.name)).toEqual(['aidoc', 'other']);
		expect(acceptWaiting(y)).toBe(5);
	});

	it('counts in a draft only what that draft reads, and nothing in a draft the quilt does not hold', () => {
		expect(acceptWaiting(m, TALK)).toBeLessThan(acceptWaiting(m));
		expect(acceptWaiting(m, 'drafting/bounds.tex')).toBe(0);
	});
});

describe('the changes section', () => {
	const x: Manifest = { ...m, changes: [change({ id: 'c-1' }), change({ id: 'c-2', documents: [MAIN, TALK] }), change({ id: 'c-3', documents: [], path: 'notes/intro.md' })], contributions: m.contributions };
	const copies = (m.contributions ?? []).filter((c) => c.kind === 'adopt').length;

	it('counts a row for each file with edits made in place and each agent copy, and leaves out a change just kept or discarded', () => {
		// c-1 and c-2 are in one file
		expect(changesWaiting(x, {})).toBe(2 + copies);
		expect(changesWaiting(x, { 'c-1': 'keep' })).toBe(2 + copies);
		expect(changesWaiting(x, { 'c-1': 'keep', 'c-2': 'keep' })).toBe(1 + copies);
	});

	it('draws one row a file for the edits made in place, holding each of them, and a suggested edit as a row of its own', () => {
		const NODE = 'drafting/nodes/sy-0001.tex';
		const y: Manifest = {
			...x,
			changes: [
				change({ id: 'c-1' }),
				change({ id: 's-1', kind: 'suggested', author: 'agent' }),
				change({ id: 'c-2', key: 'sy-0002' }),
				change({ id: 'c-3', documents: [], path: 'notes/intro.md', key: null }),
				change({ id: 's-2', kind: 'suggested', author: 'agent' }),
				change({ id: 'c-4', documents: [], path: 'notes/intro.md', key: null })
			]
		};
		const rows = editRows(y, {});
		expect(rows.map((r) => (r.type === 'file' ? [r.path, r.changes.map((c) => c.id)] : r.c.id))).toEqual([[NODE, ['c-1', 'c-2']], 's-1', 's-2', ['notes/intro.md', ['c-3', 'c-4']]]);
		expect(rows.map((r) => r.doc)).toEqual([MAIN, MAIN, MAIN, null]);
		expect(changesWaiting(y, {})).toBe(4 + copies);
		// a file whose changes are all kept or discarded is no row; one still holding some keeps only those
		expect(editRows(y, { 'c-1': 'keep' }).find((r) => r.type === 'file' && r.path === NODE)).toMatchObject({ changes: [{ id: 'c-2' }] });
		expect(changesWaiting(y, { 'c-1': 'keep', 'c-2': 'discard', 's-1': 'keep' }, MAIN)).toBe(1 + copies);
	});

	it('lists a row for each change, naming the draft whose text holds it, or the file of one in no draft', () => {
		const rows = changeList(x, {});
		expect(rows.map((r) => r.c.id)).toEqual(['c-1', 'c-2', 'c-3']);
		expect(rows.map((r) => r.doc)).toEqual([MAIN, MAIN, null]);
		expect(rows[2].label).toBe('notes/intro.md');
		expect(changeList(x, { 'c-2': 'discard' }).map((r) => r.c.id)).toEqual(['c-1', 'c-3']);
		expect(changeList(x, {}, TALK).map((r) => [r.c.id, r.doc])).toEqual([['c-2', TALK]]);
	});

	it("narrows to the changes in a draft's text, in one group, and the copies into it", () => {
		const groups = changeGroups(x, {}, TALK);
		expect(groups).toHaveLength(1);
		expect(groups[0].changes.map((c) => c.id)).toEqual(['c-2']);
		expect(changesWaiting(x, {}, TALK)).toBe(1);
		expect(changesWaiting(x, {}, MAIN)).toBe(1 + copies);
	});
});

it("counts loom's rows of a kind that concern a draft, and nothing before they are read", () => {
	const list = { groups: [{ kind: 'edits', rows: [{ row: 'edits:a', kind: 'edits', docs: [MAIN] }, { row: 'edits:b', kind: 'edits', docs: [MAIN, TALK] }, { row: 'edits:c', kind: 'edits', docs: [] }] }] } as unknown as ReviewList;
	expect(theirs(list, MAIN)).toBe(2);
	expect(theirs(list, TALK)).toBe(1);
	expect(theirs(null, MAIN)).toBeNull();
});
