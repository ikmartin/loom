// A note said once: shown the first visit it applies, and for the rest of that visit until it is closed. Remembered in this browser by its words, so it is said again only when what it says changes (another name, another list of places); a browser that keeps nothing says it each visit.

const KEY = 'arras.said';

/** The notes shown in this visit, and those closed in it. */
const shown = new Set<string>();
const closed = new Set<string>();

function said(): string[] {
	try {
		const v: unknown = JSON.parse(globalThis.localStorage?.getItem(KEY) ?? '[]');
		return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
	} catch {
		return [];
	}
}

/** Whether note `words` is to be shown now; the first time it is, it is recorded as said. */
export function once(words: string): boolean {
	if (!words || closed.has(words)) return false;
	if (shown.has(words)) return true;
	const before = said();
	if (before.includes(words)) return false;
	shown.add(words);
	try {
		globalThis.localStorage?.setItem(KEY, JSON.stringify([...before, words].slice(-40)));
	} catch {
		// shown this visit all the same
	}
	return true;
}

/** Note `words` closed: not shown again in this visit. */
export function closeOnce(words: string): void {
	closed.add(words);
	shown.delete(words);
}
