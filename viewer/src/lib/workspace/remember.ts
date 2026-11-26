// The workspace's address remembered across visits, per quilt (keyed by `keptUnder`), so `/` reopens what was open as it was left: a reload, or the next day, as well as a return from Review. In this browser only, as the display preferences are; a browser that cannot store it just starts at the default document.

import type { Manifest } from '$lib/manifest/types';
import { keptUnder } from '$lib/manifest/kept.svelte';
import { itemFromPath } from './item';

const KEY = 'viewer.workspace';

function read(): Record<string, string> {
	try {
		const raw = globalThis.localStorage?.getItem(KEY);
		const o = raw ? JSON.parse(raw) : {};
		return o && typeof o === 'object' ? (o as Record<string, string>) : {};
	} catch {
		return {};
	}
}

/** The address last open in the quilt kept under `key`, or `''`. */
export function remembered(key: string): string {
	const at = key ? read()[key] : undefined;
	return typeof at === 'string' ? at : '';
}

/** Keep the address now open in quilt `name`; nothing until `/_api` has said which quilt it is. */
export function remember(name: string, address: string): void {
	const key = keptUnder(name);
	if (!key) return;
	try {
		const all = read();
		if (all[key] === address) return;
		all[key] = address;
		globalThis.localStorage?.setItem(KEY, JSON.stringify(all));
	} catch {
		// a browser that cannot store it still has the address for this visit, in the workspace
	}
}

/** The address remembered for this corpus, when what its first pane opens is still in it; `''` otherwise, so a deleted draft falls through to the default, as a work does, which nothing the manifest says confirms. */
export function rememberedIn(m: Manifest): string {
	const at = remembered(keptUnder(m.corpus.name));
	const it = at ? itemFromPath(m, at) : null;
	if (!it) return '';
	const there =
		it.kind === 'document'
			? m.masters.some((x) => x.path === it.id) || (m.canon ?? []).some((x) => x.path === it.id)
			: it.kind === 'pdf'
				? m.masters.some((x) => x.path === it.id && !!x.pdf)
			: it.kind === 'work'
				? false
				: it.kind === 'session'
					? (m.sessions ?? []).some((x) => x.id === it.id) || !!m.threads[it.id]
					: it.kind === 'page'
						? it.id === 'state' && !!m.research_state
						: it.kind === 'file'
							? !!m.files?.some((f) => f.path === it.id)
							: !!m.nodes[it.id];
	return there ? at : '';
}
