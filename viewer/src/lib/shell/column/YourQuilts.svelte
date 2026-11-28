<script lang="ts">
	// Your quilts: a house at the left of the column's head, and atop the folded strip, that opens loom's home page in the home's own tab (`$lib/home/tab.ts`), at the address the quilt's server gave (`gone.svelte.ts`). Where no home runs, its hover text and a click, in the column's message, say how to open one. A page no loom serves, as a published viewer is, shows none.
	import Icon from '$lib/components/Icon.svelte';
	import { stopped } from '../gone.svelte';
	import { message } from '../message.svelte';
	import { HOME_TAB } from '$lib/home/tab';
	import { frame } from '$lib/words/frame';
</script>

{#if stopped.served}
	{#if stopped.home}
		<a class="yq" href={stopped.home} target={HOME_TAB} title={frame.column.yourQuilts} aria-label={frame.column.yourQuilts} data-testid="your-quilts"><Icon name="home" size={18} /></a>
	{:else}
		<button type="button" class="yq" title={frame.stopped.noHome} aria-label={frame.column.yourQuilts} data-testid="your-quilts" onclick={() => message.post(frame.stopped.noHome)}><Icon name="home" size={18} /></button>
	{/if}
{/if}

<style>
	/* a 28px target round its glyph, as the head's fold and Settings are */
	.yq {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex: none;
		width: 28px;
		height: 28px;
		padding: 0;
		border: 0;
		border-radius: 6px;
		background: none;
		color: var(--ink-faint);
		cursor: pointer;
	}
	.yq:hover {
		color: var(--ink);
		background: var(--ann-neutral-wash);
		text-decoration: none;
	}
</style>
