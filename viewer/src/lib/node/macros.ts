// A work's macros node (docs/specs/nodes.md §8) read into the macro set MathJax takes. It reads the forms `loom/scan/macros.py` reads from a paper's preamble, and makes the same choices (a paired delimiter declared on first use, `\ifinner` as `\mathchoice`, stand-ins for package commands MathJax lacks), so a node is typeset with the definitions its paper's other fragments are.
import type { Macro } from '$lib/manifest/types';

/** A macro as `math/mathjax.ts` takes one. `default` is the default of an optional first argument (`\newcommand{\x}[2][d]{…}`); that file's prefix does not write it, `macroDefinitions` does. */
export interface NodeMacro extends Macro {
	default?: string;
}

export interface MacroSet {
	/** The definitions, in the order the node first defines each name; a later definition of a name replaces its body. */
	macros: NodeMacro[];
	/** Each command the reader did not take, once, as written (`\newenvironment`, `\def\x` with delimited parameters). */
	unknown: string[];
}

/** Offset just past the group opened at `pos`, honouring escapes and inner braces; -1 when `s[pos]` is not `open` or the group is unbalanced. A `[…]` group skips over `{…}` inside it, so `[{]}]` is one group. */
export function matchGroup(s: string, pos: number, open = '{', close = '}'): number {
	if (s[pos] !== open) return -1;
	let depth = 0;
	for (let i = pos; i < s.length; i++) {
		const ch = s[i];
		if (ch === '\\') {
			i++;
			continue;
		}
		if (ch === '{' && open !== '{') {
			const j = matchGroup(s, i);
			if (j < 0) return -1;
			i = j - 1;
			continue;
		}
		if (ch === open) depth++;
		else if (ch === close && --depth === 0) return i + 1;
	}
	return -1;
}

/** Offset of the first character at or after `pos` that is not a space, tab or newline; with `blank` false it stops before a blank line, which TeX reads as a paragraph and no argument crosses. */
export function skipSpace(s: string, pos: number, blank = true): number {
	let p = pos;
	let lines = 0;
	while (p < s.length && (s[p] === ' ' || s[p] === '\t' || s[p] === '\n' || s[p] === '\r')) {
		if (s[p] === '\n' && ++lines > 1 && !blank) return pos;
		p++;
	}
	return p;
}

/** `s` with every comment removed, the newline that ends it kept; an escaped `\%` is a percent sign. */
export function uncomment(s: string): string {
	return s.replace(/(^|[^\\])((?:\\\\)*)%[^\n]*/g, '$1$2');
}

const CS = /\\([A-Za-z@]+|[^A-Za-z@])/y;

/** A control sequence's name at `pos` (`\foo` gives `foo`), or null. */
function csAt(s: string, pos: number): { name: string; end: number } | null {
	CS.lastIndex = pos;
	const m = CS.exec(s);
	return m ? { name: m[1], end: CS.lastIndex } : null;
}

/** A defined name: `{\x}` or `\x`, spaces allowed around it. */
function readName(s: string, pos: number): { name: string; end: number } | null {
	const p = skipSpace(s, pos, false);
	if (s[p] === '{') {
		const q = matchGroup(s, p);
		if (q < 0) return null;
		const inner = s.slice(p + 1, q - 1).trim();
		const cs = csAt(inner, 0);
		return cs && cs.end === inner.length ? { name: cs.name, end: q } : null;
	}
	const cs = csAt(s, p);
	return cs ? { name: cs.name, end: cs.end } : null;
}

/** A braced body's contents. */
function readBody(s: string, pos: number): { body: string; end: number } | null {
	const p = skipSpace(s, pos);
	if (s[p] !== '{') return null;
	const q = matchGroup(s, p);
	return q < 0 ? null : { body: s.slice(p + 1, q - 1), end: q };
}

