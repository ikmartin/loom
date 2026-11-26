// The home page's words: the list of quilts and each one's state, the controls on a row, the TeX notice, and the list that cannot be read. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none. No word here names a command, an id or an endpoint.

export const home = {
	/** The browser tab's title on the home page. */
	title: 'Your quilts',
	/** The home page's heading, above the list. */
	heading: 'Your quilts',
	/** The button at the heading's right that opens the system's folder dialog to put a quilt on the list. */
	openQuilt: 'Open a quilt…',
	/** The primary button at the heading's right that makes a new, empty quilt. */
	newQuilt: 'New quilt',
	/** The notice under the heading when the folder chosen by Open a quilt… is not a quilt. */
	notAQuilt: 'That folder is not a quilt.',
	/** The notice under the heading when the system has no folder dialog. */
	noDialog: 'Loom cannot show a folder dialog here.',
	/** The close button on a notice under the heading. */
	close: 'close',
	empty: {
		/** The empty list's heading, inside its dashed drop area. */
		heading: 'Drop your paper here',
		/** The empty list's first line, before and after the monospaced `.tex`. */
		paper: ['Its ', '.tex', ' file, its folder, or its source archive becomes a new quilt, open on your paper.'] as const,
		/** The empty list's second line. */
		pdf: 'A PDF becomes a new quilt for reading it.',
		/** The empty list's grey line at its foot, saying what a quilt is. */
		what: 'A quilt is a folder for one piece of research: the papers you write or read, and your notes on them.'
	},
	/** The grey line under a list that holds quilts, before and after the monospaced `.tex`. */
	hint: ['Drop a paper anywhere on this page to make a new quilt from it: its ', '.tex', ' file, its folder or its source archive, or a PDF to read.'] as const,
	state: {
		/** A row's state word for a quilt being served. */
		running: 'Running',
		/** A row's state word while its server starts. */
		starting: 'Starting…',
		/** A row's state word for a quilt not served. */
		stopped: 'Not running',
		/** A row's state for a quilt whose folder is gone. */
		missing: 'Its folder is not where it was',
		/** A row's state when another program holds the quilt's port. */
		portTaken: 'Another program is using its address',
		/** A row's state when the quilt's server refused to start, above what it said. */
		refused: 'Loom could not open it:',
		/** A row's state when the quilt's server died after its last start again. */
		exited: 'It stopped by itself three times',
		/** A row's state when loom could not start the quilt's server, above the reason. */
		cannotStart: 'Loom could not start it:',
		/** A row's state while a new quilt is made, from New quilt or a drop. */
		making: 'Being made…',
		/** In the box under "Loom could not open it:", for a quilt a newer loom made. */
		formatNewer: (found: number, reads: number) => `this quilt is format ${found}; this loom reads format ${reads}`,
		/** The hint under a quilt a newer loom made, which this loom cannot open. */
		newer: 'A newer loom made this quilt. To update loom, paste the line from loom’s GitHub page into Terminal again, as when you installed it; then open this quilt here.'
	},
	control: {
		/** A running or stopped row's Open button. */
		open: 'Open',
		/** Hover text on a running row's Open. */
		openRunning: 'Opens it in its own tab',
		/** Hover text on a stopped row's Open. */
		openStopped: 'Starts it and opens it in its own tab',
		/** A running row's Stop button. */
		stop: 'Stop',
		/** Hover text on Stop. */
		stopTip: 'Stops serving it; its folder is untouched',
		/** A row's Forget button. */
		forget: 'Forget',
		/** Hover text on Forget. */
		forgetTip: 'Takes it off this list; its folder stays where it is',
		/** A failed row's button that starts the quilt again. */
		again: 'Open again',
		/** The button on a row whose port another program holds. */
		move: 'Move to a new address',
		/** The grey line under Move to a new address. */
		moveSaid: 'Its layout and preferences start afresh there.',
		/** The small button that copies a report for whoever helps. */
		copy: 'Copy details',
		/** Hover text on Copy details. */
		copyTip: 'Copies a report on loom and this machine, with the quilt’s last lines of output, for whoever helps you',
		/** Hover text on Copy details where no quilt is concerned. */
		copyMachineTip: 'Copies a report on loom and this machine, for whoever helps you',
		/** What Copy details turns into once copied. */
		copied: 'Copied',
		/** What Copy details turns into when the browser refused the copy. */
		notCopied: 'Could not copy',
		/** Said in the row's state when a control's request was refused, with loom's reason. */
		refusedNow: 'That did not work.'
	},
	tex: {
		/** The notice under the heading when loom has no TeX. */
		none: 'Loom has no TeX yet: papers show as their source.',
		/** The notice's button that installs loom's own TeX. */
		repair: 'Repair TeX',
		/** The notice while Repair TeX runs, above its latest line. */
		repairing: 'Repairing TeX',
		/** The notice when Repair TeX ended without TeX. */
		failed: 'TeX could not be repaired.'
	},
	/** The notice in place of the list when loom cannot read it. */
	unreadable: 'Loom cannot read its list of quilts, so it shows none and gives no quilt an address until it can; the list is kept as it was. Quilts already open stay open.',
	name: {
		/** The card under the heading, while no name is known: what the name is for. */
		ask: 'Your name, as it appears beside your comments and decisions',
		/** The name field's placeholder. */
		placeholder: 'Your name',
		/** The button that saves the name. */
		save: 'Save',
		/** The quiet button that leaves the name as it was. */
		cancel: 'Cancel',
		/** In the footer while the name is changed, before its field. */
		label: 'Your name',
		/** In the footer, before the person's name. */
		shown: 'Your name: ',
		/** In the footer, after the name, where it comes from git. */
		fromGit: ', from git',
		/** The footer's link that changes the name. */
		change: 'Change',
		/** Said under the field when the name given is an agent's. */
		agent: 'That name is kept for agents; give your own.',
		/** Said under the field when loom could not save the name. */
		refused: 'Loom could not save it.'
	},
	cover: {
		/** The sheet over the page while a paper, folder or archive is dragged over it. */
		paper: 'New quilt from your paper',
		/** The sheet over the page while a PDF is dragged over it. */
		pdf: 'New quilt for reading this paper'
	},
	window: {
		/** The window's title for a drop of a paper, folder or archive. */
		paper: 'New quilt from your paper',
		/** The window's title for a dropped PDF. */
		pdf: 'New quilt for reading this paper',
		/** The window's title for New quilt, with no paper. */
		empty: 'New quilt',
		/** The window's close button. */
		close: 'close',
		/** What the window says was dropped: a folder, before and after its name in bold, with how many files it holds. */
		droppedFolder: (n: number) => ['You dropped ', `, a folder of ${n.toLocaleString('en')} ${n === 1 ? 'file' : 'files'}.`] as const,
		/** What the window says was dropped: one file, before and after its name in bold. */
		droppedFile: ['You dropped ', '.'] as const,
		/** What the window says was dropped: several files or folders at once. */
		droppedMany: (n: number) => `You dropped ${n.toLocaleString('en')} files.`,
		/** The form's label before the quilt's name. */
		name: 'Name',
		/** The empty name field's placeholder, in New quilt. */
		namePlaceholder: 'Name of the quilt',
		/** The form's label before where the quilt goes. */
		folder: 'Folder',
		/** Where the quilt goes, in the form and in New quilt. */
		place: (where: string) => `In ${where}`,
		/** The link beside where the quilt goes, which opens the system's folder dialog. */
		change: 'Change…',
		/** Hover text on Change…. */
		changeTip: "Choose where the new quilt's folder goes",
		/** The window's quiet button that puts it away. */
		cancel: 'Cancel',
		/** The window's primary button. */
		create: 'Create',
		/** Hover text on Create while no file is chosen as the paper. */
		chooseFirst: 'Choose the paper first',
		/** The one question, when several files could be the paper. */
		question: 'Which file is the paper?',
		/** The window's steps, in order. */
		steps: { making: 'Making the quilt', importing: 'Bringing your paper in and typesetting it', starting: 'Opening it' },
		/** The second line under the typesetting step while it runs. */
		importingSub: 'The first time can take a few minutes.',
		/** The step for a PDF, in place of the typesetting step. */
		reading: 'Bringing the PDF into its library',
		/** Done: the quilt is made and served. */
		ready: (name: string) => `${name} is ready.`,
		/** Done, the paper not typeset, before where TeX stopped. */
		untypeset: 'Your paper is in, shown as its source:',
		/** Done, the paper not typeset because loom has no TeX. */
		noTex: 'Loom has no TeX yet.',
		/** Done, the paper not typeset: TeX's own error, as TeX words it. */
		texStopped: (error: string) => `TeX stopped at “${error}”.`,
		/** Done, the paper not typeset, where TeX gave no error of its own. */
		texStoppedPlain: 'TeX stopped before it finished.',
		/** Done, but its server could not start; its row says why. */
		madeNotOpen: (name: string) => `${name} is made and on your list, but loom could not open it.`,
		/** The primary button once done, which opens the quilt in its own tab. */
		open: 'Open it',
		/** The window's button that puts a refusal away. */
		closeButton: 'Close',
		/** Under the name: a folder of that name is there. */
		exists: 'A folder of that name is there already.',
		/** Under the name: a quilt of that name is being made there. */
		beingMade: 'That quilt is being made already.',
		/** Under the name: the folder chosen is inside a quilt. */
		insideQuilt: 'That folder is inside a quilt.',
		/** Refused: the home is stopping. */
		stopping: "Loom's home page is stopping.",
		/** Refused: nothing answered. */
		unreachable: "Loom's home page did not answer.",
		/** The hint under either. */
		stoppingHint: 'Open Loom from your Applications folder or the Dock, then drop it again.',
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
		/** Refused: the list of quilts cannot be read. */
		unreadable: 'Loom cannot read its list of quilts, so it made nothing.',
		/** Failed: the paper could not come in, above what loom said. */
		failed: 'Loom could not bring your paper in, and made nothing:',
		/** Failed, with nothing more to say. */
		failedPlain: 'Loom could not make the quilt, and made nothing.'
	},
	report: {
		/** The first line of what Copy details copies. */
		head: 'Loom on this machine',
		/** The heading in what Copy details copies above the quilt's last lines of output. */
		log: 'The quilt’s last lines of output',
		/** The heading in what Copy details copies above a create's failure. */
		failure: 'What loom said'
	}
};
