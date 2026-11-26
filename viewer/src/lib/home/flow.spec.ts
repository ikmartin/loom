import { describe, expect, it } from 'vitest';
import { openingOf, outcomeOf, saidOf, stepAt, stepsOf } from './flow';
import { isPdf, quiltName } from './drop';
import type { Job, QuiltRow } from './api';

const job = (over: Partial<Job>): Job => ({ job: 'j', kind: 'create', state: 'running', step: 'making', ...over });
const row = (over: Partial<QuiltRow>): QuiltRow => ({ quilt: 'q', name: 'Q', folder: '/q', port: 9000, open: true, state: 'starting', ...over });

describe("the home page's window for a new quilt", () => {
	it('lists a paper’s steps, a PDF’s and an empty quilt’s, and finds the step loom names', () => {
		expect(stepsOf('paper')).toEqual(['making', 'importing', 'starting']);
		expect(stepsOf('pdf')).toEqual(['making', 'reading', 'starting']);
		expect(stepsOf('empty')).toEqual(['making', 'starting']);
		expect(stepAt('pdf', 'importing')).toBe(1);
		expect(stepAt('empty', 'starting')).toBe(1);
		expect(stepAt('paper', '')).toBe(0);
	});

	it('says a name already taken under the name, as being made while a create of it runs, and a dead end in place of the form', () => {
		expect(saidOf('exists')).toEqual({ under: 'exists' });
		expect(saidOf('exists', true)).toEqual({ under: 'beingMade' });
		expect(saidOf('inside-a-quilt')).toEqual({ under: 'insideQuilt' });
		expect(saidOf('no-paper')).toEqual({ refused: 'noPaper' });
		expect(saidOf('too-large')).toEqual({ refused: 'tooLarge' });
		expect(saidOf('stopping')).toEqual({ refused: 'stopping' });
		// an import's failure keeps what loom said; any other failure says nothing of loom's own
		expect(saidOf('cannot-import', false, 'paper.tex: a file is missing')).toEqual({ failed: 'paper.tex: a file is missing' });
		expect(saidOf('failed', false, 'Traceback …')).toEqual({ failed: '' });
	});

	it('shows the last step until the quilt made is served, since a create ends before its server answers', () => {
		expect(outcomeOf(undefined)).toBe('running');
		expect(outcomeOf(job({}))).toBe('running');
		expect(outcomeOf(job({ state: 'done' }))).toBe('running');
		expect(outcomeOf(job({ state: 'done' }), row({}))).toBe('running');
		expect(outcomeOf(job({ state: 'done' }), row({ state: 'running', url: 'http://127.0.0.1:9000/' }))).toBe('served');
		expect(outcomeOf(job({ state: 'done' }), row({ state: 'failed', why: 'refused' }))).toBe('unserved');
		expect(outcomeOf(job({ state: 'failed' }))).toBe('failed');
	});

	it('opens a PDF’s quilt on its library, and says on a paper’s first page that its working copy differs', () => {
		expect(openingOf('http://127.0.0.1:9000/', job({ state: 'done' }), false)).toBe('http://127.0.0.1:9000/');
		expect(openingOf('http://127.0.0.1:9000/', job({ state: 'done', differs: true }), false)).toBe('http://127.0.0.1:9000/?made=differs');
		expect(openingOf('http://127.0.0.1:9000/', job({ state: 'done' }), true)).toBe('http://127.0.0.1:9000/library');
	});

	it('names a quilt from what was dropped, without its ending', () => {
		expect(quiltName('arXiv-2104.01234v2.tar.gz')).toBe('arXiv-2104.01234v2');
		expect(quiltName('gadget-towers.tex')).toBe('gadget-towers');
		expect(quiltName('okafor-2022.PDF')).toBe('okafor-2022');
		expect(quiltName('gadget-towers')).toBe('gadget-towers');
		expect(quiltName('.tex')).toBe('.tex');
		expect(isPdf({ type: '', name: 'a.pdf' })).toBe(true);
		expect(isPdf({ type: 'application/x-tex', name: 'a.tex' })).toBe(false);
	});
});