/** A `[…]` argument's contents, or null when the next thing is not one. */
function readOptional(s: string, pos: number): { body: string; end: number } | null {
	const p = skipSpace(s, pos, false);
	if (s[p] !== '[') return null;
	const q = matchGroup(s, p, '[', ']');
	return q < 0 ? null : { body: s.slice(p + 1, q - 1), end: q };
}

/** A braced group's contents or a single unbraced token: a delimiter argument may be either. */
function readToken(s: string, pos: number): { body: string; end: number } | null {
	const b = readBody(s, pos);
	if (b) return b;
	const p = skipSpace(s, pos);
	const cs = csAt(s, p);
	if (cs) return { body: s.slice(p, cs.end), end: cs.end };
	return p < s.length && !/[\s{}%]/.test(s[p]) ? { body: s[p], end: p + 1 } : null;
}

/** Past the arguments of a command the reader does not know: any `*`, `[…]` and `{…}` that follow it, so its arguments are not read as definitions. */
function skipArguments(s: string, pos: number): number {
	let p = pos;
	if (s[p] === '*') p++;
	for (;;) {
		const q = skipSpace(s, p, false);
		const end = s[q] === '{' ? matchGroup(s, q) : s[q] === '[' ? matchGroup(s, q, '[', ']') : -1;
		if (end < 0) return p;
		p = end;
	}
}

const IF = /\\(if[a-zA-Z@]*|else|fi)(?![a-zA-Z@])/g;

/** The then-branch, else-branch and end offset of the conditional whose `\if…` begins at `start`. */
function branches(body: string, start: number): [string, string, number] | null {
	let depth = 0;
	let split = -1;
	let elseAt = -1;
	let head = -1;
	IF.lastIndex = start;
	for (let m = IF.exec(body); m; m = IF.exec(body)) {
		const word = m[1];
		if (head < 0) head = m.index + m[0].length;
		if (word.startsWith('if')) depth++;
		else if (word === 'else') {
			if (depth === 1 && split < 0) {
				split = m.index;
				elseAt = m.index + m[0].length;
			}
		} else if (--depth === 0) {
			return split < 0 ? [body.slice(head, m.index), '', IF.lastIndex] : [body.slice(head, split), body.slice(elseAt, m.index), IF.lastIndex];
		}
	}
	return null;
}

/** `\ifinner` as the `\mathchoice` it asks for, `\ifmmode` as its first branch; MathJax has no conditionals, and any other is left for it to report. */
export function resolveConditionals(body: string): string {
	let out = body;
	for (let i = 0; i < 8; i++) {
		const m = /\\(ifinner|ifmmode)(?![a-zA-Z@])/.exec(out);
		if (!m) return out;
		const got = branches(out, m.index);
		if (!got) return out;
		const [then, other, end] = [got[0].replace(/^ +/, ''), got[1].replace(/^ +/, ''), got[2]];
		const rep = m[1] === 'ifmmode' ? then : `\\mathchoice{${other}}{${then}}{${then}}{${then}}`;
		out = out.slice(0, m.index) + rep + out.slice(end);
	}
	return out;
}

