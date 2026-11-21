// Docs' words: its column, the picker, a work beside a draft, the notes tab, the Lean marks and the formalize panel. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none.

export const docs = {
	files: {
		/** The head over the project's files in Docs' column, which folds and opens them. */
		head: 'Files',
		/** Hover text on that head: the directory it shows. */
		title: (dir: string) => `View of files in ${dir}/`,
		/** Under the short drawer a hover lets down from the folded head. */
		openAll: 'click Files to open them all',
		/** The row for the quilt's research state, where the publisher lists no files. */
		researchState: 'Research state'
	},
	picker: {
		/** The button in Docs' column that opens the library over Docs. */
		open: 'Library',
		/** The picker's search field. */
		search: 'find a work by title or author',
		/** Beside the search: how many works. */
		count: (n: number) => (n === 1 ? '1 work' : `${n} works`),
		/** The two layouts. */
		list: 'list',
		thumbnails: 'thumbnails',
		/** The list's column heads, each sorting by itself. */
		title: 'Title',
		authors: 'Authors',
		year: 'Year',
		/** Hover text on the label a draft cites a work by. */
		citedAs: (doc: string, label: string) => `${doc.split('/').pop() ?? doc} cites it as ${label}`,
		/** A thumbnail of a work loom holds no document of. */
		noDocument: 'no document',
		/** The picker's close button. */
		close: 'Close the library'
	},
	card: {
		/** Under a cited result's name on its card: its work, and the page it stands on where known. */
		at: (short: string, page: string) => (page ? `${short} · page ${page}` : short),
		/** On a cited stub's card. */
		stub: 'Loom knows this result only by its number. Nobody has read it.',
		/** Opens the work beside the draft at the result's place. */
		open: 'open at its place',
		/** Opens a stub's work beside the draft where loom finds its name. */
		locate: 'locate in PDF',
		/** Asks an agent to read a stub. */
		read: 'ask an agent to read it',
		/** The column's message after asking. */
		asked: 'Asked an agent to read it. It comes back in Review, under Digested results to check.'
	},
	notes: {
		/** The button in Docs' column that opens the notes tab. */
		open: 'Notes',
		/** The notes tab's name. */
		tab: 'All notes',
		/** Before the two orders. */
		sortBy: 'sort by',
		work: 'work',
		date: 'date',
		/** The box that shows or hides the notes that lost their place. */
		showOrphaned: (n: number) => `show orphaned notes (${n})`,
		/** The head over the notes that lost their place. */
		orphaned: 'Orphaned · their document is gone, or their words are not found',
		/** Under a group: the notes it holds beyond those shown, which a click shows. */
		more: (n: number) => `${n} more`,
		/** Under the notes by date. */
		older: (n: number) => `${n} more, older`,
		/** Who wrote a note and when. */
		byAt: (by: string, at: string) => `${by} · ${at}`,
		/** Where an orphaned note was. */
		was: (where: string) => `was on ${where}`,
		/** On an orphaned note: anchors it again. */
		place: 'place it again',
		/** The column's message after "place it again", until placing is built. */
		placeHow: 'Click where the note belongs, or select its words.',
		/** Deletes a note. */
		delete: 'delete',
		/** The column's message after deleting. */
		deleted: 'Note deleted.'
	},
	column: {
		/** The label over the focused document's sections, low in Docs' column. */
		outline: 'Outline',
		/** The line between the files and the outline in Docs' column, which the reader drags; its accessible name. */
		resizeOutline: 'Resize the outline'
	}
} as const;
