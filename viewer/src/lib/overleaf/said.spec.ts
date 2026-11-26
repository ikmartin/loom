import { describe, expect, it } from 'vitest';
import type { OverleafState } from '$lib/manifest/types';
import { answered, mirrors, problemSaid, standing } from './said';

const base = { paired: true as const, folder: 'paper', main: 'paper/main.tex', link: 'https://www.overleaf.com/project/5f1e0c2a9b3d4e6f7a8b9c0d', waiting: false, last: null, ask_me: false, problem: null };
const now = new Date('2026-11-26T15:00:00Z');

describe('the Overleaf mirror in words', () => {
	it('knows the mirrored folder by its own name, not a neighbour that shares its start', () => {
		expect(mirrors(base, 'paper/main.tex')).toBe(true);
		expect(mirrors(base, 'paper/sections/intro.tex')).toBe(true);
		expect(mirrors(base, 'papers/main.tex')).toBe(false);
		expect(mirrors(base, 'paper')).toBe(false);
		expect(mirrors({ paired: false }, 'paper/main.tex')).toBe(false);
		expect(mirrors(undefined, 'paper/main.tex')).toBe(false);
	});

	it('says an update with no names, names, places, own changes and what it wrote over', () => {
		expect(answered({ state: 'up-to-date' })).toBe('Up to date with Overleaf · checked just now.');
		const said = answered({ state: 'updated', files: 2, by: ['Cleo', 'Dan'], own: 1, places: [{ file: 'paper/main.tex', place: 'preamble', by: ['Cleo'] }, { file: 'paper/refs.bib', place: 'not-a-document', by: [] }], here: ['k1'], overwritten: ['paper/main.tex'] });
		expect(said).toBe(
			'Updated from Overleaf just now: 2 files changed, by Cleo and Dan. 1 change only you made in Overleaf is not listed in Review. Outside the results: the preamble of main.tex (Cleo); refs.bib. 1 result you changed here was written over; the version kept before the update holds your text. Written over, as they held changes made here: main.tex. The version kept before the update holds them.'
		);
		expect(answered({ state: 'updated', files: 1, by: [], own: 0, places: [], here: [], overwritten: [] })).toBe('Updated from Overleaf just now: 1 file changed.');
	});

	it('says the last update by its time, none before the first, and what reaching Overleaf could not do', () => {
		expect(standing(base, now)).toBe('Not updated since it was paired.');
		const last = { when: '2026-11-26T14:59:30Z', files: 3, by: ['Cleo'], own: 0, places: [], here: [] };
		expect(standing({ ...base, last }, now)).toBe('Updated from Overleaf just now: 3 files changed, by Cleo.');
		expect(standing({ ...base, last: { ...last, when: '2026-11-25T09:00:00Z' } }, now)).toMatch(/^Updated from Overleaf on .+ at .+: 3 files changed, by Cleo\.$/);
		expect(standing({ ...base, problem: 'offline' } as OverleafState & { paired: true }, now)).toBe('Not updated since it was paired. Could not reach Overleaf. Your copy is as of the last update.');
	});

	it("never says loom's own sentence: a code it does not know is said plainly", () => {
		expect(problemSaid('token-refused')).toMatch(/^Overleaf did not accept the saved token/);
		expect(problemSaid('failed')).toBe('Loom could not reach the project just now. Try again.');
		expect(problemSaid(null)).toBe('');
	});
});
