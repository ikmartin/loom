<script lang="ts">
	// Over a draft in Docs whose last compile, after a change, made no PDF: that it has not compiled since; or whose last compile finished with errors but made a PDF: that it did. Each says why in the person's words where TeX's message is one the viewer knows (its own words otherwise), and where TeX stopped by its line alone, never a command to run nor the log's command. Said while nothing is compiling it again.
	import { compiles, stoppedAt } from '$lib/manifest/compiles.svelte';
	import { docs as words } from '$lib/words/docs';

	let { path }: { path: string } = $props();
	const c = $derived(compiles.all[path]);
	const result = $derived(c?.state === 'idle' ? c.last?.result : undefined);
	const line = $derived(stoppedAt(c));
	const file = $derived(path.split('/').pop() ?? path);
	const why = $derived(words.texError(c?.last?.error ?? ''));
</script>

{#if result === 'failed'}<p class="unbuilt" role="status" data-testid="doc-not-compiled">{words.notCompiled(file, why, line)}</p>
{:else if result === 'errors'}<p class="unbuilt" role="status" data-testid="doc-compiled-errors">{words.compiledWithErrors(file, why, line)}</p>{/if}

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
