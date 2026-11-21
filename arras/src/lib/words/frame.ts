// The frame's words: the column's head and foot, the four views' names and their hover cards, the marks' legend, and the column's message. Every sentence the viewer says is written in this folder, a file for each view and this one for the frame; a component holds none (`scripts/checks/words.py`). An entry is named for the place it shows, with a comment saying where, on one line, so that words seen on screen are found by searching for them.

export const frame = {
	views: {
		/** The row of four view names under the quilt's name, and the folded column's strip; its accessible name. */
		nav: 'Views',
		docs: {
			/** The first of the four view names. */
			name: 'Docs',
			/** Hover card on the view name Docs, after a short delay. */
			hover: 'Write and edit your documents. A paper from your library opens beside your draft, and changes proposed to your text show where they apply.'
		},
		library: {
			/** The second of the four view names. */
			name: 'Library',
			/** Hover card on the view name Library. */
			hover: 'The papers you rely on. Find one, read and annotate it, and digest its results so that your drafts can cite and check them.'
		},
		web: {
			/** The third of the four view names. */
			name: 'Web',
			/** Hover card on the view name Web. */
			hover: 'Every result and what it rests on, across your drafts and your library. Start from any result and follow what it uses and what uses it.'
		},
		review: {
			/** The fourth of the four view names. */
			name: 'Review',
			/** Hover card on the view name Review. */
			hover: 'What waits for your decision: questions from agents, edits proposed to your text, digested results to check against their papers, and Lean statements to attest.'
		}
	},
	column: {
		/** The button at the column's head that folds it to a strip. */
		hide: 'Hide the column',
		/** The button at the top of the folded strip that opens the column again. */
		show: 'Show the column',
		/** The line at the column's right edge, which the reader drags; its accessible name. */
		resize: 'Resize the column',
		/** Under the quilt's name, in a read-only view: whose review it shows. */
		perspective: (name: string) => `Review status for ${name}`,
		/** Under the quilt's name, in a read-only view whose reviewer is not named. */
		perspectiveUnnamed: 'Review perspective unspecified',
		/** The column's head while the manifest has not come yet, in place of the quilt's name; also the browser tab's title meanwhile. */
		unnamed: 'loom'
	},
	message: {
		/** The column's message, its accessible name as a group. */
		label: 'What was just done',
		/** The link in the column's message that takes back what was just done. */
		undo: 'undo',
		/** The close button on the column's message. */
		dismiss: 'Dismiss',
		/** The column's message when an undo failed, with the publisher's reason. */
		undoFailed: (why: string) => (why ? `It could not be undone: ${why}` : 'It could not be undone.')
	},
	legend: {
		/** The quiet link in the column's foot that opens the legend of the marks. */
		open: 'what the marks mean',
		/** The legend's first line, over the marks of a result's reading of its paper. */
		head: 'The marks, on every screen',
		/** The legend's line over the marks of Lean. */
		lean: 'Lean',
		/** The legend's line over the mark a person puts on a page. */
		page: 'On a page'
	},
	marks: {
		/** A result's paper mark, filled green: the person found loom's copy matches its paper. Also the mark's accessible name. */
		checked: 'matches the paper',
		/** A result's paper mark, an amber ring: digested and not compared with its paper yet. */
		unchecked: 'not compared yet',
		/** A result's paper mark, a dotted ring: a stub, known and not read. */
		stub: 'not read',
		/** The flag on a place of a page the person marked to digest. */
		marked: 'marked by you',
		/** A result's Lean mark, a filled diamond. */
		formalized: 'formalized',
		/** A result's Lean mark, an amber diamond: Lean accepted it and it waits for the person's word. */
		attest: 'Lean accepted, not attested',
		/** A result's Lean mark, a half-filled diamond. */
		assumed: 'assumed in Lean',
		/** A result's Lean mark, an outlined diamond. */
		not: 'not formalized'
	},
	page: {
		/** The heading of the page shown when the manifest could not be read. */
		problems: 'Problems',
		/** The page shown while the manifest is loading. */
		loading: 'Loading manifest…'
	}
} as const;
