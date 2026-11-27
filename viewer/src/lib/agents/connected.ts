// The agents connected to the quilt (specs/write-api.md §1, `connected`): one record per agent server alive as `loom serve` last looked, which is a conversation in an agent's app. "Connected" is a record in the list; "active" is one whose last call is under two minutes old. Neither says the agent is working, so the words never say "watching" or "working".

import { agents as words } from '$lib/words/agents';

/** One agent server alive as `loom serve` last looked. */
export interface Connected {
	format: number;
	pid: number;
	ppid: number;
	/** The name the agent writes as. */
	as: string;
	/** The app's own name, title and version, as its first request gave them; null where it gave none. */
	client: { name?: string; title?: string; version?: string } | null;
	protocol: string | null;
	/** The app's id for the conversation; null where the app sets none. */
	conversation: string | null;
	/** How the app was started: `claude-desktop` in the Claude app; null where the app says nothing. */
	entrypoint: string | null;
	/** The loom session it writes into; null until it has one. */
	session: string | null;
	loom: string;
	started: string;
	/** The latest call; null before the first. */
	last: { kind: 'tool' | 'prompt' | 'resource'; name: string; when: string } | null;
}

/** A call this recent makes a record active. */
export const ACTIVE_MS = 2 * 60 * 1000;

/** The app a record is a conversation of, as a person names it. */
export function appOf(r: Connected): string {
	return r.client?.title || r.client?.name || r.as || words.anApp;
}

/** Where the app was started, in words; '' where the record does not say. */
export function startedIn(r: Connected): string {
	if (r.entrypoint === 'claude-desktop') return words.startedIn.desktop;
	if (r.entrypoint === 'cli') return words.startedIn.terminal;
	return '';
}

/** Whether a record's last call is under two minutes old at `now`. */
export function isActive(r: Connected, now: number): boolean {
	if (!r.last) return false;
	const t = Date.parse(r.last.when);
	return Number.isFinite(t) && now - t < ACTIVE_MS;
}

/** How long ago `when` was at `now`, in a few words; '' for a time that does not parse. */
export function ago(when: string, now: number): string {
	const t = Date.parse(when);
	if (!Number.isFinite(t)) return '';
	const s = Math.max(0, Math.round((now - t) / 1000));
	if (s < 45) return words.ago.now;
	const min = Math.round(s / 60);
	if (min < 60) return words.ago.min(min);
	const h = Math.round(min / 60);
	if (h < 24) return words.ago.hours(h);
	return new Date(t).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

/** A clock time for `when`, as 14:02. */
export function clock(when: string): string {
	const t = Date.parse(when);
	return Number.isFinite(t) ? new Date(t).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : '';
}

/** What a call was: a tool by its name with loom's prefix dropped (`loom_ai_orient` is "the ai orient tool"), never as a command; a prompt by its mode. */
export function callOf(last: NonNullable<Connected['last']>): string {
	if (last.kind === 'prompt') return words.call.prompt(last.name);
	if (last.kind === 'resource') return words.call.resource;
	return words.call.tool(last.name.replace(/^loom_/, '').replace(/_/g, ' '));
}

export type Tone = 'unknown' | 'none' | 'connected' | 'active';

/** What the chip says: its tone, its line, and the line under it. */
export interface ChipWords {
	tone: Tone;
	lead: string;
	sub: string;
}

/**
 * The chip's words for `records` at `now`; `null` records mean the stream is down and nothing is known.
 *
 * One conversation reads "Claude Code connected"; more read "Claude Code · 2 conversations"; the line under says whether the latest call makes it active, and how long ago it was.
 */
export function chipWords(records: Connected[] | null, now: number): ChipWords {
	if (records === null) return { tone: 'unknown', lead: words.chip.unknown, sub: words.chip.unknownWhy };
	if (!records.length) return { tone: 'none', lead: words.chip.none, sub: '' };
	const apps = [...new Set(records.map(appOf))];
	const lead = records.length === 1 ? words.chip.one(apps[0]) : words.chip.many(apps.join(', '), records.length);
	const latest = records
		.map((r) => r.last)
		.filter((l): l is NonNullable<Connected['last']> => !!l)
		.sort((a, b) => b.when.localeCompare(a.when))[0];
	const active = records.some((r) => isActive(r, now));
	const sub = latest ? words.chip.lastCall(ago(latest.when, now), active) : words.chip.noCall;
	return { tone: active ? 'active' : 'connected', lead, sub };
}

/** The records of one app, by `client.name` (`claude-code`, `codex-mcp-client`) or, failing that, its title. */
export function ofApp(records: Connected[] | null, names: readonly string[]): Connected[] {
	return (records ?? []).filter((r) => names.includes(r.client?.name ?? '') || names.includes(r.client?.title ?? ''));
}
