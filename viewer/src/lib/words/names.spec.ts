// The viewer's words hold no command and none of the names `docs/specs/names.md` sets aside: every line of every file here, its comments dropped, is read.
import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const DIR = new URL('./', import.meta.url);

/** Each file's lines that are words, with comment lines and trailing comments dropped. */
const lines = readdirSync(DIR)
	.filter((f) => f.endsWith('.ts') && !f.endsWith('.spec.ts'))
	.flatMap((f) =>
		readFileSync(new URL(f, DIR), 'utf8')
			.split('\n')
			.map((text, i) => ({ at: `${f}:${i + 1}`, text: text.replace(/\s\/\/ .*$/, '') }))
			.filter(({ text }) => !/^\s*(\/\/|\/\*\*|\*)/.test(text))
	);

/** What a person would type, and the names set aside. */
const NEVER: [string, RegExp][] = [
	['a loom command', /\bloom (serve|lint|init|doctor|adopt|draft|session|write|link|open|here|upgrade|changes|config|ai|mcp|source|suggest|annotate)\b/],
	['a flag', /\s--[a-z][a-z-]+/],
	['a path inside .loom', /\.loom\//],
	['an endpoint', /\/_api\//],
	['the corpus', /\bcorpus\b/i],
	['the manifest', /\bmanifest\b/i],
	['the publisher', /\bpublisher\b/i],
	['Proposed Changes', /Proposed Changes/],
	['pending change', /\bpending changes?\b/i]
];

describe("the viewer's words", () => {
	it('are read', () => expect(lines.length).toBeGreaterThan(1000));
	for (const [what, pattern] of NEVER)
		it(`hold no ${what}`, () => {
			expect(lines.filter(({ text }) => pattern.test(text)).map(({ at, text }) => `${at}: ${text.trim()}`)).toEqual([]);
		});
});
