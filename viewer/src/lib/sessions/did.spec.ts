import { describe, expect, it } from 'vitest';
import type { Thread } from '$lib/manifest/types';
import { review } from '$lib/words/review';
import { didOf, stepOf } from './did';

const line = (time: string, command: string, extra: object = {}) => ({ time, command, ...extra }) as Thread['log'][number];

describe('what a session did', () => {
	const log = [
		line('t1', 'loom ai orient'),
		line('t3', 'loom compile drafting-ai/x.tex', { names: [{ path: '.loom/agents/copies/x.tex' }] }),
		line('t5', 'loom compile drafting-ai/x.tex', { names: [{ path: '.loom/agents/copies/x.tex' }] })
	];

	it('lists every command once, with how many times, when last, and what it names', () => {
		expect(didOf(log).ran).toEqual([
			{ command: 'loom ai orient', count: 1, last: 't1', names: [] },
			{ command: 'loom compile drafting-ai/x.tex', count: 2, last: 't5', names: [{ path: '.loom/agents/copies/x.tex' }] }
		]);
	});

	it('says each step in words, by the command loom logged, never with the command', () => {
		expect(stepOf('loom write state')).toBe('Wrote the research state');
		expect(stepOf('loom session say "found it"  (over MCP)')).toBe('Wrote in the transcript');
		expect(stepOf('loom library add paper.pdf')).toBe('Added to the library');
		expect(stepOf('loom formal')).toBe("Read the quilt's Lean");
		expect(stepOf('loom frobnicate x')).toBe(review.session.other);
		const commands = Object.keys(review.session.step).map((k) => `loom ${k}`);
		for (const words of Object.values(review.session.step)) {
			expect(words).not.toMatch(/--|`/);
			expect(commands.filter((c) => words.includes(c))).toEqual([]);
		}
	});
});
