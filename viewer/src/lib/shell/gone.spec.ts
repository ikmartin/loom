import { afterEach, describe, expect, it, vi } from 'vitest';
import { judgeStopped, stopped } from './gone.svelte';

afterEach(() => {
	vi.useRealTimers();
	vi.unstubAllGlobals();
	stopped.back();
});

describe("a quilt's page whose server stopped", () => {
	it('is said only once nothing answers a few seconds after the stream dropped, and no longer once something does', async () => {
		vi.useFakeTimers();
		let up = false;
		vi.stubGlobal('fetch', vi.fn(async () => (up ? new Response('{}') : Promise.reject(new TypeError('Failed to fetch')))));
		stopped.dropped();
		expect(stopped.on).toBe(false);
		await vi.advanceTimersByTimeAsync(3100);
		expect(stopped.on).toBe(true);
		up = true;
		await vi.advanceTimersByTimeAsync(3100);
		expect(stopped.on).toBe(false);
	});

	it('is not said when the server answers after the drop, as one restarted after an update does', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('fetch', vi.fn(async () => new Response('{}')));
		stopped.dropped();
		await vi.advanceTimersByTimeAsync(3100);
		expect(stopped.on).toBe(false);
	});

	it('keeps the home page’s address the server last gave', () => {
		judgeStopped({ write_api: 1, capabilities: [], home: 'http://127.0.0.1:8790/' });
		judgeStopped({ write_api: 1, capabilities: [] });
		expect(stopped.home).toBe('http://127.0.0.1:8790/');
	});

	it('is told a page a quilt’s server answered for, never a published one or the home page itself, and keeps it', () => {
		stopped.served = false;
		judgeStopped(null);
		expect(stopped.served).toBe(false);
		judgeStopped({ write_api: 0, capabilities: [], home: true });
		expect(stopped.served).toBe(false);
		judgeStopped({ write_api: 1, capabilities: [] });
		expect(stopped.served).toBe(true);
		judgeStopped(null);
		expect(stopped.served).toBe(true);
	});
});
