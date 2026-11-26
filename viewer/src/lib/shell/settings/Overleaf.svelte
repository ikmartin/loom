<script lang="ts">
	// Settings › Overleaf: the pairing card while the quilt mirrors no project (`Pairing`), else the mirror's card with Update and its line (`Mirror`), from the manifest's `overleaf`. A page shown as published, and a loom that serves no `overleaf-pair`, show a line saying so.
	import { store } from '$lib/manifest/client.svelte';
	import Mirror from '$lib/overleaf/Mirror.svelte';
	import Pairing from '$lib/overleaf/Pairing.svelte';
	import { paired } from '$lib/overleaf/said';
	import { overleaf as words } from '$lib/words/overleaf';
	import { can, capabilities } from '$lib/write';
	import Row from './Row.svelte';

	const o = $derived(paired(store.manifest?.overleaf));
	let served = $state<boolean | null>(null);
	let published = $state(false);
	$effect(() => {
		void Promise.all([can('overleaf-pair'), capabilities()]).then(([ok, caps]) => ((served = ok), (published = !caps)));
	});
</script>

<div class="card">
	<Row id="overleaf" stack>
		{#if served === false}<p class="cannot" data-testid="overleaf-not-served">{published ? words.settings.published : words.settings.cannot}</p>
		{:else if o}<Mirror {o} />
		{:else if served}<Pairing />
		{/if}
	</Row>
</div>

<style>
	.cannot {
		margin: 10px 0 0;
		font-size: 12.5px;
		color: var(--ink-faint);
	}
</style>
