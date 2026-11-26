import { beforeEach, describe, expect, it } from 'vitest';
import { PdfView } from '$lib/pdf/view.svelte';
import { prefs } from '$lib/prefs.svelte';
import { itemFromPath, itemKey, pathFor, type Item } from './item';
import { documentState, fileState, workState } from './state.svelte';
import { workspace } from './store.svelte';

const m = { masters: [{ path: 'drafting/main.tex' }, { path: 'drafting/talk.tex' }] };

describe('each open document keeps its own size', () => {
	beforeEach(() => {
		workspace.reset();
		prefs.zoom = { pdf: 1.4 };
		prefs.textSize = 16;
	});

	it('carries the size given an item in its address, for a PDF, a draft, a work and a file', () => {
		for (const href of ['/pdf/drafting/main?size=1.8', '/master/drafting/main?size=19#sy-0200', '/library/Kre99?page=4&size=2.2', '/file/figures/fig.pdf?size=0.9']) {
			const item = itemFromPath(m, href)!;
			expect(item.size, href).toBeGreaterThan(0);
			expect(pathFor(m, item)).toBe(href);
		}
		expect(itemFromPath(m, '/pdf/drafting/main')!.size).toBeUndefined();
	});

	it("zooms one paper and no other, and the zoom given is where the next paper opened starts", () => {
		const a = new PdfView();
		const b = new PdfView();
		a.zoomTo(2);
		expect(a.zoom).toBe(2);
		expect(b.zoom).toBe(1.4);
		expect(new PdfView().zoom).toBe(2);
		// a zoom the open item kept is the paper's own, which fitting the text does not override
		const kept: number[] = [];
		const c = new PdfView(0.8, (z) => kept.push(z));
		expect(c.zoom).toBe(0.8);
		expect(c.fitText).toBe(false);
		c.zoomTo(0.9);
		expect(kept).toEqual([0.9]);
		expect(a.zoom).toBe(2);
	});

	it('keeps a PDF in each pane apart, and records the zoom given on its item, so the address carries it', () => {
		const left: Item = { kind: 'pdf', id: 'drafting/main.tex' };
		const right: Item = { kind: 'file', id: 'figures/fig.pdf' };
		workspace.openIn(left, 0);
		workspace.beside(right, 0);
		const [l, r] = [fileState(workspace.active(0)!).pdf, fileState(workspace.active(1)!).pdf];
		l.zoomTo(2.5);
		expect(r.zoom).toBe(1.4);
		expect(workspace.active(0)!.size).toBe(2.5);
		expect(workspace.canonical(m)).toBe('/pdf/drafting/main?size=2.5&beside=%2Ffile%2Ffigures%2Ffig.pdf');
		// revealed again at a place, it keeps the size it was given
		workspace.here({ kind: 'pdf', id: 'drafting/main.tex', anchor: 'page=2' });
		expect(workspace.paneOf(itemKey(left))).toBe(0);
		expect(workspace.active(0)!.size).toBe(2.5);
	});

	it("sizes one draft's text and no other, starts the next draft opened at it, and keeps a draft's size when Settings' changes", () => {
		const main: Item = { kind: 'document', id: 'drafting/main.tex' };
		workspace.openIn(main, 0);
		const a = documentState(workspace.active(0)!);
		expect(a.size).toBe(16);
		a.sizeTo(19);
		expect(workspace.active(0)!.size).toBe(19);
		expect(prefs.textSize).toBe(19);
		workspace.beside({ kind: 'document', id: 'drafting/talk.tex' }, 0);
		const b = documentState(workspace.active(1)!);
		expect(b.size).toBe(19);
		b.sizeTo(13);
		expect(a.size).toBe(19);
		// Settings' size is the start for a new draft: it moves no draft already open
		prefs.textSize = 22;
		expect(a.size).toBe(19);
		expect(b.size).toBe(13);
		// a draft opened from an address that carries its size opens at it
		workspace.reset();
		workspace.apply(m, '/master/drafting/main?size=17');
		expect(documentState(workspace.active(0)!).size).toBe(17);
		expect(workState({ kind: 'work', id: 'Kre99', size: 2 }).pdf.zoom).toBe(2);
	});
});
