<script lang="ts">
	// The quiet link under a row's text that lays its document over Review at the result; drawn only where the quilt has that document.
	import { store } from '$lib/manifest/client.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';

	let { doc, key, name = '' }: { doc: string; key: string; name?: string } = $props();
	const here = $derived(!!store.manifest?.masters.some((x) => x.path === doc));
</script>

{#if here}<button type="button" class="linkish seeit" data-testid="see-it" onclick={() => (rv.over = { doc, key, name })}>{words.seeIt.link(doc)}</button>{/if}
