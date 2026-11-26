// What stands in for a result the viewer cannot draw itself (`docs/specs/library-views.md` §3.4, "Drawing a node"): TeX's drawing, asked for only once the person has compiled the work's source here, or the one question that compiles it, asked once for the work and never for an agent.

import { SvelteSet } from 'svelte/reactivity';
import { message } from '$lib/shell/message.svelte';
import { library as words } from '$lib/words/library';
import * as api from './api';
import { said } from './said';
import type { NodeAnswer } from './types';

/** Works whose source the person compiled in this page, by reference, before a read says so. */
export const compiledHere = new SvelteSet<string>();

/** For a node: the address of TeX's drawing where its work's source is compiled here, else null; and whether to ask the person to compile it, which only a work holding a source can be. */
export function drawing(n: NodeAnswer, here: ReadonlySet<string> = compiledHere): { drawn: string | null; ask: boolean } {
	const compiled = n.compiled === true || (n.compiled === false && here.has(n.work.ref));
	return { drawn: compiled && n.hash ? api.drawnUrl(n.hash, n.macros?.hash ?? null) : null, ask: n.compiled === false && !compiled };
}

/** The person's yes: their work's source compiled, its results drawn by TeX from then on. */
export async function compile(work: { ref: string; short: string }): Promise<void> {
	const done = await api.compileWork(work.ref);
	if (!done.ok) return message.post(said(done.error));
	compiledHere.add(work.ref);
	message.post(words.draw.compiling(work.short));
}
