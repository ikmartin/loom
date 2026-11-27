<script lang="ts">
	// The person's name and its Save: saved through the publisher into their own loom config (`reviewer-settings`), read by every quilt, and the manifest awaited so what follows reads it. Settings › Profile's field, and the one in the box a write refused for want of the name opens (`NameAsk`).
	import { refusalOf } from '$lib/library/said';
	import { store } from '$lib/manifest/client.svelte';
	import { landed } from '$lib/manifest/updating.svelte';
	import { write } from '$lib/write';
	import { frame } from '$lib/words/frame';

	const words = frame.profile;

	let { id, error = $bindable(''), onsaved }: { id: string; error?: string; onsaved?: () => void } = $props();

	let name = $state('');
	let busy = $state(false);
	const effective = $derived(store.manifest?.reviewer?.name ?? '');
	$effect(() => {
		name = effective;
	});
	async function save(): Promise<void> {
		busy = true;
		error = '';
		const answer = await write('reviewer-settings', { name });
		if (answer.ok) {
			await landed();
			onsaved?.();
		} else error = refusalOf(answer.error, words.refused);
		busy = false;
	}
</script>

<form
	onsubmit={(event) => {
		event.preventDefault();
		void save();
	}}
>
	<input {id} class="text" bind:value={name} autocomplete="name" required aria-label={words.field} data-testid="name-field" />
	<button class="btn" class:primary={!!onsaved} disabled={busy || !name.trim() || name.trim() === effective} type="submit" data-testid="name-save">{busy ? words.saving : words.save}</button>
</form>

<style>
	form {
		display: flex;
		gap: 8px;
	}
	input {
		font: inherit;
		font-size: 13px;
		padding: 6px 10px;
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--sheet);
		color: var(--ink);
		width: 15rem;
		max-width: 100%;
		box-sizing: border-box;
	}
</style>
