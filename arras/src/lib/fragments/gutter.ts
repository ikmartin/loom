// The margin beside a text: one icon for every annotation drawn there, on the line its first mark stands on, a circle in its colour, shaped as a speech bubble where it says something; and one for every pending change, a teal pen: beside its words drawn in Markup, or, for one marked on an element rather than drawn in its words, beside that element's first line in either view. Where several start on one line the line has one count instead, which opens the line chooser, a short list of them to pick from. An icon opens its annotation's or change's popup.
//
// Drawn as a layer of absolutely placed buttons beside the fragment, measured from the marks, and drawn again whenever the marks or the text's layout change; a drawing keeps each icon whose line shows what it did.

import type { Annotation, Manifest, PendingChange } from '$lib/manifest/types';
import { colorOf, typeOf } from '$lib/review/annotationTypes';
import { plain, says } from '$lib/review/annotating.svelte';
import { changeById, kindName, summary } from '$lib/review/changes';
import { inert, liveChange } from './mount';
import { CHANGES, changeIds, leadOf, MARKED, MARKS } from './popup';

/** What the margin draws an icon for: an annotation, or a pending change. */
type Item = { id: string; a: Annotation; c?: undefined } | { id: string; c: PendingChange; a?: undefined };

const PEN = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>';

/** Two marks whose tops are this close stand on one line. */
const LINE = 8;
/** An icon's height and the least room between two. */
const ICON = 15;
const STEP = 17;

export interface GutterOptions {
	/** The annotation whose popup is open, whose icon is ringed. */
	open: string | null;
	/** An icon, or a row of the line chooser, was picked. */
	onpick: (id: string) => void;
}

/** The colour pair an icon or a dot is filled and edged with. */
export function dotVars(a: Pick<Annotation, 'look'>): string {
	const c = colorOf(a.look);
	return `--fill: var(--ann-${c}-band); --edge: var(--ann-${c})`;
}

/** What a row of the line chooser, or an icon's title, says of an annotation: its type, its author, and the start of its comment. */
export function itemLabel(m: Manifest, a: Annotation): string {
	const t = typeOf(m, a)?.name;
	const said = plain(a.body_html);
	return `${t ? t + ' · ' : ''}${a.author.label ?? a.author.id}${said ? ': ' + said.slice(0, 80) : ', no comment'}`;
}

/** What a row or an icon's title says of a change: what it is, and what it does. */
export function changeLabel(c: PendingChange): string {
	return `${kindName(c)}: ${summary(c)}`;
}

/** The first box of `el` as the page lays it out now. A mark in a block the browser is skipping (`content-visibility: auto`, theme.css) reads as the top of that block: measuring the mark would lay the block out, formulas and all, once per mark, 5 to 17 ms each on a long paper and the whole of a scroll's frames once the margin followed it. Such a block is laid out before it reaches the screen, and the margin is drawn again then (Fragment.svelte), so its icons move to their lines before they are seen. */
function firstRect(el: HTMLElement): DOMRect | undefined {
	if (el.checkVisibility?.({ contentVisibilityAuto: true }) === false && el.checkVisibility()) {
		for (let b = el.parentElement; b; b = b.parentElement) {
			if (!b.checkVisibility({ contentVisibilityAuto: true })) continue;
			const r = b.getBoundingClientRect();
			return new DOMRect(r.left, r.top, r.width, Math.min(r.height, 22));
		}
	}
	return el.getClientRects()[0];
}

/** The top-level annotations whose marks are drawn in `root`, and the changes drawn there in Markup, each with the top of its first mark, in reading order; several on one mark are each one. */
export function placed(root: HTMLElement, m: Manifest): (Item & { top: number })[] {
	const seen = new Set<string>();
	const out: (Item & { top: number })[] = [];
	for (const el of root.querySelectorAll<HTMLElement>(`${MARKS}, ${CHANGES}, ${MARKED}`)) {
		if (el.matches(`${CHANGES}, ${MARKED}`)) {
			const r = firstRect(el);
			const shown = el.matches(CHANGES) ? !!liveChange(el) : el.classList.contains('change-at') && !el.closest('.changes-off');
			if (!r || !shown) continue;
			for (const id of changeIds(el)) {
				const c = changeById(m, id);
				if (!c || seen.has(id)) continue;
				seen.add(id);
				// beside a marked element's first line, not the middle of all of it
				out.push({ id, c, top: el.matches(CHANGES) ? r.top + r.height / 2 : r.top + Math.min(r.height, 22) / 2 });
			}
			continue;
		}
		if (inert(el)) continue;
		const ids = idsOf(m, el).filter((id) => !seen.has(id));
		if (!ids.length) continue;
		const r = firstRect(el) ?? el.getBoundingClientRect();
		if (!r || (!r.width && !r.height && !el.classList.contains('gone'))) continue;
		for (const id of ids) {
			seen.add(id);
			out.push({ id, a: m.annotations[id], top: r.top + r.height / 2 });
		}
	}
	return out;
}

