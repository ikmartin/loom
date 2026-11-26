// Where a followed link opens (plan 0.14): **one rule, for every link in the viewer.** A link names an item and a place in it. If the item is already open, in either pane, it is brought to the front of its pane at that place and the pane takes focus — a document's links to its own content are the same case. If it is not open, it opens as a new tab in the pane the reader is not in, so both ends of the connection stay on screen (V5); with one pane, the second is made. A click outside every pane — the side panel, the rail — is a choice of what to read, and opens in the focused pane.
//
// Two link forms name things (specs/dialect.md §2.13): `quilt:KEY[#PLACE]` for what the quilt owns — a node, a document, an annotation, a session, a project file by its path — and `cited:SCHEME:VALUE` for a place in a work, which opens at the identifier's own service, outside the viewer, since nothing the manifest says names the work's pages. The viewer's own paths are read too. `app:NAME` asks the publisher to open an application, on this click; any other scheme opens outside the viewer, whose tab it never replaces.
//
// One capture-phase listener for the whole viewer, so no renderer decides for itself and a link the router would otherwise follow is answered before it does.

import { goto } from '$app/navigation';
import type { Manifest } from '$lib/manifest/types';
import { externalUrl, isWorkLink, parseWorkLink } from '$lib/worklink';
import { anchorId, keyTarget, keyUrl, nodeUrl } from '$lib/nav';
import { isDocument } from '$lib/review/run';
import { documentOf } from '$lib/review/annotating.svelte';
import { itemFromPath, itemKey, pathFor, type Item } from './item';
export { itemForFile } from './item';
import { workspace } from './store.svelte';
import { write } from '$lib/write';

/** The kinds of project file a `quilt:` link opens as a file item; a `.tex` file is linked by its document or its keys. */
const LINKED = new Set(['markdown', 'html', 'pdf', 'image', 'notebook', 'text', 'other']);
/** Schemes never followed anywhere: what a page could run as script or read off this machine. */
const NEVER = /^(?:javascript|vbscript|data|file|blob):/i;

/** The pane an element stands in, or -1 when it is in none. */
export function paneOfElement(el: Element | null): number {
	const at = el?.closest<HTMLElement>('[data-pane]');
	return at ? Number(at.dataset.pane) : -1;
}

/**
 * The item a link names, or null when it names nothing to read in the viewer.
 *
 * A `cited:` link names a place in a work by the work's identifier, which no item answers: it opens outside (`outsideOf`).
 */
export function itemForHref(m: Manifest, href: string): Item | null {
	if (href.startsWith('quilt:')) return itemForQuilt(m, href.slice('quilt:'.length));
	if (isWorkLink(href)) return null;
	let url: URL;
	try {
		url = new URL(href, location.href);
	} catch {
		return null;
	}
	if (url.origin !== location.origin) return null;
	return itemFromPath(m, url.pathname + url.search + url.hash);
}

/**
 * The item a `quilt:` link names, by the key after the scheme, or null when the manifest knows no such thing.
 *
 * An annotation opens what it is on, with its box open (`note`); a session its transcript; a document path its document, at the place after `#`; a work by its reference its pages, at `page=N`; any other key its node, at the place in it. Words the link quotes (`&quote=`) go with the item, lit where it opens.
 */
export function itemForQuilt(m: Manifest, body: string): Item | null {
	const { key, place, quote } = quiltParts(body);
	if (!key) return null;
	const quoted = quote ? { quote } : {};
	const note = m.annotations[key];
	if (note) return noteItem(m, threadOf(m, note.id), note.target);
	if ((m.sessions ?? []).some((s) => s.id === key) || m.threads[key]) return { kind: 'session', id: key };
	if (key === 'state' && m.research_state) return { kind: 'page', id: 'state' };
	if (isDocument(m, key)) return { kind: 'document', id: key, ...(place ? { anchor: anchorId(place) } : {}), ...quoted };
	const file = m.files?.find((f) => f.path === key);
	if (file && LINKED.has(file.kind)) return { kind: 'file', id: key, ...(place ? { anchor: place } : {}), ...(file.kind === 'pdf' || file.kind === 'markdown' ? quoted : {}) };
	if (REFERENCE.test(key)) {
		const page = Number(/^page=([1-9]\d*)$/.exec(place)?.[1] ?? 0);
		const at = { ...(page ? { page } : {}), ...quoted };
		return { kind: 'work', id: key, ...(Object.keys(at).length ? { place: at } : {}) };
	}
	const at = itemFromPath(m, keyUrl(m, key));
	if (!at) return null;
	if (!place) return { ...at, ...quoted };
	// a place in a node is a region of it (`KEY#label`) or another key it holds, such as its proof
	const region = m.regions?.[`${key}#${place}`];
	return { ...at, anchor: anchorId(region ? `${key}#${place}` : place), ...quoted };
}

