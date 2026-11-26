// Diagnostics as Review › Problems reads them: which a person is shown, whose each is to fix, what is wrong in words, and where to open it. Unknown codes are titled by their message; nothing here fails on a code it has never seen.
import type { Diagnostic, Fix, Manifest } from './manifest/types';
import { keyTarget, placeUrl } from './nav';
import { pathFor } from './workspace/item';

/** Whose a diagnostic is to fix: the person's, or an agent's copy's. A publisher that does not say makes every one the person's. */
export type Owner = 'person' | 'copy';

export function ownerOf(d: Diagnostic): Owner {
	return d.owner === 'copy' ? 'copy' : 'person';
}

/** What kind of problem a diagnostic is: in a document's LaTeX, in loom's model of the quilt, or loom's own difficulty. A publisher that does not say, or says what this viewer does not know, makes it the person's LaTeX, so nothing it reports goes unseen. */
export type Class = 'latex' | 'model' | 'internal';

export function classOf(d: Pick<Diagnostic, 'class'>): Class {
	return d.class === 'model' ? 'model' : d.class === 'internal' ? 'internal' : 'latex';
}

/** What a person is shown of `items`: the problems in a document's LaTeX, one that did not compile among them, their own and an agent's copy's. Loom's model and its own difficulties are an agent's, which `loom lint` lists; the manifest keeps every one. */
export function forPerson(items: Diagnostic[]): Diagnostic[] {
	return items.filter((d) => classOf(d) === 'latex');
}

/** What each code says is wrong, in words, by the code's name after any publisher's namespace (`ns:name`), so the table names no publisher; `name severity` where one code says two things. Two codes that say one thing share a title, and so a group. */
const TITLES: Record<string, string> = {
	'duplicate-id': 'Defined twice',
	'duplicate-label': 'Defined twice',
	'dangling-link': 'A reference points nowhere',
	'missing-include': 'An included file is missing',
	'double-inclusion': 'A file is included twice',
	'inclusion-cycle': 'Files include each other in a circle',
	unreachable: 'In no document',
	'reference-to-loose': 'A reference to a block no document includes',
	'environment-spans-files': 'An environment opens in one file and closes in another',
	'line-anchoring': 'A \\begin or \\end shares its line',
	'unknown-environment': 'An environment the preamble does not declare',
	'unattached-proof': 'A proof belongs to no result',
	'multi-target-proof': 'A proof names several results',
	'macros-unloaded': "The document does not load loom's macros",
	'macro-shadowed': "The preamble redefines one of loom's macros",
	'macros-missing': 'loom.sty is missing',
	'taxon-conflict': 'Documents disagree on what an environment is',
	'unknown-directive': 'An unknown % !LOOM line',
	'invalid-name': 'A name that cannot be used',
	'unlabelled-node': 'A result has no id',
	'positional-proof-key': 'A result has several unlabelled proofs',
	'unexpected-proof': 'A proof of something that needs none',
	'missing-proof': 'A result has no proof',
	'needs-classification': 'A block needs its basis said',
	'misplaced-basis': 'A basis line outside a block',
	'equation-in-proof-referenced': 'Another block cites an equation inside a proof',
	'uses-missing': 'A proof cites something its \\uses does not list',
	'uses-unused': 'A \\uses entry the proof never mentions',
	'see-redundant': 'A see line repeats itself',
	'dependency-cycle': 'Results depend on each other in a circle',
	'snippet-failed': 'TeX could not make a text, shown as its source',
	'closure-failed': 'A block does not compile on its own',
	'import-outside-tree': 'An imported file lies outside the paper',
	'non-utf8-source': 'A file is not UTF-8',
	'unknown-theoremstyle': 'An unknown theorem style',
	'taxon-name-macro': 'An environment named by an undefined macro',
	'main-not-found': 'The default document is not a document',
	'main-unset': 'No default document',
	'unknown-config-key': 'An unknown setting',
	'retired-ledger-key': 'An acceptance of a block that is gone',
	'detached-annotation': 'Annotations lost their place',
	'previous-key-match': 'An acceptance matches a renamed proof',
	'foreign-annotations': 'An unreadable line in the annotation log',
	'foreign-evidence': 'An unreadable line in the evidence log',
	'foreign-asks': 'An unreadable line in the log of asks',
	'superseded-file': 'A document a conversion replaced',
	'history-missing': 'Part of the history is gone',
	'history-edited': 'The history was edited by hand',
	'history-corrupt': 'The history cannot be read',
	'history-interrupted': 'A step was interrupted',
	'dangling-ancestry': 'The history names a step it no longer has',
	'id-reused': 'A retired id is used again',
	'node-recovered': 'A retired id is back with its old text',
	'no-live-document': 'No document of yours',
	'derived-id-in-person-document': "An agent's id in your document",
	'agent-document-unrecorded': "An agent's copy with no record of its making",
	'plain-id-in-agent-document': "A plain id in an agent's copy",
	'agent-permissions-stale': "Claude Code's permissions are out of date",
	'home-missing': 'The home page is missing',
	'link-target-missing': 'A link to something that is not there',
	'link-place-missing': 'A link to a heading or place that is not there',
	'link-work-unknown': 'A link to a work the library does not hold',
	'link-words-missing': 'A link whose quoted words are gone',
	'bib-entry-refused': 'A bibliography entry the library cannot take',
	'write-left': 'A write loom could neither finish nor undo',
	'document-gone': 'A document is gone',
	'compile-failed': 'A document did not compile',
	'compile-errors': 'A document compiled with errors'
};

