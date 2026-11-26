import { describe, expect, it } from 'vitest';
import { toHtml, type Point } from './latexlite';
import { parseMacros } from './macros';
import { library as words } from '$lib/words/library';

const par = (s: string) => `<div class="tx-par">${s}</div>`;
const inl = (tex: string) => `<span class="math inline">\\(${tex}\\)</span>`;
/** The drawing of `body` inside its one paragraph. */
const one = (body: string, points: Record<string, Point> = {}, opts = {}) => {
	const { html } = toHtml(body, points, opts);
	expect(html.startsWith('<div class="tx-par">') && html.endsWith('</div>')).toBe(true);
	return html.slice('<div class="tx-par">'.length, -'</div>'.length);
};

// nodes.md §12: the work Smith 2024, its macros node, and what `library-node` would give as points
const MACROS = parseMacros('\\usepackage{amssymb}\n\\newcommand{\\Wid}{\\mathcal{W}}\n\\DeclareMathOperator{\\diam}{diam}').macros;
const POINTS: Record<string, Point> = {
	'tq-00A4': { name: 'Definition 2.1', number: '2.1' },
	'tq-00K3': { name: 'Lemma 3.2', number: '3.2' },
	'tq-00K3-eq00': { number: '3.3' },
	'tq-00B7': { name: 'Lemma 2.1', number: '2.1', work: 'Jones 2019' },
	'tq-00B1-ref': { name: 'Jones 2019' }
};

describe("nodes.md §12's examples", () => {
	it('draws the definition tq-00A4', () => {
		const r = toHtml('A \\emph{widget} is a compact set $W \\subset \\mathbb{R}^n$ whose boundary lies in $\\Wid$.', POINTS, { macros: MACROS });
		expect(r.html).toBe(par(`A <em>widget</em> is a compact set ${inl('W \\subset \\mathbb{R}^n')} whose boundary lies in ${inl('\\Wid')}.`));
		expect(r.math).toEqual(['\\(W \\subset \\mathbb{R}^n\\)', '\\(\\Wid\\)']);
		expect(r.unknown).toEqual([]);
	});

	it('draws the lemma tq-00K3, its anchored display tagged with the number points give', () => {
		const body = 'Let $W$ be a widget (Definition~\\ref{tq-00A4}). Then\n\\begin{enumerate}\n\\item $\\diam W < \\infty$; and\n\\item for every $x_0 \\in W$, each point $x$ of $W$ satisfies\n\\begin{equation}\\label{tq-00K3-eq00}\n  |x| \\le \\diam W + |x_0| .\n\\end{equation}\n\\end{enumerate}';
		const r = toHtml(body, POINTS, { macros: MACROS, italic: true });
		expect(r.html).toContain('(Definition\u00a0<span class="tx-ref" data-ref="tq-00A4">2.1</span>). Then <ol class="tx-list"><li>');
		expect(r.html).toContain(`<span class="tx-label">1.</span> ${inl('\\diam W &lt; \\infty')}; and</div></li>`);
		expect(r.html).toContain('<span class="tx-label">2.</span> for every');
		expect(r.math[r.math.length - 1]).toBe('\\begin{equation}\n  |x| \\le \\diam W + |x_0| .\n\\tag{3.3}\\end{equation}');
		expect(r.html).not.toContain('\\label');
		expect(r.unknown).toEqual([]);
		expect(r.unresolved).toEqual([]);
	});

	it('draws the proof tq-00K3-proof00', () => {
		expect(one('A widget is compact (Definition~\\ref{tq-00A4}), so finitely many unit balls cover it, which bounds its diameter. The second claim is the triangle inequality.', POINTS)).toBe(
			'A widget is compact (Definition\u00a0<span class="tx-ref" data-ref="tq-00A4">2.1</span>), so finitely many unit balls cover it, which bounds its diameter. The second claim is the triangle inequality.'
		);
	});

	it('draws the proposition tq-00K5', () => {
		expect(one('Let $W$ be a widget as in Definition~\\ref{tq-00A4}. Then $W$ lies in a ball about the origin.', POINTS)).toBe(
			`Let ${inl('W')} be a widget as in Definition\u00a0<span class="tx-ref" data-ref="tq-00A4">2.1</span>. Then ${inl('W')} lies in a ball about the origin.`
		);
	});

	it("draws the proof tq-00K5-proof00, another work's result as a citation with its locator", () => {
		const r = toHtml('By Lemma~\\ref{tq-00K3}, the bound \\eqref{tq-00K3-eq00} holds for a fixed $x_0$. The covering estimate of \\ref{tq-00B7} then gives the radius. For sets that are not compact see \\cite{tq-00B1-ref}.', POINTS);
		expect(r.html).toBe(
			par(
				`By Lemma\u00a0<span class="tx-ref" data-ref="tq-00K3">3.2</span>, the bound <span class="tx-ref" data-ref="tq-00K3-eq00" style="font-style:normal">(3.3)</span> holds for a fixed ${inl('x_0')}. The covering estimate of <span class="tx-ref" data-ref="tq-00B7">[Jones 2019, Lemma 2.1]</span> then gives the radius. For sets that are not compact see <span class="tx-cite" data-ref="tq-00B1-ref">[Jones 2019]</span>.`
			)
		);
		expect(r.unresolved).toEqual([]);
	});

	it('draws the stub tq-00B7 as nothing', () => {
		expect(toHtml('', POINTS)).toEqual({ html: '', math: [], unknown: [], unresolved: [] });
	});
});

