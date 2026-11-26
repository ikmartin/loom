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
		undoFailed: (why: string) => (why ? `It could not be undone. ${why}` : 'It could not be undone.')
	},
	updating: {
		/** The line in the column's foot, and the folded dot's name, from a write's answer until the page carries it. */
		on: 'Updating the page…',
		/** The line in its place when the build that was to show a write failed: the write is done, the page is not up to date. */
		failed: 'Done, but the page could not be brought up to date.',
		/** The close button on that line. */
		dismiss: 'Dismiss'
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
		/** A result's paper mark, an amber ring: digested, its copy not yet checked against its paper, as Review's Results to check list it. */
		unchecked: 'not yet checked against its paper',
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
	errors: {
		/** Where the publisher does not serve what was asked of it yet. */
		notServed: 'This loom does not serve that yet.',
		/** Where the publisher could not be reached. */
		unreachable: 'Loom could not be reached.',
		/** Where the publisher answered with no reason a person can read, or a refusal this viewer has no sentence for. */
		failed: 'Loom could not do that.',
		/** An annotation refused while loom knows no name to write it under. */
		noName: 'Loom does not know your name yet. Set it in Settings, under Profile, and try again.'
	},
	/** What a refusal of loom's says, by its code: never loom's own message, which may name a setting, a field or an id. A code with none here says `errors.failed`. */
	refused: {
		ambiguous: 'That label is on a result in more than one copy of your draft, so loom cannot tell which you mean.',
		'author-only': 'Only a person can do this; loom does not take it from an agent.',
		'bad-entry': 'That is not a BibTeX entry loom can keep for this work.',
		changed: 'It has changed since, so loom left it as it is.',
		closed: 'That has been answered already.',
		'compile-failed': 'The document did not compile, so nothing was changed.',
		'cut-short': 'The file arrived cut short. Drop it again.',
		'format-unknown': 'Loom does not know this kind of file.',
		'has-results': 'Results have been read from this document, so it stays with its work. Delete the work instead.',
		'key-taken': 'Another work in the library already has that key.',
		'network-unasked': 'Loom has not been told whether it may look papers up online.',
		'no-document': 'This work holds no document.',
		'no-identifier': 'Its entry gives no DOI, arXiv number or zbMATH number to look it up by.',
		'no-reviewer': 'Loom does not know your name yet. Set it in Settings, under Profile, and try again.',
		'no-source': 'Loom holds no TeX source of this work to read its results from.',
		'no-space': 'There is not enough room on this computer for the file.',
		'no-such-citation': 'That citation is no longer there, or it names a result now.',
		'no-such-incoming': 'That file is no longer waiting to be taken in. Drop it again.',
		'no-such-intake': 'There is nothing of that drop left to undo.',
		'no-such-node': 'That result is no longer in the library.',
		'no-such-proposal': 'That correction is no longer waiting for you.',
		'no-such-question': 'That question has been answered already.',
		'no-such-ref': 'That work is no longer in the library.',
		'no-such-file': 'That PDF is not a file of this quilt the viewer shows.',
		'no-such-result': 'That result is no longer in your drafts.',
		'no-such-row': 'That no longer waits for you.',
		'no-such-task': 'That task no longer waits for an agent.',
		'no-such-undo': 'There is nothing left to undo.',
		'no-such-work': 'That work is no longer in the library.',
		'not-a-candidate': 'That is not one of the works it might be.',
		'not-a-document': 'Loom takes PDFs, TeX sources and .bib files, and this is none of them.',
		'not-found': 'Those words are not in the paper.',
		'not-last': 'Something done after it has to be undone first.',
		'not-new': 'Results have been read from it since, so it stays. Delete the work instead.',
		'not-readable': 'Loom holds no copy of this paper it can read on this computer.',
		'not-unresolved': 'That is settled already.',
		offline: 'This quilt keeps loom offline, so nothing was looked up.',
		reading: 'Loom is still reading this work. Try again when it is done.',
		'review-unavailable': 'Review could not be read just now.',
		stub: 'Loom has no text of this result yet, so there is nothing to compare or correct.',
		'reviewer-changed': 'Your name was changed since this page was read. Reload it and try again.',
		unreachable: 'The service that looks papers up could not be reached. Try again later.'
	} as Record<string, string>,
	/** A quilt an earlier loom made, while the publisher waits on it: the one sentence, its button, and what is said while it runs and if it fails. */
	upgrade: {
		said: 'This quilt was made by an earlier version of loom; upgrading it carries its papers over to this one.',
		button: 'upgrade the quilt',
		running: 'Upgrading the quilt and carrying its papers over…',
		/** Said after an upgrade that could not carry everything; the button then opens the quilt. */
		problems: (n: number) => `The quilt is upgraded, but ${n === 1 ? 'one thing' : `${n} things`} could not be carried over.`,
		open: 'open the quilt',
		/** Why an upgrade did not happen, by the publisher's refusal; the button stays, to try again. */
		failed: (code: string) =>
			code === 'author-only'
				? "Only the quilt's author can upgrade it."
				: code === 'format-unknown'
					? 'This quilt was made by a version of loom this one cannot upgrade from.'
					: code === 'unreachable'
						? 'Loom could not be reached, so the quilt was not upgraded.'
						: 'The upgrade did not finish; try it again.'
	},
	open: {
		/** The page `loom open` lands on, when the link it was given names nothing in this quilt. */
		nothing: (link: string) => (link ? `${link} names nothing in this quilt.` : 'No link was given to open.')
	},
	page: {
		/** The heading of the page shown when the manifest could not be read. */
		problems: 'Problems',
		/** The page shown while the manifest is loading. */
		loading: 'Loading manifest…'
	}
} as const;