/** What `d` says is wrong: its code's title at its severity, else its code's, else its message. */
export function titleOf(d: Pick<Diagnostic, 'code' | 'message' | 'severity'>): string {
	const name = d.code.replace(/^[^:]*:/, '');
	return TITLES[`${name} ${d.severity}`] ?? TITLES[name] ?? d.message;
}

export interface Group {
	title: string;
	/** Every code in the group, in the order met. */
	codes: string[];
	severity: string;
	items: Diagnostic[];
}

const ORDER: Record<string, number> = { error: 0, warning: 1, info: 2 };

/** Diagnostics by what is wrong, worst first; within a severity, the larger group first. */
export function groupProblems(items: Diagnostic[]): Group[] {
	const map = new Map<string, Group>();
	for (const d of items) {
		const title = titleOf(d);
		let g = map.get(title);
		if (!g) map.set(title, (g = { title, codes: [], severity: d.severity, items: [] }));
		g.items.push(d);
		if (!g.codes.includes(d.code)) g.codes.push(d.code);
		if ((ORDER[d.severity] ?? 3) < (ORDER[g.severity] ?? 3)) g.severity = d.severity;
	}
	return [...map.values()].sort((a, b) => (ORDER[a.severity] ?? 3) - (ORDER[b.severity] ?? 3) || b.items.length - a.items.length || a.title.localeCompare(b.title));
}

/** The three parts of Problems: the person's errors and warnings, an agent's copy's, and every remark. */
export interface Parts {
	yours: Diagnostic[];
	copy: Diagnostic[];
	remarks: Diagnostic[];
}

export function partsOf(items: Diagnostic[]): Parts {
	const out: Parts = { yours: [], copy: [], remarks: [] };
	for (const d of items) {
		if (d.severity === 'info') out.remarks.push(d);
		else if (ownerOf(d) === 'copy') out.copy.push(d);
		else out.yours.push(d);
	}
	return out;
}

/** The errors and warnings in the person's own LaTeX: what Problems counts. */
export function yoursCount(m: Pick<Manifest, 'diagnostics'>): number {
	return partsOf(forPerson(m.diagnostics)).yours.length;
}

/** Where `d` is read: its first key's place, else its first location's file at the line, else nothing. A file the viewer does not show (loom's own) has no place. */
export function openUrl(m: Manifest, d: Diagnostic): string {
	const key = d.keys.find((k) => keyTarget(m, k));
	if (key) return placeUrl(m, key);
	const loc = d.locations.find((l) => m.files?.some((f) => f.path === l.file));
	return loc ? lineUrl(m, loc.file, loc.line) : '';
}

/** A shown file at one line. */
export function lineUrl(m: Manifest, path: string, line: number): string {
	return pathFor(m, { kind: 'file', id: path, anchor: `L${line}` });
}

/** The fixes a viewer acts on itself, by the endpoint each names, and the rest, each a command an agent runs, which a person is never shown. */
export function splitFixes(d: Diagnostic): { acts: Fix[]; commands: Fix[] } {
	const fixes = d.fixes ?? [];
	return { acts: fixes.filter((f) => f.act), commands: fixes.filter((f) => !f.act) };
}

export function countBySeverity(items: Diagnostic[]): Record<string, number> {
	const out: Record<string, number> = {};
	for (const d of items) out[d.severity] = (out[d.severity] ?? 0) + 1;
	return out;
}
