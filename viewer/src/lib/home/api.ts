// The home page's client for the home server's endpoints (`docs/specs/write-api.md` §7). The home answers each with its own object, not a quilt server's `{ok, result}`, so it has its own call beside `write`; the token is the one `GET /_api` gave, as for every write.

import { base } from '$app/paths';
import { capabilities, forgetCapabilities } from '$lib/write';

/** A row of `quilt-list`: one quilt and its state. */
export interface QuiltRow {
	quilt: string;
	name: string;
	/** Where the quilt lies, absolute. */
	folder: string;
	port: number;
	open: boolean;
	state: 'running' | 'starting' | 'stopped' | 'failed' | 'missing';
	url?: string;
	why?: 'port-taken' | 'refused' | 'exited' | 'cannot-start';
	/** The last lines its server wrote, or why the home could not start it: loom's text, which the page words before it shows it (`said.ts`). */
	said?: string;
}

/** A job of `quilt-list`: a create or Repair TeX, running or ended. */
export interface Job {
	job: string;
	kind: 'create' | 'repair';
	state: 'running' | 'done' | 'failed';
	/** The step running: a create's `making` or `starting`; Repair TeX's latest line. */
	step: string;
	/** A create's quilt, by name and folder, from its first answer. */
	name?: string;
	folder?: string;
	/** A create's, once done. */
	quilt?: string;
	url?: string;
	/** Repair TeX's, once done. */
	tex?: Tex;
	/** A failed job's code and loom's words. */
	why?: string;
	said?: string;
}

export type Tex = 'loom' | 'mine' | 'none';

/** `quilt-list`'s answer. */
export interface Listing {
	quilts: QuiltRow[];
	list?: 'unreadable';
	name: { name: string; source: string };
	tex: Tex;
	jobs: Job[];
	home_folder?: string;
}

/** An answer, or loom's refusal by its code. */
export type Answer<T> = { ok: true; value: T } | { ok: false; code: string; message: string };

function url(endpoint: string): string {
	return `${base}/_api/${endpoint}`;
}

/**
 * Ask the home server.
 *
 * Parameters
 * ----------
 * endpoint : str
 *     One of the home's endpoints, `quilt-list` and its siblings.
 * body : object, default {}
 *     The request's JSON body.
 *
 * Returns
 * -------
 * Answer
 *     The home's answer, or its refusal; `unreachable` when nothing answered.
 */
export async function call<T>(endpoint: string, body: Record<string, unknown> = {}): Promise<Answer<T>> {
	try {
		const send = async () => {
			const caps = await capabilities();
			return fetch(url(endpoint), {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', ...(caps?.token ? { 'X-Loom-Token': caps.token } : {}) },
				body: JSON.stringify(body)
			});
		};
		let res = await send();
		// a home started again under the page has another token: asked again once
		if (res.status === 403) {
			forgetCapabilities();
			res = await send();
		}
		const said = (await res.json().catch(() => ({}))) as { error?: { code?: string; message?: string } };
		if (res.ok) return { ok: true, value: said as T };
		return { ok: false, code: said.error?.code ?? 'failed', message: said.error?.message ?? '' };
	} catch (err) {
		return { ok: false, code: 'unreachable', message: (err as Error).message };
	}
}
