// What a result's status, as the reads pass it on from `evidence.md` §5, is drawn as: round six's glyphs, one vocabulary on every surface (`docs/specs/library-views.md` §2, "Status").

import type { LeanStatus, Paper } from '$lib/library/types';
import type { MarkKind } from './Mark.svelte';

/** A reading of the paper as a mark: `matches` is the filled circle, the rest are as named. */
export const paperMark = (p: Paper): MarkKind => (p === 'matches' ? 'checked' : p);

/** A Lean status as a mark: formalized, or assumed where its role is; the person's colour where it waits on them (Lean accepted it unattested, it changed since, or a library result under it is theirs to compare or attest); an outline where it waits on reading or on nothing yet. */
export function leanMark(l: LeanStatus): MarkKind {
	if (l.lean === 'formalized') return l.role === 'assumed' ? 'assumed' : 'formalized';
	if (l.lean === 'unattested' || l.lean === 'changed') return 'attest';
	if (l.lean === 'waiting') return (l.waiting_on ?? []).some((w) => w.why === 'unchecked' || w.why === 'unattested') ? 'attest' : 'not';
	return 'not';
}
