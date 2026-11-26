<script lang="ts">
	// Where `loom open LINK` sends the browser: `/open?link=…`, a `quilt:` or `cited:` link an editor followed in a note. The link is read as any link in the viewer is (`itemForHref`), and the page is replaced by the item it names, at its place with its quoted words; a link naming nothing here says so.
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { store } from '$lib/manifest/client.svelte';
	import { frame as words } from '$lib/words/frame';
	import { pathFor } from '$lib/workspace/item';
	import { itemForHref } from '$lib/workspace/links';

	const link = $derived(page.url.searchParams.get('link') ?? '');
	const item = $derived(store.manifest && link ? itemForHref(store.manifest, link) : null);
	$effect(() => {
		const m = store.manifest;
		if (m && item) void goto(pathFor(m, item), { replaceState: true });
	});
</script>

{#if store.manifest && !item}
	<main class="page" data-testid="open-nothing">
		<p class="muted">{words.open.nothing(link)}</p>
	</main>
{/if}
