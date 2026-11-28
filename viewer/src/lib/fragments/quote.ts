// What a reader selected in a fragment, as loom will look for it in the source: the words as they are, each formula as its TeX between `$`s, and each citation or reference as the command it was written as, which is the form loom's quote matching reads (records/selectors.py). `readOf` reads the same words as the reader sees them, a citation or reference as drawn, for what a person hands their agent. The chrome a fragment carries — the gutter's id and state, a comment count, MathJax's hidden copy — is not text of the result and is left out.

const SKIP = '.node-margin, button, .comment-slot, mjx-assistive-mml, .env-label, .qed';
/** A citation or reference the renderer drew from a command, carrying the command as written. */
const COMMAND = '.cite[data-tex], a.ref[data-tex]';

/** A formula's TeX as a quote carries it: `$…$` inline, `$$…$$` displayed. */
export function texOf(el: HTMLElement): string {
	let tex = (el.dataset.tex ?? el.textContent ?? '').trim();
	const display = el.classList.contains('display') || tex.startsWith('\\[');
	if (tex.startsWith('\\(') || tex.startsWith('\\[')) tex = tex.slice(2);
	if (tex.endsWith('\\)') || tex.endsWith('\\]')) tex = tex.slice(0, -2);
	tex = tex.trim();
	return display ? `$$${tex}$$` : `$${tex}$`;
}

/**
 * The quote a range stands for: its text, with every formula it touches whole, as TeX.
 *
 * Parameters
 * ----------
 * range : Range
 *     A selection's range, or a block's contents.
 *
 * Returns
 * -------
 * string
 *     Whitespace collapsed; '' when the range holds no text.
 */
export function quoteOf(range: Range): string {
	return walked(range, true);
}

/**
 * The words a range stands for as the reader sees them: its text, every formula it touches whole as its TeX, and each citation or reference as it is drawn (`[1, Proposition 2.1]`, `Lemma 1.2`), never as its command.
 *
 * Parameters
 * ----------
 * range : Range
 *     A selection's range.
 *
 * Returns
 * -------
 * string
 *     Whitespace collapsed; '' when the range holds no text.
 *
 * See Also
 * --------
 * quoteOf : the same words as loom finds them in the source, each citation and reference as its command.
 */
export function readOf(range: Range): string {
	return walked(range, false);
}

/** A range's words, formulas as TeX, and with `commands` each citation or reference as its command, else as drawn. */
function walked(range: Range, commands: boolean): string {
	const root = range.commonAncestorContainer;
	const top = root.nodeType === Node.ELEMENT_NODE ? (root as Element) : root.parentElement;
	if (!top) return '';
	// a selection wholly inside one formula is that formula
	const inMath = top.closest<HTMLElement>('.math');
	if (inMath) return texOf(inMath);
	// and one wholly inside a citation or a reference is the command (study F5)
	const inCommand = commands ? top.closest<HTMLElement>(COMMAND) : null;
	if (inCommand) return inCommand.dataset.tex ?? '';
	const out: string[] = [];
	// a `\cite{a,b}` is drawn as one element per key, and quoted once
	const quoted = new Set<string>();
	const walk = (node: Node): void => {
		if (!range.intersectsNode(node)) return;
		if (node.nodeType === Node.TEXT_NODE) {
			const t = node.textContent ?? '';
			const a = node === range.startContainer ? range.startOffset : 0;
			const b = node === range.endContainer ? range.endOffset : t.length;
			out.push(t.slice(a, b));
			return;
		}
		if (node.nodeType !== Node.ELEMENT_NODE) return;
		const el = node as HTMLElement;
		if (el.matches(SKIP)) return;
		if (el.matches('.math')) {
			out.push(texOf(el));
			return;
		}
		if (commands && el.matches(COMMAND)) {
			// one command drawn as several elements carries one offset; one with none is quoted wherever it stands
			const at = el.dataset.at ?? '';
			if (!at || !quoted.has(at)) out.push(el.dataset.tex ?? '');
			if (at) quoted.add(at);
			return;
		}
		for (const c of el.childNodes) walk(c);
	};
	walk(top);
	return out.join('').replace(/\s+/g, ' ').trim();
}

