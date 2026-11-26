// The page's mark that it is updating, against a stubbed manifest store: set by a write's answer, cleared once the publication it names is fetched, or its build failed, or another server first publishes.
import { beforeEach, describe, expect, it, vi } from 'vitest';

const refreshed: number[] = [];
vi.mock('./client.svelte', () => ({ store: { refresh: async () => void refreshed.push(refreshed.length) } }));

type Module = typeof import('./updating.svelte');
let m: Module;

beforeEach(async () => {
	refreshed.length = 0;
	vi.resetModules();
	m = await import('./updating.svelte');
	m.updating.listen();
});

const built = (published: number, failed = 0, why: string | null = null, server = 7) => ({ server, published, failed, why });

describe('the updating mark', () => {
	it('stands from the answer until the manifest has been fetched after the publication it names', async () => {
		await m.updating.heard(built(3));
		m.updating.expect(7, 4);
		expect(m.updating.on).toBe(true);
		let done = false;
		void m.landed().then(() => (done = true));
		await m.updating.heard(built(4));
		expect(m.updating.on).toBe(false);
		await Promise.resolve();
		expect(done).toBe(true);
		expect(refreshed.length).toBeGreaterThanOrEqual(2);
	});

	it('clears at once when the publication was heard and fetched before the answer came', async () => {
		await m.updating.heard(built(5));
		m.updating.expect(7, 5);
		expect(m.updating.on).toBe(false);
	});

	it('says a build that failed after the write was recorded, and stops waiting', async () => {
		await m.updating.heard(built(2));
		m.updating.expect(7, 3);
		await m.updating.heard(built(2, 3, 'OSError: the disk is full'));
		expect(m.updating.on).toBe(false);
		expect(m.updating.failure).toBe('OSError: the disk is full');
		m.updating.dismiss();
		expect(m.updating.failure).toBe(null);
	});

	it('waits for the later of two writes, and a failure of the first is no failure when the second published', async () => {
		await m.updating.heard(built(1));
		m.updating.expect(7, 2);
		m.updating.expect(7, 3);
		await m.updating.heard(built(2));
		expect(m.updating.on).toBe(true);
		await m.updating.heard(built(3, 2, 'why'));
		expect(m.updating.on).toBe(false);
		expect(m.updating.failure).toBe(null);
	});

	it('waits on the first publication of a server that came back as another', async () => {
		await m.updating.heard(built(9));
		m.updating.expect(7, 10);
		await m.updating.heard(built(0, 0, null, 8));
		expect(m.updating.on).toBe(true);
		await m.updating.heard(built(1, 0, null, 8));
		expect(m.updating.on).toBe(false);
	});

	it('lets whoever waits go while the stream is down, the mark standing', async () => {
		await m.updating.heard(built(1));
		m.updating.expect(7, 2);
		m.updating.down();
		await m.landed();
		expect(m.updating.on).toBe(true);
		m.updating.up();
		await m.updating.heard(built(2));
		expect(m.updating.on).toBe(false);
	});

	it('sets no mark where no stream could clear it, nor for an answer naming no build', async () => {
		m.updating.expect(7, undefined);
		expect(m.updating.on).toBe(false);
		vi.resetModules();
		const fresh: Module = await import('./updating.svelte');
		fresh.updating.expect(7, 1);
		expect(fresh.updating.on).toBe(false);
	});
});
