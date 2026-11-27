// A node's body (docs/specs/nodes.md §4) drawn as HTML in the browser: its text-mode LaTeX turned into markup, its mathematics left for MathJax with the work's macros. It is not a LaTeX engine. It knows a short list of constructs, reports every other command and environment in `unknown` rather than guessing at it, and never writes markup from the body's text, so a caller shows what it drew or asks the publisher for TeX's drawing of the node instead.
import { library as words } from '$lib/words/library';
import { matchGroup, skipSpace, type NodeMacro } from './macros';

/** What a body's pointer to an id is drawn as: the target's `number` for `\ref`, its `name` for `\cref` and `\autoref`, a reference's `name` for a citation. `work` marks a result of another work, drawn as a citation with the result's name as its locator (nodes.md §4 rule 3). */
export interface Point {
	name?: string;
	number?: string;
	page?: string;
	work?: string;
	/** An anchor loom numbers only after the person compiles the source: drawn in words saying so, never as `??`. */
	awaiting?: boolean;
}

export interface LiteOptions {
	/** The work's macros, expanded where the body uses one outside mathematics (`spin$^c$\xspace`); inside mathematics they are MathJax's. */
	macros?: NodeMacro[];
	/** Which class's default `enumerate` labels to draw, `1.` or `(1)`; a macros node does not say which class its paper used. Default 'article'. */
	labels?: 'article' | 'amsart';
	/** The body is set in italic, as amsthm's plain style sets a theorem, so `\emph` draws upright. Default false. */
	italic?: boolean;
}

export interface Drawn {
	/** The drawing. Text is escaped; each formula is a `span.math.inline` holding `\(…\)` or a `div.math.display` holding `\[…\]` or its environment, as `math/mathjax.ts` typesets them; classes `tx-*` are styled by `LITE_CSS`. */
	html: string;
	/** Each formula's TeX as placed in `html`, in order, its pointers already replaced by their words. */
	math: string[];
	/** Each command (`\foo`) and environment (`\begin{foo}`) the converter did not know, once, in order; also a construct MathJax cannot draw (`\xymatrix`). Non-empty means the drawing is not to be trusted. */
	unknown: string[];
	/** Each id a pointer names that `points` gives no words for, drawn `??` as TeX draws an undefined reference. */
	unresolved: string[];
}

/** Rules the drawing needs: paragraphs, hanging list labels, displays. Put in the page's head while a drawing is on screen, so every rule selects within a `tx-` class: one that did not would restyle the draft beside the drawing, and move its text while a citation's card is open. */
export const LITE_CSS = `
.tx-par + .tx-par { margin-top: 0.6em; }
.tx-list { margin: 0.35em 0; padding-left: 2.4em; list-style: none; }
.tx-list > li { position: relative; }
.tx-list > li + li { margin-top: 0.2em; }
.tx-list .tx-label { position: absolute; right: 100%; margin-right: 0.5em; white-space: nowrap; }
.tx-runin .tx-label, .tx-desc .tx-label { position: static; margin-right: 0.4em; }
.tx-desc .tx-label { font-weight: bold; }
.tx-center { text-align: center; }
.tx-left { text-align: left; }
.tx-right { text-align: right; }
.tx-quote { margin: 0.4em 2em; }
.tx-unknown { color: #b42318; font-family: ui-monospace, monospace; font-style: normal; }
.tx-par .math.display { display: block; margin: 0.5em 0; overflow-x: auto; overflow-y: hidden; }
`;

const BREAK = '\u0000';
/** Where a macro's expansion ends in the source: TeX reads a body as tokens of its own, so `spin$^c$\xspace` before `structure` is `\xspace` and then a word, not `\xspacestructure`. */
const SEP = '\u0001';