describe('text', () => {
	it('breaks paragraphs at a blank line or \\par, and joins a line end into a space', () => {
		expect(toHtml('One.\n\nTwo\nlines.\n  \n\nThree\\par Four', {}).html).toBe(par('One.') + par('Two lines.') + par('Three') + par('Four'));
	});

	it('drops a comment with its line end, keeping a blank line after it', () => {
		expect(toHtml('a%c\nb and c %x\n\nd', {}).html).toBe(par('ab and c') + par('d'));
	});

	it('draws emphasis and the font commands', () => {
		expect(one('\\emph{a} \\textit{b} \\textbf{c} \\textrm{d} \\textup{e}')).toBe('<em>a</em> <i>b</i> <b>c</b> <span>d</span> <span style="font-style:normal">e</span>');
		expect(one('\\textsf{a}\\texttt{b}\\textsc{c}\\textsl{d}')).toBe('<span style="font-family:sans-serif">a</span><span style="font-family:ui-monospace,monospace">b</span><span style="font-variant:small-caps">c</span><span style="font-style:oblique">d</span>');
	});

	it('sets \\emph upright inside an italic body or italic words', () => {
		expect(one('\\emph{a}', {}, { italic: true })).toBe('<em style="font-style:normal">a</em>');
		expect(one('\\textit{\\emph{a}}')).toBe('<i><em style="font-style:normal">a</em></i>');
	});

	it('scopes a font declaration to its group', () => {
		expect(one('{\\bf a} b {\\em c \\emph{d}} e')).toBe('<span style="font-weight:bold;font-style:normal">a</span> b <span style="font-style:italic">c <em style="font-style:normal">d</em></span> e');
	});

	it('draws ties, dashes and quotes as TeX does', () => {
		expect(one("a~b 1--2 a---b ``q'' `s' it's")).toBe('a\u00a0b 1–2 a—b “q” ‘s’ it’s');
	});

	it('draws spacing commands and skips the space after a control word', () => {
		expect(one('a\\,b a\\ b a\\quad b a\\qquad b \\ldots{} end')).toBe('a\u202fb a b a\u2003b a\u2003\u2003b … end');
		expect(one('a\\hspace{1em}b\\hspace*{-2pt}c')).toBe('a<span style="display:inline-block;width:1.000em"></span>b<span style="margin-left:-0.200em"></span>c');
	});

	it('draws accents, with or without braces', () => {
		expect(one("\\'e \\`a \\^{a} \\\"o \\~n \\=a \\.z \\u{g} \\v{c} \\v s \\H{o} \\c c \\k{a} \\r{u} \\d{s} \\'\\i{} Ozsv\\'ath \\ss")).toBe('é à â ö ñ ā ż ğ č š ő ç ą ů ṣ í Ozsváth ß');
	});

	it('draws \\\\ as a line break', () => {
		expect(one('a\\\\b\\\\[2pt]c')).toBe('a<br>b<br>c');
	});
});

