// The Web's list laid out as one column of lines of known heights, so that only the lines in view are drawn: a list of thousands of results draws the few dozen the person can see. Pure, so the layout is held by unit tests.

import type { Row, WebGroup, WebList, WebSection } from '$lib/library/types';

/** A line's height in pixels: a result, a work's or a document's row, a section's head, the list's last line. */
export const HEIGHT = { row: 28, group: 30, head: 32, note: 28 } as const;

export type Line =
	| { kind: 'head'; sec: WebSection; top: number }
	| { kind: 'group'; sec: WebSection; group: WebGroup; open: boolean; top: number }
	| { kind: 'row'; row: Row; indent: boolean; source: boolean; top: number }
	/** A row of an open group whose rows are not read yet, standing in for it at its height. */
	| { kind: 'pending'; group: string; top: number }
	| { kind: 'note'; top: number };

/** Every line of the list, its top in pixels from the list's top, and the list's whole height. */
export function lay(list: WebList, open: (sec: WebSection, g: WebGroup) => boolean, rowsOf: (g: WebGroup) => Row[] | null): { lines: Line[]; height: number } {
	const lines: Line[] = [];
	let top = 0;
	const push = (l: Line, h: number) => {
		lines.push(l);
		top += h;
	};
	if (list.rows) {
		for (const row of list.rows) push({ kind: 'row', row, indent: false, source: true, top }, HEIGHT.row);
		if (list.more) push({ kind: 'note', top }, HEIGHT.note);
		return { lines, height: top };
	}
	for (const sec of list.sections ?? []) {
		push({ kind: 'head', sec, top }, HEIGHT.head);
		for (const row of sec.rows ?? []) push({ kind: 'row', row, indent: false, source: false, top }, HEIGHT.row);
		for (const group of sec.groups ?? []) {
			const o = open(sec, group);
			push({ kind: 'group', sec, group, open: o, top }, HEIGHT.group);
			if (!o) continue;
			const rows = rowsOf(group);
			if (rows) for (const row of rows) push({ kind: 'row', row, indent: true, source: false, top }, HEIGHT.row);
			else for (let i = 0; i < group.n; i++) push({ kind: 'pending', group: group.group, top }, HEIGHT.row);
		}
	}
	if (list.undigested) push({ kind: 'note', top }, HEIGHT.note);
	return { lines, height: top };
}

/** The lines that stand in the view between `from` and `to` pixels, with `margin` pixels drawn beyond each end. */
export function inView(lines: Line[], from: number, to: number, margin = 280): Line[] {
	let lo = 0;
	let hi = lines.length;
	// the first line whose bottom is below the view's top
	while (lo < hi) {
		const mid = (lo + hi) >> 1;
		if (lines[mid].top + HEIGHT.group < from - margin) lo = mid + 1;
		else hi = mid;
	}
	const out: Line[] = [];
	for (let i = lo; i < lines.length && lines[i].top <= to + margin; i++) out.push(lines[i]);
	return out;
}

/** A graph's column as drawn: five of a column of more than six, the rest added to what the read said was left. */
export function capped<T>(rows: T[], more: number): { rows: T[]; more: number } {
	return rows.length > 6 ? { rows: rows.slice(0, 5), more: more + rows.length - 5 } : { rows, more };
}