/** Commands a package defines that MathJax lacks, with the closest form it has, by package; taken only where the node loads the package. The same table as `PACKAGE_COMMANDS` in `loom/scan/macros.py`. */
const PACKAGE_COMMANDS: Record<string, Record<string, [number, string]>> = {
	'old-arrows': { longhookrightarrow: [0, '\\xhookrightarrow{}'], longhookleftarrow: [0, '\\xhookleftarrow{}'] },
	amsmath: Object.fromEntries(['Hat', 'Check', 'Tilde', 'Acute', 'Grave', 'Dot', 'Ddot', 'Breve', 'Bar', 'Vec'].map((n) => [n, [0, '\\' + n.toLowerCase()] as [number, string]])),
	bm: { bm: [1, '\\boldsymbol{#1}'] },
	bbm: { mathbbm: [1, '\\mathbb{#1}'], mathbbmss: [1, '\\mathbb{#1}'], mathbbmtt: [1, '\\mathbb{#1}'] },
	dsfont: { mathds: [1, '\\mathbb{#1}'] },
	esint: Object.fromEntries(
		[
			['fint', '2A0F'],
			['oiint', '222F'],
			['oiiint', '2230'],
			['sqint', '2A16'],
			['ointclockwise', '2232'],
			['ointctrclockwise', '2233'],
			['varointclockwise', '2232'],
			['varointctrclockwise', '2233']
		].map(([n, code]) => [n, [0, `\\mathop{\\unicode{x${code}}}\\nolimits`] as [number, string]])
	),
	stmaryrd: { llbracket: [0, '\\mathopen{\\unicode{x27E6}}'], rrbracket: [0, '\\mathclose{\\unicode{x27E7}}'] },
	mathtools: { vcentcolon: [0, '\\mathrel{:}'] },
	nicefrac: { nicefrac: [2, '{}^{#1}\\!/\\!{}_{#2}'] },
	xfrac: { sfrac: [2, '{}^{#1}\\!/\\!{}_{#2}'] }
};
const LOADS: Record<string, string[]> = { mathtools: ['amsmath'], empheq: ['mathtools', 'amsmath'] };

const DEFINE = new Set(['newcommand', 'renewcommand', 'providecommand']);

/**
 * Read a macros node's body into the macro set MathJax takes.
 *
 * Parameters
 * ----------
 * body : string
 *     The node's body: `\usepackage` lines and definitions (`\newcommand`, `\renewcommand`, `\providecommand`, `\DeclareMathOperator`, `\DeclarePairedDelimiter`, `\def`, `\let`, and their starred forms).
 *
 * Returns
 * -------
 * MacroSet
 *     The macros, with the stand-ins for commands the loaded packages define and MathJax lacks, and every command not taken.
 *
 * See Also
 * --------
 * macroDefinitions : the set as one formula of definitions, defaults included.
 */
