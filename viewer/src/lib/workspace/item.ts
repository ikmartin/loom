// What reading mode shows (plan 0.13.3): an **item** is a thing with an address, a renderer, controls and optionally internal views. This module is the address half — what an item is, and the codec between an item and the route URL that names it. Nothing here renders.
//
// An item's identity is its kind and id. Its view and its place in it are state, not identity: a second tab of one document would be one document in two states (W8).

import { base } from '$app/paths';
import type { Manifest } from '$lib/manifest/types';
import { anchorId, canonStem, canonUrl, keyFromParam, masterName, masterUrl, nodeUrl, workUrl } from '$lib/nav';
import { route } from '$lib/paths';
import { placeParams, readKeys, type WorkLink } from '$lib/worklink';

export type ItemKind = 'document' | 'work' | 'node' | 'context' | 'session' | 'page' | 'file' | 'pdf' | 'notes';

/** A place on a work's page: the work-link keys without the work's identifier, which the item already names. */
export type Place = Omit<WorkLink, 'id'>;

export interface Item {
	kind: ItemKind;
	/** A document's path, a work's reference, a node's key, a session's id, a project file's path; a compiled PDF's is its document's. */
	id: string;
	/** An internal view: a session's `did`; absent means the first. */
	view?: string;
	/** An element to scroll to, by its published id: a document's section or result, a node's proof, a file's heading; a PDF file's `page=N`. */
	anchor?: string;
	/** Where on a work's pages. */
	place?: Place;
	/** An annotation to open at its mark on arrival: what a link to an annotation names. */
	note?: string;
	/** Words a `quilt:` link quotes, lit where the item opens: in a document or a node, or on a project PDF's pages; a work's are its `place.quote`. */
	quote?: string;
	/** A document's review comparison, which the review page opens by URL (`review`, `cause`). */
	params?: Record<string, string>;
	/** The size the reader gave this open item, kept with it in its address: a PDF's zoom (a document's compiled PDF, a project PDF, a work's paper), an HTML draft's text size in px. Absent until one is given, and the item is read at the starting size for its kind. */
	size?: number;
	/** Stamped by the workspace each time the item is opened or revealed, so its renderer goes to the place again even when the place is unchanged. */
	seq?: number;
}

/** What the manifest must say for a document path to be told from a landmark and a stem to be resolved. */
export interface Documents {
	masters: { path: string }[];
	canon?: { path: string }[];
}

const DOC_PARAMS = ['review', 'cause'] as const;

/** The identity of an item, for finding it among the open ones. */
export function itemKey(i: Pick<Item, 'kind' | 'id'>): string {
	return `${i.kind}:${i.id}`;
}

/** Whether a document path is a landmark rather than a draft. */
export function isLandmark(m: Documents | null, path: string): boolean {
	return !!m?.canon?.some((c) => c.path === path);
}

/**
 * The item a route URL names, or null when it names none.
 *
 * Parameters
 * ----------
 * m : Documents | null
 *     The manifest, to resolve a document's stem to its path; with none, the stem stands in.
 * href : string
 *     A path with its query and hash, with or without the app's base; an absolute same-origin URL is accepted too.
 *
 * Returns
 * -------
 * Item | null
 *     The item, carrying the view, anchor and place the URL names.
 */
export function itemFromPath(m: Documents | null, href: string): Item | null {
	let url: URL;
	try {
		url = new URL(href, 'http://x');
	} catch {
		return null;
	}
	let path = url.pathname;
	if (base && path.startsWith(base)) path = path.slice(base.length) || '/';
	const [, head, ...rest] = path.split('/');
	const tail = rest.join('/');
	if (!tail) return null;
	const anchor = url.hash ? safe(url.hash.slice(1)) : undefined;
	const query = url.searchParams;
	const note = query.get('note') || undefined;
	const quoted = query.get('quote')?.trim() ? { quote: query.get('quote')!.trim() } : {};
	const n = Number(query.get('size') ?? '');
	const size = query.has('size') && Number.isFinite(n) && n > 0 ? { size: n } : {};
	switch (head) {
		case 'master':
		case 'canon': {
			// a landmark is addressed by its stem, a document by its name, which may hold slashes
			const at = head === 'canon' ? safe(tail) : tail.split('/').map(safe).join('/');
			const id =
				head === 'canon'
					? ((m?.canon ?? []).find((d) => canonStem(d.path) === at)?.path ?? at)
					: ((m?.masters ?? []).find((d) => masterName(d.path) === at)?.path ?? at);
			const params: Record<string, string> = {};
			for (const k of DOC_PARAMS) {
				const v = query.get(k);
				if (v) params[k] = v;
			}
			return { kind: 'document', id, ...(anchor ? { anchor } : {}), ...(note ? { note } : {}), ...quoted, ...(Object.keys(params).length ? { params } : {}), ...size };
		}
		case 'library': {
			const place = readKeys({ id: '' }, url.search.slice(1)) as WorkLink;
			const { id: _drop, ...keys } = place;
			return { kind: 'work', id: safe(tail), ...(Object.keys(keys).length ? { place: keys } : {}), ...size };
		}
		case 'node':
			return { kind: 'node', id: keyFromParam(tail), ...(anchor ? { anchor } : {}), ...(note ? { note } : {}), ...quoted };
		case 'context':
			return { kind: 'context', id: keyFromParam(tail) };
		case 'session':
			return { kind: 'session', id: safe(tail), ...(query.get('view') ? { view: query.get('view')! } : {}) };
		case 'page':
			return { kind: 'page', id: safe(tail) };
		case 'file':
			return { kind: 'file', id: tail.split('/').map(safe).join('/'), ...(anchor ? { anchor } : {}), ...quoted, ...size };
		case 'notes':
			return { kind: 'notes', id: 'all' };
		case 'pdf': {
			const at = tail.split('/').map(safe).join('/');
			return { kind: 'pdf', id: (m?.masters ?? []).find((d) => masterName(d.path) === at)?.path ?? at, ...(anchor ? { anchor } : {}), ...size };
		}
		default:
			return null;
	}
}

