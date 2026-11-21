<script lang="ts">
	// A work, rendered small for a hover card (plan 0.13.3 H3–H5): **the paper, not a transcription of it**, at the place the link names, its stored PDF given by its hash, which the library knows and the manifest does not. A span or a quote is located by the publisher and lit; a box needs no mapping.
	import { libraryPdfUrl } from '$lib/paths';
	import { locateBody } from '$lib/worklink';
	import { can, write, type WriteResult } from '$lib/write';
	import PdfDoc from '$lib/pdf/PdfDoc.svelte';
	import type { Item } from '../item';

	let { item, pdf }: { item: Item; pdf: string; onresize: () => void } = $props();

	const place = $derived(item.place ?? {});
	const at = $derived(place.page ?? 1);
	const url = $derived(libraryPdfUrl(pdf));

	/** The place the link names, mapped by the publisher into rectangles; a box needs no mapping. */
	let lit = $state<{ page: number; rects: number[][] } | null>(null);

	$effect(() => {
		lit = null;
		if (place.box) {
			lit = { page: at, rects: [[...place.box]] };
			return;
		}
		if (!place.span && !place.quote) return;
		let dropped = false;
		// the work's reference, which `locate` is asked about; a quote with no page is looked for across the work, as a click on the link looks for it
		const body = locateBody(item.id, place, at)!;
		void can('locate').then((ok) => {
			if (!ok || dropped) return;
			return write('locate', body).then((res: WriteResult & { page?: number; anchor?: { quads?: number[][] } }) => {
				if (!dropped && res.ok && res.anchor?.quads?.length) lit = { page: res.page ?? at, rects: res.anchor.quads };
			});
		});
		return () => {
			dropped = true;
		};
	});
</script>

<div class="page-card" data-testid="preview-page">
	<PdfDoc {url} page={lit?.page ?? at} scale={0.99} window={0} spans={lit ? [{ id: '_locator', page: lit.page, rects: lit.rects, transient: true }] : []} focus={lit ? '_locator' : ''} />
</div>

<style>
	/* The page centres plainly here; a pane uses `safe` centring so a page wider than it stays reachable. */
	.page-card :global(.column) {
		align-items: center;
	}
	.page-card {
		width: 43.2rem;
		height: 28.8rem;
		overflow: hidden;
		background: var(--sheet);
	}
	/* **The card marks where the place starts; it does not outline it.** A dot in the margin beside the first line says where it begins and leaves the text alone. */
	.page-card :global(.mark.transient) {
		outline: none;
		background: none;
	}
	.page-card :global(.marks > .mark.transient:first-child)::before {
		content: '';
		position: absolute;
		left: -0.7em;
		top: 50%;
		width: 0.5em;
		height: 0.5em;
		transform: translateY(-50%);
		border-radius: 50%;
		background: rgb(224 168 32 / 0.55);
	}
</style>
