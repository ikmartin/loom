<script lang="ts">
	// A project file's toolbar: a PDF's bar (`PdfBar`), annotated as a cited work's pages are, with **PDF ▾** holding Open in its application where the publisher can open it, and under *view* `open in browser`, the file at its own address in a new tab, without the marks loom keeps; a Markdown file's, annotated as a document is (`AnnotateBar`), with `show settled annotations` under *view*; any other file has the plain toolbar, its views and *view*.
	import { store } from '$lib/manifest/client.svelte';
	import { filesUrl } from '$lib/paths';
	import PdfBar from '$lib/pdf/PdfBar.svelte';
	import AnnotateBar from '$lib/review/AnnotateBar.svelte';
	import { hand, hintFor } from '$lib/review/annotating.svelte';
	import { say } from '$lib/review/toasts.svelte';
	import { ui } from '$lib/ui.svelte';
	import { can } from '$lib/write';
	import type { Item } from '../item';
	import ItemToolbar from '../ItemToolbar.svelte';
	import ToolbarItem from '../ToolbarItem.svelte';
	import { openOutside } from '../links';
	import { fileState } from '../state.svelte';
	import { quoteLink } from '$lib/notes/link';

	let { item, name }: { item: Item; name: string } = $props();

	const file = $derived(store.manifest?.files?.find((f) => f.path === item.id));
	const held = $derived(fileState(item));
	// New note on the whole file, by its path
	const note = $derived(file ? { link: quoteLink(file.path), title: name } : undefined);

	let writes = $state(false);
	let opens = $state(false);
	$effect(() => {
		void can('annotate').then((ok) => (writes = ok));
		void can('open').then((ok) => (opens = ok));
	});

	async function outside(): Promise<void> {
		const refused = await openOutside({ file: item.id });
		if (refused) say({ title: 'Not opened', lines: [refused] });
	}
</script>

{#snippet reading()}<PdfBar view={held.pdf} notes={held.notes} desk={held.desk} of={name} part="read" {writes} onoutside={opens ? () => void outside() : undefined} />{/snippet}
{#snippet writing()}<PdfBar view={held.pdf} notes={held.notes} desk={held.desk} of={name} part="write" {writes} />{/snippet}
{#snippet marking()}<AnnotateBar notes={held.notes} of={name} part="read" {writes} />{/snippet}
{#snippet marks()}<AnnotateBar notes={held.notes} of={name} part="write" {writes} />{/snippet}
{#snippet settled()}
	<ToolbarItem
		label={ui.showSettled ? 'hide settled annotations' : 'show settled annotations'}
		name="{ui.showSettled ? 'hide settled' : 'show settled'} annotations in {name}"
		testid="toggle-settled"
		onclick={() => (ui.showSettled = !ui.showSettled)}
	/>
{/snippet}

{#if file?.kind === 'pdf'}
	<ItemToolbar {name} {note} bar={reading} tools={writes ? writing : undefined} on={ui.showSettled} hint={writes ? hintFor(store.manifest, held.notes, hand.value) : ''}>
		{#snippet view()}
			{@render settled()}
			<hr />
			<ToolbarItem label="open in browser" name="open {name} in the browser's own viewer, in a new tab" href={filesUrl(item.id)} testid="pdf-open-browser" />
		{/snippet}
	</ItemToolbar>
{:else if file?.kind === 'markdown'}
	<ItemToolbar {name} {note} bar={marking} tools={writes ? marks : undefined} on={ui.showSettled} hint={writes ? hintFor(store.manifest, held.notes, hand.value) : ''}>
		{#snippet view()}{@render settled()}{/snippet}
	</ItemToolbar>
{:else}
	<ItemToolbar {name} {note} />
{/if}
