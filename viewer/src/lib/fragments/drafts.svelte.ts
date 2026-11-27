// A save's changed blocks drawn from their source until TeX's arrive (`docs/specs/write-api.md` §1, the stream's `drafted` event). The publisher says the blocks as source before the save's build runs TeX; each is drawn in place by the viewer's own converter and MathJax, marked as being typeset, and dropped once the manifest of the build that publishes it has been fetched, so TeX's block takes its place in the same draw. A build that fails drops them too, and the page shows the publication it has.

import { SvelteMap } from 'svelte/reactivity';
import { store } from '$lib/manifest/client.svelte';
import type { Built } from '$lib/manifest/updating.svelte';
import type { Macro } from '$lib/manifest/types';
import { toHtml, type Point } from '$lib/node/latexlite';

/** One block a save changed: `src` as the published page's `data-src` names it; an `env` is a statement's or proof's element and `body` the text between its head and its `\end`, a `text` the paragraph between the blank lines `src` names. */
export interface DraftBlock {
	src: string;
	kind: 'env' | 'text';
	body: string;
}

/** The stream's `drafted` event: the server, the build that publishes TeX's blocks, and the blocks. */
export interface Drafted {
	server: number;
	build: number;
	blocks: DraftBlock[];
}

/** A block drawn from source, with the build whose publication replaces it. */
export interface Draft {
	block: DraftBlock;
	server: number;
	build: number;
}

const fileOf = (src: string): string => src.replace(/:\d+:\d+$/, '');

class Drafts {
	/** The blocks drawn from source now, by their `data-src`. */
	readonly shown = new SvelteMap<string, Draft>();

	/** A `drafted` event: its blocks replace every draft of the files it names, since each event is the save against the published text. */
	take(raw: string): void {
		let d: Drafted;
		try {
			d = JSON.parse(raw) as Drafted;
		} catch {
			return;
		}
		if (typeof d?.build !== 'number' || typeof d.server !== 'number' || !Array.isArray(d.blocks)) return;
		const files = new Set(d.blocks.map((b) => fileOf(b.src)));
		for (const [src, was] of this.shown) if (files.has(fileOf(src)) || was.server !== d.server) this.shown.delete(src);
		for (const block of d.blocks) if (typeof block?.src === 'string' && typeof block.body === 'string') this.shown.set(block.src, { block, server: d.server, build: d.build });
	}

	/** The stream's `built` event: a draft whose build published goes once that manifest is fetched; one whose build failed, or of another server, goes at once. */
	async heard(b: Built): Promise<void> {
		for (const [src, d] of this.shown) if (d.server !== b.server || (b.failed >= d.build && b.published < d.build)) this.shown.delete(src);
		if (![...this.shown.values()].some((d) => d.build <= b.published)) return;
		await store.refresh();
		for (const [src, d] of this.shown) if (d.server === b.server && d.build <= b.published) this.shown.delete(src);
	}
}

export const drafts = new Drafts();

/** loom's own markers, which print nothing (`loom.sty`). */
const SILENT = /\\(?:uses|incomplete)\s*\{[^{}]*\}/g;

/**
 * A block's source drawn as the viewer draws a library node: its text by `latexlite`, its formulas left for MathJax with the work's macros.
 *
 * Parameters
 * ----------
 * body : string
 *     The block's source, as `DraftBlock.body`.
 * points : Record<string, Point>
 *     The words each label and citation key is drawn as, from the page as published; one missing is drawn `??`.
 * macros : Macro[], default []
 *     The work's macros, for a use outside mathematics.
 * italic : boolean, default false
 *     Set as amsthm's plain style sets a statement.
 *
 * Returns
 * -------
 * string
 *     The drawing: paragraphs as `div.tx-par`, formulas as `.math` spans and blocks; a command it does not know as its source (`span.tx-unknown`).
 */
export function drawDraft(body: string, points: Record<string, Point>, macros: Macro[] = [], italic = false): string {
	return toHtml(body.replace(SILENT, ''), points, { macros, italic }).html;
}