describe('lists', () => {
	it("numbers enumerate as article does by default, or as amsart does, and nests", () => {
		const body = '\\begin{enumerate}\\item a\\item b\\begin{enumerate}\\item c\\end{enumerate}\\end{enumerate}';
		const article = toHtml(body, {}).html;
		expect(article).toContain('<span class="tx-label">1.</span> a');
		expect(article).toContain('<span class="tx-label">2.</span> b');
		expect(article).toContain('<span class="tx-label">(a)</span> c');
		expect(toHtml(body, {}, { labels: 'amsart' }).html).toContain('<span class="tx-label">(1)</span> a');
	});

	it("takes an item's own label, which does not step the counter", () => {
		const html = toHtml('\\begin{enumerate}\\item[(a)] x\\item y\\end{enumerate}', {}).html;
		// a list is part of its paragraph, as in TeX
		expect(html).toBe(par('<ol class="tx-list"><li>' + par('<span class="tx-label">(a)</span> x') + '</li><li>' + par('<span class="tx-label">1.</span> y') + '</li></ol>'));
	});

	it("reads an enumerate package template and enumitem's label and start", () => {
		expect(toHtml('\\begin{enumerate}[(i)]\\item a\\item b\\end{enumerate}', {}).html).toContain('<span class="tx-label">(ii)</span> b');
		expect(toHtml('\\begin{enumerate}[\\upshape (a)]\\item a\\end{enumerate}', {}).html).toContain('<span class="tx-label"><span style="font-style:normal">(a)</span></span>');
		expect(toHtml('\\begin{enumerate}[label=(\\Alph*), start=3]\\item a\\end{enumerate}', {}).html).toContain('<span class="tx-label">(C)</span> a');
	});

	it("draws paralist's run-in lists in the paragraph, and its paragraph lists as paragraphs", () => {
		expect(one('so \\begin{inparaenum}[(a)]\\item x, \\item y\\end{inparaenum}.')).toBe('so <span class="tx-runin"><span class="tx-label">(a)</span> x, <span class="tx-label">(b)</span> y</span>.');
		expect(toHtml('\\begin{asparaenum}\\item x\\item y\\end{asparaenum}', {}).html).toBe(par('<div class="tx-runin">' + par('<span class="tx-label">1.</span> x') + par('<span class="tx-label">2.</span> y') + '</div>'));
	});

	it('draws centred and quoted blocks', () => {
		expect(toHtml('\\begin{center}a\\end{center}\\begin{quote}b\\end{quote}', {}).html).toBe(par('<div class="tx-center">' + par('a') + '</div><div class="tx-quote">' + par('b') + '</div>'));
	});

	it('reports a list that resumes another, whose numbers it cannot know', () => {
		expect(toHtml('\\begin{enumerate}[resume]\\item a\\end{enumerate}', {}).unknown).toEqual(['\\begin{enumerate}[resume]']);
	});

	it('draws itemize with bullets and description with its terms', () => {
		expect(toHtml('\\begin{itemize}\\item a\\end{itemize}', {}).html).toBe(par('<ul class="tx-list"><li>' + par('<span class="tx-label">•</span> a') + '</li></ul>'));
		expect(toHtml('\\begin{description}\\item[Term] a\\end{description}', {}).html).toBe(par('<ul class="tx-list tx-desc"><li>' + par('<span class="tx-label">Term</span> a') + '</li></ul>'));
	});
});

