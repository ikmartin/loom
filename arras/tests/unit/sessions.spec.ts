// The sessions as Review › History lists them, and when each was touched.
import { describe, expect, it } from 'vitest';
import { grouped, sessionView, titleOf } from '$lib/sessions/sessions.svelte';
import { touched, when } from '$lib/sessions/when';
import type { Manifest, SessionRow } from '$lib/manifest/types';

function session(id: string, state: string, title = id): SessionRow {
	return { id, title, state, created: '2026-09-01T10:00:00Z', opened: '2026-09-01T10:00:00Z', rounds: 1, active: false };
}

const m = {
	sessions: [session('s-open', 'open'), session('s-other', 'open'), session('s-shut', 'closed')],
	annotations: {}
} as unknown as Manifest;

describe('the list', () => {
	it('separates open from closed', () => {
		const g = grouped(m);
		expect(g.open.map((s) => s.id)).toEqual(['s-open', 's-other']);
		expect(g.closed.map((s) => s.id)).toEqual(['s-shut']);
	});

	it('names a session by a pending rename until the manifest carries it', () => {
		sessionView.renamed['s-other'] = 'Colloquium';
		expect(titleOf(grouped(m).open[1])).toBe('Colloquium');
		delete sessionView.renamed['s-other'];
		expect(titleOf(grouped(m).open[1])).toBe('s-other');
	});
});

describe('when a session was touched', () => {
	const now = new Date('2026-09-21T12:00:00');
	it('says it the way a person would', () => {
		expect(when('2026-09-21T09:00:00', now)).toBe('today');
		expect(when('2026-09-20T09:00:00', now)).toBe('yesterday');
		expect(when('2026-09-17T09:00:00', now)).toBe('Thursday');
		expect(when('2026-09-14T09:00:00', now)).toBe('last week');
		expect(when('', now)).toBe('');
	});

	it('says of a closed session that it closed then', () => {
		expect(touched('2026-09-21T09:00:00', 'open', now)).toBe('today');
		expect(touched('2026-09-21T09:00:00', 'closed', now)).toBe('closed today');
	});
});
