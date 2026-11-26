<script lang="ts">
	// `see it in main.tex` (4 see it): the document laid over Review, read only, at the result, until its close button; nothing in it edits, and it never leaves Review: its references stay the in-page anchors the build gave them (`standalone`). Opened from a result changed since it was accepted, a strip under its head draws that change (`SinceAccepted`), a choice among its reasons where it has several.
	import Icon from '$lib/components/Icon.svelte';
	import Fragment from '$lib/fragments/Fragment.svelte';
	import { store } from '$lib/manifest/client.svelte';
	import { anchorId } from '$lib/nav';
	import SinceAccepted from '$lib/review/SinceAccepted.svelte';
	import { review as words } from '$lib/words/review';
	import { rv } from './state.svelte';

	let { over }: { over: { doc: string; key: string; name: string; since?: boolean } } = $props();
	const master = $derived(store.manifest?.masters.find((x) => x.path === over.doc));
	const since = $derived(!!over.since && !!store.manifest?.keys[over.key]?.acceptance?.causes?.length);
	let cause = $state(0);
	$effect(() => {
		void over.key;
		cause = 0;
	});

	// It lands at the block once the document is drawn, and again each time what is drawn changes its height (a draft drawn as its source settles after it mounts, mathematics after it is set), until the reader scrolls by their own hand.
	let box = $state<HTMLElement | null>(null);
	let moved = false;
	function land(): void {
		if (moved || !box) return;
		const at = box.querySelector<HTMLElement>(`[id="${CSS.escape(anchorId(over.key))}"]`);
		if (at) box.scrollTop += at.getBoundingClientRect().top - box.getBoundingClientRect().top;
	}
	$effect(() => {
		void over.key;
		void master;
		moved = false;
		const b = box;
		if (!b) return;
		const grows = new ResizeObserver(() => land());
		for (const c of b.children) grows.observe(c);
		const own = () => (moved = true);
		const keys = (e: KeyboardEvent) => ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(e.key) && own();
		b.addEventListener('wheel', own, { passive: true });
		b.addEventListener('pointerdown', own);
		b.addEventListener('touchstart', own, { passive: true });
		b.addEventListener('keydown', keys);
		return () => {
			grows.disconnect();
			b.removeEventListener('wheel', own);
			b.removeEventListener('pointerdown', own);
			b.removeEventListener('touchstart', own);
			b.removeEventListener('keydown', keys);
		};
	});
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (rv.over = null)} />

<section class="over" data-testid="review-over" aria-label={words.file(over.doc)}>
	<header>
		<b>{words.file(over.doc)}</b>
		<span class="quiet">{words.quiet([over.name ? words.seeIt.at(over.name) : '', words.seeIt.readOnly])}</span>
		<button type="button" class="ib" title={words.seeIt.close} aria-label={words.seeIt.close} onclick={() => (rv.over = null)}><Icon name="close" size={18} /></button>
	</header>
	{#if since}<div class="strip" data-testid="review-over-since"><SinceAccepted reviewKey={over.key} index={cause} master={over.doc} onchoose={(i) => (cause = i)} inReview /></div>{/if}
	<div class="doc" bind:this={box} data-testid="review-over-doc">
		{#if master}<div><Fragment path={master.fragment} master={master.path} macroSet={master.macros ?? ''} isolatedMacros={!!master.macros} standalone anchor={anchorId(over.key)} onmounted={() => land()} /></div>{/if}
	</div>
</section>

<style>
	.over {
		position: absolute;
		inset: 12px 16px 0;
		z-index: 20;
		display: flex;
		flex-direction: column;
		background: var(--sheet);
		border: 1px solid var(--rule);
		border-radius: 10px 10px 0 0;
		box-shadow: var(--float-shadow);
	}
	header {
		flex: none;
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 6px 8px 6px 16px;
		border-bottom: 1px solid var(--rule);
	}
	header b {
		font-weight: 500;
	}
	header .ib {
		margin-left: auto;
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-soft);
		cursor: pointer;
	}
	header .ib:hover {
		background: var(--ann-neutral-wash);
	}
	.strip {
		flex: none;
		max-height: 40%;
		overflow: auto;
		padding: 10px 40px 12px;
		border-bottom: 1px solid var(--rule);
		background: var(--review-paper);
	}
	.doc {
		flex: 1;
		min-height: 0;
		overflow: auto;
		padding: 18px 40px 60px;
	}
</style>
