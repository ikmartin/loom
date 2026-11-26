<script lang="ts">
	// Reading one work: its stored PDF, by its hash, at `GET /_api/library/pdf/<hex>`, and its annotations, annotated and read as a document's are (`MarkedDoc`). Content only, so there is one frame and not one inside another; what opens a work gives it the PDF's hash, which the library knows and the manifest does not.
	//
	// **Every annotation on the page is drawn** by the desk (`desk.svelte.ts`) in its look, unless the pane hides them all; a settled one only while the settled control is on. One that records where it stands (`rects`, `strokes`) is drawn there; one anchored by its words alone is drawn where the publisher finds them (`library-places`), asked for the whole work as the reader opens and again, with the generation held, whenever the annotations change. Where no publisher finds places, such a note is listed and drawn nowhere.
	//
	// **A locator in the URL is drawn transiently** (§3, §6): `span=`, `box=` or `quote=` name a place a message or a link pointed at, lit while the URL carries it and not recorded; `annot=` names an annotation by id and focuses its mark.
	//
	// **The one reader**, in a pane of Docs' workspace (`WorkItem`) and in the Library's tab for a work alike, with the same annotations: a view adds its own layers over it, never a second reader (`overlay` on the pages, `more` after a selection's actions, `onpage` to follow the page in view).
	//
	// **It opens where the reader last was, unless a link sends it elsewhere.** A link's place wins for as long as it is in force, and where it lands is then where the reader is. Once they move by their own hand nothing sends them back to it, and once its page has left the view the link is done with: its place comes off the item and so off the URL, so a reload returns to where they went.
	import { pdfUrl, places } from '$lib/library/api';
	import { Read } from '$lib/library/read.svelte';
	import { served } from '$lib/library/served.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { untrack } from 'svelte';
	import { paperPlace } from './place.svelte';
	import { paneOf } from '$lib/workspace/state.svelte';
	import { workspace } from '$lib/workspace/store.svelte';
	import { workState } from '$lib/workspace/state.svelte';
	import { locateBody, type WorkLink } from '$lib/worklink';
	import { write, type WriteResult } from '$lib/write';
	import { MarkDesk } from './desk.svelte';
	import MarkedDoc from './MarkedDoc.svelte';
	import type { PdfView } from './view.svelte';
	import { quoteLink } from '$lib/notes/link';
	import { notes as notesWords } from '$lib/words/notes';
	import { here } from '$lib/here.svelte';
	import { library } from '$lib/words/library';
	import type { Snippet } from 'svelte';
	import type { AnnotationPlace, PlacesAnswer, Rect } from '$lib/library/types';

	let {
		ref,
		pdf,
		short = null,
		page,
		seq = 0,
		locator = null,
		view,
		onleft,
		overlay,
		onpage,
		more
	}: {
		/** The work's reference: what an annotation on it targets and `locate` is asked about. */
		ref: string;
		/** The stored PDF's hash, `sha256:<hex>` as the library gives it; null for a work holding none. */
		pdf: string | null;
		/** The work's short name ("Smith 2024"), by which a quote names where its words came from; the reference where none is known. */
		short?: string | null;
		page: number;
		/** Changed each time a link sends the reader to a place, so being sent again lands again; 0 where no link names one. */
		seq?: number;
		/** A place the URL points at: `span`, `box`, `quote` are lit transiently; `annot` focuses an annotation's mark. */
		locator?: WorkLink | null;
		/** The reader's view, which the controls drawn beside the paper act on and which outlives this component. */
		view: PdfView;
		/** The reader has moved off the page the link sent them to. */
		onleft?: () => void;
		/** A view's layer on each page drawn, given the page and a function placing a rectangle on it. */
		overlay?: Snippet<[{ page: number; at: (r: Rect) => { left: string; top: string; width: string; height: string } }]>;
		/** The page in view, each time it changes. */
		onpage?: (e: { page: number }) => void;
		/** A view's own actions after a selection's, on the words selected; `hold` keeps them while the selection goes (a field of its own taking the keyboard), `done` takes them away. */
		more?: Snippet<[{ page: number; text: string; rects: number[][]; hold: () => void; done: () => void }]>;
	} = $props();

	// the library's source gives the address: the publisher's store, or round six's stand-in under the fixture
	const url = $derived(pdf ? pdfUrl(pdf) : '');
	// the item's annotating, which the toolbar shares; a work's pages are an item's only inside a pane
	const held = $derived(workState({ kind: 'work', id: ref }));
	// a work's pages in a pane hide every annotation while the pane does
	const holder = paneOf();
	const hide = $derived(holder ? workspace.hidesNotes(holder.index) : false);
	// where each annotation on the paper stands, asked for whole and again whenever the annotations change; known for the annotations it was last answered for
	const finds = $derived(!!pdf && served.has('library-places'));
	const stood = new Read<PlacesAnswer>();
	let stoodFor = $state.raw<unknown>(undefined);
	let asking = 0;
	$effect(() => {
		const anns = store.manifest?.annotations;
		if (!finds) return;
		const work = ref;
		const n = ++asking;
		void untrack(() => stood.load(work, (s) => places({ ref: work }, s))).then(() => {
			if (n === asking) stoodFor = anns;
		});
	});
	const stands = $derived(new Map((stood.value?.places ?? []).filter((p): p is AnnotationPlace => 'annotation' in p).map((p) => [p.annotation, p])));
	const standsOf = (id: string) => stands.get(id) ?? (stoodFor === store.manifest?.annotations ? null : undefined);
	const desk = new MarkDesk(() => ({ on: ref, owns: (a) => a.target.work === ref, url, name: `${ref}.pdf`, notes: held.notes, hidden: hide, stands: finds ? standsOf : undefined, unread: !finds || (!!stood.error && stoodFor === store.manifest?.annotations) }));
	// the list beside the paper says which notes on words are drawn on no page, and why
	$effect(() => {
		const notes = held.notes;
		const now = desk.nowhere;
		if (JSON.stringify(notes.nowhere) !== JSON.stringify(now)) notes.nowhere = now;
	});
	// the toolbar's PDF menu acts through it
	$effect(() => {
		const state = held;
		state.desk = desk;
		return () => {
			if (state.desk === desk) state.desk = null;
		};
	});

	let active = $state('');
	/** Words selected on page `n` are named by the work's short name and the page, and linked to as `loom link WORK --page N --quote` prints. */
	const offer = $derived({ name: (n: number) => notesWords.page(short ?? ref, n), link: (n: number, text: string) => quoteLink(ref, `page=${n}`, text) });

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
				name="{short ?? ref}.pdf"
				page={place.opening.page}
				share={place.opening.share}
				seq={place.opening.seq}
				spans={drawn}
				focus={focusOn}
				lands={!place.spent}
				onselect={(e) => {
					here.selection = { item: `work:${ref}`, page: e.page, text: e.text, rects: e.rects };
				}}
				onregion={(e) => {
					here.region = { item: `work:${ref}`, page: e.page, rects: e.rects };
				}}
				onmoved={(e) => {
					// what was being looked at is left behind with the place, so nothing lands back on it
					active = '';
					place.moved(e);
				}}
				{onpage}
				{overlay}
				{offer}
				{more}
			/>
		</div>
	{:else}
		<p class="muted" data-testid="reading-absent">{library.reader.noPdf}</p>
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