/** A work's reference, the library node a `quilt:` link names a work by (`nodes.md` §3): a stem and `-ref`. */
const REFERENCE = /^[A-Za-z0-9]+-[0-9A-Z]{4}-ref$/;

/**
 * A `quilt:` link's body cut at its first `#` into the key, the place and the quoted words, each decoded; a region's key holds a `#` of its own, so a document's place may be one.
 *
 * The words (`quote=`, joined to the place by `&`, or alone) are cut out before decoding, so an `&` in them, written `%26`, stays in them.
 */
export function quiltParts(body: string): { key: string; place: string; quote: string } {
	const cut = body.indexOf('#');
	const parts = cut < 0 ? [] : body.slice(cut + 1).split('&');
	const said = parts.find((p) => p.startsWith('quote='));
	return {
		key: decode(cut < 0 ? body : body.slice(0, cut)),
		place: decode(parts.filter((p) => !p.startsWith('quote=')).join('&')),
		quote: said ? decode(said.slice('quote='.length).replace(/\+/g, ' ')).replace(/\s+/g, ' ').trim() : ''
	};
}

/** Percent-decoded, or as written where it is not valid percent-encoding. */
function decode(s: string): string {
	try {
		return decodeURIComponent(s);
	} catch {
		return s;
	}
}

/**
 * What a hover card shows for a key: the node that holds it, at the display's anchor where the key is a region of it.
 *
 * Parameters
 * ----------
 * m : Manifest
 * key : str
 *     A node's key, any key it holds (a proof), or a region's (`KEY#label`).
 *
 * Returns
 * -------
 * Item | null
 *     A node item; null where the manifest holds no node for the key.
 *
 * See Also
 * --------
 * previewOfHref : what a link previews, for a link that names no key.
 */
export function previewOfKey(m: Manifest, key: string): Item | null {
	const region = m.regions?.[key];
	const k = region ? region.container : key;
	const n = m.keys[k]?.node ?? k;
	if (!m.nodes[n]) return null;
	return { kind: 'node', id: n, ...(region ? { anchor: anchorId(key) } : {}) };
}

/**
 * What a hover card shows for a link to `href`, before the card's own checks; a kind with no small render still previews nothing.
 *
 * A document at a place previews what is at the place, as `previewOfKey` has it, and nothing where the place is no key the manifest knows; a document alone previews nothing. A node at one of its regions (`quilt:KEY#label`) previews the region, any other node the node; anything else is the item the link names. A click goes where `itemForHref` says, so a document at a place opens the document there.
 *
 * Parameters
 * ----------
 * m : Manifest
 * href : str
 *     A `quilt:` or `cited:` link, or a viewer path.
 *
 * Returns
 * -------
 * Item | null
 *     The item the card renders, or null for a link that previews nothing.
 *
 * See Also
 * --------
 * previewOfKey : what a reference that names its key (`data-target`) previews.
 */
export function previewOfHref(m: Manifest, href: string): Item | null {
	if (href.startsWith('quilt:')) {
		const { key, place } = quiltParts(href.slice('quilt:'.length));
		if (key && isDocument(m, key)) return place ? previewOfKey(m, place) : null;
		if (key && place && m.regions?.[`${key}#${place}`]) return previewOfKey(m, `${key}#${place}`);
	}
	const item = itemForHref(m, href);
	return item?.kind === 'node' ? previewOfKey(m, item.id) : item;
}