export function parseMacros(body: string): MacroSet {
	const s = uncomment(body);
	const defs = new Map<string, NodeMacro>();
	const unknown: string[] = [];
	const packages = new Set<string>();
	const miss = (what: string) => {
		if (!unknown.includes(what)) unknown.push(what);
	};
	const put = (m: NodeMacro) => {
		// MathJax reads `@` as a character, so `\renewcommand{\a@b}` is an error that stops every definition after it in the same formula
		if (!/^(?:[A-Za-z]+|[^A-Za-z@])$/.test(m.name)) return miss('\\' + m.name);
		defs.set(m.name, m);
	};
	let pos = 0;
	while (pos < s.length) {
		const at = s.indexOf('\\', pos);
		if (at < 0) break;
		const cs = csAt(s, at);
		if (!cs) break;
		const head = cs.name;
		pos = cs.end;
		const star = s[pos] === '*';
		if (star) pos++;
		if (head === 'usepackage' || head === 'RequirePackage') {
			const opt = readOptional(s, pos);
			if (opt) pos = opt.end;
			const list = readBody(s, pos);
			if (list) {
				pos = list.end;
				for (const p of list.body.split(',')) if (p.trim()) packages.add(p.trim());
			}
			continue;
		}
		if (DEFINE.has(head)) {
			const name = readName(s, pos);
			if (!name) {
				miss('\\' + head);
				continue;
			}
			pos = name.end;
			let args = 0;
			let dflt: string | undefined;
			const n = readOptional(s, pos);
			if (n && /^\s*\d\s*$/.test(n.body)) {
				args = Number(n.body.trim());
				pos = n.end;
				const d = readOptional(s, pos);
				if (d) {
					dflt = d.body;
					pos = d.end;
				}
			}
			const b = readBody(s, pos);
			if (!b) {
				miss('\\' + head + '{\\' + name.name + '}');
				continue;
			}
			pos = b.end;
			if (head === 'providecommand' && defs.has(name.name)) continue;
			put(dflt === undefined ? { name: name.name, args, body: b.body } : { name: name.name, args, body: b.body, default: dflt });
			continue;
		}
		if (head === 'DeclareMathOperator') {
			const name = readName(s, pos);
			const b = name && readBody(s, name.end);
			if (!name || !b) {
				miss('\\DeclareMathOperator');
				continue;
			}
			pos = b.end;
			put({ name: name.name, args: 0, body: `\\operatorname${star ? '*' : ''}{${b.body}}` });
			continue;
		}
		if (head === 'DeclarePairedDelimiter') {
			const name = readName(s, pos);
			const left = name && readToken(s, name.end);
			const right = left && readToken(s, left.end);
			if (!name || !left || !right) {
				miss('\\DeclarePairedDelimiter');
				continue;
			}
			pos = right.end;
			// declared on first use: MathJax's mathtools then redefines the command, so its starred and sized forms work as in LaTeX, which no fixed-arity macro can do
			put({ name: name.name, args: 0, body: `\\DeclarePairedDelimiter{\\${name.name}}{${left.body}}{${right.body}}\\${name.name}` });
			continue;
		}
		if (head === 'def' || head === 'gdef') {
			const name = readName(s, pos);
			if (!name) {
				miss('\\' + head);
				continue;
			}
			const params = /^((?:#\d)*)/.exec(s.slice(name.end))![1];
			const b = s[name.end + params.length] === '{' ? readBody(s, name.end + params.length) : null;
			if (!b) {
				// a delimited parameter (`\def\x_#1{…}`) has no form MathJax's macros can take
				miss(`\\${head}\\${name.name}`);
				const open = s.indexOf('{', name.end);
				const end = open < 0 ? -1 : matchGroup(s, open);
				pos = end < 0 ? name.end : end;
				continue;
			}
			pos = b.end;
			put({ name: name.name, args: params.length / 2, body: b.body });
			continue;
		}
		if (head === 'let') {
			const a = readName(s, pos);
			if (!a) {
				miss('\\let');
				continue;
			}
			let p = skipSpace(s, a.end, false);
			if (s[p] === '=') p = skipSpace(s, p + 1, false);
			const b = csAt(s, p);
			if (!b) {
				miss(`\\let\\${a.name}`);
				pos = p;
				continue;
			}
			pos = b.end;
			// `\let` copies the meaning it has now, so a target the node defined lends its body
			const target = defs.get(b.name);
			put(target ? { ...target, name: a.name } : { name: a.name, args: 0, body: '\\' + b.name });
			continue;
		}
		miss('\\' + head);
		pos = skipArguments(s, pos - (star ? 1 : 0));
	}
	const loaded = new Set(packages);
	for (const p of packages) for (const q of LOADS[p] ?? []) loaded.add(q);
	const macros: NodeMacro[] = [...defs.values()].map((m) => ({ ...m, body: resolveConditionals(m.body) }));
	for (const p of [...loaded].sort())
		for (const [name, [args, b]] of Object.entries(PACKAGE_COMMANDS[p] ?? {})) if (!defs.has(name)) macros.push({ name, args, body: b });
	return { macros, unknown };
}

/**
 * The macro set as one formula of definitions, to typeset in a holder off the page before a node's own formulas, as `math/mathjax.ts` defines a fragment's set.
 *
 * Parameters
 * ----------
 * macros : NodeMacro[]
 *     The set, as `parseMacros` gives it.
 *
 * Returns
 * -------
 * string
 *     `\renewcommand` for each, with its default where it has one; MathJax never checks that a macro exists, so `\renewcommand` serves for a new name too.
 */
export function macroDefinitions(macros: NodeMacro[]): string {
	return macros
		.map((m) => {
			const n = m.args > 0 ? `[${m.args}]` : '';
			const d = m.default !== undefined && m.args > 0 ? `[${m.default}]` : '';
			return `\\renewcommand{\\${m.name}}${n}${d}{${m.body}}`;
		})
		.join('');
}
