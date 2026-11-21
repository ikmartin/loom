<script lang="ts">
	// The toolbar of a work of the library beside a draft: the reader's own bar (Comments, Notes, PDF, the zoom and the page) on the pane's one row, its drawing tools on the annotation row, and *view* with the pane's own line; the reader under it draws no bar of its own.
	import PdfBar from '$lib/pdf/PdfBar.svelte';
	import { lib } from '$lib/views/library/state.svelte';
	import { shortNames } from '$lib/views/docs/names.svelte';
	import type { Item } from '../item';
	import ItemToolbar from '../ItemToolbar.svelte';

	let { item, name }: { item: Item; name: string } = $props();
	const reader = $derived(lib.reader(item.id));
	const desk = $derived(lib.desk(item.id));
	const of = $derived(shortNames.get(item.id) ?? name);
</script>

{#snippet reading()}<PdfBar view={reader.view} notes={reader.notes} {desk} {of} part="read" writes={desk.writes} />{/snippet}
{#snippet writing()}<PdfBar view={reader.view} notes={reader.notes} {desk} {of} part="write" writes={desk.writes} />{/snippet}

<ItemToolbar {name} bar={reading} tools={desk.writes ? writing : undefined} />