/**
 * Ask the publisher to open the application `app`, or the file `file` in its application, for this click; the refusal, where there is one, is the answer.
 */
export async function openOutside(target: { app: string } | { file: string }): Promise<string> {
	const done = await write('open', target);
	return done.ok ? '' : (done.error?.message ?? 'loom could not open it');
}

/** The address a `cited:` link opens outside the viewer, its identifier's own service; '' for a scheme none resolves, or an href that is no `cited:` link. */
export function outsideOf(href: string): string {
	const link = parseWorkLink(href);
	return (link && externalUrl(link)) || '';
}

/** Follow a link a framed page handed over (`HtmlFrame`): a `quilt:` link as any link in the viewer, a `cited:` one at its identifier's service, an `app:` one by the publisher; nothing else. */
export function followFromFrame(m: Manifest, href: string, from: number): void {
	if (/^app:/i.test(href)) {
		void openOutside({ app: decodeURIComponent(href.slice(4)) });
		return;
	}
	if (isWorkLink(href)) {
		const out = outsideOf(href);
		if (out) window.open(out, '_blank', 'noopener');
		return;
	}
	if (!/^quilt:/i.test(href)) return;
	const item = itemForHref(m, href);
	if (item) follow(item, from, m);
}

/** The note a reply answers, and so on up: a box opens on a thread, by the note that began it. */
function threadOf(m: Manifest, id: string): string {
	const seen = new Set<string>();
	let at = id;
	while (!seen.has(at)) {
		seen.add(at);
		const up = m.annotations[at]?.in_reply_to;
		if (!up || !m.annotations[up]) break;
		at = up;
	}
	return at;
}

/** Where an annotation is read: its target, with the annotation to open there. One on a project PDF opens the file at its page; one on a work, by its reference, the work at its page, or the work itself for one on the whole work. A box round an equation is filed under the region's key (`KEY#label`), and is read in the node that holds it. */
function noteItem(m: Manifest, id: string, target: { key: string; work?: string | null; page?: number | null; file?: string | null }): Item | null {
	if (target.file) return { kind: 'file', id: target.file, ...(target.page ? { anchor: `page=${target.page}` } : {}), note: id };
	if (target.work) return target.page ? { kind: 'work', id: target.work, place: { page: target.page, annot: id } } : { kind: 'work', id: target.work };
	// a note on no block names no key: it opens in the document it was written in, beside its card in the list
	if (!target.key) {
		const a = m.annotations[id];
		const doc = a ? documentOf(m, a) : '';
		return isDocument(m, doc) ? { kind: 'document', id: doc, note: id } : null;
	}
	if (isDocument(m, target.key)) return { kind: 'document', id: target.key, note: id };
	const key = m.regions?.[target.key]?.container ?? target.key;
	const at = itemFromPath(m, keyTarget(m, key) ?? nodeUrl(key));
	return at ? { ...at, note: id } : null;
}

/**
 * Open what a link names, from the pane it stands in: where it is open, it is revealed there; otherwise it opens in the other pane.
 *
 * A node counts as open where an open document holds it (DR-280-ikmartin): the document is revealed at the node rather than the node opened beside it.
 *
 * Parameters
 * ----------
 * item : Item
 *     What to open, at its place.
 * from : number
 *     The pane the link is in, or -1 for a link outside every pane, which opens in the focused pane.
 * m : Manifest, optional
 *     What says which documents hold a node; without it a node is open only as itself.
 */
export function follow(item: Item, from: number, m: Manifest | null = null): void {
	const at = workspace.paneOf(itemKey(item));
	if (at >= 0) return workspace.openIn(item, at);
	const holder = m ? holding(m, item, from) : null;
	if (holder) return workspace.openIn(holder.item, holder.pane);
	if (from < 0) workspace.here(item);
	else workspace.beside(item, from);
}

/**
 * The open document a node link is revealed in, at the node, or null when none holds it.
 *
 * The document the link stands in first; then one on screen; then, among tabs behind others, the one last looked at. The name the link was given is the default document's, so it may read differently where it lands.
 */
