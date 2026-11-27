// What Copy details copies: a plain report for whoever helps the person, made from `quilt-check`'s answer. Doctor's rows are given by name, state and detail; their remedies, which are commands, are left out, since the person never types one and a helper knows them.

import { home as words } from '$lib/words/home';

/** One row of doctor's report, as `quilt-check` gives it. */
interface Item {
	name?: string;
	status?: string;
	detail?: string;
	remedy?: string;
}

/** `quilt-check`'s answer. */
export interface Check {
	doctor?: { python?: string; loom?: string; items?: Item[] };
	log?: string;
}

/**
 * The report Copy details copies.
 *
 * Parameters
 * ----------
 * check : Check
 *     `quilt-check`'s answer: doctor's report, and the quilt's last lines of output when a quilt was named.
 * said : str, default ''
 *     What loom said of a create that failed, put first.
 *
 * Returns
 * -------
 * str
 *     Plain text, one line a row.
 */
export function reportOf(check: Check, said = ''): string {
	const d = check.doctor ?? {};
	const out: string[] = [];
	if (said) out.push(`${words.report.failure}:`, said, '');
	out.push(`${words.report.head}: loom ${d.loom ?? '?'}, Python ${d.python ?? '?'}`);
	for (const i of d.items ?? []) out.push(`  ${i.name ?? ''}: ${i.status ?? ''}${i.detail ? ` (${i.detail})` : ''}`);
	if (check.log) out.push('', `${words.report.log}:`, check.log);
	return out.join('\n');
}
