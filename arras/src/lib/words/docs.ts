// Docs' words: its column, the picker, a work beside a draft, the notes tab, the Lean marks and the formalize panel. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none.

/** TeX's messages the viewer says in the person's words, by how each begins; any other is said as TeX said it. */
const TEX: [RegExp, string][] = [
	[/^Undefined control sequence/i, 'a command it uses is not defined'],
	[/^Environment .* undefined/i, 'an environment it uses is not defined'],
	[/^Missing \$ inserted/i, 'a formula is not closed, or mathematics stands outside one'],
	[/^(Missing \} inserted|Extra \}|Too many \}'s|Missing \{ inserted)/i, 'a brace is not matched'],
	[/^\\begin\{.*\} (on input line \d+ )?ended by \\end/i, 'an environment is ended by the wrong \\end'],
	[/^(LaTeX Error: )?File .* not found/i, 'a file it reads is missing'],
	[/^Emergency stop/i, 'TeX stopped before the end']
];

export const docs = {
	/** Over a draft whose last compile, after a change, made no PDF: its file, why (`texError`), and the line TeX stopped at, '' where unknown. */
	notCompiled: (file: string, why: string, line: string) => `${file} has not compiled since it last changed${why ? `: ${why}` : ''}${line ? ` (line ${line})` : ''}. The PDF is the one from before.`,
	/** Over a draft whose last compile finished with errors but made a PDF: its file, TeX's first error (`texError`), and the line it was at, '' where unknown. */
	compiledWithErrors: (file: string, why: string, line: string) => `${file} compiled with errors${why ? `: ${why}` : ''}${line ? ` (line ${line})` : ''}. The PDF was made anyway and may be wrong there.`,
	/** A compile's error and its line, as a title or a line under the paper says them. */
	compileError: (why: string, line: string) => `${why}${line ? ` (line ${line})` : ''}`,
	/** TeX's message in the person's words where the viewer knows it, else as TeX said it; '' for none. */
	texError: (error: string): string => {
		const e = error.replace(/^!\s*/, '').trim();
		// a file TeX could not find is named, being the person's own to put right
		const file = /^(?:LaTeX Error: )?File [`'"‘]([^`'"’]+)['"’] not found/i.exec(e)?.[1];
		if (file) return `${file}, a file it reads, is missing`;
		return TEX.find(([re]) => re.test(e))?.[1] ?? e.replace(/\.$/, '');
	},
	work: {
		/** A work's tab in Docs, where its short name is not known: the library no longer holds it, or the works list is being read. */
		deleted: 'a deleted work',
		unread: 'a work'
	},
	files: {
		/** The head over the project's files in Docs' column, which folds and opens them. */
		head: 'Files',
		/** Hover text on that head: the directory it shows. */
		title: (dir: string) => `View of files in ${dir}/`,
		/** The row for the quilt's research state, where the publisher lists no files. */
		researchState: 'Research state'
	},
	picker: {
		/** The button in Docs' column that opens the library over Docs. */
		open: 'Open a work…',
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
	formalize: {
		/** The panel's head. */
		title: (name: string) => `Formalize ${name}`,
		/** What the head names when several results are asked for at once. */
		these: (n: number) => `these ${n} results`,
		/** The panel's close button. */
		close: 'Close the formalize panel',
		/** The sentence under the statements, from what the plan holds. */
		lead: (one: boolean, parts: string[]) => `To formalize ${one ? 'this' : 'them'}, an agent will ${parts.length < 2 ? (parts[0] ?? '') : `${parts.slice(0, -1).join(', ')}, and ${parts[parts.length - 1]}`}.`,
		state: (n: number) => `state ${n} ${n === 1 ? 'definition' : 'definitions'} in Lean`,
		prove: (n: number, one: boolean) => `prove ${n} ${one ? 'of your lemmas' : 'of your results'}`,
		assumeOwn: (n: number, one: boolean) => `assume ${n} ${one ? 'of your lemmas' : 'of your results'} for now`,
		assumeLibrary: (n: number) => `assume ${n} ${n === 1 ? 'result' : 'results'} from your library`,
		/** The two parts over what the plan cannot do yet. */
		stops: 'Stops the request',
		before: 'Before it reads formalized',
		/** A result with no label, and that it stops the request. */
		noLabel: (name: string, doc: string) => `${name} has no label, so a Lean statement could not name it. Add one in ${doc.split('/').pop() ?? doc}, then ask again.`,
		stopsLine: 'This stops the request.',
		/** What keeps the result from reading formalized, and where each waits. */
		notRead: (what: string, many: boolean) => `${what} ${many ? 'have' : 'has'} not been read.`,
		notReadWhere: (many: boolean) => (many ? 'Wait in Review, under Cited results to digest.' : 'Waits in Review, under Cited results to digest.'),
		notChecked: (what: string, many: boolean) => `${what} ${many ? 'have' : 'has'} not been checked against ${many ? 'their papers' : 'its paper'}.`,
		notCheckedWhere: (many: boolean) => (many ? 'Wait in Review, under Digested results to check.' : 'Waits in Review, under Digested results to check.'),
		attest: (names: string, many: boolean) => `${names} ${many ? 'wait' : 'waits'} for you to attest ${many ? 'their' : 'its'} Lean statement.`,
		attestWhere: 'In Review, under Lean statements to attest.',
		attestedChanged: (names: string, many: boolean) => `${names} changed after you attested ${many ? 'their' : 'its'} Lean statement.`,
		attestedChangedWhere: 'In Review, under Attested results that changed.',
		/** A Lean statement the agent will write, which then waits for the person's word. */
		attestAfter: (names: string, many: boolean) => `${names} will wait for you to attest ${many ? 'their' : 'its'} Lean statement once it is written.`,
		/** A Lean that comes round, through what it rests on, to a result already asked of. */
		cycle: (names: string, many: boolean) => `The Lean of ${names} ${many ? 'come' : 'comes'} round, through what ${many ? 'they rest' : 'it rests'} on, to a result already asked of; only Lean written another way settles it.`,
		/** The line under what only the agent's work makes possible. */
		afterWhere: "After the agent's work.",
		/** Citations in what the targets use that name no result. */
		cite: (keys: string[]) => (keys.length === 1 ? `The citation of ${keys[0]} names no result of its work.` : `The citations of ${keys.slice(0, -1).join(', ')} and ${keys[keys.length - 1]} name no result of their works.`),
		/** The line under what nothing done now settles. */
		waitingWhere: 'Nothing you do now settles this; loom does not yet tell which result a citation means.',
		/** A label two blocks bear near the target, and the blocks. */
		ambiguous: (label: string, names: string) => `The label ${label} is on ${names}, so a Lean statement could not tell which is meant.`,
		ambiguousWhere: (doc: string) => `Give one of them another label in ${doc.split('/').pop() ?? doc}.`,
		/** A label, a library result or a result that nothing answers to. */
		missingLabel: (label: string) => `No block bears the label ${label}.`,
		missingNode: 'A library result it uses is no longer in the library.',
		missing: (name: string) => `${name} reads as no one text.`,
		missingWhere: (doc: string) => `Put it right in ${doc.split('/').pop() ?? doc}, or in the library.`,
		/** Under the part before it reads formalized. */
		beforeNote: (name: string | null) => (name ? `None of these stops the request; ${name} reads formalized only once all of them are done.` : 'None of these stops the request; they read formalized only once all of them are done.'),
		/** A library result of another work, after its name. */
		of: (what: string, short: string) => `${what} of ${short}`,
		/** The lists' heads. */
		toState: 'To state',
		toProve: 'To prove',
		toAssume: 'To assume',
		formalized: 'Already formalized',
		/** The choice on a result of the person's to prove. */
		proveIt: 'prove',
		assumeForNow: 'assume for now',
		/** Beside a library result to assume. */
		notReadYet: 'not read yet',
		notCheckedYet: 'not checked yet',
		/** In place of a statement loom knows only by its number. */
		numberOnly: 'Loom knows it only by its number.',
		/** The panel's button. */
		ask: (name: string) => `ask an agent to formalize ${name}`,
		needsLabel: (name: string) => `add a label to ${name} first`,
		/** Beside the button. */
		task: (one: boolean) => (one ? 'It becomes one task in Review, under Waiting for an agent.' : 'One task a result in Review, under Waiting for an agent.'),
		/** The column's message after asking. */
		asked: (name: string, one: boolean) => `Asked an agent to formalize ${name}. ${one ? 'It waits' : 'They wait'} in Review, under Waiting for an agent.`
	},
	textSize: {
		/** The text size control on an HTML draft's toolbar, its accessible name as a group, with the draft's name. */
		group: (of: string) => `Text size of ${of}`,
		/** Its step down: hover text, and with the draft's name its accessible name. */
		smaller: 'Smaller text',
		smallerOf: (of: string) => `Smaller text in ${of}`,
		/** Its step up. */
		larger: 'Larger text',
		largerOf: (of: string) => `Larger text in ${of}`,
		/** The box between the steps, which shows the size and takes one typed; its accessible name. */
		box: (of: string) => `Text size in ${of}`,
		/** What the box shows: the size in px. */
		said: (px: number) => `${px} px`
	},
	leanMarks: {
		/** The item in a draft's view menu that shows or hides the Lean marks. */
		toggle: 'Lean marks',
		/** Hover text on a mark of a result not formalized, which a click opens the formalize panel from. */
		not: 'not formalized · formalize…',
		/** The column's message on a click on a mark of a result Lean accepted that waits for the person. */
		waits: (name: string) => `${name}: Lean accepted, not attested. It waits for you in Review.`
	},
	column: {
		/** The label over the focused document's sections, low in Docs' column. */
		outline: 'Outline',
		/** The line between the files and the outline in Docs' column, which the reader drags; its accessible name. */
		resizeOutline: 'Resize the outline'
	}
} as const;
