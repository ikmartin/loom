// What the viewer says of Lean on this computer: each step by its code in the viewer's words, how a job ended, and never loom's own sentence as the line.
import { describe, expect, it } from 'vitest';
import { fenceLine, jobLines, offersCheck, offersInstall, standing, type LeanJob, type LeanState } from './said';

const job = (over: Partial<LeanJob>): LeanJob => ({ kind: 'install', state: 'running', step: '', said: '', found: {}, ...over });
const state = (over: Partial<LeanState>): LeanState => ({ on: true, project: 'lean', fence: null, job: null, ...over });

describe('a job', () => {
	it('says the step it is on by its code, in the viewer’s words', () => {
		expect(jobLines(job({ step: 'mathlib' }))).toEqual(['Installing Lean: fetching Mathlib, about 1.3 GB the first time…']);
		expect(jobLines(job({ kind: 'check', step: 'probe' }))).toEqual(['Checking the Lean: replaying it in Lean’s kernel…']);
		expect(jobLines(job({}))).toEqual(['Installing Lean: starting…']);
	});

	it('says how an install ended, with how long it took, and where one stopped', () => {
		expect(jobLines(job({ state: 'done', found: { steps: [{ step: 'toolchain', seconds: 40 }, { step: 'mathlib', seconds: 140 }] } }))).toEqual(['Lean is installed. That took 3 minutes.']);
		const stopped = job({ state: 'failed', step: 'mathlib', said: 'fetching Mathlib failed (exit 1):\nerror: could not resolve host' });
		expect(jobLines(stopped)).toEqual(['Installing Lean stopped while fetching Mathlib, about 1.3 GB the first time.']);
		expect(jobLines(stopped).join(' ')).not.toContain('exit 1');
	});

	it('says what a check recorded, and Lean’s errors and markers naming nothing where there are any', () => {
		const done = job({ kind: 'check', state: 'done', step: 'probe', found: { written: ['lem:a', 'lem:b'], unchanged: ['thm:c'], unknown: ['Formal.x: lem:gone'], errors: ['Formal/A.lean:3:1: unknown identifier'] } });
		expect(jobLines(done)).toEqual(['Checked. 2 results recorded anew, 1 result as before.', 'Lean reported 1 error.', 'One declaration is marked for a result the quilt does not have.']);
		expect(jobLines(job({ kind: 'check', state: 'done', found: { written: [], unchanged: [] } }))).toEqual(['Checked. No declaration states a result yet.']);
		expect(jobLines(job({ kind: 'check', state: 'failed', step: '', said: 'the fence is not up (nested)' }))).toEqual(['The check did not run, and recorded nothing.']);
	});
});

describe('the switch', () => {
	it('says the project once on and idle, and nothing while off or while a job runs', () => {
		expect(standing(state({}))).toBe('On. The Lean project is in lean/.');
		expect(standing(state({ project: null }))).toBe('On, but the quilt has no Lean project yet. Install again to make it.');
		expect(standing(state({ on: false }))).toBe('');
		expect(standing(state({ job: job({}) }))).toBe('');
	});

	it('says why loom cannot check Lean here by the fence’s code', () => {
		expect(fenceLine(state({ fence: 'nested' }))).toContain('runs inside a sandbox of its own');
		expect(fenceLine(state({ fence: 'something-new' }))).toBe('Loom cannot check Lean on this computer.');
		expect(fenceLine(state({ fence: 'absent', on: false }))).toBe('');
	});

	it('offers Install again after an install stopped or where there is no project, and Check again only where a check can run', () => {
		expect(offersInstall(state({ job: job({ state: 'failed' }) }))).toBe(true);
		expect(offersInstall(state({ project: null }))).toBe(true);
		expect(offersInstall(state({}))).toBe(false);
		expect(offersCheck(state({}))).toBe(true);
		expect(offersCheck(state({ fence: 'absent' }))).toBe(false);
		expect(offersCheck(state({ job: job({ kind: 'check' }) }))).toBe(false);
		expect(offersCheck(state({ on: false }))).toBe(false);
	});
});
