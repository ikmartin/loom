// What the home page's window shows of a new quilt's create, from loom's answers: its steps, where a refusal is said (under the name, or in place of the form), and when the create has ended (`QuiltWindow.svelte`).

import type { Job, QuiltRow } from './api';

/** A create's steps as the window lists them, as loom names them. */
export const STEPS = ['making', 'starting'] as const;

/** Where the step loom names stands in the list; one it does not list is the first. */
export function stepAt(step: string): number {
	const at = STEPS.indexOf(step as never);
	return at < 0 ? 0 : at;
}

/** How a refusal is said: under the name, which the person can change and try again, or in place of the form, with Close. */
export type Said = { under: 'exists' | 'beingMade' | 'insideQuilt' } | { refused: 'stopping' | 'unreachable' | 'unreadable' } | { failed: true };

/**
 * Where a refusal of `quilt-create`, or a create job's failure, is said.
 *
 * Parameters
 * ----------
 * code : str
 *     Loom's code: the answer's `error.code`, or the job's `why`.
 * making : bool, default False
 *     Whether a create of the same name in the same place is running, which `exists` then means.
 *
 * Returns
 * -------
 * Said
 */
export function saidOf(code: string, making = false): Said {
	switch (code) {
		case 'exists':
			return { under: making ? 'beingMade' : 'exists' };
		case 'inside-a-quilt':
			return { under: 'insideQuilt' };
		case 'stopping':
			return { refused: 'stopping' };
		case 'unreachable':
			return { refused: 'unreachable' };
		case 'list-unreadable':
			return { refused: 'unreadable' };
		default:
			return { failed: true };
	}
}

/**
 * Where a create stands once loom answered it with a job: running, done and served (its row running), done but not served (its row failed), or failed.
 *
 * Parameters
 * ----------
 * job : Job, optional
 *     The job as the list gives it; absent before the list holds it.
 * row : QuiltRow, optional
 *     The quilt it made, once the list holds it.
 *
 * Returns
 * -------
 * str
 *     `running`, `served`, `unserved` or `failed`. A create's own `done` comes before its quilt's server answers, so the window shows its last step until the row says running.
 */
export function outcomeOf(job?: Job, row?: QuiltRow): 'running' | 'served' | 'unserved' | 'failed' {
	if (!job || job.state === 'running') return 'running';
	if (job.state === 'failed') return 'failed';
	if (row?.state === 'running' && row.url) return 'served';
	if (row && (row.state === 'failed' || row.state === 'missing' || row.state === 'stopped')) return 'unserved';
	return 'running';
}
