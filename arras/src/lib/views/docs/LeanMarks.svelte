<script lang="ts">
	// The Lean marks in a draft's margin (8, 11a): once formalization is on for the quilt, beside each result of the draft its Lean mark, a click on one not formalized opening the formalize panel for it ("not formalized · formalize…"), on one waiting for the person saying so in the column. Laid over the draft's column at each result's height, and laid again when the draft is drawn or the marks change; the draft's view menu hides them.
	import { library as gen } from '$lib/library/gen.svelte';
	import Mark from '$lib/marks/Mark.svelte';
	import { message } from '$lib/shell/message.svelte';
	import { formalize } from '$lib/formalize/state.svelte';
	import { frame } from '$lib/words/frame';
	import { docs as words } from '$lib/words/docs';
	import { leanMarks } from './lean.svelte';

	let { doc, host, drawn }: { doc: string; host: HTMLElement | null; drawn: number } = $props();
	let layer = $state<HTMLElement | null>(null);
	let at = $state<{ key: string; name: string; mark: 'formalized' | 'not' | 'attest' | 'assumed'; top: number }[]>([]);

	$effect(() => {
		void gen.gen;
		void leanMarks.read(doc);
	});
	$effect(() => {
		const marks = leanMarks.byDoc.get(doc);
		void drawn;
		void leanMarks.shown;
		if (!host || !layer || !marks?.on || !leanMarks.shown) return void (at = []);
		const base = layer.getBoundingClientRect().top;
		at = [...host.querySelectorAll<HTMLElement>('div.env[data-key]')].flatMap((el) => {
			const key = el.dataset.key ?? '';
			const mark = marks.marks[key];
			if (!mark) return [];
			const name = [el.dataset.taxon, el.querySelector('.env-number, .num')?.textContent?.trim()].filter(Boolean).join(' ') || key;
			return [{ key, name, mark, top: el.getBoundingClientRect().top - base }];
		});
	});

	function press(m: (typeof at)[number]): void {
		if (m.mark === 'not') formalize.open([m.key]);
		else if (m.mark === 'attest') message.post(words.leanMarks.waits(m.name));
	}
</script>

<div class="layer" bind:this={layer}>
{#each at as m (m.key)}
	<button type="button" class="lm" style:top="{m.top}px" title={m.mark === 'not' ? words.leanMarks.not : frame.marks[m.mark]} aria-label={m.mark === 'not' ? words.leanMarks.not : frame.marks[m.mark]} data-testid="lean-mark" data-key={m.key} data-mark={m.mark} onclick={() => press(m)}><Mark kind={m.mark} size={14} hidden /></button>
{/each}
</div>

<style>
	.layer {
		position: relative;
		height: 0;
	}
	.lm {
		position: absolute;
		left: -40px;
		width: 28px;
		height: 28px;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		background: none;
		border: 0;
		border-radius: 6px;
		cursor: pointer;
	}
	.lm:hover {
		background: var(--ann-neutral-wash);
	}
</style>
