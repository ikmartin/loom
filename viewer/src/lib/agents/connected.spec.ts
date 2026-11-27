import { describe, expect, it } from 'vitest';
import { ago, callOf, chipWords, isActive, ofApp, startedIn, type Connected } from './connected';

const NOW = Date.parse('2026-11-20T14:10:00Z');

function record(over: Partial<Connected> = {}): Connected {
	return {
		format: 1,
		pid: 4242,
		ppid: 4200,
		as: 'Claude Code Agent',
		client: { name: 'claude-code', title: 'Claude Code', version: '2.1.321' },
		protocol: '2026-07-28',
		conversation: 'c-1',
		entrypoint: 'claude-desktop',
		session: null,
		loom: '0.1.0',
		started: '2026-11-20T14:00:00Z',
		last: null,
		...over
	};
}

describe('the chip', () => {
	it('says it does not know while the stream is down, rather than what it last heard', () => {
		expect(chipWords(null, NOW)).toEqual({ tone: 'unknown', lead: 'Agents: not known', sub: 'loom is not answering' });
	});

	it('says no agent is connected when the list is empty', () => {
		expect(chipWords([], NOW)).toEqual({ tone: 'none', lead: 'No agent connected', sub: '' });
	});

	it('names the app of one conversation, and says no call yet before its first', () => {
		expect(chipWords([record()], NOW)).toEqual({ tone: 'connected', lead: 'Claude Code connected', sub: 'no call yet' });
	});

	it('is active while the last call is under two minutes old, and connected after', () => {
		const fresh = record({ last: { kind: 'tool', name: 'loom_since', when: '2026-11-20T14:09:20Z' } });
		expect(chipWords([fresh], NOW)).toEqual({ tone: 'active', lead: 'Claude Code connected', sub: 'active · last call just now' });
		const older = record({ last: { kind: 'tool', name: 'loom_since', when: '2026-11-20T14:07:00Z' } });
		expect(chipWords([older], NOW)).toEqual({ tone: 'connected', lead: 'Claude Code connected', sub: 'last call 3 min ago' });
	});

	it('counts conversations, the latest call across them deciding the line beneath', () => {
		const a = record({ pid: 1, last: { kind: 'tool', name: 'loom_here', when: '2026-11-20T13:50:00Z' } });
		const b = record({ pid: 2, last: { kind: 'prompt', name: 'referee', when: '2026-11-20T14:05:00Z' } });
		expect(chipWords([a, b], NOW)).toEqual({ tone: 'connected', lead: 'Claude Code · 2 conversations', sub: 'last call 5 min ago' });
	});

	it('names each app where conversations of two apps are connected', () => {
		const codex = record({ pid: 3, client: { name: 'codex-mcp-client', title: 'Codex' } });
		expect(chipWords([record(), codex], NOW).lead).toBe('Claude Code, Codex · 2 conversations');
	});

	it('names an app that gave no title by its name, and one that gave nothing by the agent', () => {
		expect(chipWords([record({ client: { name: 'codex-mcp-client' } })], NOW).lead).toBe('codex-mcp-client connected');
		expect(chipWords([record({ client: null, as: 'Survey Agent' })], NOW).lead).toBe('Survey Agent connected');
	});

	it('never says watching or working', () => {
		const said = [null, [], [record()], [record({ last: { kind: 'tool', name: 'loom_annotate', when: '2026-11-20T14:09:59Z' } })]].map((r) => JSON.stringify(chipWords(r as Connected[] | null, NOW)));
		for (const s of said) expect(s).not.toMatch(/watching|working/i);
	});
});

describe('the words of a record', () => {
	it('reads a call as its command, a prompt as its mode', () => {
		expect(callOf({ kind: 'tool', name: 'loom_ai_orient', when: '' })).toBe('the ai orient tool');
		expect(callOf({ kind: 'prompt', name: 'referee', when: '' })).toBe('the referee mode, started');
	});

	it('says where the app was started only where it says', () => {
		expect(startedIn(record())).toBe('in the Claude app');
		expect(startedIn(record({ entrypoint: null }))).toBe('');
		expect(startedIn(record({ entrypoint: 'sdk-cli' }))).toBe('');
		expect(startedIn(record({ entrypoint: 'cli' }))).toBe('in a terminal');
	});

	it('is active only with a call, and only a recent one', () => {
		expect(isActive(record(), NOW)).toBe(false);
		expect(isActive(record({ last: { kind: 'tool', name: 'x', when: 'not a time' } }), NOW)).toBe(false);
	});

	it('says how long ago in minutes, then hours', () => {
		expect(ago('2026-11-20T14:09:50Z', NOW)).toBe('just now');
		expect(ago('2026-11-20T13:10:00Z', NOW)).toBe('1 h ago');
		expect(ago('nonsense', NOW)).toBe('');
	});

	it('finds an app conversations by its client name or title', () => {
		const codex = record({ pid: 3, client: { name: 'codex-mcp-client', title: 'Codex' } });
		expect(ofApp([record(), codex], ['codex-mcp-client']).map((r) => r.pid)).toEqual([3]);
		expect(ofApp(null, ['claude-code'])).toEqual([]);
	});
});
