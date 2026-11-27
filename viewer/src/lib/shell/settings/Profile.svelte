<script lang="ts">
	// Who you are on this computer, saved through the publisher into your own loom config and read by every quilt; the manifest is refreshed after. A viewer with no publisher shows the name it was published with.
	import { refusalOf } from '$lib/library/said';
	import { store } from '$lib/manifest/client.svelte';
	import { landed } from '$lib/manifest/updating.svelte';
	import { write } from '$lib/write';
	import Row from './Row.svelte';
	import { frame } from '$lib/words/frame';

	const words = frame.profile;

	let { editable }: { editable: boolean } = $props();

	let name = $state('');
	let busy = $state(false);
	let error = $state('');
	const effective = $derived(store.manifest?.reviewer?.name ?? '');
	$effect(() => {
		name = effective;
	});
	async function save(): Promise<void> {
		busy = true;
		error = '';
		const answer = await write('reviewer-settings', { name });
		if (answer.ok) await landed();
		else error = refusalOf(answer.error, 'Could not save your name');
		busy = false;
	}
</script>

<div class="card">
	<Row id="author" refused={error}>
		{#if editable}
			<form
				onsubmit={(event) => {
					event.preventDefault();
					void save();
				}}
			>
				<input id="reviewer-name" class="text" bind:value={name} autocomplete="name" required aria-label={words.field} />
				<button class="btn" disabled={busy || !name.trim() || name.trim() === effective} type="submit">{busy ? words.saving : words.save}</button>
			</form>
		{:else}
			<span class="value">{effective || words.unset}</span>
		{/if}
	</Row>
</div>
{#if store.manifest?.reviewer?.source === 'git config user.name'}<p class="from" data-testid="profile-from">{words.fromGit}</p>{/if}

<style>
	form {
		display: flex;
		gap: 8px;
	}
	.value {
		font-size: 13px;
		color: var(--ink-soft);
	}
	.from {
		font-size: 12px;
		color: var(--ink-faint);
		margin: 4px 2px;
		overflow-wrap: anywhere;
	}
</style>