/** The top-level annotations a mark stands for, a reply standing for its parent. */
export function idsOf(m: Manifest, el: HTMLElement): string[] {
	const out: string[] = [];
	for (const id of (el.dataset.annotation ?? '').split(/\s+/).filter(Boolean)) {
		const lead = leadOf(m, [id]);
		if (m.annotations[lead] && !out.includes(lead)) out.push(lead);
	}
	return out;
}

let chooser: HTMLElement | null = null;

/** Close the line chooser, wherever it is open. */
export function closeChooser(): void {
	chooser?.remove();
	chooser = null;
}

function choose(m: Manifest, items: Item[], at: HTMLElement, onpick: (id: string) => void): void {
	closeChooser();
	const menu = document.createElement('div');
	menu.className = 'ann-pick';
	menu.setAttribute('role', 'menu');
	menu.dataset.testid = 'line-chooser';
	for (const it of items) {
		const row = document.createElement('button');
		row.type = 'button';
		row.className = 'pkrow';
		row.setAttribute('role', 'menuitem');
		const dot = document.createElement('span');
		const text = document.createElement('span');
		text.className = 'pkt';
		if (it.c) {
			row.dataset.change = it.id;
			dot.className = 'pk-c';
			dot.innerHTML = PEN;
			text.textContent = changeLabel(it.c);
		} else {
			row.dataset.annotation = it.id;
			dot.className = 'pk-a';
			dot.setAttribute('style', dotVars(it.a));
			text.textContent = itemLabel(m, it.a);
		}
		row.append(dot, text);
		row.addEventListener('click', () => {
			closeChooser();
			onpick(it.id);
		});
		menu.append(row);
	}
	(at.closest('.framed') ?? document.body).append(menu);
	chooser = menu;
	const r = at.getBoundingClientRect();
	const w = menu.offsetWidth;
	const h = menu.offsetHeight;
	menu.style.left = Math.max(8, Math.min(r.left - w - 8, window.innerWidth - w - 8)) + 'px';
	menu.style.top = Math.max(8, Math.min(r.top - 6, window.innerHeight - h - 8)) + 'px';
	(menu.querySelector('button') as HTMLElement | null)?.focus();
}

/** What each margin layer's icons act on: the manifest and the pick of its latest draw. An icon kept from an earlier draw reads them here, so it opens what the latest draw would. */
const current = new WeakMap<HTMLElement, { m: Manifest; onpick: (id: string) => void }>();

/** The key an icon was made for: everything it shows and holds but where it stands and whether it is ringed. */
const made = new WeakMap<Element, string>();

