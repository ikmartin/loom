// Review's words: its column (the kinds, their counts' hover cards, the drafts, the Record line), the list and its groups, each kind's row and body, the tasks waiting for an agent, and what the column's message says after an act. An entry is named for the place it shows, with a comment saying where, on one line.

import type { ReviewKind } from '$lib/library/types';

/** A file's name from its path, as the file tree draws a document. */
const file = (doc: string) => doc.split('/').pop() ?? doc;

/** Names joined as a sentence lists them: "Theorem 2.3", "Theorem 2.3 and Corollary 4.2", "Lemma 1, Lemma 2 and Lemma 3". */
const listed = (names: string[]) => (names.length < 2 ? (names[0] ?? '') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`);

/** A result's word for two of them, where adding an s will not do. */
const PLURAL: Record<string, string> = { Corollary: 'Corollaries', Hypothesis: 'Hypotheses', Lemma: 'Lemmas' };

export const review = {
	column: {
		/** The column's first line, over Everything and the kinds. */
		waiting: 'Waiting for you',
		/** The column's first entry: every row waiting for the person, in one list. */
		everything: 'Everything',
		/** Hover card on Everything. */
		everythingHover: 'All that waits for you, in one list.',
		/** The column's line over the drafts, each with the count of what concerns it. */
		drafts: 'Drafts',
		/** Hover card on Drafts. */
		draftsHover: 'Show only what concerns one draft.',
		/** The quiet line at the column's foot that opens the Record inside Review. */
		record: 'Record',
		/** Hover card on Record. */
		recordHover: 'Every version of your documents loom kept, the sessions agents worked in, and everything done in this quilt.',
		/** The column's list of kinds, its accessible name. */
		nav: 'What waits for you'
	},
	/** The kinds' names, in the column and over their groups in the list, and the hover card on each in the column. */
	kinds: {
		'accepted-changed': { name: 'Accepted results that changed', hover: 'Results you had accepted whose text has changed since. Read the change, and accept it again or not.' },
		questions: { name: 'Agent questions', hover: 'Questions an agent asked while working. Answer with one of its choices or in your own words.' },
		'attested-changed': { name: 'Attested results that changed', hover: 'Results whose statement, or a definition under it, changed after you attested the Lean. Say whether the Lean still states it.' },
		cited: { name: 'Cited results to digest', hover: 'Results your drafts cite that loom could not read by itself. Have an agent read them, or locate one yourself.' },
		check: { name: 'Digested results to check', hover: "Loom's copies of results, each waiting for you to check it against its paper." },
		attest: { name: 'Lean statements to attest', hover: "Lean has accepted these. To attest is to give your word that the Lean statement says what your result says; only then does the result read 'formalized'." },
		fetch: { name: 'Papers to fetch', hover: 'Papers an agent needs and could not download. Open each page, download the paper, and drop the file anywhere in loom.' },
		edits: { name: 'Proposed edits', hover: 'Changes an agent proposes to your text. Keep or undo each.' },
		agents: { name: 'Waiting for an agent', hover: 'Work you asked of an agent that none has finished. Nothing here needs you.' }
	} satisfies Record<ReviewKind | 'agents', { name: string; hover: string }>,
	list: {
		/** The list where a kind, or a kind for one draft, has nothing waiting. */
		empty: 'Nothing waits here.',
		/** The list while its first answer has not come. */
		loading: 'Reading what waits for you…',
		/** The list when Review's reads failed, with the publisher's reason. */
		failed: (why: string) => `Review could not be read: ${why}`
	},
	/** A row's first line: where it is, as "main.tex · Lemma 3.3" or "Smith 2024 · 9 results". */
	at: (where: string, what: string) => `${where} · ${what}`,
	/** A document's path drawn as its file's name. */
	file,
	/** A work's results in a row's first line: named where one or two ("Theorem 2.3 and Corollary 4.2", "Lemmas 5.7 and 5.9"), else counted. */
	results: (names: string[]) => {
		if (names.length > 2) return `${names.length} results`;
		const [a, b] = names.map((n) => /^(.*\S)\s+(\S+)$/.exec(n));
		if (a && b && a[1] === b[1]) return `${PLURAL[a[1]] ?? `${a[1]}s`} ${a[2]} and ${b[2]}`;
		return listed(names);
	},
	/** A row's quiet line: which drafts rest on its results, of how many. */
	rests: (docs: string[], resting: number, of: number) => {
		if (!docs.length || !resting) return '';
		const who = `${listed(docs.map(file))} ${docs.length === 1 ? 'rests' : 'rest'} on`;
		if (of === 1) return `${who} it`;
		if (of === 2 && resting === 2) return `${who} both`;
		return `${who} ${resting === 1 ? 'one' : resting}`;
	},
	/** Pieces of a row's quiet line, joined by a middle dot. */
	quiet: (parts: string[]) => parts.filter(Boolean).join(' · '),
	cited: {
		/** A cited row's quiet line, for a work loom holds only as a PDF. */
		pdfOnly: 'PDF only',
		/** A cited row's quiet line, for a result loom looked for in the work's TeX source and did not find. */
		notInSource: 'not found in its TeX source',
		/** The row of a citation that names no result. */
		namesNone: (doc: string, where: string, short: string) => `${file(doc)} · ${where} cites ${short} without naming a result`
	},
	check: {
		/** A check row's quiet line, where an agent transcribed its results from the pages of a PDF. */
		transcribed: 'transcribed by an agent',
		/** The row of an agent's correction to a result the person compared. */
		correction: (name: string) => `a correction to ${name}`,
		/** A result's row inside a work's: its number, then its name's word ("3.2 Lemma"). */
		numbered: (number: string, name: string) => `${number} ${name.endsWith(number) ? name.slice(0, -number.length).trim() : name}`,
		/** A result's quiet line inside a work's row: which drafts rest on it, and through which result where none uses it directly. */
		rests: (docs: string[], through?: string) => (docs.length ? `${listed(docs.map(file))} ${docs.length === 1 ? 'rests' : 'rest'} on it${through ? `, through ${through}` : ''}` : ''),
		/** Over an opened result: how its text was made, and so how to compare it. */
		how: {
			extracted: () => 'extracted exactly from the TeX source, so compare it at a glance',
			transcribed: (by: string, page: string) => (page ? `transcribed by ${by} from page ${page}, so read it closely` : `transcribed by ${by}, so read it closely`),
			read: (by: string) => `read by ${by} from the TeX source, so read it closely`,
			corrected: (by: string) => `corrected by ${by}, so read it closely`,
			written: () => 'written by you'
		},
		/** The two ways a result's text is shown. */
		rendered: 'rendered',
		plain: 'plain',
		/** The question under a result's text. */
		ask: "Does loom's copy match the paper?",
		/** The person's yes. */
		yes: 'yes, it matches',
		/** The person's no. */
		no: 'no, it differs…',
		/** The column's message after "no, it differs…", until correcting is built. */
		noLater: 'Correct it here, or ask an agent to',
		/** The column's message after the yes. */
		matched: (name: string) => `${name} matches the paper.`,
		/** Over the crop of the paper beside a result. */
		page: (short: string, page: number) => `${short}, page ${page}`,
		/** In place of the crop where loom knows no place on the paper for the result. */
		noPlace: 'Loom does not know where this stands on the paper yet.',
		/** In place of a result's text that could not be read. */
		missing: 'This result could not be read.',
		/** Under an agent's proposed correction. */
		stands: (date: string) => `The text you compared on ${date} stands until you take this.`,
		/** Takes an agent's correction. */
		take: 'take',
		/** Declines it. */
		decline: 'decline',
		/** The column's message after taking one. */
		taken: (name: string) => `${name} corrected.`,
		/** The column's message after declining one. */
		declined: 'Declined.'
	},
	attest: {
		/** An attest row's quiet line: what Lean states of the result. */
		what: { 'statement and proof': 'statement and proof', 'statement only': 'statement only' }
	},
	attested: {
		/** An attested-changed row's quiet line, where the result's own statement changed. */
		statement: (date: string) => `its statement changed since you attested it, ${date}`,
		/** An attested-changed row's quiet line, where a definition changed that results rest on. */
		used: (n: number) => (n === 1 ? 'changed since you attested it · 1 result rests on it' : `changed since you attested it · ${n} results rest on it`)
	},
	/** A date as a row says it: "20 Nov". */
	day: (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }),
	questions: {
		/** An agent's question, after the agent's name: where it was asked. */
		asks: (where: string) => ` asks, ${where}: `,
		/** Where a question was asked, while the agent digested a work. */
		digesting: (short: string) => `digesting ${short}`,
		/** Where a question was asked, on a draft's result. */
		onResult: (doc: string, name: string) => `on ${file(doc)}, ${name}`,
		/** Where a question was asked, on a page of a work. */
		onPage: (short: string, page: number) => `on ${short}, page ${page}`,
		/** Where a question was asked, on a work, a node, or a draft as a whole. */
		on: (what: string) => `on ${what}`,
		/** The field under a question's choices. */
		own: 'or answer in your own words',
		/** The button beside that field. */
		send: 'send',
		/** The column's message once a question is answered. */
		answered: (by: string) => `Answered. ${by} is told.`
	},
	fetch: {
		/** The link on a paper to fetch, which opens the work's page in the browser. */
		open: 'open its page ↗',
		/** Hover text on that link: the address it opens. */
		openTitle: (link: string) => `Opens ${link} in your browser`
	},
	edits: {
		/** A proposed edit's quiet line. */
		by: (by: string) => `proposed by ${by}`,
		/** A proposed edit's quiet line when its document has not compiled since an agent made it in place. */
		broke: (doc: string, line: number) => `${file(doc)} has not compiled since this edit (line ${line})`,
		/** Under an edit made in place that stopped its document compiling: who made it, and TeX's reason in words. */
		inPlace: (by: string, doc: string, why: string, line: number) => `${by} made this edit in place. ${file(doc)} has not compiled since: ${why} (line ${line}).`,
		/** TeX's reasons, as that line says them; one not here is shown as TeX gives it. */
		errors: { 'Undefined control sequence': 'the command it adds is not defined' } as Record<string, string>,
		/** Keeps a proposed edit. */
		keep: 'keep',
		/** Discards a suggested edit. */
		discard: 'discard',
		/** Discards an edit an agent made in place, writing the old words back. */
		undo: 'undo the edit',
		/** The column's message after keeping one. */
		kept: 'Kept.',
		/** The column's message after discarding or undoing one. */
		discarded: 'Discarded.'
	},
	accepted: {
		/** Accepts a changed result again. */
		accept: 'accept',
		/** The column's message after accepting. */
		accepted: 'Accepted.'
	},
	statement: {
		/** In place of a statement whose rendering could not be read. */
		missing: 'This text could not be read.'
	},
	agents: {
		/** A task an agent has taken, after the agent's name. */
		working: 'is working on it',
		/** A task no agent has taken. */
		waiting: 'waiting',
		/** The quiet link on a task's row, on hover, that withdraws it. */
		delete: 'delete',
		/** The column's message once a task is withdrawn. */
		deleted: 'Task deleted.',
		/** A task's sentence, from what was asked and of what (`docs/specs/library-views.md` §4.3). */
		digestMarked: (n: number, short: string) => (n === 1 ? `Digest the place you marked in ${short}` : `Digest the ${n} places you marked in ${short}`),
		digestAll: (short: string) => `Digest the whole of ${short}`,
		digestUses: (short: string) => `Digest the results your drafts use in ${short}`,
		digestChosen: (n: number, short: string) => (n === 1 ? `Digest one result of ${short}` : `Digest ${n} results of ${short}`),
		read: (names: string[], short: string) => `Read ${listed(names)} of ${short}`,
		askPage: (short: string, page: number, text: string) => `Answer, on ${short}, page ${page}: ${text}`,
		askResult: (doc: string, name: string, text: string) => `Answer, on ${file(doc)}, ${name}: ${text}`,
		correct: (name: string, short: string, text: string) => `Correct ${name} of ${short}: ${text}`,
		restate: (name: string, doc: string) => `Restate the Lean of ${name} of ${file(doc)}`,
		whichResult: (short: string, where: string) => `Say which result of ${short} ${where} cites`,
		formalize: (name: string, doc: string) => `Formalize ${name} of ${file(doc)}`
	},
	/** Names joined as a sentence lists them. */
	listed
} as const;
