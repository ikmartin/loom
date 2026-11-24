// The Web's words: its column's scope and form, the list and its search, the focus card and its neighbourhood, and the graph. Every sentence the viewer says is written in this folder (`frame.ts` says how); a component holds none. An entry is named for the place it shows, with a comment saying where, on one line.

/** A file's name from its path, as the file tree draws a document. */
const file = (doc: string) => doc.split('/').pop() ?? doc;

export const web = {
	/** The Web's page where the publisher does not serve the Web's reads yet. */
	notServed: 'The Web shows every result and what it rests on once loom serves it.',
	/** A document's path drawn as its file's name. */
	file,
	column: {
		/** The column's line over the scopes. */
		scope: 'Scope',
		/** The four scopes, as radio buttons. */
		scopes: { library: 'the library', draft: 'a draft', deps: 'a draft and what it rests on', all: 'everything' },
		/** The choice of draft under a scope that needs one; its accessible name. */
		draft: 'Which draft',
		/** That choice, where the quilt names no main draft and none is chosen yet. */
		choose: 'choose a draft',
		/** The column's line over the two forms. */
		form: 'Form',
		/** The two forms. */
		list: 'list',
		graph: 'graph'
	},
	list: {
		/** The search field over the list. */
		search: 'find a result, or words in it',
		/** Beside the search: how many results the list holds. */
		count: (n: number) => (n === 1 ? '1 result' : `${n} results`),
		/** The two orders of the list. */
		byDocument: 'by document',
		byStatus: 'by status',
		/** The list's section heads. */
		uses: (doc: string) => `library results ${file(doc)} uses`,
		drafts: 'your drafts',
		library: 'library',
		/** Under the library's works, in the scope of everything. */
		undigested: (n: number) => (n === 1 ? 'and 1 work with no results digested' : `and ${n} works with no results digested`),
		/** Where the search finds nothing. */
		nothing: 'nothing matches',
		/** A scope that holds no result. */
		empty: (scope: string, doc: string) => (scope === 'library' ? 'No result of the library is listed yet.' : scope === 'all' ? 'No draft holds a result.' : `${file(doc)} holds no result.`),
		/** A scope of one draft, where the quilt names no main draft and none is chosen; `drafts`, how many drafts the quilt holds. */
		draftless: (drafts: number) => (drafts ? 'The quilt names no main draft. Choose a draft under Scope.' : 'The quilt holds no draft yet.'),
		/** At the foot of the list by status, where more is read as it comes into view. */
		more: (n: number) => `${n} more`,
		/** While the first answer has not come. */
		loading: 'Reading the web…',
		/** Where the Web's reads failed, with the publisher's reason. */
		failed: (why: string) => `The web could not be read: ${why}`,
		/** In place of the list where the publisher does not serve its reads yet. */
		notServed: 'This loom does not serve the Web yet.'
	},
	choose: {
		/** The box on a result of the person's not formalized, its accessible name. */
		box: 'choose to formalize',
		/** The bar at the list's foot while results are chosen. */
		chosen: (n: number) => `${n} chosen`,
		formalize: 'formalize…',
		clear: 'clear'
	},
	focus: {
		/** In the card's place while no result is chosen. */
		choose: 'Choose a result to see what it uses and what uses it.',
		/** The trail of results followed, its accessible name. */
		trail: 'Results followed',
		/** In place of a statement loom knows only by its number. */
		numberOnly: 'Loom knows it only by its number.',
		/** A formalized result's line, before the results it rests on in Lean. */
		relativeTo: 'Verified relative to',
		/** After them. */
		assumed: (n: number) => (n === 1 ? 'which is assumed.' : 'which are assumed.'),
		/** A formalized result that rests on nothing assumed. */
		mathlib: 'Verified, relative to Mathlib alone.',
		/** A result of the person's not formalized, before what it rests on that is not read or not compared. */
		restsOn: 'Not formalized. It rests on',
		/** A library result in that line: its name and work. */
		of: (name: string, short: string) => `${name} of ${short}`,
		/** The fold under the statement. */
		more: 'proofs, Lean, and its record',
		/** The fold's three lines. */
		proof: 'proof',
		lean: 'Lean',
		record: 'record',
		/** A proof in a draft, and what it uses. */
		proofIn: (where: string, uses: string) => `in ${where}; uses ${uses}`,
		/** A proof in a work. */
		proofFrom: (short: string, pages: string) => (pages ? `from ${short}, pages ${pages}` : `from ${short}`),
		/** What a proof uses when it uses nothing. */
		nothing: 'nothing',
		/** The record's acts, joined by a middle dot. */
		acts: {
			'lean-accepted': (by: string, date: string) => `Lean accepted its proof on ${date}`,
			attested: (by: string, date: string) => `${by === 'you' ? 'you' : by} attested it on ${date}`,
			verified: (by: string, date: string) => `compared with the paper by ${by}, ${date}`,
			digested: (by: string, date: string) => `digested by ${by}, ${date}`
		} as Record<string, (by: string, date: string) => string>,
		/** The neighbourhood's three lists. */
		statementUses: 'What its statement uses',
		proofUses: 'What its proof uses',
		usedBy: 'What uses it',
		/** Under a list: how many of its results are outside the scope. */
		outside: (n: number) => `and ${n} outside this scope`,
		/** Under a list of what uses a result: how many more there are. */
		moreUsers: (n: number) => `and ${n} more`,
		/** A list with nothing in it. */
		none: 'nothing'
	},
	graph: {
		/** The graph's column heads. */
		back: 'two steps back',
		uses: 'what it uses',
		usedBy: 'what uses it',
		/** A column's last box when it holds more than it draws. */
		more: (n: number) => `and ${n} more · in the list`,
		/** The legend under the graph. */
		statement: 'its statement uses',
		proof: 'its proof uses',
		/** The graph, its accessible name. */
		label: (name: string) => `What ${name} uses and what uses it`
	},
	/** A date as the Web says it: "20 Nov". */
	day: (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })
} as const;