/** An icon for one line, and the key that says when an icon already drawn shows the same. */
function lineIcon(layer: HTMLElement, m: Manifest, items: Item[]): { key: string; ids: string[]; build: () => HTMLButtonElement } {
	const ids = items.map((it) => it.id);
	const act = (id: string) => current.get(layer)?.onpick(id);
	if (items.length === 1 && items[0].c) {
		const c = items[0].c;
		const label = changeLabel(c);
		return {
			key: `c ${c.id} ${label}`,
			ids,
			build: () => {
				const b = document.createElement('button');
				b.className = 'mi mc';
				b.innerHTML = PEN;
				b.title = label;
				b.setAttribute('aria-label', label);
				b.dataset.testid = 'margin-change';
				b.dataset.change = c.id;
				b.addEventListener('click', () => act(c.id));
				return b;
			}
		};
	}
	if (items.length === 1 && items[0].a) {
		const a = items[0].a;
		const label = itemLabel(m, a);
		const cls = 'mi ma' + (says(a) ? ' talk' : '') + (a.status !== 'open' ? ' settled' : '');
		return {
			key: `a ${a.id} ${cls} ${dotVars(a)} ${label}`,
			ids,
			build: () => {
				const b = document.createElement('button');
				b.className = cls;
				b.setAttribute('style', dotVars(a));
				b.title = label;
				b.setAttribute('aria-label', `Annotation. ${label}`);
				b.dataset.testid = 'margin-icon';
				b.dataset.annotation = a.id;
				b.addEventListener('click', () => act(a.id));
				return b;
			}
		};
	}
	// the chooser lists each item by what it says, so a count is kept only while every row would read the same
	const rows = items.map((it) => (it.c ? `${it.id} ${changeLabel(it.c)}` : `${it.id} ${dotVars(it.a)} ${itemLabel(m, it.a)}`));
	return {
		key: `g ${rows.join(' | ')}`,
		ids,
		build: () => {
			const b = document.createElement('button');
			b.className = 'mi mg';
			b.textContent = String(items.length);
			b.title = `${items.length} on this line`;
			b.setAttribute('aria-label', `${items.length} ${items.every((it) => it.a) ? 'annotations' : 'items'} on this line`);
			b.setAttribute('aria-haspopup', 'menu');
			b.dataset.testid = 'margin-count';
			// what it holds, so the line's items are found by id whichever line breaks the reader's fonts make
			b.dataset.items = ids.join(' ');
			b.addEventListener('click', (e) => {
				e.stopPropagation();
				if (chooser) return closeChooser();
				const now = current.get(layer);
				if (now) choose(now.m, items, b, now.onpick);
			});
			return b;
		}
	};
}

/**
 * Draw the margin of `root` into `layer`: one icon per annotation and per change drawn in Markup, a count where several share a line.
 *
 * An icon already drawn that shows the same as its line would now is kept, moved and ringed in place, so a draw that changes nothing touches nothing and an icon under the pointer is never replaced by its double.
 *
 * Parameters
 * ----------
 * layer : HTMLElement
 *     An absolutely placed column beside the text; its icons kept, made or removed.
 * root : HTMLElement
 *     The fragment whose marks are measured.
 * m : Manifest | null
 *     The manifest the marks are read against; null empties the margin.
 * opts : GutterOptions
 */
export function drawGutter(layer: HTMLElement, root: HTMLElement, m: Manifest | null, opts: GutterOptions): void {
	if (!m) {
		current.delete(layer);
		layer.replaceChildren();
		return;
	}
	current.set(layer, { m, onpick: opts.onpick });
	const base = layer.getBoundingClientRect().top;
	const marks = placed(root, m).sort((x, y) => x.top - y.top);
	const lines: { top: number; items: Item[] }[] = [];
	for (const { top, ...it } of marks) {
		const last = lines.at(-1);
		if (last && Math.abs(top - last.top) < LINE) last.items.push(it as Item);
		else lines.push({ top, items: [it as Item] });
	}
	const spare = new Map<string, Element[]>();
	for (const b of layer.children) {
		const key = made.get(b);
		if (key !== undefined) spare.set(key, [...(spare.get(key) ?? []), b]);
	}
	const want: Element[] = [];
	let last = -Infinity;
	for (const line of lines) {
		const top = Math.round(Math.max(line.top - base - ICON / 2, last + STEP));
		last = top;
		const icon = lineIcon(layer, m, line.items);
		let b = spare.get(icon.key)?.shift() as HTMLButtonElement | undefined;
		if (!b) {
			b = icon.build();
			b.type = 'button';
			made.set(b, icon.key);
		}
		if (b.style.top !== `${top}px`) b.style.top = `${top}px`;
		b.classList.toggle('on', opts.open !== null && icon.ids.includes(opts.open));
		want.push(b);
	}
	// in place where the order holds, so a kept icon is never taken off the page and put back
	want.forEach((b, i) => {
		const at = layer.children[i];
		if (at !== b) layer.insertBefore(b, at ?? null);
	});
	while (layer.children.length > want.length) layer.lastElementChild!.remove();
}

// the chooser closes on a press anywhere but itself and its count, and on Escape
if (typeof document !== 'undefined') {
	document.addEventListener(
		'pointerdown',
		(e) => {
			const t = e.target as Element | null;
			if (chooser && !t?.closest?.('.ann-pick, .mi.mg')) closeChooser();
		},
		true
	);
	document.addEventListener(
		'keydown',
		(e) => {
			if (e.key !== 'Escape' || !chooser) return;
			e.preventDefault();
			closeChooser();
		},
		true
	);
}
