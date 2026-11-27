<script lang="ts">
	// Who you are on this computer, saved through the publisher into your own loom config and read by every quilt (`NameField`). A viewer with no publisher shows the name it was published with.
	import { store } from '$lib/manifest/client.svelte';
	import NameField from './NameField.svelte';
	import Row from './Row.svelte';
	import { frame } from '$lib/words/frame';

	const words = frame.profile;

	let { editable }: { editable: boolean } = $props();

	let error = $state('');
	const effective = $derived(store.manifest?.reviewer?.name ?? '');
</script>

<div class="card">
	<Row id="author" refused={error}>
		{#if editable}
			<NameField id="reviewer-name" bind:error />
		{:else}
			<span class="value">{effective || words.unset}</span>
		{/if}
	</Row>
</div>
{#if store.manifest?.reviewer?.source === 'git config user.name'}<p class="from" data-testid="profile-from">{words.fromGit}</p>{/if}

<style>
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
