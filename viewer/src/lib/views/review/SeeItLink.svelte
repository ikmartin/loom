<script lang="ts">
	// The quiet link under a row's text that lays its document over Review at the result, with what changed since it was accepted where `since` asks; drawn only where the quilt has that document.
	import { store } from '$lib/manifest/client.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';

	let { doc, key, name = '', since = false }: { doc: string; key: string; name?: string; since?: boolean } = $props();
	const here = $derived(!!store.manifest?.masters.some((x) => x.path === doc));
</script>

{#if here}<button type="button" class="linkish seeit" data-testid="see-it" onclick={() => (rv.over = { doc, key, name, since })}>{words.seeIt.link(doc)}</button>{/if}
