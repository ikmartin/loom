// A `quilt:` link to a place with the words quoted there, as `loom link` writes one (`loom.links.quilt_link`, specs/dialect.md §2.13): what Quote copies and New note is given.

/** Percent-encoded as Python's `quote` encodes, keeping `keep`: `encodeURIComponent` leaves `!'()*` alone, which would end a Markdown link or read as markup. */
function encode(s: string, keep = ''): string {
	let out = encodeURIComponent(s).replace(/[!'()*]/g, (c) => '%' + c.charCodeAt(0).toString(16).toUpperCase());
	for (const c of keep) out = out.replaceAll(encodeURIComponent(c), c);
	return out;
}

/**
 * `quilt:KEY#PLACE&quote=WORDS`, the key, the place and the words each joined only where given.
 *
 * The words are joined by single spaces and every full stop in them is encoded, so a link read raw from a note keeps words that end a sentence; a key keeps its `/` and `:`.
 */
export function quoteLink(key: string, place = '', words = ''): string {
	const said = words.split(/\s+/).filter(Boolean).join(' ');
	const keys = [place, said ? 'quote=' + encode(said).replace(/\./g, '%2E') : ''].filter(Boolean);
	return `quilt:${encode(key, '/:')}${keys.length ? '#' + keys.join('&') : ''}`;
}
