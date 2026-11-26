<script lang="ts">
	// The actions at a selection, on documents and PDF pages alike: a button at the end of the words, which a click (never a hover) opens into **Quote**, **Annotate** and **New note**. Pressing it or an action never ends the selection (`AtSelection` swallows the press), so the words stay lit while the menu is open. Quote copies the words with a link to where they are and writes nothing; Annotate marks them in the look in hand, and is absent where they are marked already (Annotate's tool on) or annotating is not served; New note runs the person's command on the link (`notes/newNote.ts`). A view's own control goes before the button (`before`: Add comment, after Annotate marked the words) and its own actions after it (`more`, the Library's digest).
	import type { Snippet } from 'svelte';
	import Icon from '$lib/components/Icon.svelte';
	import { copyText } from '$lib/clipboard';
	import { newNote } from '$lib/notes/newNote';
	import { notes as words } from '$lib/words/notes';
	import { can } from '$lib/write';
	import AtSelection from './AtSelection.svelte';
	import { quoted } from './annotating.svelte';
	import { say } from './toasts.svelte';

	type Box = { left: number; top: number; width: number; height: number };

	let {
		at,
		range,
		text,
		name,
		link,
		annotate,
		ondone,
		before,
		more
	}: {
		at: Box;
		range?: Range;
		/** The words selected, as the clipboard takes them. */
		text: string;
		/** Where they are, as a reader names it: a quote's source and a new note's name. */
		name: string;
		/** A `quilt:` link to the place, carrying the words (`quoteLink`). */
		link: string;
		/** Mark the words; omitted where they are marked already or nothing is written. */
		annotate?: () => void;
		/** The actions have done their work and go. */
		ondone: () => void;
		/** A view's control before the button. */
		before?: Snippet;
		/** A view's own actions after the button. */
		more?: Snippet;
	} = $props();

	let open = $state(false);
	let notes = $state(false);
	$effect(() => {
		void can('new-note').then((ok) => (notes = ok));
	});

	// Escape closes the menu before anything else hears it: a tool in hand stays in hand
	$effect(() => {
		if (!open) return;
		const key = (e: KeyboardEvent) => {
			if (e.key !== 'Escape') return;
			e.preventDefault();
			e.stopPropagation();
			open = false;
		};
		document.addEventListener('keydown', key, true);
		return () => document.removeEventListener('keydown', key, true);
	});

	/** Whether the menu opens up and to the left of the button, where below and to the right would leave the window. */
	let host = $state<HTMLElement | null>(null);
	const flip = $derived.by(() => {
		void open;
		const r = host?.getBoundingClientRect();
		return { up: !!r && r.bottom + 132 > window.innerHeight, left: !!r && r.left + 188 > window.innerWidth };
	});

	// each action reads its props before `ondone`, which takes away what the host draws them from
	async function quote(): Promise<void> {
		const said = { text, name };
		const ok = await copyText(quoted(text, name, link));
		window.getSelection()?.removeAllRanges();
		open = false;
		ondone();
		say({ title: words.quoted.title, words: said.text, lines: [`— ${said.name}`, ok ? words.quoted.copied : words.quoted.refused] });
	}

	function mark(): void {
		open = false;
		annotate?.();
	}

	function note(): void {
		const req = { link, quote: text, title: name };
		open = false;
		ondone();
		void newNote(req);
	}
</script>

<AtSelection {at} {range}>
	{#if before}{@render before()}{/if}
	<span class="actions" bind:this={host}>
		<button type="button" class="chip opener" class:open aria-haspopup="menu" aria-expanded={open} aria-label={words.menu.label} title={words.menu.hover} data-testid="selection-actions" onclick={() => (open = !open)}
			><Icon name="more" size={16} /><Icon name="caret" size={11} /></button
		>
		{#if open}
			<span class="menu" class:up={flip.up} class:left={flip.left} role="menu" aria-label={words.menu.menu} data-testid="selection-menu">
				<button type="button" role="menuitem" title={words.menu.quoteHover} data-testid="quote-offer" onclick={() => void quote()}><Icon name="quote" size={15} />{words.menu.quote}</button>
				{#if annotate}<button type="button" role="menuitem" title={words.menu.annotateHover} data-testid="selection-annotate" onclick={mark}><Icon name="highlighter" size={15} />{words.menu.annotate}</button>{/if}
				{#if notes}<button type="button" role="menuitem" title={words.menu.newNoteHover} data-testid="selection-new-note" onclick={note}><Icon name="note" size={15} />{words.menu.newNote}</button>{/if}
			</span>
		{/if}
	</span>
	{#if more}{@render more()}{/if}
</AtSelection>

<style>
	.actions {
		position: relative;
		display: inline-flex;
	}
	.opener {
		gap: 2px;
		padding: 0 8px 0 9px;
	}
	.opener.open {
		background: var(--leaf);
	}
	.menu {
		position: absolute;
		top: calc(100% + 4px);
		left: 0;
		display: flex;
		flex-direction: column;
		min-width: 150px;
		padding: 4px;
		background: var(--sheet);
		border: 1px solid var(--rule-strong);
		border-radius: 10px;
		box-shadow: var(--float-shadow);
	}
	.menu.up {
		top: auto;
		bottom: calc(100% + 4px);
	}
	.menu.left {
		left: auto;
		right: 0;
	}
	.menu button {
		display: flex;
		align-items: center;
		gap: 8px;
		height: 30px;
		padding: 0 10px;
		font-family: var(--sans);
		font-size: 13px;
		color: var(--ink);
		text-align: left;
		white-space: nowrap;
		background: none;
		border: 0;
		border-radius: 7px;
		cursor: pointer;
	}
	.menu button:hover,
	.menu button:focus-visible {
		background: var(--leaf);
	}
</style>
