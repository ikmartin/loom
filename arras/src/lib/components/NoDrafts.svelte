<script lang="ts">
	// What a view that is about nodes shows when nothing is being worked on.
	// It points at Problems when the person's own LaTeX has any. The landmarks are still worth naming: a reader who arrives at an empty graph should be told where the mathematics is.
	import { store } from '$lib/manifest/client.svelte';
	import { forPerson, ownerOf } from '$lib/diagnostics';
	import { canonUrl } from '$lib/nav';
	import { route } from '$lib/paths';

	let { what = 'results' }: { what?: string } = $props();
	const m = $derived(store.manifest);
	const landmarks = $derived(m?.canon?.length ? [...m.canon].reverse() : []);
	// Two different emptinesses, and saying the wrong one is worse than saying nothing: a corpus that declares it has
	// no documents is not a corpus between drafts, and telling its reader that nothing is being worked on describes a
	// state it will never leave.
	const never = $derived(m?.publishes.documents === false);
	// the problems in the person's own LaTeX; an agent's copy's, a cited work's and loom's own say nothing about why none is open
	const problems = $derived(forPerson(m?.diagnostics ?? []).filter((d) => ownerOf(d) === 'person').length);
</script>

<div class="empty" data-testid="no-drafts">
	<p class="head">{never ? 'This corpus has no documents.' : 'Nothing is being worked on.'}</p>
	<p>
		{#if never}
			Its nodes stand on their own, so there are no {what}.
		{:else}
			No document is being worked on, so there are no {what}.
		{/if}
		{#if landmarks.length}
			The corpus's landmarks are still here: <a href={canonUrl(landmarks[0].path)}>{landmarks[0].title || landmarks[0].stem}</a
			>{#if landmarks.length > 1}, and {landmarks.length - 1} older{/if}.
		{/if}
		{#if problems && !never}
			<a href={route('/review/problems')}>Problems</a> says what is wrong in your LaTeX.
		{/if}
	</p>
</div>

<style>
	.empty {
		max-width: var(--measure);
		font-size: 12px;
		line-height: 1.7;
		color: var(--ink-soft);
		padding: var(--gap-wide);
		border: 1px solid var(--rule);
		border-radius: var(--rad-card);
		background: var(--sheet);
	}
	.head {
		font-family: var(--sans);
		font-weight: 600;
		color: var(--ink);
		margin: 0 0 var(--gap-tight);
	}
	p {
		margin: 0;
	}
</style>
