<script lang="ts">
	// The paper cropped at a place: its page drawn by the reader at the crop's width, clipped to the place with a few lines above and below, the place washed as the reader washes a result.
	import * as api from '$lib/library/api';
	import type { Place } from '$lib/library/types';
	import PdfPage from '$lib/pdf/PdfPage.svelte';

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
		/** Points of the page above and below the place that the crop keeps. */
		pad?: number;
		/** Words selected on the page. */
		onselect?: (e: { page: number; text: string; rects: number[][]; client: { left: number; top: number; width: number; height: number } }) => void;
	} = $props();
	/** A page's width in points, letter's, which A4's is within a few of. */
	const PAGE = 612;
	let width = $state(0);
	const scale = $derived(width ? (width - 2) / PAGE : 0.75);
	const top = $derived(Math.max(0, Math.min(...place.rects.map((r) => r[1])) - pad));
	const bottom = $derived(Math.max(...place.rects.map((r) => r[3])) + pad);
</script>

{#if caption}<div class="crop-cap">{caption}</div>{/if}
<div class="crop" bind:clientWidth={width} style:height="{(bottom - top) * scale}px" data-testid="review-crop">
	{#if width}
		<div class="at" style:margin-top="{-top * scale}px">
			<PdfPage url={api.pdfUrl(pdf)} page={place.page} {scale} quads={place.rects.length ? [{ id: 'here', rects: place.rects }] : []} {onselect} />
		</div>
	{/if}
</div>

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
</style>
