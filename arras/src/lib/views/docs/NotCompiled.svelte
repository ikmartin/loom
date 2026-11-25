<script lang="ts">
	// Over a draft in Docs whose last compile, after a change, made no PDF: that it has not compiled since, why in the person's words where TeX's message is one the viewer knows (its own words otherwise), and where TeX stopped by its line alone, never a command to run nor the log's command. Said while nothing is compiling it again.
	import { compiles, stoppedAt } from '$lib/manifest/compiles.svelte';
	import { docs as words } from '$lib/words/docs';

	let { path }: { path: string } = $props();
	const c = $derived(compiles.all[path]);
	const failed = $derived(c?.state === 'idle' && c.last?.result === 'failed');
	const line = $derived(stoppedAt(c));
</script>

{#if failed}<p class="unbuilt" role="status" data-testid="doc-not-compiled">{words.notCompiled(path.split('/').pop() ?? path, words.texError(c?.last?.error ?? ''), line)}</p>{/if}

<style>
	.unbuilt {
		margin: 0 0 var(--gap, 12px);
		padding: 8px 12px;
		border-left: 3px solid var(--state-incomplete, var(--rule));
		background: var(--leaf);
		color: var(--ink-soft);
		font-size: 13px;
	}
</style>
