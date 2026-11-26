import type { Manifest } from '$lib/manifest/types';

const ORDINAL = ['first', 'second', 'third', 'fourth', 'fifth', 'sixth', 'seventh', 'eighth', 'ninth', 'tenth'];

/**
 * A block loom knows by its place alone, keyed `FILE#ENV:N` for want of a label, as a person reads it: "Remark in appendix.tex", or "second Remark in appendix.tex" where its file holds more than one.
 *
 * Parameters
 * ----------
 * m : {nodes}
 *     The manifest's nodes, for the block's taxon and its file's others.
 * key : str
 *
 * Returns
 * -------
 * str | null
 *     Null for a key that is not such a place.
 */
export function placeName(m: { nodes: Record<string, { taxon?: string } | undefined> }, key: string): string | null {
	const at = /^(.+)#([A-Za-z*]+):(\d+)$/.exec(key);
	if (!at) return null;
	const [, file, env, nth] = at;
	const taxon = m.nodes[key]?.taxon || env.charAt(0).toUpperCase() + env.slice(1).replace(/\*$/, '');
	const n = Number(nth);
	const several = n > 1 || Object.keys(m.nodes).some((k) => k !== key && k.startsWith(`${file}#${env}:`));
	return `${several ? `${ORDINAL[n - 1] ?? `${n}th`} ` : ''}${taxon} in ${file.split('/').pop() ?? file}`;
}

type Placed = { taxon?: string; title?: string | null; name?: string; numbers?: Record<string, { number?: string } | undefined>; parent?: Record<string, string>; reached_by?: string[] };
const numbered = (n: Placed | undefined): boolean => Object.values(n?.numbers ?? {}).some((x) => !!x?.number);

/**
 * A block with no number, no title and no label to name it by, as before a draft compiles, named by its kind and where it stands in the document: "Remark in Appendix: an incomplete argument", the section it is in (else the document's file), with "second" and so on where that place holds several such of its kind, in the order the manifest lists them.
 *
 * Parameters
 * ----------
 * m : {nodes}
 * key : str
 *     A block's id.
 * master : str, default ''
 *     The document it is read in; '' for the first that reads it.
 *
 * Returns
 * -------
 * str | null
 *     Null where the block has no kind, or its document is unknown.
 */
export function unnumberedName(m: { nodes: Record<string, Placed | undefined> }, key: string, master = ''): string | null {
	const n = m.nodes[key];
	const doc = master || n?.reached_by?.[0] || '';
	if (!n?.taxon || !doc) return null;
	const sec = n.parent?.[doc];
	const s = sec ? m.nodes[sec] : undefined;
	const where = s?.title?.trim() || s?.name?.trim() || doc.split('/').pop() || doc;
	const like = Object.keys(m.nodes).filter((k) => {
		const o = m.nodes[k];
		// a block keyed by its place is named by its file (`placeName`), so it is not counted among these
		return !!o && o.taxon === n.taxon && !o.title?.trim() && !numbered(o) && !!o.reached_by?.includes(doc) && o.parent?.[doc] === sec && !/#[A-Za-z*]+:\d+$/.test(k);
	});
	const i = like.indexOf(key);
	return `${like.length > 1 && i >= 0 ? `${ORDINAL[i] ?? `${i + 1}th`} ` : ''}${n.taxon} in ${where}`;
}

/** A title with the ids a `\ref` left in it when there was no number to print, as before a draft compiles: each said by its number in `master` (else the default document's), else its title, else `unnumberedName`; the taxon already before it kept once. */
export function titleSaid(m: { nodes: Record<string, Placed | undefined>; masters: { path: string; default?: boolean }[] }, title: string, master = ''): string {
	const main = master || m.masters.find((x) => x.default)?.path || '';
	return title.replace(/(?:\b([A-Z][A-Za-z]*)\s+)?\b([a-z][a-z0-9]*-[0-9A-Za-z]{4})\b/g, (all: string, word: string | undefined, id: string) => {
		const n = m.nodes[id];
		if (!n) return all;
		const number = n.numbers?.[main]?.number ?? Object.values(n.numbers ?? {}).find((x) => x?.number)?.number;
		const said = number ?? n.title?.trim() ?? unnumberedName(m, id, main) ?? id;
		const lead = word ?? (number || n.title?.trim() ? (n.taxon ?? '') : '');
		return lead && !(said === unnumberedName(m, id, main) && word === n.taxon) ? `${lead} ${said}` : said;
	});
}

/** One readable identity, with numbering only in an explicitly selected document; a block known by its place alone is named for it (`placeName`), and one with no number, title or label by its kind and section (`unnumberedName`), so no name is an id. */
export function displayNode(m: Manifest, key: string, master = '') {
	const owner = m.keys[key]?.node ?? key;
	const node = m.nodes[key] ?? m.nodes[owner];
	if (!node) return { name: placeName(m, key) ?? key, context: '', id: key, accessible: key };
	const number = master ? node.numbers[master]?.number : '';
	const kind = [node.taxon, number].filter(Boolean).join(' ');
	const titled = (t?: string | null) => (t?.trim() ? titleSaid(m, t.trim(), master) : '');
	const placed = number ? '' : (placeName(m, owner) ?? unnumberedName(m, owner, master) ?? '');
	let name = node.name?.trim() || titled(node.title) || (number ? kind : placed || key);
	if (key !== owner && !m.nodes[key]) {
		const index = m.nodes[owner]?.proofs.indexOf(key) ?? -1;
		name = `Proof${index > 0 ? ` ${index + 1}` : ''} of ${node.name?.trim() || titled(node.title) || (number ? kind : placed) || kind || owner}`;
	}
	const section = master ? m.nodes[node.parent[master]] : undefined;
	// a name made of its kind and section says them already
	const own = !!placed && name.endsWith(placed);
	const context = own ? '' : [name === kind ? '' : kind, section?.name || section?.title].filter(Boolean).join(' · ');
	return { name, context, id: key, accessible: [...new Set([name, context, key].filter(Boolean))].join(' · ') };
}
