// The ask for the person's name that a write refused for want of it opens (`write`, `NameAsk`): one ask at a time, every write refused meanwhile waiting on the same answer.

/** Whether the box is showing. */
export const naming = $state<{ open: boolean }>({ open: false });

/** Whether a box is mounted to ask in: a page with none (the home page, a test) answers at once that nothing was saved. */
let mounted = 0;
let waiting: ((saved: boolean) => void)[] = [];

/** Mount the box: `NameAsk` calls it on mount and the returned function on destroy. */
export function mountAsk(): () => void {
	mounted++;
	return () => {
		mounted--;
		if (!mounted) answer(false);
	};
}

/** Ask for the name; true once it is saved and the page reads it, false when the person leaves it. */
export function askName(): Promise<boolean> {
	if (!mounted) return Promise.resolve(false);
	naming.open = true;
	return new Promise((resolve) => waiting.push(resolve));
}

/** The person saved the name, or left it: every write waiting hears it, and the box goes. */
export function answer(saved: boolean): void {
	naming.open = false;
	const told = waiting;
	waiting = [];
	for (const resolve of told) resolve(saved);
}
