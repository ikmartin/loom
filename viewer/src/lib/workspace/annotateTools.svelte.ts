// Whether Annotate is on in every pane's toolbar: its tools that write (Annotate, Comment, the format menu, Undo and Redo, a PDF's drawing tools) stand in the toolbar's own row after it, those that do not fit in the menu its ˅ opens (`fold.ts`). On at first, and kept in this browser once it is turned off or on again.
//
// Turning it on arms nothing; turning it off puts down any tool in hand, so no tool is ever armed while its button is out of sight.

const KEY = 'viewer.annotate-tools';

class AnnotateTools {
	open = $state(true);

	constructor() {
		try {
			if (globalThis.localStorage?.getItem(KEY) === 'hidden') this.open = false;
		} catch {
			// a browser that stores nothing shows the tools
		}
	}

	/** Show or put away the tools, everywhere, and remember which. */
	set(open: boolean): void {
		this.open = open;
		try {
			globalThis.localStorage?.setItem(KEY, open ? 'shown' : 'hidden');
		} catch {
			// kept for this visit only
		}
	}
}

export const annotateTools = new AnnotateTools();
