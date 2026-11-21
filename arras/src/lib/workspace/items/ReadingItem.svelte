<script lang="ts">
	// A work of the library beside a draft (8): its stored PDF in the one reader, without the digest marks, at the page it was opened at. Its tab is the work's short name, learnt here from its read.
	import '$lib/views/library/library.css';
	import * as api from '$lib/library/api';
	import { library as gen } from '$lib/library/gen.svelte';
	import { Read } from '$lib/library/read.svelte';
	import type { WorkAnswer } from '$lib/library/types';
	import WorkReader from '$lib/views/library/WorkReader.svelte';
	import { lib } from '$lib/views/library/state.svelte';
	import { shortNames } from '$lib/views/docs/names.svelte';
	import type { Item } from '../item';

	let { item }: { item: Item } = $props();
	const work = new Read<WorkAnswer>();

	$effect(() => {
		const ref = item.id;
		void gen.gen;
		void work.load(ref, (s) => api.work(ref, s));
	});
	$effect(() => {
		if (work.value) shortNames.set(work.value.ref, work.value.short);
	});
	// the page it was opened at, each time it is opened again
	$effect(() => {
		const page = Number(/^page=(\d+)$/.exec(item.anchor ?? '')?.[1] ?? 0);
		const seq = item.seq ?? 0;
		if (page) lib.goto = { ...lib.goto, [item.id]: { page, seq } };
	});
</script>

<div class="lv reading" data-testid="reading-item">
	{#if work.value?.ref === item.id}<WorkReader work={work.value} beside />{/if}
</div>

<style>
	.reading {
		height: 100%;
	}
</style>
