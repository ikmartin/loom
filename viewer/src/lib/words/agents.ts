// Attach's words: the connection chip at the column's foot, the panel it opens of what an agent is told, sees and may change, the setup card in that panel and in Settings › Agents, and the Ask your agent box with the buttons that open it. An entry is named for the place it shows, with a comment saying where, on one line.

export const agents = {
	/** The connection chip at the foot of the column, open or folded to its dot. */
	chip: {
		/** The panel the chip opens; its accessible name. */
		panel: 'Agents',
		/** The chip while the stream to loom is down, so who is connected is not known. */
		unknown: 'Agents: not known',
		/** The line under it then. */
		unknownWhy: 'loom is not answering',
		/** The chip with no agent connected. */
		none: 'No agent connected',
		/** The chip with one conversation connected. */
		one: (app: string) => `${app} connected`,
		/** The chip with several conversations connected. */
		many: (apps: string, n: number) => `${apps} · ${n} conversations`,
		/** The line under the chip before any call. */
		noCall: 'no call yet',
		/** The line under the chip after a call, with whether the latest makes it active. */
		lastCall: (ago: string, active: boolean) => `${active ? 'active · ' : ''}last call ${ago}`,
		/** The chip's accessible name and, folded, its hover text: its line and the line under it. */
		label: (lead: string, sub: string) => (sub ? `${lead}, ${sub}` : lead)
	},
	/** How long ago, in a few words, as the chip and the panel say it. */
	ago: {
		now: 'just now',
		min: (n: number) => `${n} min ago`,
		hours: (n: number) => `${n} h ago`
	},
	/** An app a connected record names, as a person names it, where the record gives no name. */
	anApp: 'An agent',
	/** Where an app was started, after its name in the panel. */
	startedIn: {
		desktop: 'in the Claude app',
		terminal: 'in a terminal'
	},
	/** What a call was, in the panel: a mode started, a resource read, or a tool by its name. */
	call: {
		prompt: (mode: string) => `the ${mode} mode, started`,
		tool: (name: string) => `the ${name} tool`,
		resource: 'a resource read'
	},
	/** The panel the chip opens. */
	panel: {
		/** Its first part's heading, following the state: conversations connected, none, or not known. */
		connected: 'Connected',
		connectedNone: 'Not connected',
		connectedUnknown: 'Connection not known',
		/** Under it while loom is not answering the page. */
		unknown: 'Not known while loom is not answering this page.',
		/** Under it with none connected, above the setup card. */
		none: 'No agent is connected. One connects when a conversation in its app starts loom in this folder, and stays connected until that conversation ends.',
		/** A connected conversation's name and since when. */
		writesAs: 'Writes as',
		since: (clock: string) => `, connected since ${clock}.`,
		/** A connected conversation's last call, before the call itself. */
		lastCall: (active: boolean, ago: string) => `${active ? 'Active. ' : ''}Last call ${ago}: `,
		/** A connected conversation with no call yet. */
		noCall: 'No call yet.',
		/** Before the link to a conversation's session. */
		session: 'Its report: ',
		/** After the link to a conversation's session, which Review › History lists. */
		sessionAfter: ', in Review › History.',
		/** Under the conversations: what connected and active mean, and do not. */
		meaning: 'Connected means its conversation is open; active, that it called loom in the last two minutes. Neither says it is working now.',
		/** The second part's heading. */
		told: 'What it is told',
		/** What the line loom puts in the app's root file asks, said in words: the line itself names commands. */
		toldFirst: 'First, a line in the file its app reads on starting here: this folder is a quilt loom manages, it is to ask loom how to work here before doing anything, and it may write anywhere but the files loom protects.',
		/** After it: the orientation and the modes. */
		toldThen: (modes: number) => `Then loom's orientation and rules, and the quilt's ${modes} modes, each a way of working it may be asked for.`,
		/** With no agent layer. */
		toldNothing: 'Nothing yet: no app is set up here, so no agent is told what loom is.',
		/** From a loom that does not publish what agents are told. */
		toldUnknown: 'The loom serving this quilt does not say.',
		/** The third part's heading. */
		sees: 'What it sees',
		seesOpen: 'What you have open,',
		seesOpenWhat: ' when it asks: the document or page, the place you are at, and the words you selected, in the tab you used last.',
		seesNotes: 'Every annotation and reply you write,',
		seesNotesWhat: ' and each suggested edit you keep or discard. It reads what is new when its conversation starts, and again when you tell it you have left it something.',
		seesFiles: 'Every file in this folder,',
		seesFilesWhat: " which it can read with its app's own tools.",
		/** The fourth part's heading. */
		changes: 'What it may change',
		changesFiles: 'Any file in this folder but these,',
		changesFilesWhat: ' which it may only read:',
		changesInPlace: 'Its edits in place to your documents',
		changesInPlaceWhat: ' wait in Review, for you to keep or undo.',
		/** Before loom's own sentence on how far the apps set up here hold an agent to the list. */
		changesWho: 'Who holds it to this:',
		changesSuggested: 'Suggested edits',
		changesSuggestedWhat: ' change nothing until you keep them.',
		/** The fifth part's heading. */
		never: 'What it never does',
		neverWhat: 'Keep or discard a suggested edit, take its copy into your document, add or drop a paper in the library, restore an earlier version, or delete an annotation that is not its own. Those are yours, and loom refuses each to an agent whatever name it gives.'
	},
	/** Under the field where a person writes a new comment: who reads it. */
	readBy: 'Kept with this quilt for anyone who has it. An agent working here reads it when its conversation starts, or when you tell it you have left it something.',
	/** The setup card, in the panel with nothing set up and always in Settings › Agents. */
	setup: {
		/** Above the apps' buttons, with nothing set up. */
		lead: 'An agent in Claude or Codex can work in this folder through loom: it reads what you read, comments on it, and suggests edits for you to keep or discard. Nothing is written here until you choose an app.',
		/** The button that sets the quilt up for an app. */
		use: (app: string) => `Use with ${app}`,
		/** The same button for a second app, once one is set up. */
		also: (app: string) => `Also use with ${app}`,
		/** On a button while its set-up runs. */
		busy: 'Setting up…',
		/** Where no loom serves the page. */
		unserved: 'Setting an app up needs loom running this quilt, which this page is not served by.',
		/** When loom gave no reason for refusing. */
		failed: 'loom could not set it up',
		/** An app's heading once set up. */
		done: (app: string) => `${app} is set up here`,
		/** What loom wrote, the files with the skills counted. */
		wrote: (parts: string[]) => (parts.length ? `Loom wrote ${parts.join(', ')}.` : 'Everything was already in place.'),
		/** A count of the skills loom wrote. */
		skills: (n: number) => `${n} skill${n === 1 ? '' : 's'}, one for each mode`,
		/** What loom wrote in its own folder. */
		layer: "what agents are told, in loom's own folder",
		/** In a quilt whose agents reach loom in a shell. */
		shell: 'Agents here reach loom in a shell, so no app shows as connected here.',
		/** Once the app's first conversation has started loom here. */
		connected: (app: string, clock: string) => `Connected: ${app} at ${clock}.`,
		/** The first step for Claude: the button, or where loom opens no app, the words. */
		openClaude: 'Open Claude',
		openClaudeWords: 'Open the Claude app.',
		/** The second step for Claude, before the folder's path. */
		chooseFolder: 'In Claude, choose Code, then this folder',
		/** The third step for Claude. */
		trust: "When Claude asks whether you trust this folder, trust it. Until you do, Claude Code applies none of loom's permissions, and asks you before everything its agent does with loom.",
		/** The name of loom's server as an agent's app asks to approve it. */
		server: 'loom',
		/** The fourth step for Claude, around the server's name. */
		approve: 'If Claude asks you to approve the server ',
		approveThen: ', approve it. Then send any message.',
		/** The first step for Codex, before the folder's path. */
		codexOpen: 'Open Codex, and start a chat in this folder',
		/** The second step for Codex. */
		codexTrust: 'If Codex asks whether to trust the folder, trust it. Then send any message.',
		/** The button beside the folder's path, and what it says after. */
		copy: 'Copy',
		copied: 'Copied',
		refused: 'This browser refused the clipboard',
		/** While waiting for the app's first conversation. */
		waiting: (app: string) => `Waiting for ${app}…`,
		/** After a minute of waiting with none come, around the server's name. */
		late: 'Nothing yet. Check that you trusted the folder and approved the server ',
		lateThen: (app: string) => `, and that ${app} is up to date. A conversation started before this setup does not start loom: start a new one.`,
		/** When loom could not open the app. */
		openFailed: (app: string) => `loom could not open ${app}`
	},
	/** Settings › Agents › Apps, beside each app not set up. */
	apps: {
		setUp: 'Set up',
		notSetUp: 'Not set up'
	},
	/** Ask your agent: the buttons that open the box, and the box. */
	ask: {
		/** The button on a selection and on a toolbar. */
		open: 'Ask your agent',
		/** Hover text on it. */
		hover: "Copy a request about this for your agent's conversation",
		/** Hover text on it at a selection. */
		hoverWords: "Copy a request about these words for your agent's conversation",
		/** Its accessible name on a toolbar. */
		label: (of: string) => `Ask your agent about ${of}`,
		/** The box's heading and accessible name. */
		title: 'Ask your agent',
		/** Under the heading. */
		lead: "Copies a request naming this place, for you to paste into your agent's conversation. Nothing is sent from here.",
		/** The choice of what the request is about. */
		about: 'About',
		/** A choice: the whole document. */
		document: (name: string) => `The document, ${name}`,
		/** A choice: the result at the top of the pane. */
		reading: (name: string) => `${name}, where you are reading`,
		/** A choice: a result on screen in the pane, below the one at its top. */
		onScreen: (name: string) => `${name}, on screen`,
		/** A choice, the first: the words selected in the pane, in the result or document named. */
		selected: (name: string) => `The words you selected in ${name}`,
		/** The field of modes, and its first option. */
		mode: 'Mode',
		noMode: 'None: just look',
		/** The person's own words, and the field's placeholder. */
		words: 'Your words',
		wordsHint: 'What you want to know or have done (you can also say it in the conversation)',
		/** Above the request as it will be copied. */
		copied: 'What is copied',
		cancel: 'Cancel',
		copy: 'Copy',
		copyOpen: 'Copy and open Claude',
		/** The toast after Copy. */
		toast: (ok: boolean) => (ok ? 'Copied for your agent' : 'Nothing was copied'),
		toastLine: (ok: boolean, inClaude: boolean) => (ok ? `Paste it into your agent's conversation${inClaude ? ' in Claude' : ''}.` : 'This browser refused the clipboard.'),
		/** When loom could not open Claude. */
		openFailed: 'loom could not open Claude',
		/** The request: the place and the mode in one sentence, then the person's own words; the link, where there is one, in brackets after the place. */
		request: (mode: string, place: string, href: string, quoted: string) => `${mode ? `In loom, work in the ${mode} mode on` : 'In loom, look at'} ${place}${href ? ` (${href})` : ''}${quoted ? `, at the words “${quoted}”` : ''}.`
	}
};
