<script lang="ts">
	// A library node's statement drawn in the browser (`docs/specs/library-views.md` §3.4): rendered, its text-mode LaTeX turned into HTML by `latexlite.ts` and its mathematics typeset by MathJax with its work's macros node (`macros.ts`), each pointer drawn as what it points at; or plain, the LaTeX as the node's file holds it, each pointer a chip naming its target with its mark and no id. A body holding what the converter does not know is not drawn by it: the publisher's TeX drawing stands in where there is one to ask for, and the plain text otherwise. A theorem-like statement is set in italic, as amsthm's plain style sets it.
	import Mark from '$lib/marks/Mark.svelte';
	import { paperMark } from '$lib/marks/marks';
	import type { Point } from '$lib/library/types';
	import { store } from '$lib/manifest/client.svelte';
	import { typeset } from '$lib/math/mathjax';
	import { LITE_CSS, toHtml } from './latexlite';
	import { macroDefinitions, parseMacros } from './macros';

	let {
		body,
		macros = null,
		points = {},
		plain = false,
		italic = false,
		drawn: tex = null
	}: {
		body: string;
		/** The body of the work's macros node, applied to this node alone. */
		macros?: string | null;
		points?: Record<string, Point>;
		plain?: boolean;
		/** Set in italic, as a theorem is. */
		italic?: boolean;
		/** The address of the node drawn by TeX, for a body the converter cannot draw; null where there is none to ask for. */
		drawn?: string | null;
	} = $props();

	let el = $state<HTMLElement | null>(null);
	const defs = $derived(macros ? parseMacros(macros).macros : []);
	const out = $derived(toHtml(body, points, { macros: defs, italic }));
	const trusted = $derived(out.unknown.length === 0);
	// a definition with a default for its optional argument is written whole, ahead of the statement's formulas, since MathJax's own macro table cannot hold the default
	const prefix = $derived(macroDefinitions(defs.filter((m) => m.default !== undefined)));
	$effect(() => {
		const node = el;
		void out;
		if (!node || plain || !trusted) return;
		void typeset(node, store.manifest?.macros?.default ?? [], defs);
	});

	/** The plain text cut at each pointer, so a pointer is drawn as a chip. */
	const POINTER = /\\(?:ref|eqref|autoref|pageref|vref|Vref|cref|Cref|cite[a-z]*)\*?(?:\[[^\]]*\])?\{([^}]*)\}/g;
	const pieces = $derived.by(() => {
		const parts: ({ text: string } | { id: string })[] = [];
		let at = 0;
		for (const m of body.matchAll(POINTER)) {
			parts.push({ text: body.slice(at, m.index) });
			for (const id of m[1].split(',')) parts.push({ id: id.trim() });
			at = m.index! + m[0].length;
		}
		parts.push({ text: body.slice(at) });
		return parts;
	});
	const chip = (t: Point | undefined) => (t ? (t.work ? `${t.name ?? ''} · ${t.work}` : (t.name ?? (t.number ? `(${t.number})` : ''))) : '');
</script>

<svelte:head>{@html `<style>${LITE_CSS}</style>`}</svelte:head>

{#if plain || (!trusted && !tex)}
	<div class="plain" data-testid="node-plain">{#each pieces as p, i (i)}{#if 'text' in p}{p.text}{:else}{@const t = points[p.id]}<span class="chip">{#if t?.paper}<Mark kind={paperMark(t.paper)} size={10} />{/if}{chip(t)}</span>{/if}{/each}</div>
{:else if !trusted && tex}
	<img class="tex" src={tex} alt="" data-testid="node-drawn" />
{:else}
	<div class="body" class:italic bind:this={el} data-testid="node-rendered">{#if prefix}<span class="math inline defs">{`\\(${prefix}\\)`}</span>{/if}{@html out.html}</div>
{/if}

<style>
	.body {
		font-family: var(--serif);
		font-size: 15px;
		line-height: 1.55;
		color: var(--ink);
		overflow-x: auto;
	}
	.body.italic {
		font-style: italic;
	}
	.defs {
		display: none;
	}
	.tex {
		max-width: 100%;
	}
	.plain {
		font-family: var(--mono);
		font-size: 12px;
		line-height: 1.6;
		white-space: pre-wrap;
		color: var(--ink);
		background: var(--leaf);
		border-radius: 6px;
		padding: 8px 10px;
	}
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		padding: 0 5px;
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--sheet);
		font-family: var(--sans);
		font-size: 11px;
	}
</style>
