<script lang="ts">
	// Reading one work: its stored PDF, by its hash, at `GET /_api/library/pdf/<hex>`, and its annotations, annotated and read as a document's are (`MarkedDoc`). Content only, so there is one frame and not one inside another; what opens a work gives it the PDF's hash, which the library knows and the manifest does not.
	//
	// **Every annotation on the page is drawn** by the desk (`desk.svelte.ts`) in its look, unless the pane hides them all; a settled one only while the settled control is on. One that records where it stands (`rects`, `strokes`) is drawn there; one anchored by its words alone has no place until the publisher says where it stands.
	//
	// **A locator in the URL is drawn transiently** (§3, §6): `span=`, `box=` or `quote=` name a place a message or a link pointed at, lit while the URL carries it and not recorded; `annot=` names an annotation by id and focuses its mark.
	//
	// **It opens where the reader last was, unless a link sends it elsewhere.** A link's place wins for as long as it is in force, and where it lands is then where the reader is. Once they move by their own hand nothing sends them back to it, and once its page has left the view the link is done with: its place comes off the item and so off the URL, so a reload returns to where they went.
	import { libraryPdfUrl } from '$lib/paths';
	import { paperPlace } from './place.svelte';
	import { paneOf } from '$lib/workspace/state.svelte';
	import { workspace } from '$lib/workspace/store.svelte';
	import { workState } from '$lib/workspace/state.svelte';
	import { locateBody, type WorkLink } from '$lib/worklink';
	import { write, type WriteResult } from '$lib/write';
	import { MarkDesk } from './desk.svelte';
	import MarkedDoc from './MarkedDoc.svelte';
	import { mergeLines } from './marks';
	import type { PdfView } from './view.svelte';
	import QuoteChip from '$lib/review/QuoteChip.svelte';
	import { here } from '$lib/here.svelte';
	import { library } from '$lib/words/library';

	let {
		ref,
		pdf,
		identifier = null,
		page,
		seq = 0,
		locator = null,
		view,
		onleft,
	}: {
		/** The work's reference: what an annotation on it targets and `locate` is asked about. */
		ref: string;
		/** The stored PDF's hash, `sha256:<hex>` as the library gives it; null for a work holding none. */
		pdf: string | null;
		/** The first identifier the work's entry states, `scheme:value`, by which a quote links to it; null for none, and the quote links to the reference. */
		identifier?: string | null;
		page: number;
		/** Changed each time a link sends the reader to a place, so being sent again lands again; 0 where no link names one. */
		seq?: number;
		/** A place the URL points at: `span`, `box`, `quote` are lit transiently; `annot` focuses an annotation's mark. */
		locator?: WorkLink | null;
		/** The reader's view, which the controls drawn beside the paper act on and which outlives this component. */
		view: PdfView;
		/** The reader has moved off the page the link sent them to. */
		onleft?: () => void;
	} = $props();

	const url = $derived(pdf ? libraryPdfUrl(pdf) : '');
	// the item's annotating, which the toolbar shares; a work's pages are an item's only inside a pane
	const held = $derived(workState({ kind: 'work', id: ref }));
	// a work's pages in a pane hide every annotation while the pane does
	const holder = paneOf();
	const hide = $derived(holder ? workspace.hidesNotes(holder.index) : false);
	const desk = new MarkDesk(() => ({ on: ref, owns: (a) => a.target.work === ref, url, name: `${ref}.pdf`, notes: held.notes, hidden: hide }));
	// the toolbar's PDF menu acts through it
	$effect(() => {
		const state = held;
		state.desk = desk;
		return () => {
			if (state.desk === desk) state.desk = null;
		};
	});

	$effect(() => {
		const drop = () => {
			if (offered && !window.getSelection()?.toString().trim()) offered = null;
		};
		document.addEventListener('selectionchange', drop);
		return () => document.removeEventListener('selectionchange', drop);
	});
	let active = $state('');
	/** A bare selection, offered Quote: selecting words is not a request to annotate them, which Annotate is for. */
	let offered = $state<{ page: number; text: string; lines: number[][]; at: { left: number; top: number; width: number; height: number }; range?: Range } | null>(null);
	/** Where a quote from page `n` came from, as a link an agent can follow: the work by its identifier at the page, else its reference, whole, as `loom link` prints it. */
	const quoteHref = (n: number): string => (identifier ? `cited:${identifier}?page=${n}` : `quilt:${ref}`);

	/** The place the URL points at, mapped by loom into rectangles, while the URL carries it. */
	let lit = $state<{ page: number; rects: number[][] } | null>(null);
	$effect(() => {
		const l = locator;
		if (!l || (!l.span && !l.box && !l.quote)) {
			lit = null;
			return;
		}
		const at = l.page ?? page;
		if (l.box) {
			lit = { page: at, rects: [[...l.box]] };
			return;
		}
		let dropped = false;
		// a quote with no page is looked for across the work, and lit on the page loom finds it on
		void write('locate', locateBody(ref, l, at)!).then((res: WriteResult & { page?: number; anchor?: { quads?: number[][] } }) => {
			if (dropped) return;
			lit = res.ok && res.anchor?.quads?.length ? { page: res.page ?? at, rects: res.anchor.quads } : null;
		});
		return () => {
			dropped = true;
		};
	});
	// A link in force sends the paper to the page loom lit, which a quote with no page learns only from the answer, else the one asked for: opened at page 1 while lighting page 2, the place the renderer keeps across a redraw is page 1's, and putting it back cancels the landing's scroll.
	const place = paperPlace(
		() => view,
		() => ({ seq, page: lit?.page ?? page }),
		() => onleft?.()
	);

	/** The geometry drawn besides the annotations: the lit locator. */
	const drawn = $derived(lit ? [{ id: '_locator', page: lit.page, rects: lit.rects, transient: true }] : []);
	const focusOn = $derived(locator?.annot ?? (lit ? '_locator' : active));
</script>

<section class="reading" data-testid="reading">
	{#if url}
		<div class="paper">
			<MarkedDoc
				{desk}
				{view}
				notes={held.notes}
				{url}
				name="{ref}.pdf"
				page={place.opening.page}
				share={place.opening.share}
				seq={place.opening.seq}
				spans={drawn}
				focus={focusOn}
				lands={!place.spent}
				onselect={(e) => {
					const sel = window.getSelection();
					offered = { page: e.page, text: e.text, lines: mergeLines(e.rects), at: e.client, range: sel?.rangeCount ? sel.getRangeAt(0).cloneRange() : undefined };
					here.selection = { item: `work:${ref}`, page: e.page, text: e.text, rects: e.rects };
				}}
				onregion={(e) => {
					offered = null;
					here.region = { item: `work:${ref}`, page: e.page, rects: e.rects };
				}}
				onmoved={(e) => {
					// what was being looked at is left behind with the place, so nothing lands back on it
					active = '';
					place.moved(e);
				}}
			/>
		</div>
	{:else}
		<p class="muted" data-testid="reading-absent">{library.reader.noPdf}</p>
	{/if}
	{#if offered}
		<QuoteChip at={offered.at} range={offered.range} words={offered.text} name="{ref} p. {offered.page}" href={quoteHref(offered.page)} ondone={() => (offered = null)} />
	{/if}
</section>

<style>
	.reading {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}
	.paper {
		position: relative;
		flex: 1 1 auto;
		min-height: 0;
		display: flex;
	}
	.paper > :global(.marked) {
		flex: 1 1 auto;
		min-width: 0;
	}
</style>
