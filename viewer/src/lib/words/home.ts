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
	report: {
		/** The first line of what Copy details copies. */
		head: 'Loom on this machine',
		/** The heading in what Copy details copies above the quilt's last lines of output. */
		log: 'The quilt’s last lines of output',
		/** The heading in what Copy details copies above a create's failure. */
		failure: 'What loom said'
	}
};
