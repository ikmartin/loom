// Settings › Modes: the quilt's modes, each with when it fits, whether its text is loom's or edited in this quilt, whether a newer version from loom waits beside it, and the text itself; editing one, and putting loom's text back. An entry is named for the place it shows, with a comment saying where, on one line.

export const modes = {
	settings: {
		/** The section's name in the Settings panel. */
		section: 'Modes',
		/** Under the section's title: where the modes are kept. */
		where: "Kept in this quilt's .loom/agents/instructions/modes/, a file for each mode, shared with everyone who has the quilt. Only you change them here; an agent cannot.",
		/** The one row's name. */
		name: 'Modes',
		/** What the row is. */
		what: 'The ways of working an agent here may reach for, in the order it is shown them. Each opens with a line saying when it fits, which is all an agent sees of it until it chooses the mode or is asked for it; then it reads the whole text.'
	},
	/** The list of modes, on the left: its accessible name. */
	list: 'Modes',
	/** Under a mode's name in the list and beside it in the detail: whose its text is. */
	state: {
		loom: "loom's",
		edited: 'edited here'
	},
	/** Beside a mode's name, where `loom upgrade` left loom's newer version beside the quilt's edited copy. */
	newer: 'newer from loom',
	/** The same, said in full in the mode's detail, with the file it is in. */
	newerWhat: (path: string) => `Loom has a newer version of this mode than the one this quilt's edit started from. It is in ${path}.new, beside the edit, to compare and merge by hand.`,
	/** The detail's heading over the "When it fits" line. */
	fits: 'When it fits',
	/** In its place, for a mode whose text has dropped the line. */
	noFits: 'Its text has no "When it fits:" line, so an agent sees its name alone.',
	/** The detail's heading over the text. */
	text: 'Its text',
	/** Under the text: what an agent reads in place of a type's placeholder. */
	types: 'Where it says {type:ID}, an agent reads the name of that annotation type.',
	/** At the head of the section, where the quilt has no agent layer. */
	noLayer: "No agent's app is set up here yet, so these are loom's own, which an agent set up here is given.",
	/** In place of the list, where the loom serving the quilt sends no modes. */
	none: 'The loom serving this quilt does not list its modes.',
	/** Under a mode's name in the list, while it has an edit not yet saved. */
	unsaved: 'unsaved',
	/** The buttons in a mode's detail. */
	edit: 'Edit',
	save: 'Save',
	saving: 'Saving…',
	cancel: 'Cancel',
	putBack: "Put back loom's",
	/** The text field while editing: its accessible name. */
	field: 'The text of the mode',
	/** Asked before putting loom's text back over an edit. */
	putBackAsk: (name: string) => `Put loom's text of the ${name} mode back? This quilt's edit of it is replaced, and agents here are given loom's from their next look at it.`,
	/** The confirm and the way out of it. */
	putBackYes: 'Put back',
	keepEdit: 'Keep the edit',
	/** Where an edit is saved: what an agent reads of it, and when. */
	savedHint: "Agents here read the saved text the next time they look at this mode; one already running sees a new \"When it fits\" line when its app next starts loom.",
	/** When loom refused a save with no sentence of its own. */
	refused: 'Loom did not save it.',
	/** Where the loom serving the quilt cannot save a mode. */
	older: 'The loom serving this quilt is older than this page and cannot save a mode. Reload this page once loom has restarted with its update.',
	/** In place of a mode's text, where the loom serving the quilt does not send it. */
	noText: "The loom serving this quilt does not send a mode's text. Reload this page once loom has restarted with its update."
};
