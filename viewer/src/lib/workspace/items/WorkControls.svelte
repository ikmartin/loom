<script lang="ts">
	// A work's toolbar: on the bar the PDF's (`PdfBar`): annotating as a document is annotated, the PDF's drawing tools, **PDF ▾**, and the page and the zoom, typed into as a desktop viewer's are; under *view*, `show settled annotations`, which the page's marks honour, then `open the PDF`. They act on the PDF its pane draws (`Reading`, through the item's desk); with none drawn they stay drawn and greyed rather than gone (DR-254-ikmartin): a greyed control still says what it would act on. A work the library no longer holds has nothing they could act on, so its pane keeps *view* and the pane's own line alone, as a kind with no controls does.
	import { store } from '$lib/manifest/client.svelte';
	import PdfBar from '$lib/pdf/PdfBar.svelte';
	import { hand, hintFor } from '$lib/review/annotating.svelte';
	import { ui } from '$lib/ui.svelte';
	import { can } from '$lib/write';
	import type { Item } from '../item';
	import ItemToolbar from '../ItemToolbar.svelte';
	import type { ToolsAt } from '../fold';
	import ToolbarItem from '../ToolbarItem.svelte';
	import { workState } from '../state.svelte';
	import { library } from '$lib/words/library';
	import { lib } from '$lib/views/library/state.svelte';
	import { quoteLink } from '$lib/notes/link';

	let { item, name }: { item: Item; name: string } = $props();

	const m = $derived(store.manifest);
	const held = $derived(workState(item));
	/** The PDF the pane draws, where it draws one. */
	const url = $derived(held.desk?.surface().url ?? '');
	const readable = $derived(!!url);
	const pdfOff = $derived(readable ? undefined : library.work.noPdf);
	/** Whether the works list, read, holds this work no longer. */
	const gone = $derived(!!lib.works.value && !lib.works.value.works.some((w) => w.ref === item.id));
	// New note on the whole work, by its reference
	const note = $derived({ link: quoteLink(item.id), title: name });

	// the tools write, so a corpus served without a write API does not offer them
	let writes = $state(false);
	$effect(() => {
		void can('annotate').then((ok) => (writes = ok));
	});
</script>

{#snippet reading()}<PdfBar view={held.pdf} notes={held.notes} desk={held.desk} of={name} part="read" {writes} disabled={!readable} />{/snippet}
{#snippet writing(where: ToolsAt)}<PdfBar view={held.pdf} notes={held.notes} desk={held.desk} of={name} part="write" {writes} disabled={!readable} {where} />{/snippet}

{#if gone}
	<ItemToolbar {name} />
{:else}
<ItemToolbar {name} {note} bar={reading} tools={writes ? writing : undefined} on={ui.showSettled} hint={writes && readable ? hintFor(m, held.notes, hand.value) : ''}>
	{#snippet view()}
		<ToolbarItem
			label={ui.showSettled ? 'hide settled annotations' : 'show settled annotations'}
			name="{ui.showSettled ? 'hide settled' : 'show settled'} annotations in {name}"
			testid="toggle-settled"
			onclick={() => (ui.showSettled = !ui.showSettled)}
		/>
		<hr />
		<ToolbarItem label="open the PDF" name="open the PDF of {name}" href={url || undefined} off={pdfOff} testid="open-pdf" />
	{/snippet}
</ItemToolbar>
{/if}
