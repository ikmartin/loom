<script lang="ts">
	// A PDF's bar, on a cited work's pages and a project PDF alike, in two halves (`part`), both on the toolbar's one row. The half that writes stands after the toolbar's Annotate while it is on, in three groups (`where`, `fold.ts`): a document's annotating tools (Annotate, Comment and the format menu, then Undo and Redo) and then the PDF's own drawing tools, which go first into the menu the toolbar's ˅ opens when the row is short. The half that reads stands on the bar: the stepper, Comments and Notes, **PDF ▾** with its file acts, and the page and the zoom. Where nothing can be read here (no copy, or off the Paper view) every control stays drawn and greyed, so nothing after it moves. Turning Annotate off puts a drawing tool down.
	import { untrack } from 'svelte';
	import AnnotateBar from '$lib/review/AnnotateBar.svelte';
	import type { Annotating } from '$lib/review/annotating.svelte';
	import { annotateTools } from '$lib/workspace/annotateTools.svelte';
	import { drawnAt, ROW, type ToolsAt } from '$lib/workspace/fold';
	import type { MarkDesk } from './desk.svelte';
	import DrawTools from './DrawTools.svelte';
	import PdfMenu from './PdfMenu.svelte';
	import PdfTools from './PdfTools.svelte';
	import type { PdfView } from './view.svelte';

	let {
		view,
		notes,
		desk,
		of,
		part,
		where = ROW,
		writes = false,
		disabled = false,
		onoutside
	}: {
		view: PdfView;
		notes: Annotating;
		desk: MarkDesk | null;
		of: string;
		/** Which half: the tools that write, after the toolbar's Annotate, or what reads, on its bar. */
		part: 'read' | 'write';
		/** Where the half that writes is drawn, the row or the menu, and how much of it the menu holds. */
		where?: ToolsAt;
		/** Whether the publisher takes annotations. */
		writes?: boolean;
		/** Nothing to act on here. */
		disabled?: boolean;
		onoutside?: () => void;
	} = $props();

	/** The annotating tools' two groups, then the drawing tools. */
	const GROUPS = 3;
	const annotates = $derived(writes && !disabled && (drawnAt(where, 0, GROUPS) || drawnAt(where, 1, GROUPS)));
	const draws = $derived(writes && drawnAt(where, 2, GROUPS));

	// a drawing tool goes down with the toolbar's Annotate
	$effect(() => {
		if (part !== 'read' || annotateTools.open) return;
		untrack(() => {
			if (view.tool !== 'select') view.tool = 'select';
		});
	});
</script>

<!-- one box, since the toolbar lays its bar's children out from the right -->
<span class="pdf-bar">
	{#if part === 'write'}
		<AnnotateBar {notes} {of} part="write" writes={writes && !disabled} {where} groups={GROUPS} />
		{#if draws}
			{#if annotates}<span class="sep" aria-hidden="true"></span>{/if}
			<DrawTools {view} {notes} {of} {disabled} />
		{/if}
	{:else}
		<AnnotateBar {notes} {of} part="read" writes={writes && !disabled} />
		<PdfMenu {desk} {of} {disabled} {onoutside} />
		<span class="sep" aria-hidden="true"></span>
		<PdfTools {view} {of} {disabled} />
	{/if}
</span>

<style>
	.pdf-bar {
		display: inline-flex;
		align-items: center;
		gap: 2px;
	}
	.sep {
		width: 1px;
		height: 16px;
		margin: 0 5px;
		background: var(--rule);
	}
</style>
