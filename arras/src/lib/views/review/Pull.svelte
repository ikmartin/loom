<script lang="ts">
	// A collaborator's pull, chosen in Review's column, drawn as today's component draws it (`IncomingPull`), from the manifest's `incoming`.
	import { onMount } from 'svelte';
	import IncomingPull from '$lib/review/IncomingPull.svelte';
	import { pullLabel } from '$lib/review/proposed';
	import { store } from '$lib/manifest/client.svelte';
	import { can } from '$lib/write';

	let writable = $state(false);
	onMount(() => void can('sync-incorporate').then((yes) => (writable = yes)));
	const m = $derived(store.manifest);
</script>

{#if m?.incoming}
	{#key m.incoming.commit}<IncomingPull incoming={m.incoming} label={pullLabel(m)} {writable} />{/key}
{/if}
