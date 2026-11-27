// What the viewer says of Lean on this computer, from `formal-state` (`write-api.md`), in the words of `words/lean.ts`: the install's and the check's progress by the step's code, how each ended, and whether the switch is on with a project and a sandbox. Loom's own sentence for a failure is never the line; it is kept for the fold beneath. Pure, so the unit tests hold it.

import { lean as words } from '$lib/words/lean';

/** What the server is doing for Lean in the quilt, or did last. */
export interface LeanJob {
	kind: 'install' | 'check';
	state: 'running' | 'done' | 'failed';
	/** The step it is on or failed at, by its code; '' before the first. */
	step: string;
	/** Why it failed, in loom's words; shown only folded. */
	said: string;
	found: { steps?: { step: string; seconds: number }[]; written?: string[]; unchanged?: string[]; unknown?: string[]; errors?: string[]; unprinted?: string[] };
}

/** `formal-state`'s answer. */
export interface LeanState {
	on: boolean;
	/** The quilt's Lake project's folder, or null for none. */
	project: string | null;
	/** Null where loom can check Lean here, else why not, by its code. */
	fence: string | null;
	job: LeanJob | null;
}

/** A step's words by its code, for the job's kind. */
function step(job: LeanJob): string {
	const table = job.kind === 'install' ? words.installStep : words.checkStep;
	return table[job.step] ?? '';
}

/**
 * What a job says: its progress while it runs, else how it ended.
 *
 * Parameters
 * ----------
 * job : LeanJob
 *     The job as `formal-state` sends it.
 *
 * Returns
 * -------
 * string[]
 *     One line while it runs; after it, what it did, then Lean's errors, the markers that name no result and the results recorded without Lean's print, where there are any.
 */
export function jobLines(job: LeanJob): string[] {
	if (job.state === 'running') return [job.kind === 'install' ? words.installing(step(job) || words.installStep['']) : words.checking(step(job) || words.checkStep[''])];
	if (job.state === 'failed') return [job.kind === 'install' ? words.installFailed(job.step ? step(job) : '') : words.checkFailed(job.step ? step(job) : '')];
	if (job.kind === 'install') return [words.installed((job.found.steps ?? []).reduce((t, s) => t + s.seconds, 0))];
	const lines = [words.checked(job.found.written?.length ?? 0, job.found.unchanged?.length ?? 0)];
	if (job.found.errors?.length) lines.push(words.errors(job.found.errors.length));
	if (job.found.unknown?.length) lines.push(words.unknown(job.found.unknown.length));
	if (job.found.unprinted?.length) lines.push(words.unprinted(job.found.unprinted.length));
	return lines;
}

/** Whether a job runs now, so the state is asked again shortly. */
export function running(state: LeanState | null): boolean {
	return state?.job?.state === 'running';
}

/** The line under the switch while it is on and nothing runs: the project, or that there is none yet; '' while it is off or a job runs. */
export function standing(state: LeanState): string {
	if (!state.on || running(state)) return '';
	return state.project ? words.ready(state.project) : words.noProject;
}

/** Why loom cannot check Lean here, while it is on; '' where it can. */
export function fenceLine(state: LeanState): string {
	if (!state.on || state.fence === null) return '';
	return words.noFence[state.fence] ?? words.noFenceOther;
}

/** Whether Install again is offered: on, nothing running, and the last install stopped or the quilt has no project. */
export function offersInstall(state: LeanState): boolean {
	return state.on && !running(state) && (state.job?.kind === 'install' && state.job.state === 'failed' ? true : !state.project);
}

/** Whether Check again is offered: on, a project, a sandbox, and nothing running. */
export function offersCheck(state: LeanState | null): boolean {
	return !!state && state.on && !!state.project && state.fence === null && !running(state);
}
