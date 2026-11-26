import { describe, expect, it } from 'vitest';
import { homePage, judgeHome, repairOf, rowsOf, shortPath } from './listing.svelte';
import { reportOf } from './report';
import type { Job, Listing, QuiltRow } from './api';

const row = (over: Partial<QuiltRow>): QuiltRow => ({ quilt: 'k', name: 'Q', folder: '/Users/m/Quilts/q', port: 8800, open: true, state: 'running', ...over });
const listing = (quilts: QuiltRow[], jobs: Job[] = []): Listing => ({ quilts, jobs, name: { name: '', source: '' }, tex: 'mine', home_folder: '/Users/m' });

describe("loom's home page", () => {
	it('is drawn when the probe says home, and never for a quilt whose server names the home', () => {
		judgeHome({ write_api: 0, capabilities: [], home: true });
		expect(homePage.is).toBe(true);
		judgeHome({ write_api: 1, capabilities: [], home: 'http://127.0.0.1:8790/' });
		expect(homePage.is).toBe(false);
		judgeHome(null);
		expect(homePage.is).toBe(false);
	});

	it('lists a quilt being made by its name until the list holds it, and the quilts after', () => {
		const making: Job = { job: 'j', kind: 'create', state: 'running', step: 'importing', name: 'Gadget', folder: '/Users/m/Quilts/Gadget' };
		expect(rowsOf(listing([row({})], [making])).map((r) => ('making' in r ? 'making' : 'quilt'))).toEqual(['making', 'quilt']);
		// once on the list, the quilt's own row stands for it
		expect(rowsOf(listing([row({ folder: '/Users/m/Quilts/Gadget' })], [making]))).toHaveLength(1);
		// a create that ended, or Repair TeX, is no row
		expect(rowsOf(listing([], [{ ...making, state: 'failed' }, { job: 'r', kind: 'repair', state: 'running', step: '' }]))).toEqual([]);
	});

	it("writes a path under the person's home folder with ~", () => {
		expect(shortPath('/Users/m/Quilts/q', '/Users/m')).toBe('~/Quilts/q');
		expect(shortPath('/Users/m', '/Users/m/')).toBe('~');
		expect(shortPath('/Users/mx/q', '/Users/m')).toBe('/Users/mx/q');
		expect(shortPath('/Volumes/x', undefined)).toBe('/Volumes/x');
	});

	it('follows the newest Repair TeX', () => {
		const r: Job = { job: 'r', kind: 'repair', state: 'running', step: 'Fetching' };
		expect(repairOf(listing([], [r, { ...r, job: 'old', state: 'done' }]))?.job).toBe('r');
		expect(repairOf(null)).toBeNull();
	});

	it('copies a report that names no command: doctor’s remedies are left out', () => {
		const said = reportOf({
			doctor: { loom: '0.1.0', python: '3.13.1', items: [{ name: 'latexmk', status: 'missing', detail: 'not found', remedy: 'loom doctor --repair' }] },
			log: 'Error: config.toml, line 4'
		});
		expect(said).toContain('latexmk: missing (not found)');
		expect(said).toContain('config.toml, line 4');
		expect(said).not.toContain('loom doctor');
	});
});
