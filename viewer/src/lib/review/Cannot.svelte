<script lang="ts">
	// Why a block waiting to be accepted cannot be yet, in the person's words by loom's code (`refusal_code`), never loom's own sentence, which names a directive and keys; one marked incomplete is followed by the person's notes on it, typeset, each reference said as their documents print it.
	import TexProse from '$lib/math/TexProse.svelte';
	import type { UnresolvedReview } from '$lib/manifest/types';
	import { review as words } from '$lib/words/review';

	let { row, testid }: { row: Pick<UnresolvedReview, 'refusal_code' | 'incomplete'>; testid: string } = $props();
	const notes = $derived(row.refusal_code === 'incomplete' && row.incomplete?.length ? row.incomplete.map((t) => t.trim().replace(/\.$/, '')).join('; ') + '.' : '');
</script>

<p class="cannot" data-testid={testid}>{#if notes}{words.yours.cannotNoted} <TexProse text={notes} />{:else}{words.yours.cannot(row.refusal_code)}{/if}</p>

<style>
	.cannot {
		margin: 4px 0 var(--gap-tight, 6px);
		font-size: 12.5px;
		color: var(--ink-soft);
	}
</style>
