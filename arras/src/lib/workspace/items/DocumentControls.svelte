<script lang="ts">
	// A document's toolbar: the annotating bar (Annotate, Comment, the format menu and Undo and Redo where a publisher serves writes, with the hint beneath saying what the tool in hand does; Changes where its text has pending changes; the stepper, Comments and Notes), then its own text size (`TextSize`), then **history ▾** where the document has one; under *view*, `show settled annotations`, then `view PDF`, which opens its compiled PDF beside it as a link in a pane does, and says beside it in the tree's words how its compile stands, greyed where there is no PDF to open. A version (a landmark) has the history and its text size, and on its bar its own controls (`VersionControls`): older and newer, live text, compare with now, restore; a closed or context-only agent document has its text size alone, and `view PDF` only where a PDF of it was compiled.
	import { store } from '$lib/manifest/client.svelte';
	import { compiles, pdfLine } from '$lib/manifest/compiles.svelte';
	import { isLandmark, type Item } from '../item';
	import { historyOf } from '../history';
	import HistoryMenu from '../HistoryMenu.svelte';
	import VersionControls from '../VersionControls.svelte';
	import { follow } from '../links';
	import { documentState, getPane } from '../state.svelte';
	import ItemToolbar from '../ItemToolbar.svelte';
	import ToolbarItem from '../ToolbarItem.svelte';
	import AnnotateBar from '$lib/review/AnnotateBar.svelte';
	import ChangesMenu from '$lib/review/ChangesMenu.svelte';
	import { hand, hintFor } from '$lib/review/annotating.svelte';
	import { ui } from '$lib/ui.svelte';
	import { can } from '$lib/write';
	import { settledIn } from '$lib/annotations';
	import { leanMarks } from '$lib/views/docs/lean.svelte';
	import { docs as docsWords } from '$lib/words/docs';
	import TextSize from '$lib/views/docs/TextSize.svelte';

	let { item, name }: { item: Item; name: string } = $props();

	const pane = getPane();
	const m = $derived(store.manifest!);
	const master = $derived(isLandmark(m, item.id) ? undefined : m.masters.find((x) => x.path === item.id));
	const notes = $derived(documentState(item).notes);
	const history = $derived(historyOf(m, item.id));
	// a landmark of a live draft: the way back to its live text
	const draft = $derived(history?.of === 'draft' && history.at ? history.draft : '');
	// the settled control is offered wherever there is something for it to draw, so a document whose every annotation is settled can still show them
	const anySettled = $derived(!!master && settledIn(m, master.path));
	const pdf = $derived(master ? pdfLine(!!master.pdf, compiles.all[master.path]) : undefined);

	// the tools write, so a corpus served without a write API does not offer them
	let writes = $state(false);
	$effect(() => {
		void can('annotate').then((ok) => (writes = ok));
	});
</script>

{#snippet changes()}{#if master}<ChangesMenu {notes} document={master.path} of={name} />{/if}{/snippet}
{#snippet size()}<TextSize doc={documentState(item)} of={name} />{/snippet}
{#snippet reading()}<AnnotateBar {notes} of={name} part="read" {writes} {changes} />{@render size()}{/snippet}
{#snippet writing()}<AnnotateBar {notes} of={name} part="write" {writes} />{/snippet}
{#snippet versions()}<HistoryMenu {item} {name} divided={(!!master && !master.closed && !master.context_only) || !!draft} />{/snippet}
{#snippet live()}{#if draft}<VersionControls {item} {draft} />{/if}{@render size()}{/snippet}
{#snippet viewPdf()}
	{#if master && pdf}
		<ToolbarItem
			label="view PDF"
			name="view the PDF of {name}{pdf.word ? `, ${pdf.word}` : ''}"
			aside={pdf.word}
			off={pdf.off}
			about={pdf.about}
			testid="view-pdf"
			onclick={() => follow({ kind: 'pdf', id: master.path }, pane.index)}
		/>
	{/if}
{/snippet}

{#if master && !master.closed && !master.context_only}
	<ItemToolbar {name} bar={reading} tools={writes ? writing : undefined} history={history ? versions : undefined} on={ui.showSettled} hint={writes ? hintFor(m, notes, hand.value) : ''}>
		{#snippet view()}
			{#if notes.ready || anySettled}
				<!-- Settled annotations are hidden at rest; this shows them faintly, for the sitting, on every document and node. -->
				<ToolbarItem
					label={ui.showSettled ? 'hide settled annotations' : 'show settled annotations'}
					name="{ui.showSettled ? 'hide settled' : 'show settled'} annotations in {name}"
					testid="toggle-settled"
					onclick={() => (ui.showSettled = !ui.showSettled)}
				/>
				<hr />
			{/if}
			{#if master && leanMarks.byDoc.get(master.path)?.on}
				<ToolbarItem label={docsWords.leanMarks.toggle} name={docsWords.leanMarks.toggle} checked={leanMarks.shown} testid="toggle-lean-marks" onclick={() => (leanMarks.shown = !leanMarks.shown)} />
				<hr />
			{/if}
			{@render viewPdf()}
		{/snippet}
	</ItemToolbar>
{:else}
	<ItemToolbar {name} bar={live} history={history ? versions : undefined} view={master?.pdf ? viewPdf : undefined} />
{/if}
