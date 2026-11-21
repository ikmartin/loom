// Which source the library's reads and writes go to, chosen once at start: round six's fixture when the page was opened with `?fixture=round6` (kept for the tab's visit) or the build was made with `VITE_FIXTURE=round6`, the publisher otherwise. The fixture is what each view is built and tested against until its read exists.

import { useSource, waitForSource } from './api';
import { library } from './gen.svelte';

const KEY = 'arras.fixture';

/** Whether this visit runs on the fixture: asked once, then remembered for the tab. */
function wanted(): boolean {
	if (import.meta.env.VITE_FIXTURE === 'round6') return true;
	if (typeof window === 'undefined') return false;
	try {
		if (new URL(window.location.href).searchParams.get('fixture') === 'round6') sessionStorage.setItem(KEY, 'round6');
		return sessionStorage.getItem(KEY) === 'round6';
	} catch {
		return false;
	}
}

let chosen: Promise<void> | null = null;
let fixture = false;

/** Whether this visit runs on round six's fixture rather than a publisher. */
export const onFixture = (): boolean => fixture;

/** Points the library's client at the fixture when this visit asks for it. Begun once, as this module loads in the browser, so every read waits on it rather than racing it. */
export function chooseSource(): Promise<void> {
	chosen ??= (async () => {
		if (!wanted()) return;
		fixture = true;
		const { fixtureSource } = await import('./fixtures/source');
		const made = fixtureSource((gen) => library.heard(gen));
		useSource(made);
		library.heard(made.data.gen);
	})();
	return chosen;
}

if (typeof window !== 'undefined') waitForSource(chooseSource());
