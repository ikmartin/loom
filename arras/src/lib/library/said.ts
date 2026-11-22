// What a failed read or write says to a person: a sentence of the viewer's for each refusal of loom's (`words/frame.ts`, `refused`), the transport's and the routing's own, and a plain one for a code with none. Loom's own message is never drawn: it is written for the command line, and may name a setting, a request's field or an id.

import { frame } from '$lib/words/frame';
import type { ApiError } from './api';

/** The codes that are the publisher's routing, never a refusal a person can read. */
const NOT_SERVED = new Set(['not-served', 'unknown-endpoint']);

/** A failure in a sentence; `notServed`, the view's own words where it says it is not served yet. */
export function said(e: ApiError, notServed: string = frame.errors.notServed): string {
	if (NOT_SERVED.has(e.code)) return notServed;
	// the transport's failure has no answer, and so no status; loom's own `unreachable` (a service it asks) has one
	if (e.code === 'unreachable' && !e.status) return frame.errors.unreachable;
	return frame.refused[e.code] ?? frame.errors.failed;
}
