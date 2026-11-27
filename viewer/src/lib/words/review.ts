// Review's words: its column (the kinds, their counts' hover cards, Problems, the drafts, the History line), the list and its groups, each kind's row and body, the tasks waiting for an agent, and what the column's message says after an act. An entry is named for the place it shows, with a comment saying where, on one line.

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
		/** The column's entry for Review's Problems page, among the kinds by its name, with the count of what is wrong in the person's own files. */
		problems: 'Problems',
		/** Hover card on Problems. */
		problemsHover: "What is wrong in your own files: a document that did not compile, an error in its LaTeX, a link to something that is not there. Each opens at its place.",
		/** The quiet line at the column's foot that opens History inside Review. */
		record: 'History',
		/** Hover card on History. */
		recordHover: 'Every version of your documents loom kept, the sessions agents worked in, and everything done in this quilt.',
		/** The column's list of kinds, its accessible name. */
		nav: 'What waits for you'
	},
	/** The kinds' names, in the column and over their groups in the list, and the hover card on each in the column. */
	kinds: {
		'accepted-changed': { name: 'Results to accept', hover: 'Results you had accepted whose text has changed since come first, then those taken in from a copy or from Overleaf, what one copy brought in as one row. Read each, and accept it or not; those never accepted are folded beneath.' },
		questions: { name: 'Agent questions', hover: 'Questions an agent asked while working. Answer with one of its choices or in your own words.' },
		cited: { name: "Cited results loom can't read", hover: 'Results your drafts cite that loom could not read by itself. Have an agent read them, or locate one yourself.' },
		check: { name: 'Results to check', hover: "Loom's copies of results, each waiting for you to check it against its paper." },
		attest: { name: 'Lean statements to attest', hover: "Results whose statement, or a definition under it, changed since you attested the Lean come first: say whether the Lean still states each. Then those Lean has accepted that you never attested. To attest is to give your word that the Lean statement says what your result says; only then does the result read 'formalized'." },
		fetch: { name: 'Papers to add', hover: 'Papers an agent needs and could not download. Open each page, download the paper, and drop the file anywhere in loom.' },
		edits: { name: 'Proposed edits', hover: "Changes waiting in your text, and agents' copies to take in. Keep or discard each." },
		agents: { name: 'Agents still working', hover: 'Work you asked of an agent that none has finished. Nothing here needs you.' }
	} satisfies Record<Exclude<ReviewKind, 'attested-changed'> | 'agents', { name: string; hover: string }>,
	list: {
		/** The list where a kind, or a kind for one draft, has nothing waiting. */
		empty: 'Nothing waits here.',
		/** The list while its first answer has not come. */
		loading: 'Reading what waits for you…',
		/** The list when Review's reads failed, with the publisher's reason. */
		failed: (why: string) => `Review could not be read: ${why}`,
		/** In place of the list where the publisher does not serve its reads yet. */
		notServed: "This loom does not serve Review's lists yet."
	},
	/** A row's first line: where it is, as "main.tex · Lemma 3.3" or "Smith 2024 · 9 results". */
	at: (where: string, what: string) => `${where} · ${what}`,
	/** A library result with its work: "Theorem 2.3 of Okafor 2022". */
	of: (name: string, short: string) => `${name} of ${short}`,
	/** In place of a work's name while it is read, or where nothing names it. */
	someWork: 'a paper',
	/** In place of a result's name while it is read, or where nothing names it. */
	someResult: 'a result',
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
		/** Over the cited results, where the kind is shown alone. */
		head: (n: number) => `${n} results your drafts cite that loom could not digest by itself`,
		/** The button over the cited results that asks an agent to read every one. */
		readAll: (n: number) => `ask an agent to read all ${n}`,
		/** On a cited result's row: asks an agent to read it. */
		read: 'ask an agent to read it',
		/** On a cited result's row: opens the paper at what loom found of it, to mark its place. */
		locate: 'locate…',
		/** A cited result's quiet line once the person marked its place. */
		marked: 'marked by you',
		/** The column's message after asking for one. */
		asked: 'Asked an agent to read it. It comes back under Results to check.',
		/** The column's message after asking for all. */
		askedAll: 'Asked an agent to read them. They wait under Agents still working, and come back under Results to check.',
		/** Over the sentence of a draft that cites the result. */
		citesHere: (where: string) => `${where} cites it here`,
		/** The find bar's field, its accessible name. */
		find: 'Find in the paper',
		/** The find bar, where loom found the result's name. */
		hit: (page: number, i: number, n: number) => `these words are on page ${page} · ${i} of ${n}`,
		/** Goes to the next place the words are. */
		next: 'next ›',
		/** The find bar, where loom found nothing. */
		noHit: (page: number, pages: number) => `not in the PDF's text · page ${page} of ${pages}`,
		/** Turns to the next page, where loom found nothing. */
		nextPage: 'next page ›',
		/** Under the page while nothing is marked, where loom found the words. */
		unmarked: 'Nothing is marked. Select the passage, then mark to digest.',
		/** Under the page while nothing is marked, where loom found nothing. */
		unfound: 'Loom found nothing to go to. Page through, then select the passage.',
		/** The button over words selected on the page. */
		mark: 'mark to digest',
		/** The column's message once the person marked the passage and an agent was asked to read it. */
		markedOn: (page: number) => `Marked on page ${page}. An agent reads it from there.`,
		/** A cited row's quiet line, for a work loom holds only as a PDF. */
		pdfOnly: 'PDF only',
		/** A cited row's quiet line, for a result loom looked for in the work's TeX source and did not find. */
		notInSource: 'not found in its TeX source',
		/** The row of a citation that names no result. */
		namesNone: (doc: string, where: string, short: string) => `${file(doc)} · ${where} cites ${short} without naming a result`
	},
	citation: {
		/** Under a citation that names no result: what is wrong, and what to add. */
		explain: (short: string, doc: string) => `This cites ${short} without naming a result, so loom cannot tell what the proof rests on. Add the result to this citation in ${file(doc)}, for example`,
		/** The example of what to add, in the person's own key. */
		example: (citekey: string) => `\\cite[Lemma 2.4]{${citekey}}`,
		/** Asks an agent which result it is. */
		which: 'ask an agent which result',
		/** Says it names no result on purpose. */
		mention: 'only a mention',
		/** Under the buttons. */
		comesBack: (doc: string) => `An agent's answer comes back as a proposed edit to ${file(doc)}, which you keep or undo.`,
		/** The column's message after asking which. */
		askedWhich: 'Asked an agent which result it is.',
		/** The column's message after only a mention. */
		mentioned: 'Remembered as a mention. It is not asked about again.'
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
		/** In place of the crop where the place is on a page the paper's PDF does not have. */
		noPage: "This page is not in the paper's PDF.",
		/** Under the crop: the words of loom's copy that the page does not have where the result stands. */
		lacks: (words: string[]) => `Loom's copy has words the page does not: ${words.map((w) => `“${w}”`).join(', ')}.`,
		/** In place of the crop where loom knows no place on the paper for the result. */
		noPlace: 'Loom does not know where this stands on the paper yet.',
		/** In place of a result's text that could not be read. */
		missing: 'This result could not be read.',
		/** Under an agent's proposed correction. */
		stands: (date: string) => `The text you compared on ${date} stands until you take this.`,
		/** Under an agent's correction loom would not take now, in place of `take`. */
		cannotTake: "This can't be taken as it stands now. Decline it, and ask the agent again if it is still needed.",
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
		what: { 'statement and proof': 'statement and proof', 'statement only': 'statement only' } as Record<string, string>,
		/** Over the result's whole statement. */
		asWritten: (where: string) => `${where}, as you wrote it`,
		/** Over a library result's whole statement. */
		asPaper: (short: string) => `${short}, as the paper has it`,
		/** Over the Lean beside the statement: loom's own print of it, from its check. */
		leanStates: 'the Lean that states it, as Lean printed it when loom checked it',
		/** In place of the Lean, where loom's check kept no print of it. */
		noLean: 'Loom kept no print of this Lean; check it again to see it.',
		/** Over the table of the Lean's definitions. */
		definitions: 'What the Lean’s statement uses, each beside what it stands for in your draft',
		/** Over the table of the Lean's definitions, for a library result. */
		definitionsPaper: 'What the Lean’s statement uses, each beside what it stands for in the paper',
		/** The definitions table's second head. */
		stands: 'in your draft',
		/** The definitions table's second head, for a library result. */
		standsPaper: 'in the paper',
		/** Where a definition's Lean is marked for a result nothing answers to now. */
		standsNowhere: (label: string) => `marked for ${label}, which no result answers to now`,
		/** Under a definition the Lean stands for, once the person attested its own Lean. */
		itsLeanAttested: (date: string) => `You attested its Lean on ${date}.`,
		/** Under a definition the Lean stands for, its own Lean not yet attested. */
		itsLeanNot: 'You have not attested its Lean yet.',
		/** Beside a definition that stands for no result: the Lean defines it alone. */
		leanOnly: 'Defined in the Lean only, standing for no result, so your yes covers it.',
		/** Over the table of parts. */
		partByPart: (by: string) => `Part by part: what you wrote, and ${by}'s reading of the Lean`,
		/** Over the table of parts of a library result. */
		partByPaper: (by: string) => `Part by part: what the paper says, and ${by}'s reading of the Lean`,
		/** The table's heads. */
		draft: 'your draft',
		/** The table's first head for a library result. */
		paper: 'the paper',
		lean: 'Lean, as Lean prints it',
		reading: (by: string) => `${by}’s reading`,
		/** The parts table's head over the declaration of loom's record each part reads. */
		reads: 'the Lean it reads',
		/** Under the parts table's title: whose reading it is, and that nothing checks it. */
		readingBy: (by: string, date: string) => `${by} read the Lean on ${date}. Nothing checks a reading against the Lean: your yes is to the Lean above.`,
		/** Under the parts table's title, once loom checked the Lean again after the agent read it. */
		readingStale: (by: string, date: string) => `${by} read an earlier Lean, on ${date}; loom has checked the Lean again since, so this reading may not say what the Lean above says.`,
		/** For notation from the person's macros. */
		fromMacros: 'notation from your macros, defined by no result',
		/** A fold: the results the statement uses that the person attested already. */
		usesAttested: (names: string, date: string) => `It uses ${names}, which you attested on ${date}.`,
		/** A fold: the declarations that serve only the proof. */
		supporting: (n: number) => (n === 1 ? '1 supporting declaration serves the proof. Lean accepted it; it is not what you attest.' : `${n} supporting declarations serve the proof. Lean accepted them; they are not what you attest.`),
		/** Before an agent's note of a difference between the draft and the Lean. */
		found: (by: string) => `${by} found`,
		/** The question. */
		ask: 'Does the Lean say what you wrote?',
		/** The question for a library result. */
		askPaper: 'Does the Lean say what the paper says?',
		/** The person's yes. */
		yes: 'yes, I attest it',
		/** The person's no, which opens a field for what differs. */
		no: 'no, it differs…',
		/** Beside the yes: what it covers. */
		covers: (parts: string[], notation: string[], name: string) => `Yes covers ${parts.length === 1 ? 'part' : 'parts'} ${listed(parts)}${notation.length ? `, ${listed(notation)}` : ''}. ${name} then reads formalized.`,
		/** Beside the yes, after what it covers: the Lean's own definitions, which stand for no result. */
		coversAlone: (names: string[]) => `It covers ${listed(names)} too, which the Lean defines alone.`,
		/** Beside the yes, for a statement in one part. */
		coversAll: (name: string) => `Yes covers the statement as written. ${name} then reads formalized.`,
		/** The field after "no, it differs…". */
		differs: 'what the Lean gets wrong',
		/** The column's message after the yes. */
		attested: (name: string) => `${name} attested.`
	},
	restate: {
		/** Sends what differs, asking an agent to restate the Lean. */
		ask: 'ask an agent to restate',
		/** The column's message after asking. */
		asked: 'Asked an agent to restate it in Lean.'
	},
	attested: {
		/** The first step's head. */
		then: (date: string) => `What you attested, on ${date}`,
		/** Over the Lean the person attested. */
		leanThen: 'the Lean you attested, as Lean prints it',
		/** The second step's head. */
		now: 'How it reads now',
		/** The third step's head. */
		ask: 'Does the Lean still say this?',
		/** The person's word that it still does. */
		still: 'still states it',
		/** Under the third step, where only the statement changed. */
		leanSame: 'The Lean above has not changed; only your statement has.',
		/** Under the third step, for a definition results rest on. */
		eachAgain: (name: string) => `If it still states it, each result resting on ${name} is still asked about below, one by one.`,
		/** Over the results resting on a changed definition. */
		resting: (name: string, n: number) => `Resting on ${name} · ${n} · their words are unchanged, but what they mean has changed, so you attest each again`,
		/** A resting result's quiet line. */
		again: 'to attest again',
		/** A resting result's quiet line once attested again. */
		done: 'attested again',
		/** The question on a resting result. */
		askResting: (name: string) => `Does the Lean still say this, with ${name} as it reads now?`,
		/** The column's message after "still states it". */
		attestedAgain: 'Attested again.',
		/** An attested-changed row's quiet line, where the result's own statement changed. */
		statement: (date: string) => `its statement changed since you attested it, ${date}`,
		/** An attested-changed row's quiet line, where what its statement uses changed and nothing rests on it. */
		uses: 'what it uses changed since you attested it',
		/** An attested-changed row's quiet line, where a definition changed that results rest on. */
		used: (n: number) => (n === 1 ? 'changed since you attested it · 1 result rests on it' : `changed since you attested it · ${n} results rest on it`)
	},
	/** A date as a row says it: "20 Nov". */
	day: (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }),
	questions: {
		/** An agent's question, after the agent's name: where it was asked. */
		asks: (where: string) => ` asks, ${where}: `,
		/** Where a question was asked, while the agent's session was digesting a work. */
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
		/** Keeps a proposed edit. */
		keep: 'keep',
		/** Discards a suggested edit. */
		discard: 'discard',
		/** Discards an edit an agent made in place, writing the old words back. */
		undo: 'undo the edit',
		/** The column's message after keeping one. */
		kept: 'Kept.',
		/** The column's message after discarding or undoing one. */
		discarded: 'Discarded.',
		/** The quiet line of a file with edits made in place since the person's look: how many. */
		sinceLook: (n: number) => (n === 1 ? 'edited since your look' : `${n} edits since your look`),
		/** After it, on a document's row: how many of the files it loads beside its text (a style file, a bibliography, a preamble) its row holds too. */
		loads: (n: number) => (n === 1 ? 'with a file it loads' : `with ${n} files it loads`),
		/** Hover text on that line: which files. */
		loadsHover: (names: string[]) => `Edits to ${listed(names)}, which this document loads, are kept or discarded here with it`,
		/** Hover text on a file's own keep all and discard all, in its open row. */
		fileHover: { keep: 'Keeps every change in this file', discard: 'Discards every change in this file, writing your old words back over its edits' },
		/** The same on a document's row that holds the files it loads too. */
		loadsFileHover: { keep: 'Keeps every change in this document and the files it loads', discard: 'Discards every change in this document and the files it loads, writing your old words back over its edits' },
		/** Over Proposed edits: keeps every change listed that can be kept. */
		keepAll: (n: number) => `keep all ${n}`,
		/** Over Proposed edits: discards every change listed that can be. */
		discardAll: (n: number) => `discard all ${n}`,
		/** The column's message after keep all or discard all, then what was refused, a line each. */
		keptAll: (n: number) => (n === 1 ? 'Kept 1 change.' : `Kept ${n} changes.`),
		discardedAll: (n: number) => (n === 1 ? 'Discarded 1 change.' : `Discarded ${n} changes.`),
		/** Over Proposed edits: undoes the last keep or discard, named as the document's toolbar names it. */
		undoLast: (what: string) => `undo ${what}`,
		/** Over Proposed edits: shows the open annotations from others beneath the changes, with their count. */
		todo: (n: number) => `to do ${n}`,
		/** Hover text on it. */
		todoHover: 'The open annotations from others, beneath the changes',
		/** In place of those annotations, where there are none. */
		todoNone: 'No open annotations from others.',
		/** A copy's quiet line before what it holds. */
		copy: "an agent's copy",
		/** A copy's link at the right of its row: opens it on its own page in Review, where it is taken in and applied. */
		openCopy: 'review the copy',
		/** The column's message for changes loom would not keep or discard, one line for each reason; `why` by its code, absent where none is known. */
		notDone: (how: 'keep' | 'discard', n: number, why?: string) => `${n === 1 ? 'One change was' : `${n} changes were`} not ${how === 'keep' ? 'kept' : 'discarded'}${why ? `: ${why}` : '.'}`,
		/** Why, by the code loom refuses a keep or a discard with; a code not here is said by the frame's words, else not at all. */
		why: {
			changed: 'it changed after it was listed, so loom left it as it is.',
			'changed-since': 'its words changed in the file since, so loom left them as they are.',
			'no-such-change': 'it no longer waits.',
			'not-open': 'it was kept or discarded already.',
			'not-utf8': 'its file is not text loom can read.',
			'not-writable': 'its file cannot be written.',
			'outside-quilt': 'its file is outside the quilt.',
			mirrored: 'its document mirrors Overleaf: make the change there, then choose Done in Overleaf.'
		} as Record<string, string>,
		/** The column's message when the last keep or discard could not be undone. */
		notUndone: 'The last keep or discard could not be undone.'
	},
	accepted: {
		/** Accepts a changed result again. */
		accept: 'accept',
		/** On that button while it is answered. */
		accepting: 'accepting…',
		/** The column's message after accepting one, by its name. */
		acceptedOne: (name: string) => `Accepted ${name}.`,
		/** The column's message after accepting several. */
		acceptedMany: (n: number) => `Accepted ${n} results.`,
		/** The column's message for a result loom would not accept, and why where its row's code says (`why`). */
		notAccepted: (name: string, why?: string) => `${name} was not accepted${why ? `: ${why}` : '.'}`,
		/** Why, by the queue's `refusal_code`. */
		why: {
			'not-yours': 'it is not in your documents.',
			incomplete: 'it is marked incomplete.',
			'open-claim': 'it is a conjecture or a question, which is not accepted.',
			unclassified: 'loom cannot tell whether it is proved here, cited, or assumed.',
			unidentified: 'something it rests on cannot be identified.'
		} as Record<string, string>,
		/** A changed result's quiet line where its own text was edited. */
		changed: 'changed since you accepted',
		/** A changed result's quiet line: its first reason, and how many more it has. */
		more: (why: string, n: number) => (n ? `${why}, and ${n} more` : why),
		/** An accepted result's quiet line, in the folded list of those accepted. */
		by: (who: string, day: string) => `accepted by ${who}, ${day}`,
		/** The checkbox on a row, its accessible name. */
		pick: (name: string) => `Choose ${name} to accept with others`,
		/** Over Results to accept while some are chosen: how many. */
		picked: (n: number) => `${n} chosen`,
		/** Accepts the ones chosen. */
		acceptPicked: (n: number) => `accept ${n}`,
		/** Unchooses them. */
		clear: 'clear',
		/** An adoption's quiet line in Results to accept: how many results the person took in from an agent's copy. */
		adoption: (n: number) => `taken in ${n} ${n === 1 ? 'result' : 'results'} from the copy`,
		/** After it, how many of them cannot be accepted yet. */
		cannotCount: (n: number) => `${n} can't be accepted yet`,
		/** In an open adoption: accepts every result it took in that can be accepted. */
		acceptAll: (n: number) => `accept all ${n}`,
		/** Hover text on it. */
		acceptAllHover: 'Accepts every result taken in from this copy that can be accepted; those that cannot yet say why',
		/** A block's quiet line within its adoption where it cannot be accepted yet, by the queue's `refusal_code`. */
		cannotRow: (code?: string) =>
			({
				'not-yours': "can't be accepted: not in your documents",
				incomplete: "can't be accepted yet: marked incomplete",
				'open-claim': "can't be accepted: a conjecture or a question",
				unclassified: "can't be accepted yet: not said whether proved, cited or assumed",
				unidentified: "can't be accepted yet: rests on something unidentified"
			})[code ?? ''] ?? "can't be accepted yet",
		/** The two folds beneath the results waiting, which count nothing. */
		never: 'Never accepted',
		done: 'Accepted',
		/** Over Results to accept where no reviewer name is set. */
		noReviewer: 'Choose your reviewer name in Settings to accept.',
		/** Over Results to accept where the quilt is not served for writing. */
		readOnly: 'This copy of the quilt only reads; accepting needs the quilt served for writing.'
	},
	/** What changed in a block since it was accepted (`SinceAccepted`), in an open row of Results to accept, over Review with its document, and in Docs beside it. */
	since: {
		/** Over the block as it was last accepted, its own text since edited. */
		accepted: (name: string) => `Last accepted · ${name}`,
		/** Over what it rests on as it is now. */
		current: (name: string) => `Current · ${name}`,
		/** The choice among a block's reasons, its accessible name. */
		choose: 'Why it waits',
		/** One reason in that choice. */
		option: (why: string, i: number, n: number) => `${why} · ${i} of ${n}`
	},
	yours: {
		/** Under a block waiting to be accepted that cannot be yet, why, by loom's code (`refusal_code`); an older publisher sends none. */
		cannot: (code?: string) =>
			({
				'not-yours': "Can't be accepted: it is not in your documents.",
				incomplete: "Can't be accepted yet: it is marked incomplete.",
				'open-claim': "Can't be accepted: it is a conjecture or a question, which is not accepted.",
				unclassified: "Can't be accepted yet: loom cannot tell whether it is proved here, cited, or assumed.",
				unidentified: "Can't be accepted yet: something it rests on cannot be identified."
			})[code ?? ''] ?? "Can't be accepted yet.",
		/** The same for a block marked incomplete with notes, before the person's own notes on it. */
		cannotNoted: "Can't be accepted yet: it is marked incomplete:",
		/** Over a copy opened from Proposed edits: back to the list. */
		back: '‹ Proposed edits',
	},
	/** Settling a write loom could neither finish nor undo, on its notice in Problems (`SettleLeft`): the control, the preview drawn from `write-settle-preview`'s fields, and what is said after. Never an id, a digest, a command, or loom's own sentence. */
	settle: {
		/** The control on the notice; it asks what settling would do and writes nothing. */
		button: 'Settle as it stands',
		/** Hover card on it. */
		buttonHover: 'See what settling it leaves and records before anything is done.',
		/** While the preview is asked for. */
		reading: 'Reading what settling it would do…',
		/** The preview's first line: what settling never does. `kind` is the write's own name, "a Keep", "an import". */
		lead: (kind: string) => `Settling ${kind || 'this write'} as it stands writes none of your files.`,
		/** Over the person's files the write touched. */
		files: (n: number) => (n === 1 ? 'This file stays exactly as it is now:' : 'These files stay exactly as they are now:'),
		/** Over the suggested edits the write wrote or undid. */
		edits: (n: number) => (n === 1 ? 'This suggested edit is recorded as your file shows it:' : 'These suggested edits are recorded as your files show them:'),
		/** One suggested edit: whose and what (`words`), what it becomes by the preview's `outcome`, and why, as loom found it in the file; an outcome this viewer does not know is said as left. */
		edit: (words: string, outcome: string, why: string) => {
			const becomes = { kept: 'kept', open: 'open again, for you to keep or discard', closed: 'closed, as no longer applying' }[outcome] ?? 'left as it is';
			return `${words}: ${becomes}${why ? `, since ${why}` : ''}.`;
		},
		/** What becomes of the version of your files the write began, by the preview's `history`; '' and `recorded` say nothing. */
		history: {
			lands: 'The version loom kept of your files just before this write is recorded in your history.',
			removed: 'The version loom began of your files just before this write was never recorded, so it is not kept in your history.'
		} as Record<string, string>,
		/** Where the write touched no file loom can name and no suggested edit: the notice is all that goes. */
		nothing: 'It decides nothing of your suggested edits and keeps no version; it only takes this notice away.',
		/** The preview's confirming button. */
		confirm: 'Settle it',
		/** The preview's button that closes it, nothing done. */
		cancel: 'Cancel',
		/** While it settles. */
		busy: 'Settling…',
		/** Said after it is settled, over Problems: what was done, in counts, never loom's sentence. */
		done: (outcomes: string[], history: string) => {
			const counts = (['kept', 'open', 'closed'] as const).map((o) => [o, outcomes.filter((x) => x === o).length] as const).filter(([, n]) => n);
			const said = { kept: 'kept', open: 'open again', closed: 'closed' };
			const edits = counts.length ? ` Suggested edits: ${counts.map(([o, n]) => `${n} ${said[o]}`).join(', ')}.` : '';
			const version = history === 'lands' ? ' Its version is recorded in your history.' : history === 'removed' ? ' The version it began is not kept.' : '';
			return `Settled as it stands: none of your files was written.${edits}${version}`;
		},
		/** Why it was not settled or previewed, by loom's refusal code; any other code says the frame's word for it. */
		refused: {
			'author-only': 'Only you can settle a write; loom does not take it from an agent.',
			'no-such-act': 'That write is no longer waiting to be settled, so nothing was done.',
			'not-left': 'Loom settles that write itself the next time it writes, so there is nothing to decide.',
			changed: 'A file changed while it was being settled, so nothing was done. Look at what settling does now, and settle it again.'
		} as Record<string, string>
	},
	statement: {
		/** In place of a statement whose rendering could not be read. */
		missing: 'This text could not be read.'
	},
	/** Notes said once over a section (`SaidOnce`). */
	once: {
		/** Its close button. */
		close: 'Close this note',
		/** Over Proposed edits: what the list holds, since when, the places it never watches, and how far a deny holds for the apps set up here (`holds`, loom's sentence in the person's words, as Settings › Agents says it). */
		watched: (when: string, carried: string, unwatched: string[], holds: string) =>
			[
				`Here wait agents' suggestions, and every edit made in the places agents may edit since your look${when ? ` of ${when}` : ''}${carried ? `, carried over from ${carried}'s` : ''}.`,
				unwatched.length ? `Your own places are not watched, so an edit there is never listed: ${unwatched.join(', ')}.` : '',
				holds
			]
				.filter(Boolean)
				.join(' '),
		/** Under the bar that names the reviewer, where the name is git's. */
		nameFromGit: (name: string) => `You review as ${name}, the name git gives, and your look and acceptances are kept under it. Set your own name in Settings › Profile.`
	},
	seeIt: {
		/** Under a row's text: lays its document over Review, at the result. */
		link: (doc: string) => `see it in ${file(doc)}`,
		/** In the document's head over Review: where it was opened. */
		at: (name: string) => `at ${name}`,
		/** In the document's head: that it cannot be edited here. */
		readOnly: 'read only here; edit it in Docs',
		/** The document's close button. */
		close: 'Close the document'
	},
	agents: {
		/** A task an agent has taken, after the agent's name. */
		working: 'is working on it',
		/** A task no agent has taken. */
		waiting: 'waiting',
		/** The quiet link on a task's row, on hover, that withdraws it. */
		delete: 'delete',
		/** The column's message once a task is withdrawn, with `undo`, which asks for it again. */
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
		whichResult: (short: string, where: string) => `Say which result of ${short} ${/^proof /.test(where) ? `the ${where}` : where} cites`,
		formalize: (name: string, doc: string) => `Formalize ${name} of ${file(doc)}`
	},
	/** Review › History › Versions, under a document's versions: each version of a file no document's version holds. */
	fileVersions: {
		/** The section's heading. */
		heading: 'Other files',
		/** Under it. */
		lead: 'Files an update from Overleaf wrote over while they held changes made here, and files a restore replaced, each kept as it was.',
		/** A row's button that shows the version's bytes below it. */
		open: 'Open',
		/** A row's button that shows how the version differs from the file now. */
		compare: 'Compare with now',
		/** In place of Compare when the file holds these bytes now. */
		same: 'Same as now',
		/** A row's button that asks before restoring. */
		restore: 'Restore…',
		/** The question it asks. */
		ask: (name: string, when: string) => `Put ${name} back as it was${when ? ` on ${when}` : ''}? Its bytes now are kept as a version.`,
		/** The button that restores. */
		go: 'Restore',
		/** While it restores. */
		going: 'Restoring…',
		/** The button that cancels the question. */
		cancel: 'Cancel',
		/** A file that is neither text nor an image, opened: where its bytes are. */
		download: (name: string) => `Download ${name} as kept`,
		/** Compare on a file that is neither text nor an image. */
		differs: 'The kept bytes differ from the file now; download them to compare.',
		/** Over the version, beside the file now, when two images are compared. */
		then: 'Kept',
		now: 'Now',
		/** When the file is gone now. */
		gone: 'The file is not there now.',
		/** When the version's bytes could not be read. */
		unread: 'Its bytes could not be read.',
		/** Everything recorded's words for a file's version, by why it was kept. */
		kept: (name: string, message: string) => `Kept a version of ${name}${message ? `: ${message}` : ''}`,
		/** Everything recorded's words for a file's version put back. */
		restored: (name: string) => `Put ${name} back as a version`
	},
	/** Names joined as a sentence lists them. */
	listed
} as const;
