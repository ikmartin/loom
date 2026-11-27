// Docs' words: its column, the page of a quilt with nothing to read, the picker, a work beside a draft, the notes tab, the Lean marks and the formalize panel. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none.

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
	start: {
		/** The page of a quilt with nothing to read, where the publisher takes no paper. */
		nothing: 'Nothing to read yet.',
		/** The heading of the dashed drop area on the page of a quilt with nothing to read. */
		heading: 'Drop your paper here',
		/** The drop area's first line, before and after the monospaced `.tex`. */
		paper: ['Its ', '.tex', ' file, its folder, or its source archive comes into this quilt, open on your paper.'] as const,
		/** The drop area's second line. */
		pdf: 'A PDF comes into its library, for reading it.',
		/** The link under the drop area's lines, which opens the system's file dialog. */
		choose: 'or choose a file…',
		/** While a dropped paper comes in, in place of the link. */
		bringingPaper: 'Bringing your paper in and typesetting it',
		/** While dropped PDFs come in. */
		bringingPdf: 'Bringing the PDF into its library',
		/** While the file dialog is open, and while what was chosen in it comes in. */
		bringingChosen: 'Bringing it in',
		/** The grey line under a paper coming in. */
		bringingSub: 'The first time can take a few minutes.',
		/** The one question, when several files could be the paper. */
		question: 'Which file is the paper?',
		/** The button under the question that brings in the file chosen. */
		bring: 'Bring it in',
		/** Hover text on that button while no file is chosen. */
		chooseFirst: 'Choose the paper first',
		/** The quiet button under the question that puts it away. */
		cancel: 'Cancel',
		/** Refused: no `.tex` that begins a document. */
		noPaper: 'That holds no LaTeX file that begins a document.',
		/** The hint under it, before and after the monospaced `.tex`. */
		noPaperHint: ["Drop the folder or archive that holds your paper's ", '.tex', ' file, or a PDF to read it.'] as const,
		/** Refused: an archive loom cannot open safely. */
		badArchive: 'Loom cannot open that archive.',
		/** The hint under it. */
		badArchiveHint: 'Open it yourself, and drop the folder it holds.',
		/** Refused: more than a drop may hold. */
		tooLarge: 'That is more than 1 GB.',
		/** The hint under it. */
		tooLargeHint: 'Drop only the folder that holds the paper.',
		/** Refused: the system has no file dialog. */
		noDialog: 'Loom cannot show a file dialog here; drop the file instead.',
		/** Failed: the paper could not come in, above what loom said. */
		failed: 'Loom could not bring your paper in:',
		/** Failed, with nothing more to say. */
		failedPlain: 'Loom could not bring it in.'
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
		/** The row for the quilt's research state, in the tree or, where the publisher lists no files, alone. */
		researchState: 'Research state',
		/** Hover text on a folded folder in the tree holding the file being read: that file, as a path from the folder. */
		holds: (file: string) => `Holds ${file}, which is open`
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
		asked: 'Asked an agent to read it. It comes back in Review, under Results to check.'
	},
	beside: {
		/** The Notes list beside a document, a work or a PDF, and the toolbar button that opens it: the files of the quilt that link here. */
		title: 'Notes',
		/** Hover text on the toolbar's Notes button. */
		hover: 'Notes: the files in this quilt that link here',
		/** Accessible name of the toolbar's Notes button, with how many files link here. */
		named: (of: string, n: number) => `Notes in ${of}, ${n}`,
		/** Under the list's title. */
		sub: 'The files in this quilt that link here, each opening at its link.',
		/** The list's close button. */
		close: 'Close notes',
		/** The list with no file linking here. */
		none: 'No file links here yet. A note is a file of your own, in Markdown, org or plain text, anywhere in the quilt, holding a quilt: link to this place.',
		/** On a link that quotes no words: where it points. */
		at: (place: string) => (/^page=\d+$/.test(place) ? `page ${place.slice(5)}` : place ? `at ${place}` : 'links here'),
		/** At the right of each link: the line of the note it is on. */
		line: (n: number) => `line ${n}`
	},
	notes: {
		/** The button in Docs' column that opens the notes tab. */
		open: 'Notes',
		/** The notes tab's name. */
		tab: 'All notes'
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
		notReadWhere: (many: boolean) => (many ? "Wait in Review, under Cited results loom can't read." : "Waits in Review, under Cited results loom can't read."),
		notChecked: (what: string, many: boolean) => `${what} ${many ? 'have' : 'has'} not been checked against ${many ? 'their papers' : 'its paper'}.`,
		notCheckedWhere: (many: boolean) => (many ? 'Wait in Review, under Results to check.' : 'Waits in Review, under Results to check.'),
		attest: (names: string, many: boolean) => `${names} ${many ? 'wait' : 'waits'} for you to attest ${many ? 'their' : 'its'} Lean statement.`,
		attestWhere: 'In Review, under Lean statements to attest.',
		attestedChanged: (names: string, many: boolean) => `${names} changed after you attested ${many ? 'their' : 'its'} Lean statement.`,
		attestedChangedWhere: 'In Review, under Lean statements to attest.',
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
		task: (one: boolean) => (one ? 'It becomes one task in Review, under Agents still working.' : 'One task a result in Review, under Agents still working.'),
		/** The column's message after asking. */
		asked: (name: string, one: boolean) => `Asked an agent to formalize ${name}. ${one ? 'It waits' : 'They wait'} in Review, under Agents still working.`
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
	node: {
		/** Under a result whose proof is missing, where the proof would be. */
		noProof: 'No proof is attached.',
		/** After it, where the block waits to be accepted: what waits, and where, in words; nothing there leaves Docs. */
		waitsToAccept: 'It waits for you in Review, under Results to accept.'
	},
	history: {
		/** The word on a document's toolbar that opens its history menu, and the accessible names of the word and of the menu. */
		label: 'history',
		name: (of: string) => `history menu for ${of}`,
		menu: (of: string) => `history of ${of}`,
		/** The menu's first line, which opens a field to name the version in place; its accessible name. */
		record: 'record this version…',
		recordName: (of: string) => `record a version of ${of}`,
		/** The field that names the version to record, and its accessible name. */
		recordField: 'name this version',
		recordFieldName: (of: string) => `the name of the version of ${of} to record`,
		/** The button beside the field, and its accessible name. */
		recordGo: 'record',
		recordGoName: (of: string) => `record this version of ${of} under that name`,
		/** The column's message once a version is recorded: the document's file and the name. */
		recorded: (file: string, name: string) => `Recorded this version of ${file} as “${name}”.`,
		/** The line for the draft's own text, and a version's accessible name: its label and the document. */
		live: 'live text',
		versionName: (label: string, of: string) => `${label}, ${of}`,
		/** At a version's right, which compares it with the one shown; its accessible name. */
		compare: 'compare',
		compareName: (of: string, label: string) => `compare ${of} with ${label}`,
		/** The line for an agent's copy, or for a copy's source: its file. */
		compareWith: (file: string) => `compare with ${file}`,
		/** Under the newest versions, the line that lists the rest in the menu; once they are listed, the line that folds them again. Its accessible name. */
		older: (n: number) => `${n} older`,
		fewer: (n: number) => `only the newest ${n}`,
		olderName: (of: string) => `the older versions of ${of}`
	},
	/** A block drawn from the person's saved source while TeX typesets it (a demonstration): the note beside it, and that note's hover text. */
	draft: {
		text: 'typesetting…',
		title: 'Drawn from your saved source by the viewer. TeX’s typesetting replaces it when it is ready.'
	},
	column: {
		/** The label over the focused document's sections, low in Docs' column. */
		outline: 'Outline',
		/** The line between the files and the outline in Docs' column, which the reader drags; its accessible name. */
		resizeOutline: 'Resize the outline'
	}
} as const;
