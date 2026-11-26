// Whether this page is loom's home page, and what the home lists. `GET /_api` answering `home: true` makes the frame draw the home page in place of a quilt (`judgeHome`, as `judgeFormat` does for a quilt an earlier loom made); the list is `quilt-list`, asked once a second while the page is in view, since a quilt's server starts, stops and fails on its own.

import type { Capabilities } from '$lib/write';
import { call, type Job, type Listing, type QuiltRow } from './api';

/** How often the list is asked for while the page is in view. */
const EVERY = 1000;

class Home {
	/** True once `GET /_api` said this is the home. */
	is = $state(false);
	/** The list as last answered; null before the first answer. */
	listing = $state.raw<Listing | null>(null);
	/** Whether the last ask went unanswered. */
	unreachable = $state(false);
	#timer: ReturnType<typeof setInterval> | null = null;

	/** Ask for the list now. */
	async refresh(): Promise<void> {
		const r = await call<Listing>('quilt-list');
		if (r.ok) {
			this.listing = r.value;
			this.unreachable = false;
		} else this.unreachable = r.code === 'unreachable';
	}

	/** Ask now and then once a second while the page is in view, until `stop`. */
	start(): void {
		if (this.#timer) return;
		void this.refresh();
		this.#timer = setInterval(() => {
			if (typeof document === 'undefined' || document.visibilityState === 'visible') void this.refresh();
		}, EVERY);
	}

	stop(): void {
		if (this.#timer) clearInterval(this.#timer);
		this.#timer = null;
	}
}

export const homePage = new Home();

/** Take a probe's answer: the home says `home: true`, a quilt's server names the home's address there instead. */
export function judgeHome(caps: Capabilities | null): void {
	homePage.is = caps?.home === true;
}

/**
 * The rows the page lists: each quilt, and before them each quilt being made that the list does not hold yet.
 *
 * Parameters
 * ----------
 * listing : Listing
 *     `quilt-list`'s answer.
 *
 * Returns
 * -------
 * list
 *     `{quilt}` for a quilt on the list, `{making}` for a create still running.
 */
export function rowsOf(listing: Listing): ({ quilt: QuiltRow } | { making: Job })[] {
	const known = new Set(listing.quilts.map((q) => q.folder));
	const making = listing.jobs.filter((j) => j.kind === 'create' && j.state === 'running' && j.name && !known.has(j.folder ?? ''));
	return [...making.map((j) => ({ making: j })), ...listing.quilts.map((q) => ({ quilt: q }))];
}

/**
 * A path as the page writes it: under the person's home folder with `~`.
 *
 * Parameters
 * ----------
 * path : str
 *     An absolute path.
 * home : str, optional
 *     The person's home folder, as `quilt-list` gives it.
 *
 * Returns
 * -------
 * str
 */
export function shortPath(path: string, home?: string): string {
	if (!home) return path;
	const h = home.replace(/\/+$/, '');
	if (path === h) return '~';
	return path.startsWith(h + '/') ? '~' + path.slice(h.length) : path;
}

/** The newest Repair TeX job, running or ended; null when none ran. */
export function repairOf(listing: Listing | null): Job | null {
	return listing?.jobs.find((j) => j.kind === 'repair') ?? null;
}

/** The `source` loom gives a name read from git's own settings. */
const FROM_GIT = 'git config user.name';

/**
 * The person's name as the page shows it: asked for while none is known, else with where it comes from only when that is git, since any other source is a file's path (I-13).
 *
 * Parameters
 * ----------
 * listing : Listing or null
 *     `quilt-list`'s answer.
 *
 * Returns
 * -------
 * object
 *     `{asked: true}` while no name is known, else `{name, fromGit}`; null before the list answers.
 */
export function nameOf(listing: Listing | null): { asked: true } | { asked: false; name: string; fromGit: boolean } | null {
	if (!listing) return null;
	const { name, source } = listing.name;
	return name ? { asked: false, name, fromGit: source === FROM_GIT } : { asked: true };
}
