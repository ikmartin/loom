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

/** One readable identity, with numbering only in an explicitly selected document; a block known by its place alone is named for it (`placeName`). */
export function displayNode(m: Manifest, key: string, master = '') {
	const owner = m.keys[key]?.node ?? key;
	const node = m.nodes[key] ?? m.nodes[owner];
	if (!node) return { name: placeName(m, key) ?? key, context: '', id: key, accessible: key };
	const number = master ? node.numbers[master]?.number : '';
	const kind = [node.taxon, number].filter(Boolean).join(' ');
	let name = node.name?.trim() || node.title?.trim() || (number ? kind : (placeName(m, owner) ?? key));
	if (key !== owner && !m.nodes[key]) {
		const index = m.nodes[owner]?.proofs.indexOf(key) ?? -1;
		name = `Proof${index > 0 ? ` ${index + 1}` : ''} of ${node.name?.trim() || node.title?.trim() || kind || owner}`;
	}
	const section = master ? m.nodes[node.parent[master]] : undefined;
	const context = [name === kind ? '' : kind, section?.name || section?.title].filter(Boolean).join(' · ');
	return { name, context, id: key, accessible: [...new Set([name, context, key].filter(Boolean))].join(' · ') };
}
