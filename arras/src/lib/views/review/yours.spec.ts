// What the two kinds today's Your Changes draws count: the blocks its accept section lists as waiting, each once, and the cards of its changes section, each narrowed to a draft as it is drawn.
import { describe, expect, it } from 'vitest';
import fixture from '../../../../tests/fixture/manifest.json';
import type { Manifest, PendingChange } from '$lib/manifest/types';
import type { ReviewList } from '$lib/library/types';
import { acceptSections, acceptWaiting, changeGroups, changesWaiting, theirs } from './yours';

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

	it('counts in a draft only what that draft reads, and nothing in a draft the quilt does not hold', () => {
		expect(acceptWaiting(m, TALK)).toBeLessThan(acceptWaiting(m));
		expect(acceptWaiting(m, 'drafting/bounds.tex')).toBe(0);
	});
});

describe('the changes section', () => {
	const x: Manifest = { ...m, changes: [change({ id: 'c-1' }), change({ id: 'c-2', documents: [MAIN, TALK] }), change({ id: 'c-3', documents: [], path: 'notes/intro.md' })], contributions: m.contributions };
	const copies = (m.contributions ?? []).filter((c) => c.kind === 'adopt').length;

	it('counts each change and each agent copy, and leaves out one just kept or discarded', () => {
		expect(changesWaiting(x, {})).toBe(3 + copies);
		expect(changesWaiting(x, { 'c-1': 'keep' })).toBe(2 + copies);
	});

	it("narrows to the changes in a draft's text, in one group, and the copies into it", () => {
		const groups = changeGroups(x, {}, TALK);
		expect(groups).toHaveLength(1);
		expect(groups[0].changes.map((c) => c.id)).toEqual(['c-2']);
		expect(changesWaiting(x, {}, TALK)).toBe(1);
		expect(changesWaiting(x, {}, MAIN)).toBe(2 + copies);
	});
});

it("counts loom's rows of a kind that concern a draft, and nothing before they are read", () => {
	const list = { groups: [{ kind: 'edits', rows: [{ row: 'edits:a', kind: 'edits', docs: [MAIN] }, { row: 'edits:b', kind: 'edits', docs: [MAIN, TALK] }, { row: 'edits:c', kind: 'edits', docs: [] }] }] } as unknown as ReviewList;
	expect(theirs(list, MAIN)).toBe(2);
	expect(theirs(list, TALK)).toBe(1);
	expect(theirs(null, MAIN)).toBeNull();
});
