<script lang="ts">
	// Beside the focus card in the list form: what its statement uses, what its proof uses, and what uses it, each a list of results with how many stand outside the scope.
	import type { Row, WebFocus } from '$lib/library/types';
	import { web as words } from '$lib/words/web';
	import WebRow from './WebRow.svelte';

	let { focus }: { focus: WebFocus } = $props();
</script>

{#snippet list(rows: Row[], outside: number, more = 0)}
	{#each rows as r (r.result)}<WebRow row={r} />{/each}
	{#if outside}<p class="outscope">{words.focus.outside(outside)}</p>{/if}
	{#if more}<p class="outscope">{words.focus.moreUsers(more)}</p>{/if}
	{#if !rows.length && !outside}<p class="outscope">{words.focus.none}</p>{/if}
{/snippet}

<div class="nb3" data-testid="web-neighbourhood">
	<div>
		<h3 class="nbh">{words.focus.statementUses}</h3>
		{@render list(focus.uses.statement, focus.uses.outside.statement)}
		<h3 class="nbh">{words.focus.proofUses}</h3>
		{@render list(focus.uses.proof, focus.uses.outside.proof)}
	</div>
	<div>
		<h3 class="nbh">{words.focus.usedBy}</h3>
		{@render list(focus.used_by.rows, focus.used_by.outside, focus.used_by.more)}
	</div>
</div>