/** The key a place in a fragment belongs to: the closest result, proof or section around it, else `fallback`. */
export function keyOf(node: Node, fallback: string): string {
	const el = node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
	const at = el?.closest<HTMLElement>('div.env[data-key], details.env-proof[data-key], section[data-key], section[data-id]');
	return at?.dataset.key ?? at?.dataset.id ?? fallback;
}

/** A run of a fragment's text as a quote reads it: a text node's characters, or a formula or command whole, as its TeX (`atom`). */
export interface Piece {
	text: string;
	atom: boolean;
}

/**
 * Where quoted words stand among a fragment's pieces, read as `quoteOf` reads them, with whitespace collapsed: the piece each end is in and the offset there, an atom taken whole.
 *
 * Parameters
 * ----------
 * pieces : list of Piece
 *     The fragment's text in reading order.
 * quote : str
 *     Words as a link or an annotation quotes them.
 *
 * Returns
 * -------
 * { start: [number, number]; end: [number, number] } | null
 *     The first occurrence: `[piece, offset]` for each end, the end's offset past its last character; null where the words are not there.
 */
export function findIn(pieces: Piece[], quote: string): { start: [number, number]; end: [number, number] } | null {
	const want = quote.replace(/\s+/g, ' ').trim();
	if (!want) return null;
	let read = '';
	const at: [number, number][] = [];
	let space = true;
	pieces.forEach((p, i) => {
		for (let k = 0; k < p.text.length; k++) {
			const white = /\s/.test(p.text[k]);
			if (white && space) continue;
			read += white ? ' ' : p.text[k];
			at.push([i, k]);
			space = white;
		}
	});
	const hit = read.indexOf(want);
	if (hit < 0) return null;
	const [si, so] = at[hit];
	const [ei, eo] = at[hit + want.length - 1];
	return { start: [si, pieces[si].atom ? 0 : so], end: [ei, pieces[ei].atom ? pieces[ei].text.length : eo + 1] };
}

/** The range quoted words stand at in `root`, read as `quoteOf` reads a selection, so the words a selection was quoted as are found where it was; a formula or a command is taken whole. Null where they are not there. */
export function quoteRange(root: Element, quote: string): Range | null {
	const nodes: Node[] = [];
	const pieces: Piece[] = [];
	const quoted = new Set<string>();
	const walk = (node: Node): void => {
		if (node.nodeType === Node.TEXT_NODE) {
			nodes.push(node);
			pieces.push({ text: node.textContent ?? '', atom: false });
			return;
		}
		if (node.nodeType !== Node.ELEMENT_NODE) return;
		const el = node as HTMLElement;
		if (el.matches(SKIP)) return;
		if (el.matches('.math')) {
			nodes.push(el);
			pieces.push({ text: texOf(el), atom: true });
			return;
		}
		if (el.matches(COMMAND)) {
			const at = el.dataset.at ?? '';
			if (!at || !quoted.has(at)) {
				nodes.push(el);
				pieces.push({ text: el.dataset.tex ?? '', atom: true });
			}
			if (at) quoted.add(at);
			return;
		}
		for (const c of el.childNodes) walk(c);
	};
	walk(root);
	const hit = findIn(pieces, quote);
	if (!hit) return null;
	const range = document.createRange();
	const [si, so] = hit.start;
	const [ei, eo] = hit.end;
	if (pieces[si].atom) range.setStartBefore(nodes[si]);
	else range.setStart(nodes[si], so);
	if (pieces[ei].atom) range.setEndAfter(nodes[ei]);
	else range.setEnd(nodes[ei], eo);
	return range;
}

/** The words a link quotes, lit while the link is in force: one highlight for every pane, each fragment adding its range and taking it away. Nothing where the browser draws no highlights. */
const LIT = 'loom-quote';
export function lightRange(range: Range): () => void {
	const reg = (globalThis.CSS as unknown as { highlights?: Map<string, { add(r: Range): void; delete(r: Range): void; size: number }> })?.highlights;
	const Make = (globalThis as unknown as { Highlight?: new () => { add(r: Range): void; delete(r: Range): void; size: number } }).Highlight;
	if (!reg || !Make) return () => {};
	const lit = reg.get(LIT) ?? new Make();
	lit.add(range);
	reg.set(LIT, lit);
	return () => {
		lit.delete(range);
		if (!lit.size) reg.delete(LIT);
	};
}
