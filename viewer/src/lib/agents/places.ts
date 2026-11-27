// What Ask your agent is about from a pane's toolbar: words selected in the pane first, at the result they are in; then a result by its key, or a document as a whole and the result at the top of its pane, the latter first. Each named as a reader names it (`linkName`), a result in a document by the number that document shows, with the `quilt:` link every loom tool resolves.

import type { Manifest } from '$lib/manifest/types';
import { here } from '$lib/here.svelte';
import { itemKey, type Item } from '$lib/workspace/item';
import { linkName } from '$lib/workspace/names';
import { agents as words } from '$lib/words/agents';
import type { Place } from './ask';

/** The places a pane's toolbar offers for `item`: the words selected in it, at their result; then a result alone, or the result at the pane's top and then the document. */
export function placesFor(m: Manifest | null, item: Item): Place[] {
	if (!m) return [];
	const own = linkName(m, `quilt:${item.id}`);
	const sel = here.selection;
	const picked = sel && sel.item === itemKey(item) && sel.key && sel.text ? { key: sel.key, text: sel.text } : null;
	if (item.kind !== 'document') {
		const whole: Place = { name: own, href: `quilt:${item.id}`, label: own };
		return picked ? [{ ...whole, words: picked.text, label: words.ask.selected(own) }, whole] : [{ name: own, href: `quilt:${item.id}` }];
	}
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
	if (key && key !== item.id && key !== picked?.key) {
		const reading = at(key);
		out.push({ ...reading, label: words.ask.reading(reading.label ?? '') });
	}
	return [...out, doc];
}

/** A selection's link without its quoted words, which the request quotes itself. */
export function withoutQuote(link: string): string {
	return link.replace(/[#&]quote=.*$/, '');
}
