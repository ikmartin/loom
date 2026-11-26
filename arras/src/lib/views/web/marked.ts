// A search hit's words as one source for the converter, the match between two marks it passes through as text (U+E000 and U+E001), which the snippet turns into `<mark>` once the words are HTML.

/** Opens a match's mark in the source. */
export const OPEN = '';
/** Closes it. */
export const CLOSE = '';

/** The words around the match as one source with the match marked; a match inside a formula, `\(…\)` or `$…$`, marks the whole formula, so no mark stands inside the mathematics. */
export function marked(before: string, match: string, after: string): string {
	const dollars = (t: string) => [...t.matchAll(/(?<!\\)\$/g)].map((m) => m.index!);
	const paren = before.lastIndexOf('\\(');
	const open = dollars(before);
	let from = -1;
	let to = -1;
	if (paren > before.lastIndexOf('\\)')) {
		from = paren;
		const close = after.indexOf('\\)');
		to = close < 0 ? -1 : close + 2;
	} else if (open.length % 2) {
		from = open[open.length - 1];
		const close = dollars(after)[0];
		to = close === undefined ? -1 : close + 1;
	}
	if (from >= 0) {
		match = before.slice(from) + match + (to > 0 ? after.slice(0, to) : '');
		before = before.slice(0, from);
		if (to > 0) after = after.slice(to);
	}
	return `${before}${OPEN}${match}${CLOSE}${after}`;
}