/**
 * The route URL that names an item, with the app's base: the inverse of `itemFromPath`.
 *
 * Parameters
 * ----------
 * m : Documents | null
 *     The manifest, to tell a landmark from a draft.
 * item : Item
 *     The item, with whatever view, anchor and place it is at.
 *
 * Returns
 * -------
 * str
 *     Path, query and hash.
 */
export function pathFor(m: Documents | null, item: Item): string {
	const hash = item.anchor ? '#' + item.anchor : '';
	const sized = item.size ? '?size=' + item.size : '';
	switch (item.kind) {
		case 'document': {
			const at = isLandmark(m, item.id) ? canonUrl(item.id) : masterUrl(item.id);
			const q = new URLSearchParams();
			for (const k of DOC_PARAMS) if (item.params?.[k]) q.set(k, item.params[k]);
			if (item.note) q.set('note', item.note);
			if (item.quote) q.set('quote', item.quote);
			if (item.size) q.set('size', String(item.size));
			return at + (q.size ? '?' + q : '') + hash;
		}
		case 'work': {
			const q = placeParams(item.place ?? {});
			if (item.size) q.set('size', String(item.size));
			return workUrl(item.id) + (q.size ? '?' + q : '');
		}
		case 'node': {
			const q = new URLSearchParams();
			if (item.note) q.set('note', item.note);
			if (item.quote) q.set('quote', item.quote);
			return nodeUrl(item.id) + (q.size ? '?' + q : '') + hash;
		}
		case 'context':
			return route('/context/' + item.id.split('/').map(encodeURIComponent).join('/'));
		case 'session':
			return route('/session/' + encodeURIComponent(item.id)) + (item.view ? '?view=' + encodeURIComponent(item.view) : '');
		case 'page':
			return route('/page/' + encodeURIComponent(item.id));
		case 'file': {
			const q = new URLSearchParams();
			if (item.quote) q.set('quote', item.quote);
			if (item.size) q.set('size', String(item.size));
			return fileRoute(item.id) + (q.size ? '?' + q : '') + hash;
		}
		case 'pdf':
			return pdfRoute(item.id) + sized + hash;
		case 'notes':
			return route('/notes');
	}
}

/** A document's compiled PDF's address in the viewer: `/pdf/` and the document's name, as `/master/` has it. */
export function pdfRoute(path: string): string {
	return route('/pdf/' + masterName(path).split('/').map(encodeURIComponent).join('/'));
}

/**
 * What a row of the project's tree opens: a document as itself; an included `.tex` file as the document that reads it, at its first key, where it holds one (V7); every other file as a file item.
 */
export function itemForFile(m: Manifest, path: string): Item {
	const file = m.files?.find((f) => f.path === path);
	if (file?.kind === 'document' || m.masters.some((x) => x.path === path) || !!m.canon?.some((c) => c.path === path)) return { kind: 'document', id: path };
	if (file?.kind === 'tex') {
		const first = Object.entries(m.nodes)
			.filter(([, n]) => n.file === path && n.reached_by.length)
			.sort(([, a], [, b]) => a.src[0] - b.src[0])[0];
		if (first) {
			const [key, n] = first;
			const main = m.masters.find((x) => x.default)?.path;
			return { kind: 'document', id: main && n.reached_by.includes(main) ? main : n.reached_by[0], anchor: anchorId(key) };
		}
	}
	return { kind: 'file', id: path };
}

/**
 * The region of a node, a labelled equation, that a node item's anchor is at: what a link to the equation names, and what its hover card draws.
 *
 * A region's published id is its key's slug (`anchorId`), so it is found by that, among the regions the item's node holds; a proof's region is held by its statement's node.
 *
 * Parameters
 * ----------
 * m : Pick<Manifest, 'keys' | 'regions'>
 * item : Item
 *     Any item; only a node item with an anchor can be at a region.
 *
 * Returns
 * -------
 * str | null
 *     The region's key (`KEY#label`), or null.
 */
export function regionAt(m: Pick<Manifest, 'keys' | 'regions'>, item: Item): string | null {
	if (item.kind !== 'node' || !item.anchor) return null;
	for (const [key, region] of Object.entries(m.regions ?? {})) {
		if (anchorId(key) === item.anchor && (m.keys[region.container]?.node ?? region.container) === item.id) return key;
	}
	return null;
}

/** A project file's address in the viewer: `/file/` and its path, each segment encoded. */
export function fileRoute(path: string): string {
	return route('/file/' + path.split('/').map(encodeURIComponent).join('/'));
}

function safe(s: string): string {
	try {
		return decodeURIComponent(s);
	} catch {
		return s;
	}
}
