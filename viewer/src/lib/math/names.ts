// The empty links in published prose named as a reader names what they point at, and the bare ids in it made links first (`ids.ts`): what Prose.svelte does to a body, and a Markdown file's page drawn as a fragment does to its own.
import type { Manifest } from '$lib/manifest/types';
import { linkName } from '$lib/workspace/names';
import { elided, linkIds } from './ids';

/**
 * Name every empty `quilt:` or `cited:` link in `node` as the viewer names the thing, after making each bare id the manifest knows a link.
 *
 * Parameters
 * ----------
 * node : Element
 *     Rendered prose.
 * m : Manifest
 *     What names the things linked.
 */
export function nameLinks(node: Element, m: Manifest): void {
	linkIds(node, (key) => !!m.nodes[key]);
	// the words before a link may already say its kind ("Corollary [](quilt:…)"), and then it reads its number alone
	let last: { el: Element; kind: string } | null = null;
	for (const a of node.querySelectorAll<HTMLAnchorElement>('a[href^="quilt:"], a[href^="cited:"]')) {
		if (a.textContent?.trim()) continue;
		const before = a.previousSibling?.nodeType === Node.TEXT_NODE ? (a.previousSibling.textContent ?? '') : '';
		const chained = last && a.previousSibling?.previousSibling === last.el ? last.kind : null;
		const { text, kind } = elided(before, linkName(m, a.getAttribute('href') ?? ''), chained);
		a.textContent = text;
		last = kind ? { el: a, kind } : null;
	}
}
