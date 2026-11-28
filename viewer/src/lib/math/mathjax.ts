// MathJax 3, TeX input and SVG output, bundled from the mathjax package so nothing loads from a CDN and a deployed site works offline. Macros come from the manifest: those it holds when MathJax loads are its configuration, and any the corpus gains or changes later (a paper brought into a quilt that had none) are defined before the next typeset; a fragment naming a per-fragment set gets those definitions applied before its math is typeset.
import type { Macro } from '$lib/manifest/types';

/** One formula in MathJax's list of what it has typeset; once typeset, `start.node` is its output's container. */
type MathItem = { start: { node: Node } };

type MJ = {
	typesetPromise: (els: Element[]) => Promise<void>;
	typesetClear: (els: Element[]) => void;
	startup: { promise: Promise<void>; document?: { math: Iterable<MathItem> & { remove: (...items: MathItem[]) => void } } };
	texReset?: () => void;
};

declare global {
	interface Window {
		MathJax: unknown;
	}
}

let loaded: Promise<MJ> | null = null;
/** The corpus-wide macros MathJax has, by name: its configuration, then each defined since. */
let currentMacros: Record<string, string | [string, number]> = {};
/** The list `currentMacros` was last brought up to, so a typeset with the same list costs one comparison. */
let lastMacros: Macro[] | null = null;

function toConfig(macros: Macro[]): Record<string, string | [string, number]> {
	const out: Record<string, string | [string, number]> = {};
	for (const m of macros) out[m.name] = m.args > 0 ? [m.body, m.args] : m.body;
	return out;
}

/**
 * Load MathJax once, with the corpus-wide macros as its configuration, and bring those up to `macros` on every later call.
 *
 * Parameters
 * ----------
 * macros : Macro[]
 *     The corpus-wide macros as the manifest now holds them.
 *
 * Returns
 * -------
 * Promise<MJ>
 *     MathJax, with every macro of `macros` that it lacked or held otherwise queued for definition ahead of whatever the caller typesets next.
 */
export function ensureMathJax(macros: Macro[]): Promise<MJ> {
	if (!loaded) {
		lastMacros = macros;
		currentMacros = toConfig(macros);
		window.MathJax = {
			tex: {
				inlineMath: [['\\(', '\\)']],
				displayMath: [['\\[', '\\]']],
				processEscapes: true,
				// `tags: 'none'` gives MathJax no labels, so a `\ref` outside mathematics could only ever read `???`; loom turns a fragment's own into links, and one in a message or a note reads as written
				processRefs: false,
				packages: { '[+]': ['ams', 'amscd', 'boldsymbol', 'mathtools', 'newcommand', 'color', 'cancel', 'bbox', 'html', 'unicode', 'verb', 'mhchem', 'physics', 'textmacros'] },
				macros: currentMacros,
				tags: 'none'
			},
			// One glyph cache for the page, not one per expression. A local cache puts a `<defs>` block inside every container whose paths sit thousands of pixels above it in the SVG's coordinate space, and a scroll container counts that as content: every display block then had a vertical scrollbar beside a formula that fitted.
			svg: { fontCache: 'global' },
			options: { skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] },
			startup: { typeset: false }
		};
		// the full component carries every TeX extension, so \color and friends never trigger a runtime load from a path that does not exist offline
		loaded = import('mathjax/es5/tex-svg-full.js').then(async () => {
			const mj = window.MathJax as MJ;
			await mj.startup.promise;
			return mj;
		});
	}
	return loaded.then((mj) => {
		bringUp(mj, macros);
		return mj;
	});
}

/** Defines each macro of `macros` that MathJax lacks or holds otherwise, a formula apiece, so one it cannot read leaves the rest defined.
 *
 * MathJax reads its configuration only at load: a page that loaded it before the quilt's paper came in showed the paper's macros as their names, in red. A macro the corpus dropped stays defined. */
function bringUp(mj: MJ, macros: Macro[]): void {
	if (macros === lastMacros) return;
	lastMacros = macros;
	const next = toConfig(macros);
	const changed = macros.filter((m) => JSON.stringify(currentMacros[m.name]) !== JSON.stringify(next[m.name]));
	currentMacros = { ...currentMacros, ...next };
	if (changed.length) define(mj, changed, true);
}

