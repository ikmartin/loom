import { expect, it, vi } from 'vitest';
import { store } from './client.svelte';
import type { AdoptionReview, Manifest, PendingChange } from './types';

const choices = (revision: number, keys: string[]) => ({ revision, keys }) as unknown as AdoptionReview['choices'];

it('replaces the manifest whole when an adoption is acknowledged, never writing into the one held', () => {
	const other = { kind: 'pull' };
	const held = { contributions: [{ kind: 'adopt', copy: 'c', fingerprint: 'f', choices: choices(1, []) }, other] } as unknown as Manifest;
	store.manifest = held;

	store.setAdoption('c', 'f', choices(2, ['k']));
	const now = store.manifest!;
	expect(now).not.toBe(held);
	expect((held.contributions?.[0] as AdoptionReview).choices.revision).toBe(1);
	expect((now.contributions?.[0] as AdoptionReview).choices.keys).toEqual(['k']);
	expect(now.contributions?.[1]).toBe(other);

	// a late acknowledgement of an older revision changes nothing
	store.setAdoption('c', 'f', choices(1, []));
	expect(store.manifest).toBe(now);
	store.manifest = null;
});

it('holds rows made pending again in every manifest that does not list them, until they are let go, never writing into the one held', async () => {
	const row = { id: 'e-1', kind: 'suggested', old: 'a', new: 'b', state: 'ready' } as unknown as PendingChange;
	const held = { changes: [] } as unknown as Manifest;
	store.manifest = held;
	let landed = () => {};
	store.hold([row], new Promise<void>((r) => (landed = r)));
	expect(held.changes).toEqual([]);
	expect(store.manifest?.changes).toEqual([row]);
	landed();
	await new Promise((r) => setTimeout(r));
	expect(store.manifest?.changes).toEqual([]);
	store.manifest = null;
});

it('keeps a held row through a manifest that predates the act it undoes and the publication of that act, showing it once where a manifest lists it', async () => {
	const row = { id: 'e-1', kind: 'suggested', old: 'a', new: 'b', state: 'ready' } as unknown as PendingChange;
	const serving = (changes: PendingChange[]) => vi.stubGlobal('fetch', async () => new Response(JSON.stringify({ changes })));
	store.url = '/manifest.json';
	try {
		// the manifest shown when the undo is answered is the one from before the Keep's publication, and lists the row
		serving([row]);
		await store.refresh();
		let landed = () => {};
		store.hold([row], new Promise<void>((r) => (landed = r)));
		expect(store.manifest?.changes?.map((c) => c.id)).toEqual(['e-1']);
		// the Keep's publication lists it no more; the undo's has not landed
		serving([]);
		await store.refresh();
		expect(store.manifest?.changes).toEqual([row]);
		// the undo's publication lists it, once
		const again = { ...row };
		serving([again]);
		await store.refresh();
		expect(store.manifest?.changes).toEqual([again]);
		landed();
		await new Promise((r) => setTimeout(r));
		expect(store.manifest?.changes).toEqual([again]);
	} finally {
		vi.unstubAllGlobals();
		store.url = '';
		store.manifest = null;
	}
});
