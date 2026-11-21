// Docs' words: its column, the picker, a work beside a draft, the notes tab, the Lean marks and the formalize panel. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none.

export const docs = {
	column: {
		/** The label over the focused document's sections, low in Docs' column. */
		outline: 'Outline',
		/** The line between the files and the outline in Docs' column, which the reader drags; its accessible name. */
		resizeOutline: 'Resize the outline'
	}
} as const;
