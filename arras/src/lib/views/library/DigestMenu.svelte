<script lang="ts">
	// The `digest…` menu (2 digest, 1 digest), on a work or over the whole list: items that finish the sentence, each with its count, and a quiet foot saying who does the work. Its counts are read when it opens. `results I choose…` starts choosing in the work's outline; the rest digest at once: loom writes the nodes now where it has the TeX source, and an agent is asked where it has only the PDF.
	import { said } from '$lib/library/said';
	import * as api from '$lib/library/api';
	import type { DigestScope, DigestScopes, Work } from '$lib/library/types';
	import { message } from '$lib/shell/message.svelte';
	import { library as words } from '$lib/words/library';
	import { lib } from './state.svelte';
	import { menus } from './menus.svelte';

	let { target, left = false }: { target: 'all' | Pick<Work, 'ref' | 'short' | 'holds'>; left?: boolean } = $props();

	let counts = $state<DigestScopes | null>(null);
	$effect(() => {
		const t = target;
		void api.digestScopes(t === 'all' ? { all: true } : { ref: t.ref }).then((r) => {
			if (r.ok) counts = r.value;
		});
	});

	const work = $derived(target === 'all' ? null : target);
	const nothing = $derived(!!work && !work.holds.pdf && !work.holds.tex);
	const foot = $derived(target === 'all' ? words.digest.byEither : work?.holds.tex ? words.digest.byLoom : words.digest.byAgent);

	async function run(scope: DigestScope): Promise<void> {
		menus.open = null;
		const refs = target === 'all' ? (scope === 'all' ? [...lib.multi] : 'all') : [target.ref];
		const done = await api.digest(refs, scope);
		if (!done.ok) return message.post(said(done.error));
		const { made, tasks, job } = done.value;
		message.post(job ? words.digest.reading : made ? words.digest.made(made) : words.digest.asked(tasks.length));
	}

	function choose(): void {
		if (!work) return;
		menus.open = null;
		lib.openWork(work.ref);
		lib.stopChoosing();
		lib.choosing = work.ref;
	}

	const count = (n: number | null | undefined) => (n === null || n === undefined ? '' : words.digest.count(n));
</script>

<div class="menu digest" class:left data-testid="digest-menu">
	{#if nothing}
		<div class="mh">{words.digest.noDocument}</div>
	{:else}
		<div class="mh head">{words.digest.head}</div>
		{#if target === 'all'}
			<button type="button" class="mi" onclick={() => void run('used')} data-testid="digest-used">{words.digest.usedEvery} <span class="grey">{count(counts?.used)}</span></button>
			<button type="button" class="mi" disabled={lib.multi.size === 0} onclick={() => void run('all')} data-testid="digest-selected">
				{words.digest.selected}
				{#if lib.multi.size}<span class="grey">{words.digest.selectedCount(lib.multi.size)}</span>{:else}<span class="s">{words.digest.selectHint}</span>{/if}
			</button>
		{:else}
			<button type="button" class="mi" disabled={counts?.used === 0} onclick={() => void run('used')} data-testid="digest-used">{words.digest.used} <span class="grey">{count(counts?.used)}</span></button>
			<button type="button" class="mi" disabled={counts?.marked === 0} onclick={() => void run('marked')} data-testid="digest-marked">{words.digest.marked} <span class="grey">{count(counts?.marked)}</span></button>
			{#if target.holds.tex}<button type="button" class="mi" onclick={choose} data-testid="digest-choose">{words.digest.choose}</button>{/if}
			<button type="button" class="mi" onclick={() => void run('all')} data-testid="digest-all-of">
				{words.digest.all(target.short)}
				<span class="grey">{counts?.all === undefined || counts?.all === null ? '' : target.holds.tex ? words.digest.count(counts.all) : words.digest.pages(counts.all)}</span>
			</button>
		{/if}
		<hr />
		<div class="mh foot">{foot}</div>
	{/if}
</div>

<style>
	.digest {
		right: 0;
		top: calc(100% + 4px);
		width: 300px;
		line-height: 1.45;
	}
	.digest.left {
		right: auto;
		left: 0;
	}
	.head {
		color: var(--ink);
	}
	.foot {
		padding-bottom: 4px;
	}
</style>
