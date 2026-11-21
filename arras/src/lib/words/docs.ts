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
		open: 'Notes'
	},
	column: {
		/** The label over the focused document's sections, low in Docs' column. */
		outline: 'Outline',
		/** The line between the files and the outline in Docs' column, which the reader drags; its accessible name. */
		resizeOutline: 'Resize the outline'
	}
} as const;