describe('mathematics', () => {
	it('keeps inline mathematics in either delimiter for MathJax, a dollar inside \\text included', () => {
		const r = toHtml('$x$ and \\(y\\) and $a \\text{ if $b$}$', {});
		expect(r.math).toEqual(['\\(x\\)', '\\(y\\)', '\\(a \\text{ if $b$}\\)']);
		expect(r.html).toBe(par(`${inl('x')} and ${inl('y')} and ${inl('a \\text{ if $b$}')}`));
	});

	it('keeps every display environment as display mathematics', () => {
		const envs = ['equation', 'equation*', 'align', 'align*', 'gather', 'gather*', 'multline', 'multline*', 'eqnarray*', 'flalign'];
		for (const env of envs) {
			const r = toHtml(`a \\begin{${env}}x\\end{${env}} b`, {});
			expect(r.html).toBe(par(`a <div class="math display">\\begin{${env}}x\\end{${env}}</div> b`));
		}
		expect(toHtml('\\[x\\] $$y$$ \\begin{displaymath}z\\end{displaymath}', {}).math).toEqual(['\\[x\\]', '\\[y\\]', '\\[z\\]']);
	});

	it('tags each labelled row of a multi-row display, and a one-number display once at its end', () => {
		const pts = { r1: { number: '2.1' }, r2: { number: '2.2' }, e: { number: '4' } };
		expect(toHtml('\\begin{align}a\\label{r1}\\\\b\\nonumber\\\\c\\label{r2}\\end{align}', pts).math).toEqual(['\\begin{align}a\\tag{2.1}\\\\b\\nonumber\\\\c\\tag{2.2}\\end{align}']);
		expect(toHtml('\\begin{equation}\\label{e}\\begin{split}a\\\\b\\end{split}\\end{equation}', pts).math).toEqual(['\\begin{equation}\\begin{split}a\\\\b\\end{split}\\tag{4}\\end{equation}']);
		expect(toHtml('\\[x\\label{e}\\]', pts).math).toEqual(['\\[x\\tag{4}\\]']);
	});

	it('drops a label with no number, and every label in inline mathematics', () => {
		expect(toHtml('\\begin{equation}\\label{none}x\\end{equation} $y\\label{e}$', { e: { number: '4' } }).math).toEqual(['\\begin{equation}x\\end{equation}', '\\(y\\)']);
	});

	it("replaces a pointer inside mathematics with its words as text", () => {
		expect(toHtml('$\\eqref{e} \\Rightarrow \\ref{t}$', { e: { number: '3.3' }, t: { number: '2.1' } }).math).toEqual(['\\(\\text{(3.3)} \\Rightarrow \\text{2.1}\\)']);
		expect(toHtml('$x \\cite[p.~2]{r}$', { r: { name: 'Smith 2024' } }).math).toEqual(['\\(x \\text{[Smith 2024, p. 2]}\\)']);
	});

	it('reports what MathJax cannot draw, in the body or in a macro the body uses', () => {
		expect(toHtml('\\[\\xymatrix{A \\ar[r] & B}\\]', {}).unknown).toEqual(['\\xymatrix']);
		const macros = parseMacros('\\newcommand\\doublelong[2]{\\mathbin{\\xymatrix{{}\\ar[r]^{#1}&}}}').macros;
		expect(toHtml('$A \\doublelong{f}{g} B$', {}, { macros }).unknown).toEqual(['\\xymatrix']);
		expect(toHtml('\\[\\begin{tikzcd} A \\end{tikzcd}\\]', {}).unknown).toEqual(['\\begin{tikzcd}']);
	});

	it('reports mathematics that never closes', () => {
		expect(toHtml('a $x', {}).unknown).toEqual(['$']);
		expect(toHtml('\\begin{align}x', {}).unknown).toEqual(['\\begin{align}']);
	});
});

describe('pointers', () => {
	const pts: Record<string, Point> = {
		a: { name: 'Lemma 3.2', number: '3.2', page: '12' },
		b: { name: 'definition 2.1', number: '2.1' },
		e: { number: '3.3' },
		r: { name: 'Smith 2024' },
		s: { name: 'Jones 2019' }
	};
	it('draws each referencing command with the words points give', () => {
		expect(one('\\ref{a} \\ref*{a} \\vref{a} \\Vref{a} \\eqref{e} \\autoref{a} \\pageref{a}', pts)).toBe(
			'<span class="tx-ref" data-ref="a">3.2</span> <span class="tx-ref" data-ref="a">3.2</span> <span class="tx-ref" data-ref="a">3.2</span> <span class="tx-ref" data-ref="a">3.2</span> <span class="tx-ref" data-ref="e" style="font-style:normal">(3.3)</span> <span class="tx-ref" data-ref="a">Lemma 3.2</span> <span class="tx-ref" data-ref="a">12</span>'
		);
	});

	it('draws a cleveref list of ids, \\Cref capitalised', () => {
		expect(one('\\cref{a,b} \\Cref{b}', pts)).toBe('<span class="tx-ref" data-ref="a">Lemma 3.2</span> and <span class="tx-ref" data-ref="b">definition 2.1</span> <span class="tx-ref" data-ref="b">Definition 2.1</span>');
		expect(one('\\cref{a, b, e}', pts)).toContain('Lemma 3.2</span>, <span class="tx-ref" data-ref="b">definition 2.1</span> and <span class="tx-ref" data-ref="e">3.3</span>');
	});

	it('draws the citation commands, with a locator and with natbib notes', () => {
		expect(one('\\cite{r} \\cite[Lemma~2.1]{r} \\citep{r,s} \\citet{r} \\citealp[p.~3]{r} \\citep[see][Thm.~1]{s}', pts)).toBe(
			[
				'<span class="tx-cite" data-ref="r">[Smith 2024]</span>',
				'<span class="tx-cite" data-ref="r">[Smith 2024, Lemma\u00a02.1]</span>',
				'<span class="tx-cite" data-ref="r s">[Smith 2024, Jones 2019]</span>',
				'<span class="tx-cite" data-ref="r">Smith 2024</span>',
				'<span class="tx-cite" data-ref="r">Smith 2024, p.\u00a03</span>',
				'<span class="tx-cite" data-ref="s">[see Jones 2019, Thm.\u00a01]</span>'
			].join(' ')
		);
	});

	it('draws a pointer points has no words for as TeX does, and lists it', () => {
		const r = toHtml('\\ref{zz} \\eqref{a} \\cite{qq} \\ref{constructor}', { a: { name: 'Lemma 1' } });
		expect(r.html).toBe(par('<span class="tx-ref" data-ref="zz">??</span> <span class="tx-ref" data-ref="a" style="font-style:normal">??</span> <span class="tx-cite" data-ref="qq">[?]</span> <span class="tx-ref" data-ref="constructor">??</span>'));
		expect(r.unresolved).toEqual(['zz', 'a', 'qq', 'constructor']);
		expect(r.unknown).toEqual([]);
	});
});

