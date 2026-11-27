<script lang="ts">
	// A node, rendered small for a hover card (plan 0.13.3 H1–H3): its label, number and state, its id only where Settings › Show ids is on, and its statement typeset — proofs hidden, the text clamped by a fade rather than cut. A section says how many entries it holds and no more: its fragment is the whole section, too much to fetch and typeset for a glance.
	// A node item at one of its regions (`regionAt`), a labelled equation, is drawn as that display alone: its number and what it stands in, then the display cut from the node's fragment, a section's too, and typeset as the page sets it. Where the fragment holds no such display, the node's own card stands.
	import { tick } from 'svelte';
	import { displayNode } from '$lib/nodes/display';
	import { store } from '$lib/manifest/client.svelte';
	import { fetchFragment } from '$lib/fragments/fetch';
	import { wire } from '$lib/fragments/mount';
	import { typeset } from '$lib/math/mathjax';
	import { nodeBadge } from '$lib/badges';
	import Badge from '$lib/components/Badge.svelte';
	import { regionAt, type Item } from '../item';
	import { regionName } from '../names';
	import { prefs } from '$lib/prefs.svelte';
	import { docs } from '$lib/words/docs';

	let { item, onresize = () => {}, master = '', persistent = false }: { item: Item; onresize?: () => void; master?: string; persistent?: boolean } = $props();

	const m = $derived(store.manifest!);
	const node = $derived(m.nodes[item.id]);
	const identity = $derived(displayNode(m, item.id, master));
	const region = $derived(regionAt(m, item));
	const named = $derived(region ? regionName(m, region) : null);
	let html = $state('');
	/** Whether the node's fragment holds the region's display: null until it is fetched. */
	let found = $state<boolean | null>(null);
	/** The card is the region's display from the first frame, so the card is placed at its size, until the fragment is found to hold none. */
	const drawsDisplay = $derived(!!region && found !== false);
	let body: HTMLElement | undefined = $state();

	/** The display a region is, cut from its node's fragment: by its published id, else by its label; '' where the fragment has neither. */
	function displayIn(fragment: string, id: string, label: string): string {
		const t = document.createElement('template');
		t.innerHTML = fragment;
		const displays = [...t.content.querySelectorAll<HTMLElement>('div.math.display, figure.diagram')];
		const at = displays.find((d) => d.id === id) ?? displays.find((d) => d.dataset.label === label);
		return at?.outerHTML ?? '';
	}

	$effect(() => {
		const current = node;
		const manifest = m;
		const hash = store.hash;
		const key = region;
		const anchor = item.anchor ?? '';
		void master;
		html = '';
		found = null;
		let gone = false;
		void (async () => {
			if (!current || (!key && current.kind === 'section')) return;
			const text = await fetchFragment(current.fragment, hash).catch(() => null);
			if (gone) return;
			const display = key && text ? displayIn(text, anchor, manifest.regions[key].label) : '';
			found = !!display;
			if (!display && current.kind === 'section') {
				// the section's own card, which fetches nothing, now stands in the display's place
				await tick();
				if (!gone) onresize();
				return;
			}
			html = display || (text ?? '<p>Statement preview unavailable.</p>');
			await tick();
			if (!body || gone) return;
			wire(body, manifest, () => {});
			await typeset(body, manifest.macros.default ?? []);
			if (!gone) onresize();
		})();
		return () => {
			gone = true;
		};
	});
</script>

{#if node && region && named && drawsDisplay}
	<p class="head">
		<span class="label">{named.number}</span>
		<span class="title">{docs.preview.within(named.within)}</span>
		{#if prefs.ids}<span class="id">{region}</span>{/if}
	</p>
	<div class="body fragment display" bind:this={body} data-testid="preview-display">{@html html}</div>
{:else if node}
	<p class="head">
		<span class="label">{identity.name}</span>
		{#if identity.context}<span class="title">{identity.context}</span>{/if}
		{#if prefs.ids}<span class="id">{node.id}</span>{/if}
	</p>
	<p class="state"><Badge parts={nodeBadge(m, node)} /></p>
	{#if node.kind === 'section'}
		{#if node.children.length}<p class="more">{docs.preview.entries(node.children.length)}</p>{/if}
	{:else}
		<div class="body fragment" class:persistent bind:this={body}>{@html html}</div>
	{/if}
{/if}

<style>
	p {
		margin: 0;
	}
	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--gap-tight);
	}
	.label {
		font-weight: 500;
		color: var(--ink);
	}
	.title {
		font-family: var(--body-face);
		font-size: 13px;
		color: var(--ink);
	}
	.id {
		margin-left: auto;
		font-family: var(--mono);
		font-size: 9px;
		color: var(--link);
	}
	.state {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--gap-tight);
		margin: var(--gap-hair) 0;
	}
	.more {
		color: var(--ink-faint);
		font-size: 10px;
	}
	/* Clamped by height with a fade rather than by truncating the text, which could split a formula; the fade reads as continuing rather than ending. */
	.body {
		max-height: 12rem;
		overflow: hidden;
		-webkit-mask-image: linear-gradient(to bottom, #000 9rem, transparent);
		mask-image: linear-gradient(to bottom, #000 9rem, transparent);
		font-size: 12.5px;
		text-align: left;
	}
	.body.display {
		margin-top: var(--gap-hair);
	}
	.body.persistent { max-height: 28rem; overflow: auto; -webkit-mask-image: none; mask-image: none; }
	.body :global(p) { text-align: left; }
	.body :global(.env) {
		margin: 0;
	}
	/* the card's own header already names the result, and a proof is not what a glance is for */
	.body :global(details.env-proof),
	.body :global(.node-margin),
	.body :global(a.heading-link),
	.body :global(.env > .env-label) {
		display: none !important;
	}
	.body :global(.math.display) {
		background: none;
	}
</style>
