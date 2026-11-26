// The reader's view of a document: which of the PDF's own tools is in hand, how large the page is drawn, and where in it they are. Each open paper has its own, so its zoom is its own: zooming one paper zooms no other.
//
// It is a separate object because the controls and the renderer need not be in the same place. `PdfDoc` draws its own toolbar when nothing else claims one, and a page with a rail of its own creates a view, hands it to both, and puts the controls on one line with everything else it offers.

import { prefs } from '$lib/prefs.svelte';
import type { PageTool } from './marks';
import type { PagePlace, PaperFile } from './position';

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 5;

/** A zoom as the view keeps it: within the bounds, to the percent. */
export const clampZoom = (v: number): number => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(v * 100) / 100));

export class PdfView {
	/** The drawing tool in hand; `select` reads, and Annotate and Comment are the item's (`Annotating.tool`). */
	tool = $state<PageTool>('select');
	/** Whether the page is matched to the column, which then survives a resize. */
	fitWidth = $state(false);
	/** Whether a page wider than its column is drawn so its text fits instead: a paper opened into half a pane is read, not scrolled sideways. The reader's own zoom takes over as soon as they give one. */
	fitText = $state(true);
	/** The page the reader is on and how many there are; the renderer writes both. */
	page = $state(1);
	count = $state(0);
	/** The scale actually drawn, which is the fitted one while `fitWidth` holds; the renderer writes it. */
	scale = $state(1);
	/** This paper's own zoom: it starts at the zoom last given any PDF (`prefs.zoom.pdf`), which is then the start of the next paper opened, and changes only by `zoomTo`. */
	zoom = $state(prefs.zoom.pdf ?? 1.4);
	#kept: ((zoom: number) => void) | undefined;

	/**
	 * A paper's view.
	 *
	 * Parameters
	 * ----------
	 * zoom : number, optional
	 *     A zoom the reader gave this paper before, which the open item kept; it holds over fitting the text, as a zoom given does.
	 * kept : (zoom: number) => void, optional
	 *     Told each zoom the reader gives, to keep it with the open item.
	 */
	constructor(zoom?: number, kept?: (zoom: number) => void) {
		if (zoom !== undefined && Number.isFinite(zoom) && zoom > 0) {
			this.zoom = clampZoom(zoom);
			this.fitText = false;
		}
		this.#kept = kept;
	}

	/** The file open here, once it is known; the renderer writes it in the same step that lays out its pages, so what opens the paper can say where. */
	file = $state.raw<PaperFile | null>(null);
	/** Where the reader is, as the renderer last read it off the column. This view outlives its renderer, so a paper made again for the same tab opens here. */
	place = $state.raw<PagePlace | null>(null);
	/** The stamp of the last link the reader has moved on from by their own hand: nothing sends them back to it, and a paper made again opens where they went. */
	spent = $state(0);

	/** A request to scroll somewhere, which the renderer takes off once it has gone: a paper made again must not answer it a second time. */
	jump = $state<{ page: number } | null>(null);

	/** Send the reader to a page. Out-of-range asks are clamped rather than refused: a reader who types 99 of 12 means the end. */
	goTo(page: number): void {
		this.jump = { page: Math.max(1, this.count ? Math.min(page, this.count) : page) };
	}

	/** Set this paper's zoom, which becomes the start of the next paper opened. An instruction about size leaves the fitted mode rather than fighting it. */
	zoomTo(v: number): void {
		this.fitWidth = false;
		this.fitText = false;
		const z = clampZoom(v);
		this.zoom = z;
		prefs.zoom = { ...prefs.zoom, pdf: z };
		this.#kept?.(z);
	}
}
