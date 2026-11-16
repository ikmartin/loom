import { expect, it } from 'vitest';
import { store } from './client.svelte';
import type { AdoptionReview, Manifest } from './types';

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