describe("the work's macros outside mathematics", () => {
	const macros = parseMacros('\\newcommand{\\spinc}{spin$^c$\\xspace}\\newcommand{\\qc}{quasi-coherent\\xspace}\\newcommand{\\term}[1]{\\emph{#1}}\\newcommand{\\opt}[2][dflt]{#1/#2}\\def\\loop{\\loop}').macros;

	it('expands a macro as a token of its own, so xspace sees the word after it', () => {
		// slice4D: `spin$^c$\xspace` before `structure` read as the one command \xspacestructure
		expect(one('a \\spinc structure, a \\qc. sheaf, \\qc{} x', {}, { macros })).toBe(`a spin${inl('^c')} structure, a quasi-coherent. sheaf, quasi-coherent x`);
	});

	it('substitutes arguments, and the default of an optional one', () => {
		expect(one('\\term{x} \\opt{y} \\opt[z]{w}', {}, { macros })).toBe('<em>x</em> dflt/y z/w');
	});

	it('ends a definition that calls itself, reporting it', () => {
		expect(toHtml('\\loop', {}, { macros }).unknown).toEqual(['\\loop']);
	});
});

describe('safety', () => {
	it('escapes text, mathematics and ids, so the body writes no markup', () => {
		const r = toHtml('a <script>alert(1)</script> & "q" $a<b>c$ \\ref{x"y}', { 'x"y': { number: '<i>' } });
		expect(r.html).toBe(par(`a &lt;script&gt;alert(1)&lt;/script&gt; &amp; ”q” ${inl('a&lt;b&gt;c')} <span class="tx-ref" data-ref="x&quot;y">&lt;i&gt;</span>`));
	});

	it('takes a colour only by name', () => {
		expect(one('\\textcolor{red}{a}\\textcolor{red;background:url(x)}{b}')).toBe('<span style="color:red">a</span>b');
	});
});

describe('what it does not know', () => {
	it('reports each unknown command and environment once, and draws its source', () => {
		const r = toHtml('\\foo{x} \\foo \\begin{tikzpicture}y\\end{tikzpicture} \\footnote{n} \\alpha', {});
		expect(r.unknown).toEqual(['\\foo', '\\begin{tikzpicture}', '\\footnote', '\\alpha']);
		expect(r.html).toContain('<span class="tx-unknown">\\foo</span>x');
	});

	it("draws an author's list environment as a list while reporting it", () => {
		// ACGS's \begin{enumeratei}, a \newenvironment that a macros node cannot hold
		const r = toHtml('\\begin{enumeratei}\\item a\\end{enumeratei}', {});
		expect(r.unknown).toEqual(['\\begin{enumeratei}']);
		expect(r.html).toContain('<ol class="tx-list">');
	});
});

describe('an anchor whose number waits for the person\'s compile', () => {
	it('draws its display with no tag and a reference to it in words, never as ??', () => {
		const points = { 'tq-0002-eq00': { awaiting: true, number: null as unknown as undefined } };
		const r = toHtml('Then\n\\begin{equation}\\label{tq-0002-eq00} a = b \\end{equation}\nso \\eqref{tq-0002-eq00} holds.', points);
		expect(r.html).not.toContain('\\tag');
		expect(r.html).not.toContain('??');
		expect(r.html).toContain(words.side.awaitingRef);
		expect(r.unresolved).toEqual([]);
	});
	it('draws a number loom sends as null as unresolved, never as (null)', () => {
		const points = { 'tq-0002-eq00': { number: null as unknown as undefined } };
		const r = toHtml('By \\eqref{tq-0002-eq00} and \\ref{tq-0002-eq00}.', points);
		expect(r.html).not.toContain('null');
		expect(r.unresolved).toEqual(['tq-0002-eq00']);
	});
});