const ESC: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
const esc = (s: string): string => s.replace(/[&<>"']/g, (c) => ESC[c]);

/** Text for MathJax's `\text{…}`, its specials escaped. */
const texText = (s: string): string => s.replace(/[\\{}$&#%_^~]/g, (c) => (c === '\\' || c === '^' || c === '~' ? ' ' : '\\' + c));

/** Letters and the like with no command of their own; a control word skips the spaces after it, as TeX does. */
const SYMBOLS: Record<string, string> = {
	ldots: '…', dots: '…', textellipsis: '…', S: '§', P: '¶', dag: '†', ddag: '‡', textdagger: '†', textdaggerdbl: '‡',
	copyright: '©', textcopyright: '©', textregistered: '®', texttrademark: '™', pounds: '£', textsterling: '£',
	ss: 'ß', ae: 'æ', AE: 'Æ', oe: 'œ', OE: 'Œ', o: 'ø', O: 'Ø', aa: 'å', AA: 'Å', l: 'ł', L: 'Ł', i: 'ı', j: 'ȷ',
	textendash: '–', textemdash: '—', textbullet: '•', textperiodcentered: '·', textasteriskcentered: '∗', textbackslash: '\\',
	textasciitilde: '~', textasciicircum: '^', textbar: '|', textless: '<', textgreater: '>', textquoteleft: '‘',
	textquoteright: '’', textquotedblleft: '“', textquotedblright: '”', textdegree: '°', textdollar: '$', textunderscore: '_',
	textbraceleft: '{', textbraceright: '}', textsection: '§', LaTeX: 'LaTeX', TeX: 'TeX', LaTeXe: 'LaTeX2ε',
	quad: '\u2003', qquad: '\u2003\u2003', enspace: '\u2002', enskip: '\u2002', thinspace: '\u202f', space: ' ',
	hfill: ' ', hfil: ' ', dotfill: ' … ', negthinspace: ''
};

/** Commands that draw nothing: spacing between paragraphs, breaks a browser makes itself, sizes. */
const IGNORE = new Set([
	'noindent', 'indent', 'smallskip', 'medskip', 'bigskip', 'allowbreak', 'nobreak', 'relax', 'protect', 'leavevmode',
	'nobreakdash', 'ignorespaces', 'unskip', 'centering', 'raggedright', 'raggedleft', 'normalsize', 'small', 'footnotesize',
	'scriptsize', 'tiny', 'large', 'Large', 'LARGE', 'huge', 'Huge', 'selectfont', 'newpage', 'clearpage', 'phantomsection'
]);

/** A control symbol and what it draws. */
const CONTROL: Record<string, string> = {
	'%': '%', '&': '&', '#': '#', $: '$', _: '_', '{': '{', '}': '}', ',': '\u202f', ';': '\u2005', ':': '\u2005', '>': '\u2005',
	'!': '', '/': '', '@': '', '-': '\u00ad', ' ': ' ', '\n': ' ', '\t': ' '
};

/** Accents, as the combining mark each adds. */
const ACCENTS: Record<string, string> = {
	"'": '\u0301', '`': '\u0300', '^': '\u0302', '"': '\u0308', '~': '\u0303', '=': '\u0304', '.': '\u0307',
	u: '\u0306', v: '\u030c', H: '\u030b', c: '\u0327', k: '\u0328', r: '\u030a', d: '\u0323', b: '\u0331', t: '\u0361'
};

type Shape = { open: string; close: string; italic?: boolean | 'toggle' };

/** Font commands taking one argument. `italic` says what they do to the shape, for `\emph` inside them. */
const WRAP: Record<string, Shape> = {
	emph: { open: '', close: '', italic: 'toggle' },
	textit: { open: '<i>', close: '</i>', italic: true },
	textsl: { open: '<span style="font-style:oblique">', close: '</span>', italic: true },
	textup: { open: '<span style="font-style:normal">', close: '</span>', italic: false },
	textnormal: { open: '<span style="font-style:normal;font-weight:normal;font-variant:normal;font-family:inherit">', close: '</span>', italic: false },
	textbf: { open: '<b>', close: '</b>' },
	textmd: { open: '<span style="font-weight:normal">', close: '</span>' },
	textrm: { open: '<span>', close: '</span>' },
	textsf: { open: '<span style="font-family:sans-serif">', close: '</span>' },
	texttt: { open: '<span style="font-family:ui-monospace,monospace">', close: '</span>' },
	textsc: { open: '<span style="font-variant:small-caps">', close: '</span>' },
	underline: { open: '<u>', close: '</u>' },
	uline: { open: '<u>', close: '</u>' },
	sout: { open: '<s>', close: '</s>' },
	textsuperscript: { open: '<sup>', close: '</sup>' },
	textsubscript: { open: '<sub>', close: '</sub>' },
	mbox: { open: '<span style="white-space:nowrap">', close: '</span>' },
	hbox: { open: '<span style="white-space:nowrap">', close: '</span>' },
	text: { open: '<span>', close: '</span>' },
	fbox: { open: '<span style="border:1px solid;padding:0 0.2em">', close: '</span>' }
};

/** Font declarations, which last to the end of their group. */
const DECLARE: Record<string, Shape> = {
	em: { open: '', close: '', italic: 'toggle' },
	it: { open: '<span style="font-style:italic;font-weight:normal">', close: '</span>', italic: true },
	itshape: { open: '<span style="font-style:italic">', close: '</span>', italic: true },
	sl: { open: '<span style="font-style:oblique;font-weight:normal">', close: '</span>', italic: true },
	slshape: { open: '<span style="font-style:oblique">', close: '</span>', italic: true },
	upshape: { open: '<span style="font-style:normal">', close: '</span>', italic: false },
	bf: { open: '<span style="font-weight:bold;font-style:normal">', close: '</span>', italic: false },
	bfseries: { open: '<span style="font-weight:bold">', close: '</span>' },
	mdseries: { open: '<span style="font-weight:normal">', close: '</span>' },
	rm: { open: '<span style="font-style:normal;font-weight:normal;font-family:inherit">', close: '</span>', italic: false },
	rmfamily: { open: '<span style="font-family:inherit">', close: '</span>' },
	normalfont: { open: '<span style="font-style:normal;font-weight:normal;font-variant:normal;font-family:inherit">', close: '</span>', italic: false },
	sf: { open: '<span style="font-family:sans-serif;font-style:normal">', close: '</span>', italic: false },
	sffamily: { open: '<span style="font-family:sans-serif">', close: '</span>' },
	tt: { open: '<span style="font-family:ui-monospace,monospace;font-style:normal">', close: '</span>', italic: false },
	ttfamily: { open: '<span style="font-family:ui-monospace,monospace">', close: '</span>' },
	sc: { open: '<span style="font-variant:small-caps;font-style:normal">', close: '</span>', italic: false },
	scshape: { open: '<span style="font-variant:small-caps">', close: '</span>' }
};

/** Display environments, and whether one formula takes one number (a label anywhere in it is its tag) or each row its own. */
const DISPLAY: Record<string, 'one' | 'rows'> = {
	equation: 'one', 'equation*': 'one', displaymath: 'one', multline: 'one', 'multline*': 'one',
	align: 'rows', 'align*': 'rows', gather: 'rows', 'gather*': 'rows', flalign: 'rows', 'flalign*': 'rows',
	alignat: 'rows', 'alignat*': 'rows', eqnarray: 'rows', 'eqnarray*': 'rows'
};

type ListKind = { type: 'enumerate' | 'itemize' | 'description'; mode: 'block' | 'para' | 'inline' };
const LISTS: Record<string, ListKind> = {
	enumerate: { type: 'enumerate', mode: 'block' },
	itemize: { type: 'itemize', mode: 'block' },
	description: { type: 'description', mode: 'block' },
	compactenum: { type: 'enumerate', mode: 'block' },
	compactitem: { type: 'itemize', mode: 'block' },
	compactdesc: { type: 'description', mode: 'block' },
	asparaenum: { type: 'enumerate', mode: 'para' },
	asparaitem: { type: 'itemize', mode: 'para' },
	inparaenum: { type: 'enumerate', mode: 'inline' },
	inparaitem: { type: 'itemize', mode: 'inline' }
};

const BLOCKS: Record<string, string> = { center: 'tx-center', flushleft: 'tx-left', flushright: 'tx-right', quote: 'tx-quote', quotation: 'tx-quote', verse: 'tx-quote' };

const REFS = new Set(['ref', 'eqref', 'autoref', 'cref', 'Cref', 'pageref', 'vref', 'Vref']);
const CITES = new Set(['cite', 'citep', 'citet', 'citealp', 'citealt', 'Citet', 'Citep', 'Citealp', 'Citealt', 'parencite', 'Parencite', 'textcite', 'Textcite', 'autocite', 'Autocite']);
/** Citations drawn in brackets; the rest are textual (`\citet`: "Jones 2019"). */
const BRACKETED = new Set(['cite', 'citep', 'Citep', 'parencite', 'Parencite', 'autocite', 'Autocite']);
/** Commands a body's structure and pointers are written with, never taken from the work's macros. */
const PROTECTED = new Set(['begin', 'end', 'item', 'label', 'par', ...REFS, ...CITES]);

const REF_RE = /\\(ref|eqref|autoref|cref|Cref|pageref|vref|Vref)\*?\s*\{([^{}]*)\}/g;
const CITE_RE = /\\(cite|citep|citet|citealp|citealt|Citet|Citep|Citealp|Citealt|parencite|Parencite|textcite|Textcite|autocite|Autocite)\*?\s*(?:\[([^\]]*)\])?\s*(?:\[([^\]]*)\])?\s*\{([^{}]*)\}/g;
const LABEL_RE = /\\label\s*\{([^{}]*)\}/g;
/** What MathJax cannot draw: a diagram is TeX's. */
const LACKS = /\\(xymatrix|xygraph|xy|SelectTips|includegraphics|tikz)(?![A-Za-z])|\\begin\s*\{(tikzcd|tikzpicture|xy|tabular|picture)\}/g;

const COUNTERS: Record<string, (n: number) => string> = {
	arabic: (n) => String(n),
	alph: (n) => (n >= 1 && n <= 26 ? String.fromCharCode(96 + n) : String(n)),
	Alph: (n) => (n >= 1 && n <= 26 ? String.fromCharCode(64 + n) : String(n)),
	roman: (n) => roman(n),
	Roman: (n) => roman(n).toUpperCase()
};

function roman(n: number): string {
	if (n <= 0 || n >= 4000) return String(n);
	const parts: [number, string][] = [[1000, 'm'], [900, 'cm'], [500, 'd'], [400, 'cd'], [100, 'c'], [90, 'xc'], [50, 'l'], [40, 'xl'], [10, 'x'], [9, 'ix'], [5, 'v'], [4, 'iv'], [1, 'i']];
	let out = '';
	for (const [v, s] of parts) while (n >= v) ((out += s), (n -= v));
	return out;
}

/** The default `enumerate` labels by depth, in the counter form enumitem writes. */
const ENUM_LABELS = { article: ['\\arabic*.', '(\\alph*)', '\\roman*.', '\\Alph*.'], amsart: ['(\\arabic*)', '(\\alph*)', '(\\roman*)', '(\\Alph*)'] };
const BULLETS = ['•', '–', '∗', '·'];
const BARE_KEYS = new Set(['noitemsep', 'nosep', 'nolistsep', 'resume', 'resume*', 'wide', 'leftmargin=*', 'shortlabels']);

/** A length's size in em, at the 10pt a body's text is set in; null for one with no fixed size (`\fill`). */
function ems(len: string): number | null {
	const m = /^\s*(-?\d*\.?\d+)\s*(em|ex|pt|mm|cm|in|bp|pc|mu)\s*$/.exec(len);
	if (!m) return null;
	const per: Record<string, number> = { em: 1, ex: 0.43, pt: 0.1, mm: 0.2845, cm: 2.845, in: 7.227, bp: 0.1004, pc: 1.2, mu: 1 / 18 };
	return Number(m[1]) * per[m[2]];
}

/** Top-level comma-separated parts of an option list, braces protecting their contents. */
function splitTop(s: string): string[] {
	const out: string[] = [];
	let depth = 0;
	let cur = '';
	for (const ch of s) {
		if (ch === '{') depth++;
		else if (ch === '}') depth--;
		if (ch === ',' && depth === 0) {
			out.push(cur);
			cur = '';
		} else cur += ch;
	}
	out.push(cur);
	return out.map((x) => x.trim()).filter(Boolean);
}

/** An enumerate package label (`(a)`, `\upshape (i)`) in enumitem's counter form: its first unbraced `1`, `a`, `A`, `i` or `I` is the counter. */
function starForm(template: string): string {
	for (let i = 0; i < template.length; i++) {
		const ch = template[i];
		if (ch === '\\') {
			const m = /^\\([A-Za-z]+|.)/.exec(template.slice(i));
			i += (m ? m[0].length : 1) - 1;
			continue;
		}
		if (ch === '{') {
			const q = matchGroup(template, i);
			if (q < 0) break;
			i = q - 1;
			continue;
		}
		const counter = { '1': 'arabic', a: 'alph', A: 'Alph', i: 'roman', I: 'Roman' }[ch];
		if (counter) return template.slice(0, i) + `\\${counter}*` + template.slice(i + 1);
	}
	return template;
}

/** Wrap the paragraphs of `html` (split at breaks) in `div.tx-par`, dropping empty ones. */
function assemble(html: string): string {
	return html
		.split(BREAK)
		.map((p) => p.replace(/^[ \n\t]+|[ \n\t]+$/g, ''))
		.filter((p) => p !== '')
		.map((p) => `<div class="tx-par">${p}</div>`)
		.join('');
}

/** "A", "A and B", "A, B and C". */
function andList(parts: string[]): string {
	return parts.length <= 2 ? parts.join(' and ') : parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1];
}

interface Ctx {
	points: Record<string, Point>;
	macros: Map<string, NodeMacro>;
	labels: 'article' | 'amsart';
	italic: boolean;
	math: string[];
	unknown: string[];
	unresolved: string[];
	expansions: number;
	enumDepth: number;
	itemDepth: number;
}

/** How many macro expansions a body may make, so a definition that calls itself ends. */
const MAX_EXPANSIONS = 5000;

const CS = /\\([A-Za-z]+|[\s\S])/y;
const PLAIN = /[^\\{}$%~\s`'\-<>&"\u0000\u0001]+/y;
const END = /\\end\s*\{([^{}]*)\}/y;

class Parser {
	pos = 0;
	private stop: (p: Parser) => boolean = () => false;

	constructor(
		public s: string,
		private c: Ctx
	) {}

	/** Draw from here until `stop` holds or the source ends; paragraph breaks are `BREAK` in what it returns. */
	run(stop: (p: Parser) => boolean = () => false): string {
		const outer = this.stop;
		this.stop = stop;
		let out = '';
		while (this.pos < this.s.length && !stop(this)) out += this.step();
		this.stop = outer;
		return out;
	}

	/** A fragment of source (an argument, a label) drawn inline, sharing this body's state. */
	inline(src: string): string {
		return new Parser(src, this.c).run().split(BREAK).join('<br>');
	}

	private miss(what: string): void {
		if (!this.c.unknown.includes(what)) this.c.unknown.push(what);
	}

	private point(id: string): Point | undefined {
		return Object.hasOwn(this.c.points, id) ? this.c.points[id] : undefined;
	}

	private unresolved(id: string): void {
		if (!this.c.unresolved.includes(id)) this.c.unresolved.push(id);
	}

	private step(): string {
		const s = this.s;
		const ch = s[this.pos];
		switch (ch) {
			case '\\':
				return this.command();
			case '{': {
				this.pos++;
				const inner = this.run((p) => p.s[p.pos] === '}');
				if (s[this.pos] === '}') this.pos++;
				return inner;
			}
			case '}':
			case SEP:
				this.pos++;
				return '';
			case '$':
				return this.dollar();
			case '%':
				return this.comment();
			case '~':
				this.pos++;
				return '\u00a0';
			case ' ':
			case '\t':
			case '\n':
				return this.space();
			case '`':
				if (s[this.pos + 1] === '`') {
					this.pos += 2;
					return '“';
				}
				this.pos++;
				return '‘';
			case "'":
				if (s[this.pos + 1] === "'") {
					this.pos += 2;
					return '”';
				}
				this.pos++;
				return '’';
			case '-':
				if (s.startsWith('---', this.pos)) {
					this.pos += 3;
					return '—';
				}
				if (s.startsWith('--', this.pos)) {
					this.pos += 2;
					return '–';
				}
				this.pos++;
				return '-';
			case '"':
				this.pos++;
				return '”';
			case '<':
			case '>':
			case '&':
				this.pos++;
				return esc(ch);
		}
		PLAIN.lastIndex = this.pos;
		const m = PLAIN.exec(s);
		if (m) {
			this.pos = PLAIN.lastIndex;
			return m[0];
		}
		this.pos++;
		return esc(ch);
	}

	private space(): string {
		const s = this.s;
		let lines = 0;
		while (this.pos < s.length && (s[this.pos] === ' ' || s[this.pos] === '\t' || s[this.pos] === '\n')) {
			if (s[this.pos] === '\n') lines++;
			this.pos++;
		}
		return lines > 1 ? BREAK : ' ';
	}

	/** A comment eats its line's end and the next line's leading spaces; a blank line after it is still a paragraph break. */
	private comment(): string {
		const s = this.s;
		const nl = s.indexOf('\n', this.pos);
		if (nl < 0) {
			this.pos = s.length;
			return '';
		}
		let p = nl + 1;
		while (s[p] === ' ' || s[p] === '\t') p++;
		this.pos = p;
		return s[p] === '\n' ? BREAK : '';
	}

	/** The spaces after a control word, and one line end, as TeX skips them; a blank line after it stays a paragraph break. */
	private skipWordSpace(): void {
		const s = this.s;
		let p = this.pos;
		while (s[p] === ' ' || s[p] === '\t') p++;
		if (s[p] === '\n') {
			let q = p + 1;
			while (s[q] === ' ' || s[q] === '\t') q++;
			if (s[q] === '\n') {
				this.pos = p;
				return;
			}
			p = q;
		}
		this.pos = p;
	}

	/** An undelimited argument: a group's contents, a control sequence, or one character. */
	private arg(): string | null {
		const s = this.s;
		const p = this.skipSep(this.pos);
		if (p >= s.length) return null;
		if (s[p] === '{') {
			const q = matchGroup(s, p);
			if (q < 0) return null;
			this.pos = q;
			return s.slice(p + 1, q - 1);
		}
		if (s[p] === '}') return null;
		if (s[p] === '\\') {
			CS.lastIndex = p;
			const m = CS.exec(s);
			if (m) {
				this.pos = CS.lastIndex;
				return m[0];
			}
		}
		this.pos = p + 1;
		return s[p];
	}

	/** A `[…]` argument, or null with nothing consumed when the next thing is not one. */
	private optArg(): string | null {
		const s = this.s;
		const p = this.skipSep(this.pos);
		if (s[p] !== '[') return null;
		const q = matchGroup(s, p, '[', ']');
		if (q < 0) return null;
		this.pos = q;
		return s.slice(p + 1, q - 1);
	}

	/** Past spaces (no blank line) and the ends of expansions, to where an argument would begin. */
	private skipSep(pos: number): number {
		let p = skipSpace(this.s, pos, false);
		while (this.s[p] === SEP) p = skipSpace(this.s, p + 1, false);
		return p;
	}

	private star(): boolean {
		if (this.s[this.pos] !== '*') return false;
		this.pos++;
		return true;
	}

	atEnd(env: string): boolean {
		if (this.s[this.pos] !== '\\') return false;
		END.lastIndex = this.pos;
		const m = END.exec(this.s);
		return !!m && m[1].trim() === env;
	}

	private consumeEnd(env: string): void {
		if (!this.atEnd(env)) return;
		END.lastIndex = this.pos;
		END.exec(this.s);
		this.pos = END.lastIndex;
	}

	private command(): string {
		CS.lastIndex = this.pos;
		const m = CS.exec(this.s);
		if (!m) {
			this.pos++;
			return esc('\\');
		}
		const name = m[1];
		this.pos = CS.lastIndex;
		const word = /^[A-Za-z]/.test(name);
		if (word) this.skipWordSpace();
		// the work's own definitions come first, as in TeX, except for the commands a body's structure and pointers are written with
		const mac = this.c.macros.get(name);
		if (mac && !PROTECTED.has(name)) return this.expand(name, mac);
		if (!word) return this.symbol(name);
		if (REFS.has(name)) return this.ref(name);
		if (CITES.has(name)) return this.cite(name);
		switch (name) {
			case 'begin':
				return this.begin();
			case 'end': {
				const env = this.envName();
				this.miss(`\\end{${env ?? ''}}`);
				return '';
			}
			case 'item':
				this.miss('\\item');
				return '';
			case 'par':
				return BREAK;
			case 'label':
				this.arg();
				return '';
			case 'index':
			case 'vspace':
			case 'addvspace':
				this.star();
				this.arg();
				return '';
			case 'newline':
				return '<br>';
			case 'linebreak':
				this.optArg();
				return '<br>';
			case 'nolinebreak':
			case 'pagebreak':
			case 'nopagebreak':
				this.optArg();
				return '';
			case 'xspace':
				return this.xspace();
			case 'ensuremath':
				return this.inlineMath(this.arg() ?? '');
			case 'hspace':
				return this.hspace();
			case 'textcolor': {
				this.optArg();
				const color = this.arg() ?? '';
				const body = this.inline(this.arg() ?? '');
				return /^[A-Za-z]+$/.test(color) ? `<span style="color:${color}">${body}</span>` : body;
			}
			case 'color': {
				this.optArg();
				const color = this.arg() ?? '';
				return /^[A-Za-z]+$/.test(color) ? this.declare({ open: `<span style="color:${color}">`, close: '</span>' }) : '';
			}
			case 'url':
				return `<span style="font-family:ui-monospace,monospace">${esc(this.arg() ?? '')}</span>`;
			case 'href':
				this.arg();
				return this.inline(this.arg() ?? '');
			case 'verb':
				return this.verb();
			case 'footnote':
				this.miss('\\footnote');
				return `<span class="tx-unknown">\\footnote</span>(${this.inline(this.arg() ?? '')})`;
			case 'phantom':
				return `<span style="visibility:hidden">${this.inline(this.arg() ?? '')}</span>`;
		}
		if (Object.hasOwn(SYMBOLS, name)) return esc(SYMBOLS[name]);
		if (IGNORE.has(name)) return '';
		if (Object.hasOwn(WRAP, name)) return this.wrap(WRAP[name], this.arg() ?? '');
		if (Object.hasOwn(DECLARE, name)) return this.declare(DECLARE[name]);
		if (Object.hasOwn(ACCENTS, name)) return this.accent(ACCENTS[name]);
		this.miss('\\' + name);
		return `<span class="tx-unknown">${esc('\\' + name)}</span>`;
	}

	private symbol(name: string): string {
		switch (name) {
			case '\\':
				this.star();
				// `\\[2pt]` is a line break with extra space; a bracket that is not a length is the next line's text
				if (/^\s*\[\s*-?[\d.]+\s*[a-z]{2}\s*\]/.test(this.s.slice(this.pos, this.pos + 24))) this.optArg();
				return '<br>';
			case '(': {
				const src = this.scanTo('\\)');
				return src === null ? this.unclosed('\\(') : this.inlineMath(src);
			}
			case '[': {
				const src = this.scanTo('\\]');
				return src === null ? this.unclosed('\\[') : this.display('\\[', src, '\\]', 'one');
			}
		}
		if (Object.hasOwn(ACCENTS, name)) return this.accent(ACCENTS[name]);
		if (Object.hasOwn(CONTROL, name)) return esc(CONTROL[name]);
		this.miss('\\' + name);
		return `<span class="tx-unknown">${esc('\\' + name)}</span>`;
	}

	private unclosed(delim: string): string {
		this.miss(delim);
		return `<span class="tx-unknown">${esc(delim)}</span>`;
	}

	/** A use of one of the work's macros outside mathematics: its body, arguments substituted, read in its place. */
	private expand(name: string, m: NodeMacro): string {
		if (++this.c.expansions > MAX_EXPANSIONS) {
			this.miss('\\' + name);
			return '';
		}
		const args: string[] = [];
		if (m.default !== undefined && m.args > 0) args.push(this.optArg() ?? m.default);
		while (args.length < m.args) args.push(this.arg() ?? '');
		let body = m.body;
		for (let i = m.args; i >= 1; i--) {
			const val = args[i - 1];
			// `\to#1` with an argument that begins with a letter would make one undefined control word
			if (/^[A-Za-z]/.test(val)) body = body.replace(new RegExp(`(\\\\[A-Za-z]+)#${i}`, 'g'), `$1 #${i}`);
			body = body.split(`#${i}`).join(val);
		}
		body = body.replace(/##/g, '#');
		this.s = this.s.slice(0, this.pos) + body + SEP + this.s.slice(this.pos);
		return '';
	}

	/** xspace: a space unless punctuation or a group's end comes next. */
	private xspace(): string {
		while (this.s[this.pos] === SEP) this.pos++;
		const next = this.s[this.pos];
		if (next === undefined || /[,.'/?;:!~\-)}{\s]/.test(next)) return '';
		if (next === '\\' && /[ /]/.test(this.s[this.pos + 1] ?? '')) return '';
		if (this.s.startsWith('\\footnote', this.pos)) return '';
		return ' ';
	}

	private hspace(): string {
		this.star();
		const w = ems(this.arg() ?? '');
		if (w === null) return ' ';
		if (w === 0) return '';
		return w > 0 ? `<span style="display:inline-block;width:${w.toFixed(3)}em"></span>` : `<span style="margin-left:${w.toFixed(3)}em"></span>`;
	}

	private verb(): string {
		this.star();
		const d = this.s[this.pos];
		const end = d === undefined ? -1 : this.s.indexOf(d, this.pos + 1);
		if (end < 0) return this.unclosed('\\verb');
		const raw = this.s.slice(this.pos + 1, end);
		this.pos = end + 1;
		return `<span style="font-family:ui-monospace,monospace;white-space:pre">${esc(raw)}</span>`;
	}

	private accent(mark: string): string {
		const raw = this.arg();
		if (raw === null || raw.trim() === '') return mark === '\u0301' ? '´' : esc(('\u00a0' + mark).normalize('NFC'));
		const base = raw === '\\i' ? 'i' : raw === '\\j' ? 'j' : raw;
		if (/^[A-Za-z]$/.test(base)) return (base + mark).normalize('NFC');
		const inner = this.inline(raw);
		if (/^[^<&]/.test(inner)) {
			const first = [...inner][0];
			return (first + mark).normalize('NFC') + inner.slice(first.length);
		}
		return inner + mark;
	}

	private wrap(shape: Shape, raw: string): string {
		const was = this.c.italic;
		const italic = shape.italic === 'toggle' ? !was : (shape.italic ?? was);
		this.c.italic = italic;
		const inner = this.inline(raw);
		this.c.italic = was;
		if (shape.italic === 'toggle') return italic ? `<em>${inner}</em>` : `<em style="font-style:normal">${inner}</em>`;
		return shape.open + inner + shape.close;
	}

	/** A declaration: the rest of the group in its style, each paragraph wrapped on its own so the markup stays nested. */
	private declare(shape: Shape): string {
		const was = this.c.italic;
		const italic = shape.italic === 'toggle' ? !was : (shape.italic ?? was);
		this.c.italic = italic;
		const rest = this.run(this.stop);
		this.c.italic = was;
		const [open, close] = shape.italic === 'toggle' ? [`<span style="font-style:${italic ? 'italic' : 'normal'}">`, '</span>'] : [shape.open, shape.close];
		return rest
			.split(BREAK)
			.map((p) => (p.trim() ? open + p + close : p))
			.join(BREAK);
	}

	private ref(cmd: string): string {
		this.star();
		const raw = this.arg() ?? '';
		const ids = cmd === 'cref' || cmd === 'Cref' ? raw.split(',').map((x) => x.trim()).filter(Boolean) : [raw.trim()];
		// amsmath sets an `\eqref` upright, inside an italic theorem too
		const style = cmd === 'eqref' ? ' style="font-style:normal"' : '';
		return andList(ids.map((id) => `<span class="tx-ref" data-ref="${esc(id)}"${style}>${esc(this.refWords(cmd, id))}</span>`));
	}

	/** The words a pointer is drawn as, `??` where `points` has none. */
	private refWords(cmd: string, id: string): string {
		const p = this.point(id);
		let w: string | undefined;
		if (p?.awaiting && p.number == null) return words.side.awaitingRef;
		if (p) {
			// loom sends a number it does not hold as null: unresolved, as one it does not send
			const number = p.number ?? undefined;
			if (cmd === 'eqref') w = number === undefined ? undefined : `(${number})`;
			else if (cmd === 'pageref') w = p.page;
			else if (cmd === 'ref' || cmd === 'vref' || cmd === 'Vref') w = number;
			else w = p.name ?? number;
			if (w !== undefined && cmd === 'Cref') w = w.charAt(0).toUpperCase() + w.slice(1);
			if (w !== undefined && p.work !== undefined) w = `[${p.work}, ${p.name ?? w}]`;
		}
		if (w === undefined) {
			this.unresolved(id);
			return '??';
		}
		return w;
	}

	/** A citation's words: each key's name, the notes around them, in brackets for a parenthetical command. `draw` turns a name or a note into the output's form. */
	private citeWords(cmd: string, pre: string | null, post: string | null, keys: string, name: (s: string) => string, draw: (s: string) => string): { ids: string[]; text: string } {
		const ids = keys.split(',').map((x) => x.trim()).filter(Boolean);
		const names = ids.map((id) => {
			const n = this.point(id)?.name;
			if (n === undefined) this.unresolved(id);
			return name(n ?? '?');
		});
		let inner = names.join(', ');
		if (pre) inner = draw(pre) + ' ' + inner;
		if (post) inner += ', ' + draw(post);
		return { ids, text: BRACKETED.has(cmd) ? `[${inner}]` : inner };
	}

	private cite(cmd: string): string {
		this.star();
		const o1 = this.optArg();
		const o2 = o1 === null ? null : this.optArg();
		const keys = this.arg() ?? '';
		const [pre, post] = o2 === null ? [null, o1] : [o1, o2];
		const { ids, text } = this.citeWords(cmd, pre, post, keys, esc, (x) => this.inline(x));
		return `<span class="tx-cite" data-ref="${esc(ids.join(' '))}">${text}</span>`;
	}

	private envName(): string | null {
		const p = skipSpace(this.s, this.pos, false);
		if (this.s[p] !== '{') return null;
		const q = matchGroup(this.s, p);
		if (q < 0) return null;
		this.pos = q;
		return this.s.slice(p + 1, q - 1).trim();
	}

	private begin(): string {
		const env = this.envName();
		if (env === null) {
			this.miss('\\begin');
			return '';
		}
		if (Object.hasOwn(DISPLAY, env) || env === 'math') {
			const src = this.scanEnv(env);
			if (src === null) return this.unclosed(`\\begin{${env}}`);
			if (env === 'math') return this.inlineMath(src);
			if (env === 'displaymath') return this.display('\\[', src, '\\]', 'one');
			return this.display(`\\begin{${env}}`, src, `\\end{${env}}`, DISPLAY[env]);
		}
		if (Object.hasOwn(LISTS, env)) return this.list(env, LISTS[env]);
		if (Object.hasOwn(BLOCKS, env)) {
			const body = this.run((p) => p.atEnd(env));
			this.consumeEnd(env);
			return `<div class="${BLOCKS[env]}">${assemble(body)}</div>`;
		}
		this.miss(`\\begin{${env}}`);
		// an environment of the author's that holds items is drawn as a list, so what is shown while TeX's drawing is asked for still reads in order
		const save = this.pos;
		this.optArg();
		const p = skipSpace(this.s, this.pos);
		this.pos = save;
		if (/^\\item(?![A-Za-z])/.test(this.s.slice(p, p + 6))) return this.list(env, LISTS.enumerate);
		const body = this.run((p) => p.atEnd(env));
		this.consumeEnd(env);
		return `<div>${assemble(body)}</div>`;
	}

	private list(env: string, kind: ListKind): string {
		const opt = this.optArg();
		const depth = kind.type === 'enumerate' ? ++this.c.enumDepth : kind.type === 'itemize' ? ++this.c.itemDepth : 0;
		const { start, label } = this.labeler(kind.type, depth, opt);
		const atItem = (p: Parser) => p.s.startsWith('\\item', p.pos) && !/[A-Za-z]/.test(p.s[p.pos + 5] ?? '');
		const stop = (p: Parser) => atItem(p) || p.atEnd(env);
		this.run(stop);
		const items: string[] = [];
		let n = start - 1;
		while (atItem(this)) {
			this.pos += 5;
			const o = this.optArg();
			const mark = o === null ? label(++n) : this.inline(o);
			const body = this.run(stop);
			const lab = mark === '' ? '' : `<span class="tx-label">${mark}</span>`;
			const rest = body.replace(/^[ \n\t]+/, '');
			if (kind.mode === 'inline') items.push(lab + ' ' + rest.split(BREAK).join(' ').replace(/[ \n\t]+$/, ''));
			else items.push(kind.mode === 'para' ? assemble(lab + ' ' + rest) : `<li>${assemble(lab + body)}</li>`);
		}
		this.consumeEnd(env);
		if (kind.type === 'enumerate') this.c.enumDepth--;
		else if (kind.type === 'itemize') this.c.itemDepth--;
		if (kind.mode === 'inline') return `<span class="tx-runin">${items.join(' ')}</span>`;
		if (kind.mode === 'para') return `<div class="tx-runin">${items.join('')}</div>`;
		const tag = kind.type === 'enumerate' ? 'ol' : 'ul';
		return `<${tag} class="tx-list${kind.type === 'description' ? ' tx-desc' : ''}">${items.join('')}</${tag}>`;
	}

	/** Where a list's numbering starts and how its n-th label is drawn: the class's default, an enumerate package template (`[(a)]`) or enumitem's `label=` key. */
	private labeler(type: ListKind['type'], depth: number, opt: string | null): { start: number; label: (n: number) => string } {
		if (type === 'description') return { start: 1, label: () => '' };
		let template: string | null = null;
		let start = 1;
		if (opt !== null) {
			const parts = splitTop(opt);
			if (parts.some((x) => x.includes('=')) || (parts.length > 0 && parts.every((x) => BARE_KEYS.has(x)))) {
				for (const part of parts) {
					const [k, ...rest] = part.split('=');
					const v = rest.join('=').trim().replace(/^\{([\s\S]*)\}$/, '$1');
					const key = k.trim();
					if (key === 'label') template = v;
					else if (key === 'start' && /^\d+$/.test(v)) start = Number(v);
					else if (key === 'resume' || key === 'resume*' || key === 'series') this.miss(`\\begin{enumerate}[${key}]`);
				}
			} else template = type === 'enumerate' ? starForm(opt) : opt;
		}
		if (type === 'itemize') {
			const t = template;
			const bullet = t === null ? esc(BULLETS[(depth - 1) % 4]) : this.inline(t);
			return { start, label: () => bullet };
		}
		const form = template ?? ENUM_LABELS[this.c.labels][(depth - 1) % 4];
		return { start, label: (n) => this.inline(form.replace(/\\(arabic|alph|Alph|roman|Roman)\*/g, (_, f: string) => COUNTERS[f](n))) };
	}

	/** Source up to `close` (`$`, `$$`, `\)` or `\]`), past it; null when it never closes. A `$` inside braces belongs to a `\text{…}` in the formula. */
	private scanTo(close: '$' | '$$' | '\\)' | '\\]'): string | null {
		const s = this.s;
		let depth = 0;
		for (let i = this.pos; i < s.length; i++) {
			const ch = s[i];
			if (ch === '\\') {
				if ((close === '\\)' && s[i + 1] === ')') || (close === '\\]' && s[i + 1] === ']')) {
					const src = s.slice(this.pos, i);
					this.pos = i + 2;
					return src;
				}
				i++;
				continue;
			}
			if (ch === '{') depth++;
			else if (ch === '}') depth--;
			else if (ch === '$' && depth <= 0 && close[0] === '$') {
				if (close === '$$' && s[i + 1] !== '$') continue;
				const src = s.slice(this.pos, i);
				this.pos = i + close.length;
				return src;
			}
		}
		return null;
	}

	/** An environment's source up to its matching `\end`, past it. */
	private scanEnv(env: string): string | null {
		const re = new RegExp(`\\\\(begin|end)\\s*\\{${env.replace(/[*]/g, '\\*')}\\}`, 'g');
		re.lastIndex = this.pos;
		let depth = 1;
		for (let m = re.exec(this.s); m; m = re.exec(this.s)) {
			if (m[1] === 'begin') depth++;
			else if (--depth === 0) {
				const src = this.s.slice(this.pos, m.index);
				this.pos = re.lastIndex;
				return src;
			}
		}
		return null;
	}

	private dollar(): string {
		if (this.s[this.pos + 1] === '$') {
			this.pos += 2;
			const src = this.scanTo('$$');
			return src === null ? this.unclosed('$$') : this.display('\\[', src, '\\]', 'one');
		}
		this.pos++;
		const src = this.scanTo('$');
		return src === null ? this.unclosed('$') : this.inlineMath(src);
	}

	private inlineMath(src: string): string {
		const tex = '\\(' + this.mathSource(src, null) + '\\)';
		this.c.math.push(tex);
		return `<span class="math inline">${esc(tex)}</span>`;
	}

	private display(open: string, src: string, close: string, numbering: 'one' | 'rows'): string {
		const tex = open + this.mathSource(src, numbering) + close;
		this.c.math.push(tex);
		return `<div class="math display">${esc(tex)}</div>`;
	}

	/** A formula with its pointers replaced by their words and its labels by the tags their numbers give (none in inline mathematics); the rest is MathJax's. */
	private mathSource(src: string, numbering: 'one' | 'rows' | null): string {
		let tag: string | null = null;
		let out = src.replaceAll(SEP, '').replace(LABEL_RE, (_, id: string) => {
			const n = numbering === null ? undefined : this.point(id.trim())?.number;
			// an anchor loom numbers only after the person's compile is drawn with no tag
			if (n == null) return '';
			if (numbering === 'rows') return `\\tag{${texText(n)}}`;
			tag ??= n;
			return '';
		});
		out = out.replace(REF_RE, (_, cmd: string, raw: string) => {
			const ids = cmd === 'cref' || cmd === 'Cref' ? raw.split(',').map((x) => x.trim()).filter(Boolean) : [raw.trim()];
			return `\\text{${texText(andList(ids.map((id) => this.refWords(cmd, id))))}}`;
		});
		out = out.replace(CITE_RE, (_, cmd: string, o1: string | undefined, o2: string | undefined, keys: string) => {
			const [pre, post] = o2 === undefined ? [null, o1 ?? null] : [o1 ?? null, o2];
			const { text } = this.citeWords(cmd, pre, post, keys, (x) => x, (x) => x);
			return `\\text{${texText(text)}}`;
		});
		if (tag !== null) out += `\\tag{${texText(tag)}}`;
		this.lacks(out, 3);
		return out;
	}

	/** Report what MathJax cannot draw in `tex`, or in the body of a macro of the work's that `tex` uses, to `depth` levels. */
	private lacks(tex: string, depth: number): void {
		for (const m of tex.matchAll(LACKS)) this.miss(m[1] ? '\\' + m[1] : `\\begin{${m[2]}}`);
		if (depth === 0 || this.c.macros.size === 0) return;
		for (const m of tex.matchAll(/\\([A-Za-z]+)/g)) {
			const mac = this.c.macros.get(m[1]);
			if (mac) this.lacks(mac.body, depth - 1);
		}
	}
}

/**
 * Draw a node's body as HTML, its mathematics left for MathJax.
 *
 * Parameters
 * ----------
 * body : string
 *     The node's body: text-mode LaTeX with inline and display mathematics, pointing at other nodes by id.
 * points : Record<string, Point>
 *     For each id and anchor the body names (`library-node`'s `points`), the words drawn in its place; an anchor's `number` is the tag of the display that labels it.
 * options : LiteOptions, default {}
 *     The work's macros for text-mode uses, the class whose list labels to draw, and whether the body is set in italic.
 *
 * Returns
 * -------
 * Drawn
 *     The HTML, its formulas, what the converter did not know, and the ids `points` gave no words for.
 */
export function toHtml(body: string, points: Record<string, Point>, options: LiteOptions = {}): Drawn {
	const ctx: Ctx = {
		points,
		macros: new Map((options.macros ?? []).map((m) => [m.name, m])),
		labels: options.labels ?? 'article',
		italic: options.italic ?? false,
		math: [],
		unknown: [],
		unresolved: [],
		expansions: 0,
		enumDepth: 0,
		itemDepth: 0
	};
	const src = body.replace(/\r\n?/g, '\n').replace(/[\u0000\u0001]/g, '');
	const html = assemble(new Parser(src, ctx).run());
	return { html, math: ctx.math, unknown: ctx.unknown, unresolved: ctx.unresolved };
}
