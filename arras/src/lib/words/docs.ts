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
	column: {
		/** The label over the focused document's sections, low in Docs' column. */
		outline: 'Outline',
		/** The line between the files and the outline in Docs' column, which the reader drags; its accessible name. */
		resizeOutline: 'Resize the outline'
	}
} as const;
