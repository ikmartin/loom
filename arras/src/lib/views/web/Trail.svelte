<script lang="ts">
	// The trail of results followed to the one in focus; an earlier one goes back to it.
	import { web as words } from '$lib/words/web';
	import { wb } from './state.svelte';
</script>

{#if wb.trail.length}
	<nav class="trail" aria-label={words.focus.trail}>
		{#each wb.trail as t, i (t.result)}
			{#if i < wb.trail.length - 1}<button type="button" class="linkish" onclick={() => wb.back(i)}>{t.name}</button><span class="sep">›</span>{:else}<span class="cur">{t.name}{#if t.title}{' · ' + t.title}{/if}</span>{/if}
		{/each}
	</nav>
{/if}
