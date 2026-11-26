import { describe, expect, it } from 'vitest';
import { mainDraft } from './documents';

const doc = (path: string, extra: Record<string, unknown> = {}) => ({ path, default: false, ...extra }) as never;

describe('mainDraft', () => {
	it('is the document the manifest marks default, whatever its path', () => {
		expect(mainDraft({ masters: [doc('drafting/main.tex'), doc('main-atomic.tex', { default: true })] })).toBe('main-atomic.tex');
	});
	it('is null where the manifest marks none, or marks only an agent copy', () => {
		expect(mainDraft({ masters: [doc('drafting/main.tex'), doc('drafting/talk.tex')] })).toBeNull();
		expect(mainDraft({ masters: [doc('.loom/agents/copies/a.tex', { default: true, copy_of: 'drafting/main.tex' })] })).toBeNull();
		expect(mainDraft(null)).toBeNull();
	});
});
