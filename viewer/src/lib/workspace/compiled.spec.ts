import { describe, expect, it } from 'vitest';
import type { Manifest } from '$lib/manifest/types';
import { compileError, compileWord, compiles, pdfLine, pdfWord, type Compile } from '$lib/manifest/compiles.svelte';
import { compiledUrl } from '$lib/paths';
import { itemFromPath, pathFor } from './item';
import { pdfFileName, pdfName } from './names';

// A document's compiled PDF (plan 0.29.1): an item of its own, addressed by its document's name, and how its compile stands in a word.
const m = { masters: [{ path: 'paper/main.tex' }, { path: 'notes/main.tex' }, { path: 'talk.tex' }] } as unknown as Manifest;

describe("a document's compiled PDF", () => {
	it('is addressed at /pdf/ by its document\'s name, and read back as that document', () => {
		const item = { kind: 'pdf' as const, id: 'paper/main.tex' };
		expect(pathFor(m, item)).toBe('/pdf/paper/main');
		expect(itemFromPath(m, '/pdf/paper/main')).toEqual(item);
		expect(itemFromPath(m, '/pdf/paper/main#page=3')).toEqual({ ...item, anchor: 'page=3' });
	});

	it("is named by its document and never by a file name an author's own PDF may have: by path only where two documents share a file name", () => {
		expect(pdfName(m.masters, 'talk.tex')).toBe('talk.tex · PDF');
		expect(pdfName(m.masters, 'paper/main.tex')).toBe('paper/main.tex · PDF');
	});

	it("is saved under its document's label, never as a hidden file or with a slash in its name", () => {
		expect(pdfFileName(m.masters, 'talk.tex')).toBe('talk.pdf');
		expect(pdfFileName(m.masters, 'paper/main.tex')).toBe('paper-main.pdf');
		const agents = [{ path: 'drafting/main.tex' }, { path: '.hidden/main.tex' }, { path: '.hidden/aidoc.tex' }];
		expect(pdfFileName(agents, '.hidden/aidoc.tex')).toBe('aidoc.pdf');
		expect(pdfFileName(agents, '.hidden/main.tex')).toBe('hidden-main.pdf');
	});

	it('is fetched at the address its manifest entry gives, by the compile it is, and has none before a compile made one', () => {
		expect(compiledUrl({ pdf: 'somewhere/main.pdf', compiled: '2026-11-17T10:00:00Z' })).toBe('/build/somewhere/main.pdf?v=2026-11-17T10%3A00%3A00Z');
		expect(compiledUrl({})).toBe('');
	});
});

describe('how a compile stands', () => {
	const last = (result: 'ok' | 'errors' | 'failed') => ({ result, ended: 'now', error: result === 'ok' ? null : '! Undefined control sequence.', at: result === 'ok' ? null : 'l.12 \\hlind' });
	const c = (state: Compile['state'], result?: 'ok' | 'errors' | 'failed'): Compile => ({ state, again: false, last: result ? last(result) : null });

	it('says nothing of a compile that went well, and says what is under way or what went wrong', () => {
		expect(compileWord(undefined)).toBe('');
		expect(compileWord(c('idle', 'ok'))).toBe('');
		expect(compileWord(c('compiling', 'failed'))).toBe('compiling');
		expect(compileWord(c('queued'))).toBe('waiting to compile');
		expect(compileWord(c('idle', 'failed'))).toBe('did not compile');
		expect(compileWord(c('idle', 'errors'))).toBe('compiled with errors');
		expect(compileError(c('idle', 'failed'))).toBe('a command it uses is not defined (line 12)');
		expect(compileError(c('idle', 'ok'))).toBe('');
	});

	it("says beside a document's view PDF that nothing is compiled yet where there is no PDF and nothing under way", () => {
		expect(pdfWord(false, undefined)).toBe('not compiled yet');
		expect(pdfWord(true, undefined)).toBe('');
		expect(pdfWord(false, c('compiling'))).toBe('compiling');
		expect(pdfWord(true, c('idle', 'failed'))).toBe('did not compile');
		expect(pdfWord(false, c('idle', 'failed'))).toBe('did not compile');
	});

	it('greys view PDF only where there is no PDF to open, saying why, and opens the last PDF of a compile that failed or had errors', () => {
		expect(pdfLine(true, undefined)).toEqual({ word: '', about: undefined });
		expect(pdfLine(false, undefined)).toEqual({ word: 'not compiled yet', off: 'There is no compiled PDF to open yet' });
		expect(pdfLine(false, c('compiling'))).toEqual({ word: 'compiling', off: 'There is no compiled PDF to open yet' });
		expect(pdfLine(false, c('queued'))).toEqual({ word: 'waiting to compile', off: 'There is no compiled PDF to open yet' });
		expect(pdfLine(false, c('idle', 'failed'))).toEqual({ word: 'did not compile', off: 'a command it uses is not defined (line 12)' });
		expect(pdfLine(true, c('idle', 'failed'))).toEqual({ word: 'did not compile', about: 'a command it uses is not defined (line 12)' });
		expect(pdfLine(true, c('idle', 'errors'))).toEqual({ word: 'compiled with errors', about: 'a command it uses is not defined (line 12)' });
		expect(pdfLine(true, c('compiling', 'ok'))).toEqual({ word: 'compiling', about: undefined });
	});

	it('takes what the stream says, and keeps what it had when the stream says nothing it can read', () => {
		compiles.take(JSON.stringify({ 'paper/main.tex': c('compiling') }));
		expect(compiles.all['paper/main.tex'].state).toBe('compiling');
		compiles.take('not json');
		compiles.take('[1, 2]');
		expect(compiles.all['paper/main.tex'].state).toBe('compiling');
	});
});
