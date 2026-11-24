// Round six's fixture as a source: it answers each read of the views' spec from `round6.ts` and applies each write to it in memory, raising the generation as the publisher does, so the views are built and tried with no backend. Chosen by `../source.ts`.

import type { Answer, Source } from '../api';
import type { Gen } from '../types';
import { addWork, check, checkRows, digest, fixturePdfUrl, lookUp, nodeAnswer, placesOf, REF, round6, scopesOf, workAnswer, workOfNode, type Fixture } from './round6';
import { notesAnswer } from './notes6';
import { formalMarks, formalPlan, growWeb, webFocus, webFragment, webGraph, webGroup, webList, webSearch } from './web6';
import { ask, attest, body, close, counts, fragmentOf, list, markStub, taskOf, unwithdraw, withdraw } from './review6';
import type { ReviewKind, TaskRow, WebScope } from '../types';

type Body = Record<string, unknown>;

/** The labels round six's main.tex cites its works by. */
const CITED: Record<string, string> = { arden24: '[1]', okafor: '[2]', arden25: '[3]', vance: '[4]' };

/** A source over a fresh copy of round six's data; `onChange` hears each write's new generation. */
export function fixtureSource(onChange: (gen: number) => void = () => {}, o: { network?: 'asked' | 'off' | 'unasked'; web?: 'large' } = {}): Source & { data: Fixture } {
	const f = round6();
	if (o.network) f.network = o.network;
	if (o.web === 'large') growWeb();
	// a copy, as an answer over the wire is: the fixture changes its own objects in place, and a view keeps an answer whole
	const ok = <T>(value: T): Answer<T & Gen> => ({ ok: true, value: structuredClone({ gen: f.gen, ...value }) as T & Gen });
	const no = (code: string, message = code) => ({ ok: false as const, error: { code, message } });
	const changed = () => onChange(f.gen);
	const answered = new Set<string>();

	const reads: Record<string, (b: Body) => Answer<Gen>> = {
		// asked for a draft, each work says the label that draft cites it by, as round six's main.tex does
		'library-works': (b) => ok({ works: b.doc ? f.works.map((w) => ({ ...w, cited_as: CITED[Object.keys(REF).find((k) => REF[k] === w.ref) ?? ''] ?? null })) : f.works }),
		'library-work': (b) => {
			const a = workAnswer(f, b.ref as string);
			return a ? ok(a) : no('no-such-ref');
		},
		'library-digest-scopes': (b) => (b.all ? ok({ used: 14 }) : ok(scopesOf(f, b.ref as string))),
		'library-places': (b) => {
			const ref = (b.ref as string) ?? workOfNode(f, b.node as string);
			const work = f.works.find((w) => w.ref === ref);
			if (!work) return no('no-such-ref');
			if (!work.holds.pdf) return no('no-document');
			const places = placesOf(f, b as { ref?: string; node?: string; pages?: number[] });
			return ok({ result: `${places.length} placed`, pdf: work.holds.pdf, places });
		},
		'library-node': (b) => {
			const a = nodeAnswer(f, b as { node?: string; ref?: string; item?: string; brief?: boolean });
			return a ? ok(a) : no('no-such-node');
		},
		'library-find': (b) => {
			const pdf = f.works.find((w) => w.ref === b.ref)?.holds.pdf ?? '';
			return ok({ pdf, hits: [{ page: 1, rects: [[72, 140, 300, 156]] }], pages: 24 });
		},
		'formal-marks': (b) => ok({ on: true, marks: formalMarks(b.doc as string) }),
		'formal-plan': (b) => ok(formalPlan(REF, b.targets as string[], (b.assume as string[]) ?? [])),
		notes: (b) => ok(notesAnswer(f.notes, b as { sort: string; orphaned?: boolean; group?: string; offset?: number })),
		'web-list': (b) => ok(webList(REF, b as { scope: WebScope; doc?: string; sort: string; open?: string[]; offset?: number })),
		'web-group': (b) => ok(webGroup(REF, b as { scope: WebScope; doc?: string; group: string })),
		'web-search': (b) => ok(webSearch(REF, b as { scope: WebScope; doc?: string; q: string })),
		'web-focus': (b) => {
			const a = webFocus(REF, b as { scope: WebScope; doc?: string; result: string; more?: boolean });
			return a ? ok(a) : no('no-such-result');
		},
		'web-graph': (b) => {
			const a = webGraph(REF, b as { scope: WebScope; doc?: string; result: string });
			return a ? ok(a) : no('no-such-result');
		},
		'review-counts': () => ok(counts(f.review, checkRows(f))),
		'review-list': (b) => ok(list(f.review, checkRows(f), (b.kind ?? 'all') as ReviewKind | 'all' | 'agents', b.doc as string | undefined)),
		'review-row': (b) => {
			const a = body(f.review, b.row as string, b.node as string | undefined);
			if (!a) return no('no-such-row');
			// a cited result's locate… draws the work's PDF, by its hash
			const cited = b.node ? f.review.rows.find((r) => r.row === b.row && r.kind === 'cited') : undefined;
			const pdf = cited && 'ref' in cited ? (f.works.find((w) => w.ref === cited.ref)?.holds.pdf ?? null) : undefined;
			return ok(pdf === undefined ? a : { ...a, body: { ...a.body, pdf } });
		}
	};

	/** Closes the row `test` finds, raising the generation; `no-such-row` where nothing waits there any more. */
	const closing = (test: Parameters<typeof close>[1]) => {
		if (!close(f.review, test)) return no('no-such-row');
		f.gen++;
		changed();
		return ok({});
	};

	const writes: Record<string, (b: Body) => Answer<Gen>> = {
		'library-digest': (b) => {
			const done = digest(f, b.refs as string[] | 'all', b.scope as string, (b.chosen as string[]) ?? []);
			changed();
			return ok(done);
		},
		'library-check': (b) => {
			if (!check(f, b.node as string)) return no('no-such-node');
			changed();
			return ok({});
		},
		'library-delete': (b) => {
			const i = f.works.findIndex((w) => w.ref === b.ref);
			if (i < 0) return no('no-such-ref');
			const undo = `u-${f.gen}`;
			f.deleted[undo] = { work: f.works[i], at: i };
			f.works.splice(i, 1);
			f.gen++;
			changed();
			return ok({ undo });
		},
		'library-restore': (b) => {
			const d = f.deleted[b.undo as string];
			if (!d) return no('no-such-undo');
			f.works.splice(d.at, 0, d.work);
			delete f.deleted[b.undo as string];
			f.gen++;
			changed();
			return ok({ ref: d.work.ref });
		},
		annotate: (b) => {
			if (b.purpose !== 'to-digest') return ok({});
			if (b.node) markStub(f.review, b.node as string);
			const mark = `a-${f.gen}-mark`;
			(f.marks[b.target as string] ??= []).push({ mark, page: b.page as number, words: String(b.quote ?? '').slice(0, 40) + '…' });
			f.gen++;
			changed();
			return ok({ annotation: mark });
		},
		delete: (b) => {
			f.notes = f.notes.filter((n) => n.annotation !== b.annotation);
			for (const ms of Object.values(f.marks)) {
				const i = ms.findIndex((m) => m.mark === b.annotation);
				if (i >= 0) ms.splice(i, 1);
			}
			f.gen++;
			changed();
			return ok({});
		},
		// an ask of an agent, as `evidence.md` §7 takes it: the place and what the kind needs in `on`, the person's words in `text`
		'review-task': (b) => {
			const on = (b.on ?? {}) as Record<string, unknown>;
			const text = (b.text as string) ?? '';
			const docs = (b.docs as string[]) ?? [];
			const made = taskOf(String(b.kind), on, text);
			if (!made) return no('bad-field', 'kind is read, digest, ask, correct, restate or which-result');
			// a stub asked for leaves the cited results; its row goes with its last
			if (b.kind === 'read') {
				const nodes = (on.nodes as string[]) ?? [];
				for (const r of f.review.rows) if (r.kind === 'cited' && r.citation === undefined) r.stubs = r.stubs.filter((s) => !nodes.includes(s.node));
				f.review.rows = f.review.rows.filter((r) => !(r.kind === 'cited' && r.citation === undefined && !r.stubs.length));
			}
			if (b.kind === 'which-result') close(f.review, (r) => r.kind === 'cited' && r.citation !== undefined && r.key === on.key && r.ref === on.ref);
			const task = ask(f.review, String(b.kind), made.place, docs, made.fields);
			f.gen++;
			changed();
			return ok({ task });
		},
		// an answer closes the question; a second, or one to a question withdrawn, is refused `closed`
		'review-answer': (b) => {
			if (answered.has(b.question as string)) return no('closed', 'this question is answered or withdrawn already; reload Review');
			if (!close(f.review, (r) => r.kind === 'questions' && r.question === b.question)) return no('no-such-task');
			answered.add(b.question as string);
			f.gen++;
			changed();
			return ok({});
		},
		'review-task-delete': (b) => {
			if (!(b.undo === true ? unwithdraw(f.review, b.task as string) : withdraw(f.review, b.task as string))) return no('no-such-task');
			f.gen++;
			changed();
			return ok({});
		},
		'change-keep': (b) => closing((r) => r.kind === 'edits' && (b.changes as string[]).includes(r.change)),
		'change-discard': (b) => closing((r) => r.kind === 'edits' && (b.changes as string[]).includes(r.change)),
		'formal-attest': (b) => {
			if (!attest(f.review, b.result as string)) return no('no-such-result');
			f.gen++;
			changed();
			return ok({});
		},
		'formal-ask': (b) => {
			const plan = formalPlan(REF, b.targets as string[], (b.assume as string[]) ?? []);
			if (plan.stops.length) return no('needs-label', `${plan.stops.map((r) => r.name).join(', ')} needs a label`);
			const tasks = plan.targets.map((t) => ask(f.review, 'formalize', { label: t.key }, [t.doc], { target: { label: t.key } }));
			f.gen++;
			changed();
			return ok({ tasks });
		},
		'library-mention': (b) => closing((r) => r.kind === 'cited' && r.citation === b.citation),
		'review-accept': (b) => closing((r) => r.kind === 'accepted-changed' && (b.keys as string[]).includes(r.key)),
		'library-correction-take': (b) => closing((r) => r.kind === 'check' && r.correction === b.correction),
		'library-correction-decline': (b) => closing((r) => r.kind === 'check' && r.correction === b.correction),
		'library-look-up': (b) => {
			if (f.network === 'unasked' && b.online !== true) return no('network-unasked', '');
			if (f.network === 'off' && b.online !== true) return no('offline', '');
			if (!lookUp(f, b.ref as string)) return no('no-identifier', '');
			changed();
			return ok({ ref: b.ref });
		},
		// undoing an add takes the work it added back out
		'library-undo': (b) => {
			if (!((b.id as string) in f.taken)) return no('no-such-intake', '');
			const ref = f.taken[b.id as string];
			const i = f.works.findIndex((w) => w.ref === ref);
			if (i >= 0) f.works.splice(i, 1);
			delete f.taken[b.id as string];
			f.gen++;
			changed();
			return ok({});
		},
		// a question no drop here asks; an answer of a work of its own adds it, as the intake does
		// the person's answer: the file filed under the work they named, or a work of its own
		'library-answer': (b) => {
			const q = f.questions[String(b.question)];
			if (!q) return no('no-such-question');
			if (b.same && !q.candidates.includes(String(b.same))) return no('not-a-candidate');
			delete f.questions[String(b.question)];
			if (b.same) {
				const w = f.works.find((x) => x.ref === b.same)!;
				if (!w.holds.pdf) w.holds = { ...w.holds, pdf: `sha256:${'0'.repeat(56)}${f.gen.toString(16).padStart(8, '0')}` };
				f.gen++;
				changed();
				return ok({ row: { id: String(b.question), item: 0, name: q.name, state: 'added', act: `x-${f.gen}`, ref: w.ref, short: w.short, title: w.title, authors: w.authors, year: w.year, found_by: 'entry', tex: w.holds.tex, unconfirmed: false, identifier: w.link ? `arxiv:${w.link.split('/').pop()}` : null, under: true } });
			}
			const added = addWork(f, q.name, b.online !== true);
			changed();
			return ok({ row: { id: String(b.question), item: 0, name: q.name, state: 'added', act: `x-${f.gen}`, ref: added.ref, short: added.short, title: added.title, authors: added.authors, year: added.year, found_by: 'none', tex: false, unconfirmed: false, identifier: null, under: false } });
		},
		// a work's PDF taken off it waits again as a drop
		'library-unfile': (b) => {
			const w = f.works.find((x) => x.ref === b.ref);
			if (!w) return no('no-such-work', '');
			if (!w.holds.pdf) return no('no-document', '');
			const incoming = w.holds.pdf.replace(/^sha256:/, '');
			w.holds = { ...w.holds, pdf: null };
			f.gen++;
			changed();
			return ok({ incoming, act: `x-${f.gen}`, row: { id: incoming, item: 0, name: `${w.short}.pdf`, state: 'received' } });
		},
		// one BibTeX entry, kept as the work's in place of the one it had; its title, where it states one, is the work's
		'library-entry': (b) => {
			const w = f.works.find((x) => x.ref === b.ref);
			if (!w) return no('no-such-ref', '');
			const text = String(b.bibtex ?? '');
			if (!/^\s*@\w+\s*\{\s*[^,\s]+\s*,[\s\S]*\}\s*$/.test(text)) return no('bad-entry');
			f.entries[w.ref] = text.trim();
			const title = /\btitle\s*=\s*\{([^}]*)\}/i.exec(text)?.[1].trim();
			if (title) w.title = title;
			f.gen++;
			changed();
			return ok({ ref: w.ref });
		},
		'library-take': (b) => {
			const offline = b.online === false;
			if (f.network === 'unasked' && !offline) return no('network-unasked', '');
			const rows = ((b.items as { incoming?: string; text?: string; for?: string }[]) ?? []).map((it, item) => {
				const name = it.incoming ? it.incoming.replace(/^f-\d+-/, '') : (it.text ?? '');
				// a file named by an arXiv number a work in the library states asks whether it is that work, as the intake asks of an identifier a file states
				const stated = it.incoming ? /^(\d{4}\.\d{4,5})(v\d+)?/.exec(name) : null;
				const same = stated ? f.works.filter((w) => w.link?.endsWith(`/${stated[1]}`)) : [];
				if (stated && same.length) {
					const question = `q-${f.gen}-${item}`;
					f.questions[question] = { name, candidates: same.map((w) => w.ref) };
					const how = `arxiv:${stated[1]}`;
					return { id: `d-${f.gen}-${item}`, item, name, state: 'question', question, document: { name, kind: 'pdf', identifiers: [`arxiv:${stated[1]}${stated[2] ?? ''}`] }, candidates: same.map((w) => ({ ref: w.ref, short: w.short, title: w.title, authors: w.authors, year: w.year, how })) };
				}
				const arxiv = /^\d{4}\.\d{4,5}/.test(name);
				const added = addWork(f, name, offline);
				const id = `d-${f.gen}-${item}`;
				f.taken[id] = added.ref;
				// an added row as the intake sends it (`write-api.md` §6): a file is found by the identifier it states, else by its name
				return { id, item, name, state: 'added', act: `x-${f.gen}-${item}`, ref: added.ref, short: added.short, title: added.title, authors: added.authors, year: added.year, found_by: arxiv ? 'arxiv' : it.text ? 'none' : 'title', tex: arxiv && !offline, unconfirmed: offline && arxiv, identifier: arxiv ? `arxiv:${name}` : null, under: !!it.for };
			});
			changed();
			return ok({ rows });
		}
	};

	return {
		data: f,
		async call<T extends Gen>(name: string, body: Body): Promise<Answer<T>> {
			const read = reads[name];
			if (read) {
				if (typeof body.since === 'number' && body.since === f.gen) return { ok: true, value: { gen: f.gen, unchanged: true } as T };
				return read(body) as Answer<T>;
			}
			const write = writes[name];
			if (write) return write(body) as Answer<T>;
			return no('not-served', `the fixture does not answer ${name}`);
		},
		async receive(file: File) {
			// a PDF, a .bib, a TeX file or an archive of a source, as the intake keeps
			if (!/\.(pdf|bib|tex|tar|gz|tgz|zip)$/i.test(file.name)) return { ok: false as const, error: { code: 'not-a-document', message: '' } };
			return { ok: true as const, value: { incoming: `f-${f.gen}-${file.name}`, name: file.name, size: file.size } };
		},
		async serves(name: string) {
			return name in reads || name in writes;
		},
		async fragment(path: string) {
			return fragmentOf(f.review, path) ?? webFragment(path);
		},
		pdfUrl: fixturePdfUrl,
		drawnUrl: () => null,
		thumbUrl: () => null
	};
}
