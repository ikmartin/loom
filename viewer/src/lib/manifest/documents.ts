// What a document is, read from its manifest entry.

import type { Manifest, Master } from './types';

/** Whether a document is an agent's: a copy of one of the person's documents, `copy_of` naming it, as the history records it (docs/specs/manifest.md §2a). */
export function isAgentDocument(m: Pick<Master, 'copy_of'> | null | undefined): boolean {
	return !!m?.copy_of;
}

/** The quilt's main draft as the manifest gives it: `[quilt] main`, else its only document of the person's; null where it names none. */
export function mainDraft(m: Pick<Manifest, 'masters'> | null | undefined): string | null {
	return m?.masters.find((x) => x.default && !isAgentDocument(x))?.path ?? null;
}
