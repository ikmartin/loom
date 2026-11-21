<script lang="ts">
	// The list of works as thumbnails (1 thumbs): each work's first page, its title and its byline, sixty at first and more as the person scrolls; a work loom holds no document of is a blank page saying so. A thumbnail is the publisher's picture of the PDF's first page, asked for only as its card comes into view; where none can be asked for (the fixture), the card draws a plain page with the title on it.
	import { thumbUrl } from '$lib/library/api';
	import type { Work } from '$lib/library/types';
	import { library as words } from '$lib/words/library';
	import { lib } from './state.svelte';

	let { works }: { works: Work[] } = $props();

	const STEP = 60;
	let count = $state(STEP);
	let end = $state<HTMLElement | null>(null);
	$effect(() => {
		const el = end;
		if (!el) return;
		const seen = new IntersectionObserver((xs) => {
			if (xs.some((x) => x.isIntersecting)) count += STEP;
		});
		seen.observe(el);
		return () => seen.disconnect();
	});
	const page = $derived(works.slice(0, count));

	function opened(e: MouseEvent, w: Work): void {
		if (e.metaKey || e.ctrlKey || e.shiftKey) {
			if (lib.multi.has(w.ref)) lib.multi.delete(w.ref);
			else lib.multi.add(w.ref);
			return;
		}
		lib.openWork(w.ref);
	}
</script>

<div class="scroll">
	<div class="grid" data-testid="works-thumbnails">
		{#each page as w (w.ref)}
			{@const src = w.holds.pdf ? thumbUrl(w.holds.pdf) : null}
			<button type="button" class="th" class:multi={lib.multi.has(w.ref)} onclick={(e) => opened(e, w)} data-testid="work-thumb" data-ref={w.ref}>
				{#if !w.holds.pdf}
					<span class="pg none">{words.works.noDocument}</span>
				{:else if src}
					<img class="pg" {src} alt="" loading="lazy" draggable="false" />
				{:else}
					<span class="pg drawn"><span class="t1">{w.title}</span><span class="t1 by">{words.byline(w.authors)}</span>{#each { length: 9 } as _, i (i)}<span class="ln"></span>{/each}</span>
				{/if}
				<span class="cap"><span class="t">{w.title}</span>{words.byline(w.authors)} {w.year}</span>
			</button>
		{/each}
	</div>
	{#if works.length > count}<p class="small grey" bind:this={end}>{words.works.more(works.length - count)}</p>{/if}
</div>

<style>
	.scroll {
		flex: 1;
		overflow: auto;
		padding: 0 20px 20px;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
		gap: 20px 18px;
		padding: 16px 0;
	}
	.th {
		font: inherit;
		text-align: left;
		background: none;
		border: 0;
		padding: 0;
		cursor: pointer;
		color: inherit;
	}
	.pg {
		display: flex;
		width: 100%;
		height: 160px;
		object-fit: cover;
		object-position: top;
		background: #fff;
		border: 1px solid var(--rule);
		border-radius: 3px;
	}
	.drawn {
		flex-direction: column;
		align-items: center;
		gap: 5px;
		padding: 16px 12px;
		overflow: hidden;
		font-family: var(--serif);
		color: #2c2c2a;
	}
	.t1 {
		font-size: 10px;
		text-align: center;
		line-height: 1.25;
	}
	.t1.by {
		font-size: 8px;
		margin-bottom: 4px;
	}
	.ln {
		height: 3px;
		background: #e4e2dc;
		border-radius: 2px;
		width: 100%;
	}
	.none {
		align-items: center;
		justify-content: center;
		background: var(--leaf);
		border-style: dashed;
		color: var(--ink-faint);
		font-size: 11px;
	}
	.multi .pg {
		outline: 2px solid var(--link);
	}
	.cap {
		display: block;
		margin-top: 6px;
		line-height: 1.35;
		font-size: 11px;
		color: var(--ink-faint);
	}
	.cap .t {
		font-family: var(--serif);
		font-size: 13px;
		color: var(--ink);
		display: block;
	}
</style>
