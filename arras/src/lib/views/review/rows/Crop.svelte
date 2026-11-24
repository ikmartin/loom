<script lang="ts">
	// The paper cropped at a place, at reading size: its page drawn by the reader, clipped to the place with a few lines above and below and from a little left of it, the place washed as the reader washes a found passage. A page the PDF does not have says so in a sentence, never in pdf.js's words.
	import * as api from '$lib/library/api';
	import type { Place } from '$lib/library/types';
	import { document_ } from '$lib/pdf/document';
	import PdfPage from '$lib/pdf/PdfPage.svelte';
	import { review as words } from '$lib/words/review';

	let {
		pdf,
		place,
		caption = '',
		pad = 44,
		onselect
	}: {
		pdf: string;
		place: Pick<Place, 'page' | 'rects'>;
		caption?: string;
		/** Points of the page above and below the place that the crop keeps; with no place, how much of the page's top it shows. */
		pad?: number;
		/** Words selected on the page. */
		onselect?: (e: { page: number; text: string; rects: number[][]; client: { left: number; top: number; width: number; height: number } }) => void;
	} = $props();
	/** The reader's own size, so the words cropped read as they do on the page. */
	const SCALE = 1.25;
	/** A page's width in points, letter's, which A4's is within a few of. */
	const PAGE = 612;
	let width = $state(0);
	let pages = $state<number | null>(null);
	const url = $derived(api.pdfUrl(pdf));
	$effect(() => {
		const u = url;
		void document_(u)
			.then((d) => (pages = d.numPages))
			.catch(() => (pages = 0));
	});
	const has = $derived(place.rects.length > 0);
	const top = $derived(has ? Math.max(0, Math.min(...place.rects.map((r) => r[1])) - pad) : 0);
	const bottom = $derived(has ? Math.max(...place.rects.map((r) => r[3])) + pad : 300);
	// from a little left of the place, but never past the page's right edge
	const left = $derived(has ? Math.max(0, Math.min(Math.min(...place.rects.map((r) => r[0])) - 24, PAGE - width / SCALE)) : 0);
</script>

{#if caption}<div class="crop-cap">{caption}</div>{/if}
{#if pages !== null && place.page > pages}
	<p class="crop-none" data-testid="review-crop-missing">{words.check.noPage}</p>
{:else}
	<div class="crop" bind:clientWidth={width} style:height="{(bottom - top) * SCALE}px" data-testid="review-crop">
		{#if width && pages}
			<div class="at" style:margin-top="{-top * SCALE}px" style:margin-left="{-left * SCALE}px">
				<PdfPage {url} page={place.page} scale={SCALE} quads={has ? [{ id: 'here', rects: place.rects }] : []} focus="here" {onselect} />
			</div>
		{/if}
	</div>
{/if}

<style>
	.crop-cap {
		margin: 0 0 6px;
		font-size: 11.5px;
		color: var(--ink-faint);
	}
	.crop {
		overflow: hidden;
		border: 1px solid var(--rule);
		border-radius: 6px;
		background: var(--sheet);
	}
	.crop-none {
		margin: 0;
		padding: 12px;
		font-size: 12px;
		color: var(--ink-faint);
		border: 1px dashed var(--rule);
		border-radius: 6px;
	}
</style>
