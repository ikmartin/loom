<script lang="ts" module>
	/** A result's two marks: how its reading of the paper stands, and how its Lean stands (`docs/specs/library-views.md` §2, "Status"). */
	export type PaperMark = 'checked' | 'unchecked' | 'stub' | 'marked';
	export type LeanMark = 'formalized' | 'attest' | 'assumed' | 'not';
	export type MarkKind = PaperMark | LeanMark;
</script>

<script lang="ts">
	// One mark of the one vocabulary every surface uses: a circle for the reading of the paper, a diamond for Lean; filled for a person's yes, amber for what waits on a person, an outline for nothing yet. Its accessible name is the mark's words.
	import { frame } from '$lib/words/frame';

	let { kind, size = 12, hidden = false }: { kind: MarkKind; size?: number; /** Drawn beside its own words, as in the legend, so not read a second time. */ hidden?: boolean } = $props();
	const words = $derived(frame.marks[kind]);
</script>

<svg class="mark {kind}" width={size} height={size} viewBox="0 0 12 12" role={hidden ? undefined : 'img'} aria-label={hidden ? undefined : words} aria-hidden={hidden ? 'true' : undefined} data-mark={kind}>
	{#if !hidden}<title>{words}</title>{/if}
	{#if kind === 'checked'}
		<circle cx="6" cy="6" r="5.4" class="fill" />
		<path d="M3.3 6.1l1.8 1.9 3.6-3.8" class="tick" />
	{:else if kind === 'unchecked'}
		<circle cx="6" cy="6" r="4.6" class="ring" stroke-width="1.8" />
	{:else if kind === 'stub'}
		<circle cx="6" cy="6" r="4.7" class="ring" stroke-width="1.4" stroke-dasharray="2.2 1.7" />
	{:else if kind === 'marked'}
		<path d="M2.8 11.2V1.2" class="ring" stroke-width="1.4" stroke-linecap="round" />
		<path d="M3.2 1.5h6.6L8.2 4.1l1.6 2.6H3.2z" class="fill" />
	{:else if kind === 'formalized'}
		<path d="M6 .5 11.5 6 6 11.5.5 6z" class="fill" />
	{:else if kind === 'attest'}
		<path d="M6 1.2 10.8 6 6 10.8 1.2 6z" class="ring" stroke-width="1.7" />
		<circle cx="6" cy="6" r="1.4" class="fill" />
	{:else if kind === 'assumed'}
		<path d="M6 1.3 10.7 6 6 10.7 1.3 6z" class="ring" stroke-width="1.5" />
		<path d="M1.3 6h9.4L6 10.7z" class="fill" />
	{:else}
		<path d="M6 1.4 10.6 6 6 10.6 1.4 6z" class="ring" stroke-width="1" />
	{/if}
</svg>

<style>
	.mark {
		flex: none;
		vertical-align: -1px;
		color: var(--mark-none);
	}
	.checked,
	.formalized,
	.assumed {
		color: var(--mark-yes);
	}
	.unchecked,
	.attest {
		color: var(--mark-wait);
	}
	.marked {
		color: var(--mark-person);
	}
	.fill {
		fill: currentColor;
	}
	.ring {
		fill: none;
		stroke: currentColor;
	}
	.tick {
		fill: none;
		stroke: var(--sheet);
		stroke-width: 1.5;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
</style>
