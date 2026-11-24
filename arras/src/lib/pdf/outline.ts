// A PDF's own outline (its bookmarks), read by pdf.js from the document the reader already has: each entry's title, its depth, and the page it goes to. What the Library shows as a work's contents where loom holds only the PDF (`docs/specs/library-views.md` §3.2), asked of nobody.

import { document_ } from './document';

export interface OutlineEntry {
	title: string;
	level: number;
	page: number | null;
}

/** The outline of the PDF at `url`, flattened in reading order; empty where it has none or cannot be read. */
export async function pdfOutline(url: string): Promise<OutlineEntry[]> {
	try {
		const doc = await document_(url);
		const top = await doc.getOutline();
		const out: OutlineEntry[] = [];
		type Item = { title: string; dest: string | unknown[] | null; items?: Item[] };
		const walk = async (items: Item[] | null | undefined, level: number) => {
			for (const it of items ?? []) {
				let page: number | null = null;
				try {
					const dest = typeof it.dest === 'string' ? await doc.getDestination(it.dest) : it.dest;
					const target = Array.isArray(dest) ? dest[0] : null;
					if (target && typeof target === 'object') page = (await doc.getPageIndex(target as Parameters<typeof doc.getPageIndex>[0])) + 1;
					else if (typeof target === 'number') page = target + 1;
				} catch {
					page = null;
				}
				out.push({ title: it.title, level, page });
				await walk(it.items, level + 1);
			}
		};
		await walk(top as Item[] | null, 1);
		return out;
	} catch {
		return [];
	}
}

/** The section an entry with a page stands in: the last outline entry starting at or before that page. */
export function sectionOf(outline: OutlineEntry[], page: number): number {
	let at = -1;
	outline.forEach((e, i) => {
		if (e.page !== null && e.page <= page && e.level === 1) at = i;
	});
	return at;
}
