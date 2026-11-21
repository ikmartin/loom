// What a failed read or write says to a person: the publisher's refusal, which is written for a reader, or, where the failure is the transport's or a name the publisher does not serve, a sentence of the viewer's. No endpoint's name, file or code reaches a person.

import { frame } from '$lib/words/frame';
import type { ApiError } from './api';

/** The codes that are the transport's or the publisher's routing, never a refusal a person can read. */
const NOT_SERVED = new Set(['not-served', 'unknown-endpoint']);

/** A failure in a sentence; `notServed`, the view's own words where it says it is not served yet. */
export function said(e: ApiError, notServed: string = frame.errors.notServed): string {
	if (NOT_SERVED.has(e.code)) return notServed;
	if (e.code === 'unreachable') return frame.errors.unreachable;
	if (e.code === 'failed' || !e.message.trim()) return frame.errors.failed;
	return e.message;
}
