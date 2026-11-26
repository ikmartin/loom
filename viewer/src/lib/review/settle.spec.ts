import { describe, expect, it } from 'vitest';
import { doneSays, drawPreview, refusedSays, settleAct, type SettleAnswer } from './settle';

const ID = 'w-2026-11-25-abc123';

/** A Keep left after it wrote its file, as `write-settle-preview` answers it: one file, one suggested edit kept, no version of its own. */
const keep: SettleAnswer = {
	act: ID,
	kind: 'a Keep',
	files: ['drafting/nodes/sy-0002.tex'],
	edits: [{ id: 'e-2026-09-17-zwvx4m', words: 'Referee Agent\'s suggestion “the fixed points are those of” for “compare”', outcome: 'kept', why: 'its words stand where it was written' }],
	history: ''
};

/** Every sentence of a drawn preview, in order. */
const all = (p: SettleAnswer) => Object.values(drawPreview(p)).flat().filter(Boolean).join('\n');

describe('the notice that offers settling', () => {
	it('is the one whose fix carries write-settle, and its id is read from that fix alone', () => {
		expect(settleAct({ fixes: [{ label: 'settle it as it stands', command: `loom doctor --settle ${ID}`, act: { endpoint: 'write-settle', body: { act: ID } } }] })).toBe(ID);
		expect(settleAct({ fixes: [{ label: 'bring them up to date', command: 'loom upgrade', act: { endpoint: 'agents-update', body: {} } }] })).toBe('');
		expect(settleAct({ fixes: [{ label: 'settle it as it stands', command: `loom doctor --settle ${ID}` }] })).toBe('');
		expect(settleAct({})).toBe('');
	});
});

describe('the preview, drawn from its fields', () => {
	it('says every file and every suggested edit with what it becomes and why, and never an id, a digest or a command', () => {
		const d = drawPreview(keep);
		expect(d.lead).toBe('Settling a Keep as it stands writes none of your files.');
		expect(d.filesHead).toBe('This file stays exactly as it is now:');
		expect(d.files).toEqual(['drafting/nodes/sy-0002.tex']);
		expect(d.editsHead).toBe('This suggested edit is recorded as your file shows it:');
		expect(d.edits).toEqual(['Referee Agent\'s suggestion “the fixed points are those of” for “compare”: kept, since its words stand where it was written.']);
		expect(d.history).toBe('');
		expect(d.nothing).toBe('');
		const text = all(keep);
		expect(text).not.toContain(ID);
		expect(text).not.toContain('e-2026');
		expect(text).not.toMatch(/sha256|loom doctor|--settle/);
	});

	it('names each outcome in the viewer\'s words, and an outcome it does not know as left', () => {
		const edit = (outcome: string) => drawPreview({ ...keep, edits: [{ ...keep.edits[0], words: 'W', why: 'Y', outcome }] }).edits[0];
		expect(edit('kept')).toBe('W: kept, since Y.');
		expect(edit('open')).toBe('W: open again, for you to keep or discard, since Y.');
		expect(edit('closed')).toBe('W: closed, as no longer applying, since Y.');
		expect(edit('as-is')).toBe('W: left as it is, since Y.');
		expect(edit('something-new')).toBe('W: left as it is, since Y.');
		expect(drawPreview({ ...keep, edits: [{ ...keep.edits[0], words: 'W', why: '', outcome: 'kept' }] }).edits[0]).toBe('W: kept.');
	});

	it('counts files and edits in its heads', () => {
		const d = drawPreview({ ...keep, files: ['a.tex', 'b.tex'], edits: [keep.edits[0], keep.edits[0]] });
		expect(d.filesHead).toBe('These files stay exactly as they are now:');
		expect(d.editsHead).toBe('These suggested edits are recorded as your files show them:');
	});

	it('says what becomes of the version the write began: recorded where its lines land, not kept where they cannot, nothing where it is in the history already', () => {
		expect(drawPreview({ ...keep, history: 'lands' }).history).toBe('The version loom kept of your files just before this write is recorded in your history.');
		expect(drawPreview({ ...keep, history: 'removed' }).history).toBe('The version loom began of your files just before this write was never recorded, so it is not kept in your history.');
		expect(drawPreview({ ...keep, history: 'recorded' }).history).toBe('');
	});

	it('says, of a write with no file loom believes and no edit, that only the notice goes', () => {
		const d = drawPreview({ kind: 'a Keep', files: [], edits: [], history: '' });
		expect(d.nothing).toBe('It decides nothing of your suggested edits and keeps no version; it only takes this notice away.');
		expect(d.filesHead).toBe('');
		expect(d.editsHead).toBe('');
		expect(drawPreview({ kind: '', files: [], edits: [], history: '' }).lead).toBe('Settling this write as it stands writes none of your files.');
	});
});

describe('what is said after', () => {
	it("says the outcome in the viewer's words by counts, never loom's result", () => {
		expect(doneSays(keep)).toBe('Settled as it stands: none of your files was written. Suggested edits: 1 kept.');
		expect(doneSays({ edits: [{ ...keep.edits[0], outcome: 'open' }, { ...keep.edits[0], outcome: 'closed' }, { ...keep.edits[0], outcome: 'as-is' }], history: 'removed' })).toBe(
			'Settled as it stands: none of your files was written. Suggested edits: 1 open again, 1 closed. The version it began is not kept.'
		);
		expect(doneSays({ edits: [], history: 'lands' })).toBe('Settled as it stands: none of your files was written. Its version is recorded in your history.');
		expect(doneSays({ edits: [], history: '' })).not.toMatch(/settled a Keep/);
	});

	it("says a refusal by its code, settling's own first, then the frame's, else a plain sentence", () => {
		expect(refusedSays('author-only')).toBe('Only you can settle a write; loom does not take it from an agent.');
		expect(refusedSays('no-such-act')).toBe('That write is no longer waiting to be settled, so nothing was done.');
		expect(refusedSays('not-left')).toBe('Loom settles that write itself the next time it writes, so there is nothing to decide.');
		expect(refusedSays('changed')).toBe('A file changed while it was being settled, so nothing was done. Look at what settling does now, and settle it again.');
		expect(refusedSays('unreachable')).toBe('Loom could not be reached.');
		expect(refusedSays('no-reviewer')).toBe('Loom does not know your name yet. Set it in Settings, under Profile, and try again.');
		expect(refusedSays('never-heard-of')).toBe('Loom could not do that.');
		expect(refusedSays(undefined)).toBe('Loom could not do that.');
	});
});
