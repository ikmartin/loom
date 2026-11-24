// Links into a work (specs/dialect.md §2.13): `cited:<scheme>:<value>?page=N&quote=…` names a place in a work by its global identifier, never by a citekey, so it survives a bibliography re-export and means the same thing to a collaborator whose citekeys differ. The keys are the app URL's own -- `page`, `span`, `box`, `annot`, spelled out because agents and authors write them by hand -- so there is one locator syntax with two prefixes. The `#page=`/`#quote=` fragment form is read too, as the spec allows.
// The link form is the interface's; nothing here knows the publisher.

export interface WorkLink {
	/** `scheme:value`, the scheme lowercased. */
	id: string;
	page?: number;
	quote?: string;
	/** Offsets into the page's committed text, `start-end`. */
	span?: [number, number];
	/** A rectangle on the page, in points with the origin at the top left. */
	box?: [number, number, number, number];
	/** An annotation whose own anchor says where; the form most links should take, since it survives re-anchoring. */
	annot?: string;
}

const PREFIX = 'cited:';

/** Whether an href is a work link. */
export function isWorkLink(href: string | null | undefined): boolean {
	return !!href && href.toLowerCase().startsWith(PREFIX);
}

/** A work link's identifier and anchor, or null when the href is not one. */
export function parseWorkLink(href: string): WorkLink | null {
	if (!isWorkLink(href)) return null;
	const body = href.slice(PREFIX.length);
	// the query is the form; the fragment is read too
	const [target, rest = ''] = body.split(/[?#](.*)/s, 2);
	const at = target.indexOf(':');
	if (at < 1 || at === target.length - 1) return null;
	const link: WorkLink = { id: normalId(target) };
	readKeys(link, rest.replace('#', '&'));
	return link;
}

/** The place keys, from a `cited:` link's query or an app URL's: the same keys, read the same way. */
export function readKeys(link: WorkLink, query: string): WorkLink {
	for (const part of query.split('&')) {
		const eq = part.indexOf('=');
		if (eq < 0) continue;
		const key = part.slice(0, eq);
		const value = safeDecode(part.slice(eq + 1));
		if (key === 'page' && /^\d+$/.test(value) && Number(value) > 0) link.page = Number(value);
		if (key === 'quote' && value.trim()) link.quote = value.trim();
		if (key === 'span') {
			const m = value.match(/^(\d+)-(\d+)$/);
			if (m) link.span = [Number(m[1]), Number(m[2])];
		}
		if (key === 'box') {
			const nums = value.split(',').map(Number);
			if (nums.length === 4 && nums.every((n) => Number.isFinite(n))) link.box = [nums[0], nums[1], nums[2], nums[3]];
		}
		if (key === 'annot' && /^a-\d{4}-\d{2}-\d{2}-[0-9a-z]+$/.test(value)) link.annot = value;
	}
	return link;
}

/** The place keys as query parameters, in the one order the app writes them. */
export function placeParams(link: Omit<WorkLink, 'id'>): URLSearchParams {
	const q = new URLSearchParams();
	if (link.page) q.set('page', String(link.page));
	if (link.span) q.set('span', `${link.span[0]}-${link.span[1]}`);
	if (link.box) q.set('box', link.box.join(','));
	if (link.annot) q.set('annot', link.annot);
	if (link.quote) q.set('quote', link.quote);
	return q;
}

function safeDecode(s: string): string {
	try {
		return decodeURIComponent(s.replace(/\+/g, ' '));
	} catch {
		return s;
	}
}

/** An identifier in one spelling: the scheme lowercased, and a DOI's value too, since DOIs are case-insensitive. */
export function normalId(id: string): string {
	const at = id.indexOf(':');
	if (at < 1) return id;
	const scheme = id.slice(0, at).trim().toLowerCase();
	const value = id.slice(at + 1).trim();
	return `${scheme}:${scheme === 'doi' ? value.toLowerCase() : value}`;
}

/**
 * What `locate` is asked for a place on a work's pages: the work by its reference, with the span on `page`, else the quote on the place's own page or, where it names none, across the work.
 *
 * Parameters
 * ----------
 * ref : str
 *     The work's reference.
 * place : Omit<WorkLink, 'id'>
 *     The place a link or an item names.
 * page : number
 *     The page a span is on.
 *
 * Returns
 * -------
 * Record<string, unknown> | null
 *     The body of a `locate` request; null for a place naming neither a span nor a quote, which `locate` is not asked about.
 */
export function locateBody(ref: string, place: Omit<WorkLink, 'id'>, page: number): Record<string, unknown> | null {
	if (place.span) return { ref, page, span: place.span };
	if (place.quote) return { ref, ...(place.page ? { page: place.page } : {}), text: place.quote };
	return null;
}

/** The identifier at its own service: arXiv's PDF at the page, a DOI's landing page, MathSciNet's or zbMATH's record; undefined for a scheme none resolves. */
export function externalUrl(link: WorkLink): string | undefined {
	const at = link.id.indexOf(':');
	const value = link.id.slice(at + 1).trim();
	if (at < 1 || !value) return undefined;
	switch (link.id.slice(0, at)) {
		case 'arxiv':
			return `https://arxiv.org/pdf/${value}` + (link.page ? `#page=${link.page}` : '');
		case 'doi':
			return 'https://doi.org/' + value;
		case 'mr':
			return 'https://mathscinet.ams.org/mathscinet-getitem?mr=' + value.replace(/^MR/i, '');
		case 'zbl':
			return 'https://zbmath.org/?q=an:' + value;
		default:
			return undefined;
	}
}
