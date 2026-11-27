// The write client against a stubbed publisher: a restarted publisher mints a new token, and a 403 re-probes `/_api` once for it.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { store } from '$lib/manifest/client.svelte';
import type { Manifest } from '$lib/manifest/types';
import { forgetCapabilities, write } from './write';

/** A stub publisher. `token` is what a probe answers now (set it to restart the publisher); `answer` decides a POST's status from the token it carries. Every request is logged as `GET <url>` or `POST <url> <token>`. */
function publisher(answer: (token: string, current: string) => number = (t, c) => (t === c ? 200 : 403)) {
	const state = { token: 'first', log: [] as string[] };
	vi.stubGlobal('fetch', async (url: string, init?: RequestInit) => {
		if (!init) {
			state.log.push(`GET ${url}`);
			return Response.json({ write_api: 1, capabilities: ['session-close'], token: state.token });
		}
		const carried = (init.headers as Record<string, string>)['X-Loom-Token'] ?? '';
		state.log.push(`POST ${url} ${carried}`);
		const status = answer(carried, state.token);
		if (status === 200) return Response.json({ ok: true, result: 'closed' });
		return Response.json({ ok: false, error: { code: status === 403 ? 'forbidden' : 'bad-request', message: `refused with ${status}` } }, { status });
	});
	return state;
}

beforeEach(() => forgetCapabilities());
afterEach(() => vi.unstubAllGlobals());

describe('a write carrying a stale token', () => {
	it('re-probes for the fresh token on a 403 and retries once', async () => {
		const p = publisher();
		expect(await write('session-close', { session: 's-1' })).toEqual({ ok: true, result: 'closed' });
		// the publisher restarts and mints a new token; the page still holds the old probe
		p.token = 'second';
		p.log.length = 0;
		expect(await write('session-close', { session: 's-1' })).toEqual({ ok: true, result: 'closed' });
		expect(p.log).toEqual(['POST /_api/session-close first', 'GET /_api', 'POST /_api/session-close second']);
		// the fresh probe is kept: the next write asks nothing first
		p.log.length = 0;
		await write('session-close', { session: 's-1' });
		expect(p.log).toEqual(['POST /_api/session-close second']);
	});

	it('gives up after one retry, and shows the refusal', async () => {
		const p = publisher(() => 403);
		expect(await write('session-close', { session: 's-1' })).toEqual({ ok: false, error: { code: 'forbidden', message: 'refused with 403' } });
		expect(p.log).toEqual(['GET /_api', 'POST /_api/session-close first', 'GET /_api', 'POST /_api/session-close first']);
	});

	it('does not retry any other refusal', async () => {
		const p = publisher(() => 400);
		expect(await write('session-close', { session: 's-1' })).toEqual({ ok: false, error: { code: 'bad-request', message: 'refused with 400' } });
		expect(p.log).toEqual(['GET /_api', 'POST /_api/session-close first']);
	});
});


it('carries the displayed reviewer through a request even when the view changes while awaiting discovery', async () => {
	store.manifest = { reviewer: { name: 'Bob', source: 'local' } } as Manifest;
	let sent: Record<string, unknown> = {};
	vi.stubGlobal('fetch', async (_url: string, init?: RequestInit) => {
		if (!init) {
			store.manifest = { reviewer: { name: 'Alice', source: 'local' } } as Manifest;
			return Response.json({ write_api: 1, capabilities: ['review-accept'], token: 'token' });
		}
		sent = JSON.parse(String(init.body));
		return Response.json({ ok: false, error: { code: 'reviewer-changed', message: 'Reload Review' } }, { status: 409 });
	});
	expect((await write('review-accept', { keys: ['k'] })).error?.code).toBe('reviewer-changed');
	expect(sent.reviewer).toBe('Bob');
	store.manifest = null;
});

it('marks the page updating from an answer naming the build that publishes it, by the server that answered', async () => {
	const { updating } = await import('$lib/manifest/updating.svelte');
	updating.listen();
	vi.stubGlobal('fetch', async (_url: string, init?: RequestInit) => {
		if (!init) return Response.json({ write_api: 1, capabilities: ['annotate'], token: 'token', pid: 4242 });
		return Response.json({ ok: true, result: 'a-1', publication: 6 });
	});
	expect((await write('annotate', { target: 'k', message: 'm' })).publication).toBe(6);
	expect(updating.awaited).toEqual({ server: 4242, n: 6 });
});

describe('a write refused for want of the person’s name', () => {
	/** A publisher that refuses `annotate` with `no-reviewer` until `named`; every POST counted. */
	function nameless() {
		const state = { named: false, posts: 0 };
		vi.stubGlobal('fetch', async (_url: string, init?: RequestInit) => {
			if (!init) return Response.json({ write_api: 1, capabilities: ['annotate'], token: 'token' });
			state.posts++;
			if (state.named) return Response.json({ ok: true, result: 'a-1' });
			return Response.json({ ok: false, error: { code: 'no-reviewer', message: 'no author name' } }, { status: 409 });
		});
		return state;
	}

	it('asks for the name over the page and, once it is saved, sends the write again', async () => {
		const { answer, mountAsk, naming } = await import('$lib/shell/name.svelte');
		const unmount = mountAsk();
		const p = nameless();
		const done = write('annotate', { target: 'k', message: 'm' });
		await vi.waitFor(() => expect(naming.open).toBe(true));
		p.named = true;
		answer(true);
		expect(await done).toEqual({ ok: true, result: 'a-1' });
		expect(p.posts).toBe(2);
		expect(naming.open).toBe(false);
		unmount();
	});

	it('asks the same way for a write of the library’s and Review’s client', async () => {
		const { server } = await import('$lib/library/api');
		const { answer, mountAsk, naming } = await import('$lib/shell/name.svelte');
		const unmount = mountAsk();
		const p = nameless();
		const done = server.call('annotate', { target: 'k' });
		await vi.waitFor(() => expect(naming.open).toBe(true));
		p.named = true;
		answer(true);
		expect((await done).ok).toBe(true);
		expect(p.posts).toBe(2);
		unmount();
	});

	it('answers with the refusal when the name is left unsaved, or nothing on the page can ask', async () => {
		const { answer, mountAsk, naming } = await import('$lib/shell/name.svelte');
		const unmount = mountAsk();
		const p = nameless();
		const done = write('annotate', { target: 'k', message: 'm' });
		await vi.waitFor(() => expect(naming.open).toBe(true));
		answer(false);
		expect((await done).error?.code).toBe('no-reviewer');
		expect(p.posts).toBe(1);
		unmount();
		expect((await write('annotate', { target: 'k', message: 'm' })).error?.code).toBe('no-reviewer');
		expect(naming.open).toBe(false);
		expect(p.posts).toBe(2);
	});
});