/** A fragment's macro set as one formula of definitions. `\renewcommand` alone: MathJax's never checks that a macro exists, and it has no `\providecommand`, whose argument it would read as math and fail on, showing the formula's source instead. */
function macroPrefix(macros: Macro[]): string {
	return macros.map((m) => (m.args > 0 ? `\\renewcommand{\\${m.name}}[${m.args}]{${m.body}}` : `\\renewcommand{\\${m.name}}{${m.body}}`)).join('');
}

/** Queue a fragment's macro set for definition: one formula of `\renewcommand`, or with `apart` one formula per macro, typeset in a holder off the page and removed.
 *
 * MathJax keeps a definition page-wide (WQ-51), so whatever is queued next sees it; call it in the same task as the fragment's own `run`. Not written into one of the fragment's own formulas, which need not open with `\(` or `\[` (an `align`, a formula already typeset), and outside a delimiter MathJax reads the definitions as prose. */
function define(mj: MJ, macros: Macro[], apart = false): void {
	const holder = document.createElement('span');
	holder.setAttribute('aria-hidden', 'true');
	holder.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden';
	holder.textContent = apart ? macros.map((m) => `\\(${macroPrefix([m])}\\)`).join(' ') : `\\(${macroPrefix(macros)}\\)`;
	document.body.append(holder);
	void run(mj, [holder])
		.catch(() => {})
		.finally(() => holder.remove());
}

/** Typesetting is serialised: MathJax is not safe to enter twice, and a document typesetting in the background shares it with titles and previews. */
let queue: Promise<unknown> = Promise.resolve();
function run(mj: MJ, els: Element[]): Promise<void> {
	const next = queue.then(() => {
		prune(mj);
		return mj.typesetPromise(els);
	});
	queue = next.catch(() => {});
	return next;
}

/** Forget the formulas whose output has left the page. MathJax lists every formula it has typeset and each entry holds its output, so a document replaced or a box closed would otherwise stay alive for good, and every later typeset would walk its entries. Run inside the queue, where nothing is being typeset. */
function prune(mj: MJ): void {
	const list = mj.startup.document?.math;
	if (!list) return;
	const gone: MathItem[] = [];
	for (const item of list) if (!item.start.node.isConnected) gone.push(item);
	for (let i = 0; i < gone.length; i += 1000) list.remove(...gone.slice(i, i + 1000));
}

/** Give the page a turn between batches, so input and painting are never held behind a whole document. */
function yieldToPage(): Promise<void> {
	const s = (globalThis as { scheduler?: { yield?: () => Promise<void> } }).scheduler;
	return s?.yield ? s.yield() : new Promise((r) => setTimeout(r, 0));
}

/** How many formulas one pass typesets before the page gets a turn.
 *
 * 160 was one long task of 90-100ms on a 1250-formula document, which is a visible stall; 48 costs a few more yields and keeps each pass around 30ms, under the 50ms a frame can absorb. The first screen of a document holds about 25 formulas, so a document still reveals in one pass. */
const BATCH = 48;

/** Bodies waiting for `typesetSoon`, in the order they asked. */
let soon: { el: Element; done: () => void }[] = [];
let soonQueued = false;

/** The task after the next paint. */
function afterPaint(): Promise<void> {
	return new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
}

/**
 * Typeset a short body (an annotation, a reply, a message, a quoted passage) after the next paint, together with every other body that asked before then.
 *
 * A list of comment cards typeset one card at a time made MathJax measure font metrics once per card, each measurement forcing a style recalc and layout of the whole page while a long document was open: opening the Comments panel on a 150-page paper held the click for half a second. Here the cards are drawn first and typeset in passes of about `BATCH` formulas, each in a task of its own; a body's formulas, or a quoted passage whole, stay hidden (`data-typesetting`, theme.css) until its pass has run.
 *
 * Parameters
 * ----------
 * el : Element
 *     The body; its formulas are `.math` spans, or `\(…\)` in its text.
 * defaults : Macro[]
 *     The corpus-wide macros, applied when MathJax first loads.
 *
 * Returns
 * -------
 * Promise<void>
 *     Resolves once `el` is typeset, or once its turn came and it had left the page.
 *
 * See Also
 * --------
 * typeset : a fragment, or anything that must be typeset before it is shown.
 */
