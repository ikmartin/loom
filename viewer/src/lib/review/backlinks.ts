// The Notes list beside an item (`docs/design/model.md`, "Notes"): the files whose links name it, as the manifest's backlinks have them. A note is a file of the person's own; nothing here writes one, and the list is computed, so nobody edits it.

import type { Backlink, Manifest } from '$lib/manifest/types';

/** A file that links to an item, with each of its links to it in line order. */
export interface NoteFile {
	path: string;
	links: Backlink[];
}

/** The node a key is shown in: a key's node, a region's container, or the key itself. */
function nodeOf(m: Pick<Manifest, 'keys' | 'regions'>, key: string): string {
	const k = m.regions?.[key]?.container ?? key;
	return m.keys[k]?.node ?? k;
}

/**
 * The files whose links name the item `on`, by path, each with its links to it.
 *
 * A link to a node counts for the node and for each document that reaches it; a link to a document's place, for the document.
 *
 * Parameters
 * ----------
 * m : Manifest
 * on : str
 *     The item's key, `kind:id` (`itemKey`): a document, a work, a project file or a node.
 *
 * Returns
 * -------
 * list of NoteFile
 *     In path order; empty for an item no file links to, or a manifest with no backlinks.
 */
export function noteFiles(m: Pick<Manifest, 'backlinks' | 'keys' | 'regions' | 'nodes'> | null | undefined, on: string): NoteFile[] {
	if (!m || !on) return [];
	const cut = on.indexOf(':');
	const kind = on.slice(0, cut);
	const id = on.slice(cut + 1);
	const names = (b: Backlink): boolean => {
		if (b.kind === kind && b.key === id && kind !== 'node') return true;
		if (b.kind !== 'node') return false;
		const node = nodeOf(m, b.key);
		return kind === 'node' ? node === id : kind === 'document' && !!m.nodes[node]?.reached_by.includes(id);
	};
	const by = new Map<string, Backlink[]>();
	for (const b of m.backlinks ?? []) if (names(b)) by.set(b.from, [...(by.get(b.from) ?? []), b]);
	return [...by.keys()].sort().map((path) => ({ path, links: by.get(path)! }));
}

/** Where a note's link to the item is read: a plain-text note at the link's line (`L` and the line), a Markdown note or a notebook at the heading above the link, else the note whole. */
export function noteHref(m: Pick<Manifest, 'files'>, b: Backlink): string {
	const kind = m.files?.find((f) => f.path === b.from)?.kind;
	const at = kind === 'text' ? `L${b.line}` : kind === 'markdown' || kind === 'notebook' ? (b.at ?? '') : '';
	return `quilt:${b.from.split('/').map(encodeURIComponent).join('/')}${at ? `#${encodeURIComponent(at)}` : ''}`;
}
