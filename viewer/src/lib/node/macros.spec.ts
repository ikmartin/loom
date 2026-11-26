import { describe, expect, it } from 'vitest';
import { macroDefinitions, parseMacros, resolveConditionals } from './macros';

const names = (body: string) => Object.fromEntries(parseMacros(body).macros.map((m) => [m.name, m]));

describe('parseMacros', () => {
	it("reads nodes.md §12's macros node, its package line ignored", () => {
		const { macros, unknown } = parseMacros('\\usepackage{amssymb}\n\\newcommand{\\Wid}{\\mathcal{W}}\n\\DeclareMathOperator{\\diam}{diam}');
		expect(macros).toEqual([
			{ name: 'Wid', args: 0, body: '\\mathcal{W}' },
			{ name: 'diam', args: 0, body: '\\operatorname{diam}' }
		]);
		expect(unknown).toEqual([]);
	});

	it('takes argument counts and the default of an optional first argument', () => {
		const m = names('\\newcommand{\\norm}[1]{\\left\\Vert#1\\right\\Vert}\n\\newcommand{\\pair}[2][x]{(#1,#2)}');
		expect(m.norm).toEqual({ name: 'norm', args: 1, body: '\\left\\Vert#1\\right\\Vert' });
		expect(m.pair).toEqual({ name: 'pair', args: 2, body: '(#1,#2)', default: 'x' });
	});

	it('reads the forms real preambles write: no braces round the name, spaces and a line before the body, starred', () => {
		// all four from the fixture papers: ACGS, slice4D, mZK
		const m = names('\\newcommand\\ocM{\\overline{\\mathcal{M}}}\n\\newcommand{\\mK} {\\mkern3mu K}\n\\newcommand\\curshom\n{\\mathop{\\mathcal{H}om}\\nolimits}\n\\newcommand*{\\st}{\\operatorname{st}}');
		expect(m.ocM.body).toBe('\\overline{\\mathcal{M}}');
		expect(m.mK.body).toBe('\\mkern3mu K');
		expect(m.curshom.body).toBe('\\mathop{\\mathcal{H}om}\\nolimits');
		expect(m.st.body).toBe('\\operatorname{st}');
	});

	it('lets a later definition replace an earlier one, and \\providecommand never replace one', () => {
		const m = names('\\newcommand{\\a}{1}\\renewcommand{\\a}{2}\\providecommand{\\a}{3}\\providecommand{\\b}{4}');
		expect(m.a.body).toBe('2');
		expect(m.b.body).toBe('4');
	});

	it('writes \\DeclareMathOperator and its starred form as operator names', () => {
		const m = names('\\DeclareMathOperator\\supp{supp}\n\\DeclareMathOperator*{\\esssup}{ess\\,sup}');
		expect(m.supp.body).toBe('\\operatorname{supp}');
		expect(m.esssup.body).toBe('\\operatorname*{ess\\,sup}');
	});

	it('declares a paired delimiter on first use, so its starred and sized forms work', () => {
		expect(names('\\DeclarePairedDelimiter{\\ceil}{\\lceil}{\\rceil}').ceil).toEqual({ name: 'ceil', args: 0, body: '\\DeclarePairedDelimiter{\\ceil}{\\lceil}{\\rceil}\\ceil' });
	});

	it('takes \\def with simple parameters and reports a delimited one, without reading its body as definitions', () => {
		const { macros, unknown } = parseMacros('\\def\\sn{\\operatorname{sn}}\\def\\mapright#1{\\smash{#1}}\\def\\displaytimes_#1{\\mathrel{\\mathop{\\times}\\limits_{#1}}}');
		expect(macros.map((m) => [m.name, m.args])).toEqual([
			['sn', 0],
			['mapright', 1]
		]);
		expect(unknown).toEqual(['\\def\\displaytimes']);
	});

	it('takes \\let with or without `=`, copying a body the node defined', () => {
		const m = names('\\newcommand{\\R}{\\mathbb{R}}\\let\\reals=\\R\\let\\oldtocsection=\\tocsection\\let\\eps\\varepsilon');
		expect(m.reals).toEqual({ name: 'reals', args: 0, body: '\\mathbb{R}' });
		expect(m.oldtocsection.body).toBe('\\tocsection');
		expect(m.eps.body).toBe('\\varepsilon');
	});

	it('gives the stand-ins for commands a loaded package defines and MathJax lacks, unless the node defines them', () => {
		const m = names('\\usepackage{amssymb,bbm}\\usepackage[makeroom]{cancel}\\newcommand{\\1}{\\mathbbm{1}}');
		expect(m['1'].body).toBe('\\mathbbm{1}');
		expect(m.mathbbm).toEqual({ name: 'mathbbm', args: 1, body: '\\mathbb{#1}' });
		expect(names('\\usepackage{bm}\\renewcommand{\\bm}[1]{#1}').bm.body).toBe('#1');
		// mathtools loads amsmath, whose capitalised accents MathJax lacks
		expect(names('\\usepackage{mathtools}').Hat.body).toBe('\\hat');
	});

	it('reports what it does not take, once, and skips its arguments', () => {
		const { macros, unknown } = parseMacros('\\newenvironment{named}[1]{\\renewcommand\\theoremname{#1}}{\\end{x}}\n\\newtheorem{lemma}[theorem]{Lemma}\n\\newtheorem{lemma2}{Lemma}\n\\theoremstyle{plain}');
		expect(macros).toEqual([]);
		expect(unknown).toEqual(['\\newenvironment', '\\newtheorem', '\\theoremstyle']);
	});

	it('refuses a name MathJax cannot define, which would end every definition after it', () => {
		const { macros, unknown } = parseMacros('\\def\\a@b{x}\\newcommand{\\ok}{y}');
		expect(macros.map((m) => m.name)).toEqual(['ok']);
		expect(unknown).toEqual(['\\a@b']);
	});

	it('ignores comments and keeps an escaped percent', () => {
		const m = names('% \\newcommand{\\no}{1}\n\\newcommand{\\pc}{50\\%} % trailing\n');
		expect(Object.keys(m)).toEqual(['pc']);
		expect(m.pc.body).toBe('50\\%');
	});

	it('rewrites \\ifinner as the \\mathchoice it asks for', () => {
		// ACGS's arrow: MathJax has no conditionals and drew the words \ifinner, \else, \fi in red
		expect(names('\\newcommand\\arr{\\ifinner\\to\\else\\longrightarrow\\fi}').arr.body).toBe('\\mathchoice{\\longrightarrow}{\\to}{\\to}{\\to}');
		expect(resolveConditionals('\\ifmmode x\\else y\\fi')).toBe('x');
		expect(resolveConditionals('\\ifx\\a\\b c\\fi')).toBe('\\ifx\\a\\b c\\fi');
	});
});

describe('macroDefinitions', () => {
	it('writes each as \\renewcommand, with its argument count and default', () => {
		const { macros } = parseMacros('\\newcommand{\\Wid}{\\mathcal{W}}\\newcommand{\\pair}[2][x]{(#1,#2)}\\newcommand{\\abs}[1]{|#1|}');
		expect(macroDefinitions(macros)).toBe('\\renewcommand{\\Wid}{\\mathcal{W}}\\renewcommand{\\pair}[2][x]{(#1,#2)}\\renewcommand{\\abs}[1]{|#1|}');
	});
});
