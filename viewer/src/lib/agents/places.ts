// What Ask your agent is about from a pane's toolbar: words selected in the pane first, at the result they are in; then a result by its key, or the results on screen in a document's pane (the one at its top first) and the document as a whole, a section at the pane's top after the results. Each named as a reader names it (`linkName`), a result by the number its document shows, with the `quilt:` link every loom tool resolves, which the request gives without its key unless Show ids is on (`ask.ts`).

import type { Manifest } from '$lib/manifest/types';
import { here } from '$lib/here.svelte';
import { itemKey, type Item } from '$lib/workspace/item';
import { documentLabel, linkName } from '$lib/workspace/names';
import { agents as words } from '$lib/words/agents';
import type { Place } from './ask';

/** The most results on screen a toolbar offers beside the one at the pane's top. */
const SEEN = 4;

/** The places a pane's toolbar offers for `item`: the words selected in it, at their result; then a result alone, or the results on screen and then the document. */
export function placesFor(m: Manifest | null, item: Item): Place[] {
	if (!m) return [];
	const sel = here.selection;
	// the words as the reader sees them, a citation as drawn rather than its command
	const picked = sel && sel.item === itemKey(item) && sel.key && sel.text ? { key: sel.key, text: sel.read || sel.text } : null;
	if (item.kind !== 'document') {
		const whole = alone(m, item);
		return picked ? [{ ...whole, words: picked.text, label: words.ask.selected(whole.label ?? whole.name) }, whole] : [{ name: whole.name, href: whole.href }];
	}
	const own = linkName(m, `quilt:${item.id}`);
	const at = (key: string): Place => {
		const name = linkName(m, `quilt:${item.id}#${key}`);
		return { name: `${own}, ${name}`, href: `quilt:${item.id}#${key}`, label: name };
	};
	const doc: Place = { name: own, href: `quilt:${item.id}`, label: words.ask.document(own) };
	const out: Place[] = [];
	if (picked) {
		const place = picked.key === item.id ? doc : at(picked.key);
		out.push({ ...place, words: picked.text, label: words.ask.selected(picked.key === item.id ? own : (place.label ?? own)) });
	}
	const key = here.block[itemKey(item)]?.key;
	const top = key && key !== item.id && key !== picked?.key ? key : null;
	// a section at the top is where the reader is only roughly: the results on screen come before it
	const section = top !== null && m.nodes[top]?.kind === 'section';
	if (top && !section) out.push({ ...at(top), label: words.ask.reading(at(top).label ?? '') });
	const seen = (here.seen[itemKey(item)] ?? []).filter((k) => k !== top && k !== picked?.key && k !== item.id).slice(0, SEEN);
	for (const k of seen) out.push({ ...at(k), label: words.ask.onScreen(at(k).label ?? '') });
	if (top && section) out.push({ ...at(top), label: words.ask.reading(at(top).label ?? '') });
	return [...out, doc];
}

/** A result, work or file open on its own: a result named and linked through the document that numbers it, as `nodeName` numbers it, so its request carries a link a reader may see. */
function alone(m: Manifest, item: Item): Place {
	const node = item.kind === 'node' ? m.nodes[item.id] : undefined;
	const main = m.masters.find((x) => x.default)?.path;
	const doc = node ? ([main, ...Object.keys(node.numbers)].find((d) => d && node.numbers[d]?.number && m.masters.some((x) => x.path === d)) ?? null) : null;
	if (doc) {
		const name = linkName(m, `quilt:${doc}#${item.id}`);
		return { name: `${documentLabel(m.masters, doc)}, ${name}`, href: `quilt:${doc}#${item.id}`, label: name };
	}
	const own = linkName(m, `quilt:${item.id}`);
	return { name: own, href: `quilt:${item.id}`, label: own };
}

/** A selection's link without its quoted words, which the request quotes itself. */
export function withoutQuote(link: string): string {
	return link.replace(/[#&]quote=.*$/, '');
}
