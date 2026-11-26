// What Ask your agent is about from a pane's toolbar: a result by its key, or a document as a whole and the result at the top of its pane, the latter first. Each named as a reader names it (`linkName`), with the `quilt:` link every loom tool resolves.

import type { Manifest } from '$lib/manifest/types';
import { here } from '$lib/here.svelte';
import { itemKey, type Item } from '$lib/workspace/item';
import { linkName } from '$lib/workspace/names';
import { agents as words } from '$lib/words/agents';
import type { Place } from './ask';

/** The places a pane's toolbar offers for `item`: a result alone, or the result at the pane's top and then the document. */
export function placesFor(m: Manifest | null, item: Item): Place[] {
	if (!m) return [];
	const own = linkName(m, `quilt:${item.id}`);
	if (item.kind !== 'document') return [{ name: own, href: `quilt:${item.id}` }];
	const doc: Place = { name: own, href: `quilt:${item.id}`, label: words.ask.document(own) };
	const key = here.block[itemKey(item)]?.key;
	if (!key || key === item.id) return [doc];
	const at = linkName(m, `quilt:${key}`);
	return [{ name: `${own}, ${at}`, href: `quilt:${item.id}#${key}`, label: words.ask.reading(at) }, doc];
}

/** A selection's link without its quoted words, which the request quotes itself. */
export function withoutQuote(link: string): string {
	return link.replace(/[#&]quote=.*$/, '');
}