/** The words the page as published draws for each label and citation key: a reference's number, a display's tag, a citation's name, and every result's number in `numbers`. */
export function pointsIn(root: ParentNode, numbers: Record<string, string> = {}): Record<string, Point> {
	const out: Record<string, Point> = {};
	for (const [key, number] of Object.entries(numbers)) out[key] = { number };
	for (const a of root.querySelectorAll<HTMLElement>('.ref[data-tex]')) {
		const label = /\\(?:eq)?ref\s*\{([^{}]*)\}/.exec(a.dataset.tex ?? '')?.[1]?.trim();
		const said = (a.textContent ?? '').trim().replace(/^\((.*)\)$/, '$1');
		if (label && said && !out[label]) out[label] = { number: said };
	}
	for (const d of root.querySelectorAll<HTMLElement>('[data-label][data-number]')) out[d.dataset.label!] ??= { number: d.dataset.number! };
	for (const c of root.querySelectorAll<HTMLElement>('.cite[data-citekey]')) {
		const post = c.dataset.postnote ?? '';
		let said = (c.textContent ?? '').trim().replace(/^\[(.*)\]$/, '$1');
		if (post && said.endsWith(post)) said = said.slice(0, -post.length).replace(/,\s*$/, '');
		const keys = c.dataset.citekey!.split(',').map((k) => k.trim());
		if (keys.length === 1 && said) out[keys[0]] ??= { name: said };
	}
	return out;
}

const range = (src: string): { file: string; start: number; end: number } | null => {
	const m = /^(.*):(\d+):(\d+)$/.exec(src);
	return m ? { file: m[1], start: Number(m[2]), end: Number(m[3]) } : null;
};

/** The leaves of a paragraph's window: the elements with a `data-src` in it and none inside them, outside every statement and proof, side by side under one parent; none where they are not. */
function leavesIn(root: ParentNode, src: string): HTMLElement[] {
	const want = range(src);
	if (!want) return [];
	const hit = [...root.querySelectorAll<HTMLElement>(`[data-src^="${CSS.escape(want.file + ':')}"]`)].filter((el) => {
		const r = range(el.dataset.src ?? '');
		return r && r.file === want.file && !el.querySelector('[data-src]') && !el.closest('.env') && Math.min(r.end, want.end) > Math.max(r.start, want.start);
	});
	if (!hit.length || hit.some((el) => el.parentNode !== hit[0].parentNode)) return [];
	for (let i = 1; i < hit.length; i++) if (hit[i - 1].nextElementSibling !== hit[i]) return [];
	return hit;
}

/**
 * Draw each draft in place in `t`, the published markup about to be drawn: a statement's or proof's element keeps itself and its label and holds the drawing; a paragraph's leaves give way to one element holding it, which keeps the first's `data-src`. Each is marked `.draft` with the note `note`. A draft whose block the markup does not hold, or whose paragraph is not one run of leaves, is not drawn, and TeX's block will be.
 *
 * Parameters
 * ----------
 * t : HTMLTemplateElement
 *     The markup, changed in place.
 * shown : Iterable<Draft>
 *     The drafts standing now.
 * numbers : Record<string, string>
 *     Each result's number in the document drawn, by key.
 * macros : Macro[]
 *     The work's macros.
 * note : { text: string; title: string }
 *     The mark's words and its hover text.
 *
 * Returns
 * -------
 * number
 *     How many drafts were drawn.
 */
export function drawDrafts(t: HTMLTemplateElement, shown: Iterable<Draft>, numbers: Record<string, string>, macros: Macro[], note: { text: string; title: string }): number {
	const points = pointsIn(t.content, numbers);
	const mark = (): HTMLElement => {
		const n = document.createElement('span');
		n.className = 'draft-note';
		n.textContent = note.text;
		n.title = note.title;
		return n;
	};
	let drawn = 0;
	for (const { block } of shown) {
		if (block.kind === 'env') {
			const at = t.content.querySelector<HTMLElement>(`.env[data-src="${CSS.escape(block.src)}"]`);
			if (!at) continue;
			const label = at.querySelector(':scope > .env-label, :scope > summary');
			const body = document.createElement('div');
			body.className = 'draft-body';
			body.innerHTML = drawDraft(block.body, points, macros, at.dataset.style === 'plain');
			label?.append(mark());
			at.replaceChildren(...(label ? [label] : [mark()]), body);
			at.classList.add('draft');
		} else {
			const leaves = leavesIn(t.content, block.src);
			if (!leaves.length) continue;
			const at = document.createElement('div');
			at.className = 'draft';
			at.dataset.src = leaves[0].dataset.src!;
			at.innerHTML = drawDraft(block.body, points, macros);
			at.prepend(mark());
			leaves[0].replaceWith(at);
			for (const el of leaves.slice(1)) el.remove();
		}
		drawn++;
	}
	return drawn;
}
