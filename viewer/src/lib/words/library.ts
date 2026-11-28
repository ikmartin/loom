// The Library's words: its column, the list of works, a work's tab, the reader's overlay, a result beside its page, and the drop of a paper. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none.

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
/** Names in a sentence: `A`, `A and B`, `A, B and C`. */
const list = (names: string[]) => (names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`);

/** How each identifier's scheme is written for a person. */
const SCHEMES: Record<string, string> = { arxiv: 'arXiv', doi: 'doi', mr: 'MR', zbl: 'zbMATH' };

export const library = {
	work: {
		/** A work's toolbar, on `open the PDF` and the PDF's tools while no PDF is drawn. */
		noPdf: 'No PDF of this work is open'
	},
	tabs: {
		/** The first tab of the Library, always there: the list of works. */
		works: 'Works',
		/** The close button on a work's tab. */
		close: 'close'
	},
	/** A work's authors as the list draws them: one, two joined, or the first and "et al." */
	byline: (a: readonly string[]) => (!a.length ? '' : a.length === 1 ? a[0] : a.length === 2 ? `${a[0]} and ${a[1]}` : `${a[0]} et al.`),
	column: {
		/** The four filters in the Library's column while the list of works is shown. */
		filters: { all: 'All works', used: 'Cited in your drafts', nodoc: 'No PDF or source' },
		/** Accessible name of the filters' list. */
		filtersLabel: 'Filters',
		/** A work's head in the column: what loom holds of it, after its authors and year. */
		holds: { both: 'PDF and TeX', pdf: 'PDF', tex: 'TeX', none: 'no document' },
		/** The fold under a work's head that shows its BibTeX entry. */
		entry: 'entry',
		/** The entry's field, its accessible name, and its controls. */
		entryField: 'BibTeX entry',
		editEntry: 'edit',
		saveEntry: 'save',
		cancelEntry: 'cancel',
		/** The column's message once an entry is saved. */
		entrySaved: (short: string) => `Saved the entry of ${short}.`,
		/** The label over a work's outline when it comes from its TeX source. */
		contents: 'Contents',
		/** The label over a work's outline when it comes from the PDF's own outline. */
		contentsFromPdf: "Contents, from the PDF's outline",
		/** A section's page at the right of its row in the outline. */
		page: (n: number) => `p. ${n}`,
		/** The label over a PDF-only work's stubs that have no place yet. */
		unplaced: 'Cited, not yet placed',
		/** Under the unplaced stubs: what they are, before the link. */
		notRead: 'not read',
		/** The link under the unplaced stubs that opens the paper at loom's best guess. */
		locate: 'locate in PDF',
		/** The outline of a work of which loom has a PDF and no outline, and nothing digested. */
		nothingDigested: 'No results digested yet.',
		/** A work's outline in the column while nothing reads a work's results: said, rather than drawing nothing. */
		notReadYet: "Loom does not read a work's sections and results yet, so its outline is empty. The paper opens here as it is.",
		/** Beside a result in a TeX source's outline that points at an equation outside every result: loom writes it once the person compiles the source, which numbers that equation. */
		waitsCompile: 'written once you compile the source',
		/** The outline while the survey of a TeX source is still being read. */
		reading: 'Reading the TeX source…',
		/** The button under the outline that digests what was ticked. */
		digestChosen: (n: number) => `digest ${n} chosen`,
		/** The quiet link beside it that stops choosing. */
		cancel: 'cancel'
	},
	works: {
		/** A work's tab when the work has left the library since it was opened. */
		gone: 'This work is no longer in the library.',
		/** The search over the list of works. */
		search: 'find a work by title or author',
		/** Beside the search while it narrows the list. */
		narrowed: (n: number, of: number) => `${n} of ${of}`,
		/** The link that clears the search. */
		clear: 'clear',
		/** The two ways the list is drawn. */
		list: 'list',
		thumbnails: 'thumbnails',
		/** The buttons above the list. */
		add: 'add work…',
		digest: 'digest…',
		/** The columns of the list, and the columns menu's head. */
		cols: { title: 'Title', authors: 'Authors', year: 'Year', digested: 'Digested', holds: 'Loom has', used: 'Used in' },
		colsHead: 'Columns',
		/** The columns menu's button at the right of the list's head; its accessible name. */
		colsOpen: 'columns',
		/** The Digested column: how many results are digested, of how many the source holds, and how many are checked against their paper. */
		digested: (n: number, of: number | null, compared: number) => `${of === null ? n : `${n} of ${of}`} · ${compared} checked`,
		/** After a work's title: the words that tell a later version apart. */
		version: (v: number | string) => (v === 2 ? 'second version' : typeof v === 'number' ? `version ${v}` : v),
		/** A thumbnail's page for a work of which loom has no document. */
		noDocument: 'no document',
		/** A thumbnail's page for a work added by an identifier and not looked up, the network not allowed. */
		notLookedUp: 'not looked up yet',
		/** Under the thumbnails while more are below. */
		more: (n: number) => `${n} more as you scroll`,
		/** The menu at a row's right; its accessible name. */
		rowMenu: 'more',
		/** The row menu's items. */
		openSource: 'open its source ↗',
		editEntry: 'edit its entry…',
		delete: 'delete',
		/** A row looked up while the network is off: the identifier loom found, and the question. */
		lookAsk: 'look it up this once?',
		/** An identifier loom found, `scheme:value`, as a person reads it: "arXiv 2209.01234v2". */
		identifier: (id: string): string => {
			const at = id.indexOf(':');
			const scheme = id.slice(0, at).toLowerCase();
			return `${SCHEMES[scheme] ?? scheme} ${id.slice(at + 1)}`;
		},
		yes: 'yes',
		notNow: 'not now',
		/** A row whose details were not looked up. */
		unconfirmed: 'details unconfirmed ·',
		lookUp: 'look up',
		/** A row being looked up. */
		lookingUp: 'looking up…',
		/** The list while it loads, and when the library is empty. */
		loading: 'Loading the library…',
		/** The list when its read failed. */
		failed: (why: string) => `The library could not be read: ${why}`,
		/** In place of the list where the publisher does not serve its reads yet. */
		notServed: 'This loom does not serve the Library yet.',
		/** The column's message after a work was deleted. */
		deleted: (short: string) => `Deleted ${short}, with its results and notes`
	},
	empty: {
		/** The box an empty library shows in place of the list. */
		head: 'Drop papers here to start your library',
		body: "PDFs, TeX sources, or a .bib file. A paper's arXiv number or DOI is enough: loom looks up the rest online once you say it may, and fetches the TeX source where arXiv has it."
	},
	add: {
		/** The panel under `add work…`. */
		choose: 'choose files…',
		paste: 'or paste an arXiv number or DOI',
		drop: 'or drop files anywhere in loom',
		/** The column's message after a work was added: its title, its short name, and how it was known. */
		added: (title: string, short: string, how: string, tex: boolean) => `Added ${title}${short && short !== title ? `, ${short}` : ''}${how ? `, found by its ${how}` : ''}${tex ? ', with its TeX source' : ''}.`,
		/** The column's message after a work was added by an identifier it was not looked up by, the network not allowed: the identifier, and what waits for the person's word in its row. */
		addedUnlooked: (identifier: string) => `Added ${identifier}. Its title and authors are not looked up yet: that goes online, which loom does only when you say so, and its row asks.`,
		/** The column's message when a file was filed under a work the library had: dropped on its row, or the person's answer that it is that work. */
		filed: (name: string, short: string) => `Filed ${name} under ${short}.`,
		/** What a work was known by, in the message. */
		foundBy: { arxiv: 'arXiv number', doi: 'DOI', isbn: 'ISBN', entry: 'entry', row: 'row', none: '' } as Record<string, string>,
		/** The column's message when loom already holds the dropped file's work. */
		here: (name: string, short: string) => `${name} is ${short}, already in your library.`,
		/** The column's message when a drop could not be added. */
		cannot: (name: string, why: string) => `${name} was not added: ${why.replace(/\.$/, '')}.`,
		/** Why a file or a pasted line was not added, by the intake's code for it; loom's own words for it are never drawn. */
		cannotWhy: {
			'not-recognised': 'it names no work loom can find',
			'no-service': 'loom does not look up ISBNs or MathSciNet numbers',
			missing: 'nothing was found under its identifier',
			unreachable: 'the service that looks papers up could not be reached',
			'key-taken': 'another work in the library has its key',
			'has-document': 'the work holds a document of that kind already',
			'not-a-source': 'it is not a TeX source loom can unpack',
			'bad-name': 'its name holds a character no file name can',
			refused: 'loom could not keep its entry'
		} as Record<string, string>,
		/** Why, where the intake's code has no sentence here. */
		cannotWhyAny: 'loom could not add it',
		/** The column's message after a drop of several: how many were added, then each that was not, joined by a semicolon. */
		many: (added: number, others: string[]) => [added ? `Added ${added} ${added === 1 ? 'work' : 'works'}` : '', ...others].filter(Boolean).join('; ') + '.',
		/** A file of such a drop that loom already held. */
		hereShort: (name: string, short: string) => `${name} is ${short}, already in your library`,
		/** A file of such a drop that was not added. */
		cannotShort: (name: string, why: string) => `${name} was not added: ${why.replace(/\.$/, '')}`,
		/** A file of a drop that loom has a question about, which the column asks next. */
		question: (name: string) => `${name} waits for your answer`,
		/** The intake's question, asked in the column: the file, the identifier it states, and the works in the library that state it too. */
		asks: (name: string, stated: string, works: string[]) => (works.length === 1 ? `${name} states ${stated}, as ${works[0]} in your library does. Is it that work?` : `${name} states ${stated}, as ${works.length} works in your library do. Is it one of them?`),
		/** The question of a file dropped on a work's row in the Library, asked before it is taken in, and of one the intake asks about that states nothing a work states. */
		asksOn: (name: string, short: string) => `Is ${name} ${short}, the work you dropped it on?`,
		/** The same, of several files dropped on one row together. */
		asksOnMany: (names: string[], short: string) => `Are ${list(names)} ${short}, the work you dropped them on?`,
		/** The question of a file dropped anywhere while the Library shows a work's tab, asked before it is taken in. */
		asksOpen: (name: string, short: string) => `Is ${name} ${short}, the work you have open?`,
		/** The same, of several files dropped together. */
		asksOpenMany: (names: string[], short: string) => `Are ${list(names)} ${short}, the work you have open?`,
		/** The question where every work it named has since been deleted: only whether the file is a work of its own. */
		asksGone: (name: string, stated: string) => (stated ? `${name} states ${stated}, as a work since deleted from your library did. Add it as a work of its own?` : `The work ${name} was dropped on has since been deleted from your library. Add it as a work of its own?`),
		/** The question where every work the file's identifiers name holds a document of its kind already: the copy asked about as what it is, kept as a work of its own or let go. */
		asksHeld: (name: string, stated: string, kind: string, works: string[]) => `${name} states ${stated}, whose ${kind} ${list(works)} ${works.length === 1 ? 'holds' : 'hold'} already. Keep it as a work of its own?`,
		/** Beside a question with works to offer, the works that state the identifier too but hold a document of the file's kind already, and so are not offered. */
		alsoHeld: (kind: string, works: string[]) => `${list(works)} ${works.length === 1 ? 'states it too and holds its' : 'state it too and hold their'} ${kind} already.`,
		/** A document's kind, in those questions. */
		kind: { pdf: 'PDF', tex: 'TeX source' } as Record<string, string>,
		ownWork: 'yes, a work of its own',
		/** The answer that lets a copy go, and the column's message once it has gone. */
		letGo: 'no, let it go',
		letGone: (name: string) => `Let ${name} go.`,
		/** The answers: that it is the one work asked about, that it is a work of its own beside one or several. */
		isIt: 'yes',
		notIt: 'no, a work of its own',
		notThem: 'no, works of their own',
		noneOfThem: 'none of them: a work of its own',
		/** A work the question names whose short name another work asked about shares, told apart by its title. */
		candidate: (short: string, title: string) => `${short} · ${title}`
	},
	drop: {
		/** The cover over any view while a file is dragged over the window. */
		cover: 'Drop to add to your library.',
		/** Its second line, only while papers wait for their file. */
		waiting: (n: number) => `If it is one of the ${plural(n, 'paper', 'papers')} waiting to be fetched, it is attached to that paper.`
	},
	digest: {
		/** The digest menu's head. */
		head: 'Digest…',
		/** A work's menu: what to digest, each finishing the sentence, with its count after it. */
		used: 'results my drafts use',
		marked: 'what I marked in this paper',
		choose: 'results I choose…',
		all: (short: string) => `everything in ${short}`,
		/** The count after an item. */
		count: (n: number) => `(${n})`,
		/** The count after "everything in" for a work held only as a PDF. */
		pages: (n: number) => `(${n} pages)`,
		/** The list's menu: across every work, and over the works selected. */
		usedEvery: 'results my drafts use, in every paper',
		selected: 'everything in the papers I select',
		selectedCount: (n: number) => `(${n} selected)`,
		selectHint: '⌘-click papers in the list to select them',
		/** The menu's foot line: who does the work. */
		byLoom: 'Loom does this itself, now, from the TeX source.',
		byAgent: 'An agent does this, from the PDF. It waits in Review, under Agents still working.',
		byEither: 'Loom does this itself, now, where it has a paper\'s TeX source. For a paper it has only as a PDF an agent does it, and it waits in Review.',
		/** A work's menu when loom has no document of it. */
		noDocument: 'Loom has no document of this work yet.',
		/** The column's message after digesting. */
		made: (n: number) => `Digested ${plural(n, 'result', 'results')} from the TeX source`,
		asked: (n: number) => `Asked an agent to digest ${plural(n, 'paper', 'papers')}; it waits in Review`,
		/** The column's message when the survey must first be read. */
		reading: 'Reading the TeX source first; the results follow when it is done',
		/** While choosing in the outline. */
		chooseHint: 'Tick the results to digest in the outline, then digest them'
	},
	reader: {
		/** The reader, in place of the pages, for a work holding no PDF. */
		noPdf: 'Loom holds no PDF of this work.',
		/** The Library's menu in the reader's toolbar, which holds the digest marks. */
		view: 'view',
		/** The field under "ask an agent…" in the selection popup, and its button. */
		askPlaceholder: 'what to ask about these words',
		send: 'send',
		/** The reader's view menu item that shows the digest marks on the pages. */
		overlay: 'digest marks',
		/** The selection popup on a work's page. */
		mark: 'mark to digest',
		highlight: 'highlight',
		note: 'note',
		ask: 'ask an agent…',
		/** The column's message once a question on selected words is sent. */
		asked: 'Added to agent tasks: a question on these words.',
		/** The column's message after marking a place to digest. */
		marked: (page: number) => `Marked on page ${page}, to digest`,
		/** A work with no document, in place of the reader. */
		noDocument: "Loom has this work's entry and no document. Drop its PDF anywhere to add it.",
		/** A work added by an identifier and not looked up, in place of the reader, and its button. */
		notLookedUp: 'Loom has not looked this work up yet, so it has no title, authors or paper here: that goes online, which loom does only when you say so.',
		lookUpOnce: 'look it up this once',
		/** The chip's accessible name beside a result on the page. */
		chip: (name: string) => name,
		/** Over the Comments list beside a work, where loom could not learn where its notes on words stand. */
		unread: (n: number) => (n === 1 ? 'Loom could not learn where a note on words stands on the paper, so it is listed here and drawn on no page.' : `Loom could not learn where ${n} notes on words stand on the paper, so they are listed here and drawn on no page.`),
		/** On a note's card where loom found its words on no page. */
		unfound: 'Its words were not found on the paper, so it is drawn on no page.'
	},
	side: {
		/** The close button of the result beside the page. */
		close: 'close',
		/** Under the result's name: its page, and how loom has it. */
		where: (page: string, how: string) => (page ? `page ${page} · ${how}` : how),
		how: { extracted: 'extracted exactly from the TeX source', transcribed: 'transcribed by an agent from the pages', read: 'read by an agent from the TeX source', corrected: 'corrected by an agent', written: 'written by you', stub: 'known from the TeX source, not read', none: 'not digested' },
		/** Drawn in place of a reference to an equation whose number loom keeps only after the person compiles the source. */
		awaitingRef: '(numbered once you compile the source)',
		/** The two ways the statement is shown. */
		rendered: 'rendered',
		plain: 'plain',
		/** The question under a statement not yet compared, and its answers. */
		ask: "Does loom's copy match the paper?",
		yes: 'yes, it matches',
		no: 'no, it differs…',
		/** The message after "no, it differs…", until correcting is built. */
		noLater: 'Correct it here, or ask an agent to',
		/** A result of the source not digested yet. */
		notDigested: 'Not digested. Loom has the TeX source, so it can extract this exactly, now.',
		/** A stub of a work with its TeX source. */
		stub: 'Known from the TeX source and not read.',
		/** The button that digests one result. */
		digestIt: 'digest it',
		/** The label over the results it uses. */
		uses: 'uses',
		/** The column's message after the yes. */
		checked: (name: string) => `${name} matches the paper`,
		/** The column's message after a yes that opened the next result not compared. */
		checkedNext: (name: string) => `${name} matches the paper; the next not compared is open.`
	},
	draw: {
		/** Under a result whose text holds what the viewer cannot draw itself (a diagram, an environment it does not know), shown plain, while the person has not compiled its work's source here: asked once for the work. */
		ask: (short: string) => `Loom cannot draw this itself. Compile the source of ${short} on this machine and TeX draws it, and every other result of ${short}; you are asked this once for the work.`,
		/** The button that compiles the work's source, after which TeX draws its results. */
		compile: 'compile and draw',
		/** The column's message once the compile is asked for. */
		compiling: (short: string) => `Compiling the source of ${short}; its results are drawn by TeX as they are shown.`
	}
} as const;
