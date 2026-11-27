// Every refusal the library's endpoints can answer has a sentence of the viewer's, and loom's own message is never drawn. The codes are read from both places that can add one: the write API's table (`docs/specs/write-api.md`, the rows of `/_api/library-*`) and loom's own raise sites (`loom/src/loom/library/`, `render/endpoints/library.py`), so a code added on either side fails here until it has its sentence.
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { frame } from '$lib/words/frame';
import { refusalOf, said } from './said';

const ROOT = new URL('../../../../', import.meta.url);
const read = (path: string) => readFileSync(new URL(path, ROOT), 'utf8');

/** The codes the write API's table names for the library's endpoints: each backticked before an HTTP status. */
function specCodes(): Set<string> {
	const rows = read('docs/specs/write-api.md')
		.split('\n')
		.filter((l) => l.startsWith('| `POST` | `/_api/library-'));
	const out = new Set<string>();
	for (const row of rows) for (const run of row.matchAll(/((?:`[a-z]+(?:-[a-z]+)*`(?:,\s*|\s+or\s+|\s+and\s+)?)+)\s*\(\d{3}/g)) for (const c of run[1].matchAll(/`([a-z]+(?:-[a-z]+)*)`/g)) out.add(c[1]);
	return out;
}

/** The codes loom raises in the library's code: the first argument of each refusal, every quoted code in it (a conditional names two). */
function loomCodes(): Set<string> {
	const files = [...readdirSync(new URL('loom/src/loom/library/', ROOT)).filter((f) => f.endsWith('.py')).map((f) => `loom/src/loom/library/${f}`), 'loom/src/loom/render/endpoints/library.py'];
	const out = new Set<string>();
	for (const f of files) for (const m of read(f).matchAll(/(?:ApiError|[A-Z]\w*Refused)\(\s*([^,]+),/g)) for (const c of m[1].matchAll(/"([a-z]+(?:-[a-z]+)+|[a-z]+)"/g)) out.add(c[1]);
	return out;
}

/** Refusals that are the viewer's own fault, a request it built wrongly, said in the plain sentence on purpose. */
const PLAIN = new Set(['bad-field', 'missing-field', 'bad-request', 'refused']);

describe('a refusal said in place', () => {
	it("is the frame's sentence for its code, else the place's own words, never loom's message", () => {
		expect(refusalOf({ code: 'no-such-change', status: 404 })).toBe(frame.refused['no-such-change']);
		expect(refusalOf({ code: 'refused', status: 400 }, 'Not written.')).toBe('Not written.');
		expect(refusalOf({ code: 'refused', status: 400 })).toBe(frame.errors.failed);
		expect(refusalOf({ code: 'unreachable' })).toBe(frame.errors.unreachable);
		expect(refusalOf(undefined, 'Not written.')).toBe('Not written.');
	});
});

describe('a refusal of the library', () => {
	const codes = [...new Set([...specCodes(), ...loomCodes()])].sort();

	it('is read from both the spec and loom', () => {
		// a parse that found nothing would pass everything below
		expect(specCodes().size).toBeGreaterThan(15);
		expect(loomCodes().size).toBeGreaterThan(15);
		expect(codes).toContain('offline');
		expect(codes).toContain('changed');
	});

	for (const code of codes)
		it(`${code} has a sentence of the viewer's`, () => {
			if (!PLAIN.has(code)) expect(frame.refused[code], `no sentence for ${code} in words/frame.ts`).toBeTruthy();
			const text = said({ code, message: 'LOOMS-OWN sm-0001-ref library.online', status: 409 });
			expect(text).not.toContain('LOOMS-OWN');
			expect(text.trim()).not.toBe('');
		});

	it("says nothing internal for a code it does not know, and tells the transport's failure from a service loom could not reach", () => {
		expect(said({ code: 'never-heard-of-it', message: 'sm-0001-ref', status: 409 })).toBe(frame.errors.failed);
		expect(said({ code: 'unreachable', message: 'Failed to fetch' })).toBe(frame.errors.unreachable);
		expect(said({ code: 'unreachable', message: 'arXiv timed out', status: 409 })).toBe(frame.refused.unreachable);
	});
});