export function typesetSoon(el: Element, defaults: Macro[]): Promise<void> {
	el.setAttribute('data-typesetting', '');
	return new Promise((done) => {
		soon.push({ el, done });
		if (soonQueued) return;
		soonQueued = true;
		void afterPaint().then(() => typesetWaiting(defaults));
	});
}

async function typesetWaiting(defaults: Macro[]): Promise<void> {
	try {
		const mj = await ensureMathJax(defaults);
		while (soon.length) {
			const pass: typeof soon = [];
			for (let n = 0; soon.length && n < BATCH; ) {
				const next = soon.shift()!;
				pass.push(next);
				n += Math.max(1, next.el.querySelectorAll('.math').length);
			}
			const els = pass.map((p) => p.el).filter((el) => el.isConnected);
			if (els.length) await run(mj, els).catch(() => {});
			for (const p of pass) {
				p.el.removeAttribute('data-typesetting');
				p.done();
			}
			if (soon.length) await yieldToPage();
		}
	} catch {
		// MathJax did not load: the bodies show their source rather than nothing
		for (const p of soon.splice(0)) {
			p.el.removeAttribute('data-typesetting');
			p.done();
		}
	} finally {
		soonQueued = false;
	}
}

/**
 * Typeset the mathematics inside `el`.
 *
 * A short fragment is typeset in one pass. A long one — a whole document, where two or three thousand formulas took over a second before anything showed — is typeset in batches, each of which gives the page a turn before the next: first everything up to `until` (the element a link points at) or the first screenful, and the returned promise resolves once that part is done, so the caller can reveal and scroll; then the rest. Everything above the reader is typeset before the promise resolves, so nothing above them changes height afterwards and the page never jumps under them.
 *
 * Parameters
 * ----------
 * el : Element
 *     The container.
 * defaults : Macro[]
 *     The corpus-wide macros, applied when MathJax first loads.
 * perFragment : Macro[], default []
 *     The fragment's own macro set (a landmark's), defined just before its formulas are typeset.
 * until : Element | null, default null
 *     Typeset at least through this element before resolving.
 *
 * Returns
 * -------
 * Promise<void>
 *     Resolves when the part the reader will see first is typeset; the remainder continues while the element stays in the document.
 */
export async function typeset(el: Element, defaults: Macro[], perFragment: Macro[] = [], until: Element | null = null): Promise<void> {
	const mj = await ensureMathJax(defaults);
	const items = [...el.querySelectorAll('.math')];
	// queued in this task, with the first pass below, so nothing typeset between the two sees another fragment's set
	if (perFragment.length && items.length) define(mj, perFragment);
	if (items.length <= BATCH) {
		await run(mj, [el]);
		return;
	}
	// the first part: through the linked element, or through what fits on the first screen
	let cut = 0;
	if (until) {
		cut = items.findIndex((m) => until.compareDocumentPosition(m) & Node.DOCUMENT_POSITION_FOLLOWING);
		if (cut < 0) cut = items.length;
	}
	const screen = window.innerHeight * 1.5;
	while (cut < items.length && items[cut].getBoundingClientRect().top < screen) cut++;
	cut = Math.min(items.length, Math.max(cut, BATCH));
	// MathJax resolves on microtasks alone, so batches that only awaited one another ran as one task: every batch yields
	for (let i = 0; i < cut; i += BATCH) {
		if (i) await yieldToPage();
		if (!el.isConnected) return;
		await run(mj, items.slice(i, Math.min(cut, i + BATCH)));
	}
	void (async () => {
		for (let i = cut; i < items.length; i += BATCH) {
			await yieldToPage();
			if (!el.isConnected) return;
			await run(mj, items.slice(i, i + BATCH));
		}
	})();
}
