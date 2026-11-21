// The Library's words: its column, the list of works, a work's tab, the reader's overlay, a result beside its page, and the drop of a paper. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none.

export const library = {
	/** The Library's page until its list of works is built on this branch; taken out with it. */
	placeholder: 'The Library is being built.',
	work: {
		/** A work's tab in Docs, opened by a link to a note on it, in place of its pages, which only the Library can open; taken out once it does. */
		unread: "This work's pages open from the Library, which is being built.",
		/** A work's toolbar, on `open the PDF` and the PDF's tools while no PDF is drawn. */
		noPdf: 'No PDF of this work is open'
	},
	reader: {
		/** The reader, in place of the pages, for a work holding no PDF. */
		noPdf: 'Loom holds no PDF of this work.'
	}
} as const;
