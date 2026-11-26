import { afterEach, describe, expect, it, vi } from 'vitest';

const sent: { endpoint: string; body: Record<string, unknown> }[] = [];
let answer: Record<string, unknown> = { ok: true, how: 'ran', said: '' };
vi.mock('$lib/write', () => ({
	write: async (endpoint: string, body: Record<string, unknown>) => {
		sent.push({ endpoint, body });
		return answer;
	}
}));

const { newNote } = await import('./newNote');
const { toast } = await import('$lib/review/toasts.svelte');

afterEach(() => {
	sent.length = 0;
});

describe('New note', () => {
	it('sends the link, the words and the name, and nothing else', async () => {
		await newNote({ link: 'quilt:a.md#quote=x', quote: 'x', title: 'A' });
		expect(sent).toEqual([{ endpoint: 'new-note', body: { link: 'quilt:a.md#quote=x', quote: 'x', title: 'A' } }]);
		expect(toast.said?.title).toBe('New note sent to your editor');
	});

	it('says where a Markdown note was written, and why a note was not made', async () => {
		answer = { ok: true, how: 'wrote', path: 'notes/2026-11-26-a.md' };
		await newNote({ link: 'quilt:a.md', title: 'A' });
		expect(toast.said?.title).toBe('New note: notes/2026-11-26-a.md');
		answer = { ok: false, error: { code: 'command-failed', message: 'ed stopped with status 1' } };
		await newNote({ link: 'quilt:a.md', title: 'A' });
		expect(toast.said).toMatchObject({ title: 'No note made', lines: ['ed stopped with status 1'] });
	});
});
