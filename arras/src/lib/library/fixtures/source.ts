// Round six's fixture as a source: it answers each read of the views' spec from `round6.ts` and applies each write to it in memory, raising the generation as the publisher does, so the views are built and tried with no backend. Chosen by `../source.ts`.

import type { Answer, Source } from '../api';
import type { Gen } from '../types';
import { addWork, check, digest, fixturePdfUrl, nodeAnswer, placesOf, round6, scopesOf, workAnswer, type Fixture } from './round6';

type Body = Record<string, unknown>;

/** A source over a fresh copy of round six's data; `onChange` hears each write's new generation. */
export function fixtureSource(onChange: (gen: number) => void = () => {}): Source & { data: Fixture } {
	const f = round6();
	const ok = <T>(value: T): Answer<T & Gen> => ({ ok: true, value: { gen: f.gen, ...value } as T & Gen });
	const no = (code: string, message = code) => ({ ok: false as const, error: { code, message } });
	const changed = () => onChange(f.gen);

	const reads: Record<string, (b: Body) => Answer<Gen>> = {
		'library-works': () => ok({ works: f.works }),
		'library-work': (b) => {
			const a = workAnswer(f, b.ref as string);
			return a ? ok(a) : no('no-such-ref');
		},
		'library-digest-scopes': (b) => (b.all ? ok({ used: 14 }) : ok(scopesOf(f, b.ref as string))),
		'library-places': (b) => {
			const ref = (b.ref as string) ?? Object.keys(f.results).find((r) => f.results[r].some((x) => x.node === b.node)) ?? '';
			const pdf = f.works.find((w) => w.ref === ref)?.holds.pdf ?? '';
			return ok({ pdf, places: placesOf(f, b as { ref?: string; node?: string; pages?: number[] }) });
		},
		'library-node': (b) => {
			const a = nodeAnswer(f, b as { node?: string; ref?: string; item?: string; brief?: boolean });
			return a ? ok(a) : no('no-such-node');
		},
		'library-find': (b) => {
			const pdf = f.works.find((w) => w.ref === b.ref)?.holds.pdf ?? '';
			return ok({ pdf, hits: [{ page: 1, rects: [[72, 140, 300, 156]] }], pages: 24 });
		}
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
			const mark = `a-${f.gen}-mark`;
			(f.marks[b.target as string] ??= []).push({ mark, page: b.page as number, words: String(b.quote ?? '').slice(0, 40) + '…' });
			f.gen++;
			changed();
			return ok({ annotation: mark });
		},
		delete: (b) => {
			for (const ms of Object.values(f.marks)) {
				const i = ms.findIndex((m) => m.mark === b.annotation);
				if (i >= 0) ms.splice(i, 1);
			}
			f.gen++;
			changed();
			return ok({});
		},
		'review-task': () => {
			f.tasks.push(`t-${f.tasks.length + 1}`);
			f.gen++;
			changed();
			return ok({ task: f.tasks[f.tasks.length - 1] });
		},
		'library-look-up': () => ok({}),
		'library-undo': () => ok({}),
		'library-take': (b) => {
			const rows = ((b.items as { incoming?: string; text?: string; for?: string }[]) ?? []).map((it, item) => {
				const name = it.incoming ? it.incoming.replace(/^f-\d+-/, '') : (it.text ?? '');
				const added = addWork(f, name);
				return { id: `d-${f.gen}-${item}`, item, name, state: 'added', act: 'add', ref: added.ref, short: added.short, title: added.title, found_by: /^\d{4}\.\d{4,5}/.test(name) ? 'arxiv' : 'none', tex: /^\d{4}\.\d{4,5}/.test(name), unconfirmed: false };
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
			return { ok: true as const, value: { incoming: `f-${f.gen}-${file.name}`, name: file.name, size: file.size } };
		},
		pdfUrl: fixturePdfUrl,
		drawnUrl: () => null,
		thumbUrl: () => null
	};
}
