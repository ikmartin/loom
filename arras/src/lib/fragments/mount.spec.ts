// A fragment wired against the manifest a build publishes, which names no cited work: a citation stays the text the publisher drew, and the wiring after it (images, marks, heading links) is all done. Node has no DOM, so each element is a stand-in answering only what `wire` asks of it, and the root answers each selector `wire` queries with the elements put there for it.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../../../tests/fixture/manifest.json';
import type { Manifest } from '$lib/manifest/types';
import { wire } from './mount';

const m = fixture as unknown as Manifest;

/** An element as `wire` reads and writes it. */
class El {
	dataset: Record<string, string> = {};
	attrs = new Map<string, string>();
	classes = new Set<string>();
	children: El[] = [];
	parentElement: El | null = null;
	listeners: string[] = [];
	textContent = '';
	props = new Map<string, string>();
	style = { setProperty: (k: string, v: string) => void this.props.set(k, v), getPropertyValue: (k: string) => this.props.get(k) ?? '' };
	constructor(
		public tagName: string,
		init: { classes?: string[]; dataset?: Record<string, string>; attrs?: Record<string, string> } = {}
	) {
		for (const c of init.classes ?? []) this.classes.add(c);
		Object.assign(this.dataset, init.dataset ?? {});
		for (const [k, v] of Object.entries(init.attrs ?? {})) this.attrs.set(k, v);
	}
	get classList() {
		const c = this.classes;
		return { add: (x: string) => c.add(x), remove: (x: string) => c.delete(x), contains: (x: string) => c.has(x), toggle: (x: string, on?: boolean) => ((on ?? !c.has(x)) ? c.add(x) : c.delete(x)), [Symbol.iterator]: () => c[Symbol.iterator]() };
	}
	set className(v: string) {
		this.classes = new Set(v.split(/\s+/).filter(Boolean));
	}
	getAttribute(n: string) {
		return this.attrs.get(n) ?? null;
	}
	setAttribute(n: string, v: string) {
		this.attrs.set(n, String(v));
	}
	removeAttribute(n: string) {
		this.attrs.delete(n);
	}
	set href(v: string) {
		this.attrs.set('href', v);
	}
	set src(v: string) {
		this.attrs.set('src', v);
	}
	set title(v: string) {
		this.attrs.set('title', v);
	}
	addEventListener(type: string) {
		this.listeners.push(type);
	}
	appendChild(c: El) {
		c.parentElement = this;
		this.children.push(c);
		return c;
	}
	append(...cs: (El | string)[]) {
		for (const c of cs) if (typeof c !== 'string') this.appendChild(c);
	}
	prepend(c: El) {
		c.parentElement = this;
		this.children.unshift(c);
	}
	get firstChild() {
		return this.children[0] ?? null;
	}
	querySelector() {
		return null;
	}
	querySelectorAll() {
		return [];
	}
	closest() {
		return null;
	}
}

/** A fragment's root, answering each selector with the elements given for it. */
class Root extends El {
	constructor(private found: Record<string, El[]>) {
		super('div');
	}
	querySelectorAll(sel?: string) {
		return (this.found[sel ?? ''] ?? []) as never[];
	}
}

describe('a fragment with a citation, wired against a manifest that names no cited work', () => {
	beforeEach(() => {
		vi.stubGlobal('document', { createElement: (tag: string) => new El(tag) });
	});
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('leaves the citation as the text it is, and wires its images, marks and heading links', () => {
		expect('references' in m).toBe(false);
		const cite = new El('span', { classes: ['cite'], dataset: { citekey: 'Kre99', postnote: 'Theorem 2.1' } });
		const img = new El('img', { attrs: { src: 'figures/fig.svg' } });
		const mark = new El('mark', { classes: ['annotation'], dataset: { annotation: 'a-2026-09-16-ecnav2' } });
		const env = new El('div', { classes: ['env'], dataset: { id: 'sy-0003', taxon: 'Lemma' } });
		const label = new El('p', { classes: ['env-label'] });
		env.appendChild(label);
		const root = new Root({
			'span.cite[data-citekey]': [cite],
			'.env[data-taxon]': [env],
			'img[src]': [img],
			'mark.annotation[data-annotation], .annotation-block[data-annotation]': [mark],
			'section[data-id] > :is(h1,h2,h3,h4,h5,h6), div.env[data-id] > p.env-label': [label]
		});
		wire(root as unknown as HTMLElement, m, () => {}, () => {}, { headingLinks: true });
		// the citation: no link made of it
		expect(cite.children).toEqual([]);
		// what follows it in the wiring
		expect(img.getAttribute('src')).toBe('/build/figures/fig.svg');
		expect(env.props.get('--taxon-tone')).toBeTruthy();
		expect(mark.dataset.wiredMark).toBe('1');
		expect(mark.getAttribute('role')).toBe('button');
		expect(mark.classes.has('ann-' + (m.annotations['a-2026-09-16-ecnav2'].look.style ?? 'highlight'))).toBe(true);
		expect(mark.listeners).toContain('click');
		const link = label.children.find((c) => c.classes.has('heading-link'));
		expect(link?.getAttribute('href')).toBe('/node/sy-0003');
	});
});
