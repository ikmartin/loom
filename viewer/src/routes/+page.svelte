<script lang="ts">
	// `/` is reading where it was left: this visit's workspace, else the address remembered from an earlier visit, else the default document, else the newest landmark (`readingAddress`). A quilt with nothing to read opens on a drop area instead, where the person's paper or a PDF comes in (`PaperDrop.svelte`); where the publisher takes no paper, it says only that there is nothing to read.
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { readingAddress } from '$lib/shell/views';
	import { rememberedIn } from '$lib/workspace/remember';
	import { served } from '$lib/manifest/kept.svelte';
	import { workspace } from '$lib/workspace/store.svelte';
	import { can } from '$lib/write';
	import PaperDrop from '$lib/start/PaperDrop.svelte';
	import { docs } from '$lib/words/docs';

	const m = $derived(store.manifest!);
	// what was open is remembered per quilt, which `/_api` says: the address waits for it
	const to = $derived(served.digest === undefined ? '' : readingAddress(m, workspace.canonical(m) || rememberedIn(m)));
	$effect(() => {
		if (to) void goto(to, { replaceState: true, noScroll: true, keepFocus: true });
	});
	/** Whether the publisher takes a paper in; null until it has said. */
	let takes = $state<boolean | null>(null);
	onMount(() => void Promise.all([can('paper-receive'), can('paper-import'), can('paper-choose')]).then((all) => (takes = all.every(Boolean))));
</script>

{#if !to && takes !== null}
	<main class="page start" data-testid="how-to-start">
		{#if takes}
			<PaperDrop />
		{:else}
			<p class="nothing">{docs.start.nothing}</p>
		{/if}
	</main>
{/if}

<style>
	.nothing {
		color: var(--ink-faint);
	}
</style>