export function holding(m: Manifest, item: Item, from: number): { item: Item; pane: number } | null {
	if (item.kind !== 'node') return null;
	const within = new Set(m.nodes[item.id]?.reached_by ?? []);
	if (!within.size) return null;
	const open: { doc: Item; pane: number; front: boolean }[] = [];
	workspace.panes.forEach((p, pane) => {
		for (const it of p.items) if (it.kind === 'document' && within.has(it.id)) open.push({ doc: it, pane, front: p.active === itemKey(it) });
	});
	if (!open.length) return null;
	const rank = (o: (typeof open)[number]) => (o.front && o.pane === from ? 3 : o.front ? 2 : 1);
	open.sort((a, b) => rank(b) - rank(a) || workspace.shownAt(itemKey(b.doc)) - workspace.shownAt(itemKey(a.doc)));
	const { doc, pane } = open[0];
	return { item: { kind: 'document', id: doc.id, anchor: item.anchor ?? anchorId(item.id), ...(item.note ? { note: item.note } : {}) }, pane };
}

/**
 * Close every session but `id`, wherever it stands: one transcript is open at a time, the one read last.
 */
export function soleSession(id: string): void {
	for (let p = workspace.panes.length - 1; p >= 0; p--) {
		for (const it of [...workspace.panes[p].items]) if (it.kind === 'session' && it.id !== id) workspace.close(p, itemKey(it));
	}
}

/**
 * Install the listener. Returns its removal.
 *
 * Parameters
 * ----------
 * active : () => boolean
 *     Whether reading mode is on screen; elsewhere the router follows links as it always did, and arriving in reading mode opens what was followed.
 * manifest : () => Manifest | null
 */
export function interceptLinks(active: () => boolean, manifest: () => Manifest | null): () => void {
	const click = (e: MouseEvent) => {
		if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
		const a = (e.target as Element | null)?.closest?.('a');
		const href = a?.getAttribute('href');
		if (!a || !href || a.target === '_blank' || a.hasAttribute('download')) return;
		const m = manifest();
		if (!m) return;
		const from = paneOfElement(a);
		// a jump within the text the link is in: the same item at a new place, revealed where it is like any other
		if (href.startsWith('#')) {
			const here = from >= 0 ? workspace.active(from) : null;
			if (!here) return;
			e.preventDefault();
			follow({ ...here, anchor: decodeURIComponent(href.slice(1)), note: undefined }, from);
			return;
		}
		// a browser drops controls and spaces from an address before it reads the scheme, so this does too
		if (NEVER.test(href.replace(/[\x00-\x20]/g, ''))) {
			e.preventDefault();
			return;
		}
		if (/^app:/i.test(href)) {
			// an application, opened by the publisher on this machine; where none is served, the link says why
			e.preventDefault();
			void openOutside({ app: decodeURIComponent(href.slice(4)) }).then((why) => {
				if (why) a.title = why;
			});
			return;
		}
		const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(href)?.[1]?.toLowerCase();
		const outside = !!scheme && scheme !== 'quilt' && scheme !== 'cited' && (scheme === 'http' || scheme === 'https' ? new URL(href).origin !== location.origin : true);
		if (outside) {
			// another site, or another application's own scheme, which the browser asks about: never in the viewer's tab
			e.preventDefault();
			window.open(href, '_blank', 'noopener');
			return;
		}
		if (isWorkLink(href)) {
			// a work by its identifier, at that identifier's own service: never in the viewer's tab
			e.preventDefault();
			const out = outsideOf(href);
			if (out) window.open(out, '_blank', 'noopener');
			return;
		}
		const quilt = href.startsWith('quilt:');
		// outside reading mode the router follows its own paths; a `quilt:` link it cannot, so it goes to its item's page
		if (!active() && !quilt) return;
		// a `quilt:` link is never a browser navigation, even to nothing
		if (quilt) e.preventDefault();
		const item = itemForHref(m, href);
		if (!item) return;
		e.preventDefault();
		if (active()) follow(item, from, m);
		else void goto(pathFor(m, item));
	};
	document.addEventListener('click', click, true);
	return () => document.removeEventListener('click', click, true);
}
