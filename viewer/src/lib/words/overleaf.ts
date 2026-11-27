// The Overleaf mirror's words: Settings › Overleaf (pairing, the mirror's card, Update and its line, ending the pairing), Update on a mirrored document's toolbar, and Copy new text and Done in Overleaf in place of Keep on a change to a mirrored document. An entry is named for the place it shows, with a comment saying where, on one line.

/** Names joined as a sentence lists them: "Cleo", "Cleo and Dan", "Cleo, Dan and Eve". */
const listed = (names: string[]) => (names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names.at(-1)}`);
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** A file's name, its folders dropped. */
const file = (path: string) => path.split('/').pop() ?? path;

export const overleaf = {
	/** Settings › Overleaf. */
	settings: {
		/** The section's name in the Settings panel. */
		section: 'Overleaf',
		/** Under the section's title: where the pairing and its parts are kept. */
		where: "The pairing is recorded in .loom/records/source-sync.json and travels with the quilt. Who you are on Overleaf, your git token and loom's copy of the project stay on this computer.",
		/** The setting's name. */
		project: 'Overleaf project',
		/** What it does. */
		projectWhat: 'A folder of this quilt holding one Overleaf project as Overleaf holds it. Loom reads the project when you press Update and never writes to it, so change the text in Overleaf. Agents may not write in the folder.',
		/** In place of the card where the loom serving the quilt cannot pair. */
		cannot: 'The loom serving this quilt cannot pair with Overleaf. Reload this page once loom has restarted with its update.',
		/** In place of the card on a page shown as published, with no loom serving it. */
		published: 'Shown as published. Pairing with Overleaf and updating need loom serving this quilt.'
	},
	/** The pairing card in Settings › Overleaf, while the quilt mirrors no project. */
	pair: {
		/** Above the link's field. */
		lede: "Paste an Overleaf project's link to keep a copy of it in this quilt. Loom reads it over git, which Overleaf offers when the project's owner has a premium plan.",
		/** The link field's accessible name. */
		link: "The project's link",
		/** Its placeholder. */
		linkPlaceholder: 'https://www.overleaf.com/project/…',
		/** The button that reaches the project. */
		connect: 'Connect',
		/** On it while loom reaches Overleaf. */
		connecting: 'Reaching Overleaf…',
		/** When Overleaf asks for a token and none is kept. */
		token: "Overleaf asks for a git token once. Make one in Overleaf under Account Settings, Git integration, and paste it here; loom keeps it in your Mac's Keychain.",
		/** When Overleaf refused the token kept. */
		tokenRefused: 'Overleaf did not accept the saved token; tokens last a year. Make a new one in Overleaf under Account Settings, Git integration, and paste it here.',
		/** The token field's accessible name. */
		tokenField: 'Git token',
		/** The button that gives loom the token and tries again. */
		useToken: 'Use this token',
		/** The folder's field, with what it is. */
		folder: 'Folder',
		folderWhat: 'A new folder of this quilt that the project is copied into.',
		/** The main file's choice, where the project has several. */
		main: 'Main file',
		mainWhat: 'The project has several files that begin a document. Choose the one Overleaf compiles.',
		/** The question over the history's authors. */
		me: 'Which of these is you on Overleaf?',
		meWhat: 'Review leaves out the changes only you made. Tick each that is you.',
		/** The choice for a person the history does not name yet. */
		noneYet: 'None of these yet',
		/** A history that names nobody: the line in place of the choices. */
		nobody: 'The project names nobody yet; loom will ask again once it does.',
		/** Copies the project into the folder. */
		go: 'Copy the project',
		/** On it while loom copies. */
		copying: 'Copying…',
		/** Goes back to the link. */
		cancel: 'Cancel',
		/** After pairing. */
		paired: (folder: string) => `Connected. Your paper is in the folder ${folder}.`
	},
	/** The mirror's card in Settings › Overleaf, while the quilt mirrors a project. */
	paired: {
		/** Its first line. */
		mirrors: (folder: string) => `This quilt mirrors an Overleaf project in the folder ${folder}.`,
		/** Labels beside the folder and the main document. */
		folder: 'Folder',
		main: 'Main document',
		/** The link to the project's page in Overleaf. */
		open: 'Open in Overleaf',
		/** Asks again which authors are the person. */
		whoAgain: 'Who you are on Overleaf',
		/** Saves the answer to that question. */
		saveMe: 'Save',
		/** Ends the pairing; then the question and its answers. */
		unpair: 'End the pairing',
		unpairAsk: 'End the pairing? The folder stays, its files yours to edit, and agents stay denied it until you change that under Agents.',
		unpairYes: 'End it',
		unpairNo: 'Keep it',
		/** After ending it. */
		unpaired: 'The pairing is ended. The folder stays.'
	},
	/** Update, in Settings › Overleaf and on a mirrored document's toolbar, and the line beside it. */
	update: {
		/** The button. */
		label: 'Update from Overleaf',
		/** On the toolbar, where room is short. */
		short: 'Overleaf',
		/** On it while loom updates. */
		busy: 'Updating…',
		/** Hover text on the toolbar's button, then the line. */
		hover: (doc: string) => `${file(doc)} mirrors Overleaf: change it there, then update here.`,
		/** Beside the button when the last fetch found text not taken in. */
		waiting: 'Overleaf has changes.',
		/** The line when an update found nothing new. */
		upToDate: 'Up to date with Overleaf · checked just now.',
		/** The line before any update. */
		never: 'Not updated since it was paired.',
		/** The line for an update: when, how many files, by whom. */
		updated: (when: string, files: number, by: string[]) => `Updated from Overleaf ${when}: ${plural(files, 'file', 'files')} changed${by.length ? `, by ${listed(by)}` : ''}.`,
		/** Right after the press, in place of the time. */
		now: 'just now',
		/** The time of an update, as the line says it. */
		at: (date: string, time: string) => `on ${date} at ${time}`,
		/** After it: how many changes only the person made, which Review leaves out. */
		own: (n: number) => `${plural(n, 'change', 'changes')} only you made in Overleaf ${n === 1 ? 'is' : 'are'} not listed in Review.`,
		/** After it: changes outside any result, each with its file and who made it. */
		places: (each: string[]) => `Outside the results: ${each.join('; ')}.`,
		/** One such change. */
		place: (path: string, where: string, by: string[]) => `${where ? `${where} of ` : ''}${file(path)}${by.length ? ` (${listed(by)})` : ''}`,
		/** Where in a file such a change is, by the code loom gives it. */
		where: { preamble: 'the preamble', between: 'text between results', removed: 'a result removed', 'not-a-document': '' } as Record<string, string>,
		/** After it: blocks changed here that the update wrote over. */
		here: (n: number) => `${plural(n, 'result', 'results')} you changed here ${n === 1 ? 'was' : 'were'} written over; the version kept before the update holds your text.`,
		/** After it, right after the press: files changed here that the update wrote over. */
		overwritten: (paths: string[]) => `Written over, as they held changes made here: ${listed(paths.map(file))}. History keeps each as it was before the update.`
	},
	/** What reaching Overleaf could not do, by the code loom gives; a code not here is said by `other`. */
	problem: {
		'no-git': 'Loom needs git to reach Overleaf, and this computer has none. Install the Command Line Tools, then update.',
		'no-token': "Overleaf asks for a git token. Make one in Overleaf under Account Settings, Git integration, and paste it here; loom keeps it in your Mac's Keychain.",
		'token-refused': 'Overleaf did not accept the saved token; tokens last a year. Make a new one in Overleaf under Account Settings, Git integration, and paste it here.',
		'no-git-access': "Overleaf would not give loom this project. Git access needs the project's owner to have a premium plan, and the link must be the project's own.",
		offline: 'Could not reach Overleaf. Your copy is as of the last update.',
		'sharing-link': "That is a sharing link, which does not name the project. Paste the address of the project's own page, or the link in Overleaf's Git dialog.",
		'not-a-project': "That is not an Overleaf project's link. Paste the address of the project's own page.",
		'bad-token': 'That is not a git token: a token is one line of letters and digits.',
		'bad-record': "This quilt's record of its Overleaf project is not one loom can use. End the pairing and pair it again.",
		'bad-folder': 'Loom cannot make a folder by that name here. Choose a plain name inside the quilt.',
		'folder-exists': 'A folder by that name exists already. Choose a new name.',
		'no-main': 'Choose the main file.',
		paired: 'This quilt mirrors a project already.',
		'not-paired': 'This quilt mirrors no Overleaf project now.',
		'taken-in': 'Another update took that in first. Update again.',
		'no-clone': "Loom's copy of the project had been changed, so loom will make it again. Update again.",
		'author-only': 'Only a person can do this; loom does not take it from an agent.',
		other: 'Loom could not reach the project just now. Try again.'
	} as Record<string, string>,
	/** On a change to a mirrored document, in place of Keep: in Review's rows, a document's list and its popup. */
	change: {
		/** Copies the change's new words. */
		copy: 'Copy new text',
		copyHover: 'Copy the words this change puts in, to paste in Overleaf',
		/** After copying. */
		copied: 'Copied. Paste it in Overleaf, then choose Done in Overleaf.',
		/** When the browser refused the clipboard. */
		notCopied: 'This browser refused the clipboard, so nothing was copied.',
		/** Updates from Overleaf, then keeps the change. */
		done: 'Done in Overleaf',
		doneHover: 'Update from Overleaf, and keep this change once Overleaf has it',
		/** On it while it works. */
		doing: 'Updating…',
		/** After it, when Overleaf had the change. */
		kept: 'Kept.',
		/** After it, when Overleaf does not have the change. */
		notYet: 'Overleaf does not have this change yet.',
		/** Why Keep is not offered, under the change. */
		why: "Its document mirrors Overleaf: make the change there, then choose Done in Overleaf."
	}
};
