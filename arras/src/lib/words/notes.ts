// Notes' words: the actions at a selection (Quote, Annotate, New note), New note in an item's toolbar, what a new note's toast says, the Notes list of a quilt's note files, and Settings › Notes. An entry is named for the place it shows, with a comment saying where, on one line.

export const notes = {
	/** The actions at the end of a selection, on documents and PDF pages alike. */
	menu: {
		/** Hover text on the button standing at the end of a selection, which a click opens. */
		hover: 'Quote, annotate or start a note on these words',
		/** The button's accessible name. */
		label: 'Actions on the words selected',
		/** The menu's accessible name. */
		menu: 'What to do with the words selected',
		/** The first action: copy the words and where they came from. */
		quote: 'Quote',
		/** Hover text on Quote. */
		quoteHover: 'Copy the words, with where they came from, to paste to your agent',
		/** The second action: mark the words in the look in hand. */
		annotate: 'Annotate',
		/** Hover text on Annotate. */
		annotateHover: 'Mark the words in the look in hand, to comment on them',
		/** The third action: run the person's new-note command with a link to the words. */
		newNote: 'New note',
		/** Hover text on New note at a selection. */
		newNoteHover: 'Start a note of your own on these words, with a link back to them'
	},
	/** A place on a PDF's page, as a quote and a new note name it. */
	page: (name: string, n: number) => `${name} p. ${n}`,
	/** The toast after Quote. */
	quoted: {
		title: 'Quoted for your agent',
		/** Its last line, when the clipboard took the quote. */
		copied: 'Copied with where it came from. Paste it to your agent.',
		/** Its last line, when the browser refused the clipboard. */
		refused: 'This browser refused the clipboard, so nothing was copied.'
	},
	/** New note in an item's toolbar, for the whole document, work, page or file. */
	toolbar: {
		/** The button's words. */
		label: 'New note',
		/** Its hover text and accessible name. */
		hover: (name: string) => `Start a note of your own on ${name}, with a link back to it`
	},
	/** The toast after New note. */
	made: {
		/** Title when the person's command ran. */
		ran: 'New note sent to your editor',
		/** Its line: what the command printed, if anything, else this. */
		ranLine: 'Your new-note command ran with the link and the words.',
		/** Title when no command is set and loom wrote a Markdown note. */
		wrote: (path: string) => `New note: ${path}`,
		/** Its line. */
		wroteLine: 'Opened in the app this computer opens Markdown with. To use your own editor, set its command in Settings › Notes.',
		/** Title when loom refused or the command failed. */
		failed: 'No note made',
		/** Its line when the publisher said nothing. */
		noAnswer: 'loom did not answer'
	},
	/** The "All notes" tab: every file in the quilt that links into it. */
	all: {
		/** The tab's heading. */
		heading: 'Notes',
		/** Under the heading. */
		lede: 'Every file in this quilt that links to a place in it, with the places it links to. A note is a file of your own, written in your own editor.',
		/** When no file links anywhere. */
		none: 'No file links to a place in this quilt yet. Select words and choose New note to start one.',
		/** On a row: how many places it links to. */
		links: (n: number) => (n === 1 ? '1 link' : `${n} links`),
		/** Hover text on a row. */
		open: (path: string) => `Open ${path}`
	},
	/** Settings › Notes. */
	settings: {
		/** The section's name in the Settings panel. */
		section: 'Notes',
		/** Under the section's title: where each of its two settings is kept. */
		where: "The folder is saved in this quilt's config.toml and shared with everyone who has the quilt. The command is yours alone, kept on this computer for this quilt; it never travels with the quilt, and an agent cannot set it.",
		/** The folder's row. */
		dir: 'Notes folder',
		/** What the folder does. */
		dirWhat: 'Where a new note goes. Notes beside a document list every file that links to it, wherever the file is.',
		/** The folder picker's accessible name. */
		dirPick: 'Pick the notes folder from the files of this quilt',
		/** The picker's first option, the default folder. */
		dirDefault: (dir: string) => `${dir}/ (the default)`,
		/** The command's row. */
		command: 'New-note command',
		/** What the command does. */
		commandWhat: 'Run when you choose New note, with no shell. Write `{link}`, `{quote}`, `{title}`, `{dir}` or `{quilt}` where each goes, or `{request}` for the path of a JSON file holding all five, which an editor that evaluates what it is given, such as `emacsclient -e`, must use. Selected words may begin with a dash, so put `--` before a placeholder where the program reads options. Empty, loom writes a Markdown note in the folder and opens it.',
		/** The command field's placeholder. */
		commandPlaceholder: 'emacsclient -n -e \'(my-new-note "{request}")\'',
		/** Saving the command. */
		save: 'Save command',
		/** While it saves. */
		saving: 'Saving…',
		/** After it saved. */
		saved: 'Saved for you, for this quilt.',
		/** Where it is kept, after its path. */
		kept: (path: string) => `Kept in ${path}`,
		/** When the publisher cannot keep a command, or a viewer with none serving it. */
		cannot: 'The loom serving this quilt cannot keep a command. Stop loom serve, run it again, then reload.'
	}
};
