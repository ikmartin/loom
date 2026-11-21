import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MESSAGE_FOR, message } from './message.svelte';

describe("the column's message", () => {
	beforeEach(() => vi.useFakeTimers());
	afterEach(() => {
		message.clear();
		vi.useRealTimers();
	});

	it('goes by itself, but not while the pointer or the keyboard is on it', () => {
		message.post('Added a work.');
		message.hold();
		vi.advanceTimersByTime(MESSAGE_FOR * 2);
		expect(message.said?.text).toBe('Added a work.');
		message.release();
		vi.advanceTimersByTime(MESSAGE_FOR);
		expect(message.said).toBeNull();
	});

	it('stays while its undo is answered, and says when the undo failed', async () => {
		let answer: (v: { ok: boolean; error?: { message: string } }) => void = () => {};
		message.post('Deleted a work.', () => new Promise((r) => (answer = r)));
		const done = message.undo((why) => `failed: ${why}`);
		vi.advanceTimersByTime(MESSAGE_FOR * 2);
		expect(message.said?.text).toBe('Deleted a work.');
		expect(message.undoing).toBe(true);
		answer({ ok: false, error: { message: 'something stands in its place' } });
		await done;
		expect(message.said?.text).toBe('failed: something stands in its place');
	});

	it('goes when its undo succeeds, and a new message replaces the last', async () => {
		message.post('First.', () => ({ ok: true }));
		message.post('Second.');
		expect(message.said?.undo).toBeUndefined();
		message.post('Third.', () => ({ ok: true }));
		await message.undo((why) => why);
		expect(message.said).toBeNull();
	});

	it('goes by itself after a message taken down from under the pointer, which is told of no leaving', async () => {
		message.post('Added a work.', () => ({ ok: true }));
		message.hold();
		message.clear();
		message.post('Deleted a work.', () => ({ ok: true }));
		message.hold();
		await message.undo((why) => why);
		message.post('Marked on page 7, to digest.');
		vi.advanceTimersByTime(MESSAGE_FOR);
		expect(message.said).toBeNull();
	});

	it('keeps the pointer\'s hold on a box a new message replaces', () => {
		message.post('First.');
		message.hold();
		message.post('Second.');
		vi.advanceTimersByTime(MESSAGE_FOR * 2);
		expect(message.said?.text).toBe('Second.');
		message.release();
		vi.advanceTimersByTime(MESSAGE_FOR);
		expect(message.said).toBeNull();
	});
});
