<script lang="ts">
	// The box over the page when a write is refused because loom knows no name to record it under (`no-reviewer`): what the name is for, Settings › Profile's own field, and Not now. Saving it sends every write that waited on it again (`write`); Not now, Escape or a press outside leaves them refused, each said in its own place.
	import { onMount } from 'svelte';
	import Popover from '$lib/components/Popover.svelte';
	import NameField from './settings/NameField.svelte';
	import { answer, mountAsk, naming } from './name.svelte';
	import { frame } from '$lib/words/frame';

	const words = frame.nameAsk;

	onMount(mountAsk);

	let error = $state('');
	$effect(() => {
		if (naming.open) error = '';
	});
</script>

<Popover modal bind:open={naming.open} label={words.title} testid="name-ask" onclose={() => answer(false)}>
	<div class="ask">
		<h3>{words.title}</h3>
		<p class="lead">{words.lead}</p>
		<NameField id="name-ask-field" bind:error onsaved={() => answer(true)} />
		{#if error}<p class="refused" role="alert">{error}</p>{/if}
		<div class="acts"><button type="button" class="btn quiet" data-testid="name-ask-later" onclick={() => answer(false)}>{words.later}</button></div>
	</div>
</Popover>

<style>
	.ask {
		box-sizing: border-box;
		width: min(440px, calc(100vw - 48px));
		padding: 16px 18px;
		display: grid;
		gap: 10px;
		font-size: 13px;
		color: var(--ink);
	}
	h3 {
		margin: 0;
		font-size: 15px;
		font-weight: 600;
	}
	.lead {
		margin: 0;
		color: var(--ink-soft);
		font-size: 12.5px;
	}
	.refused {
		margin: 0;
		color: var(--state-incomplete);
	}
	.acts {
		display: flex;
		justify-content: flex-end;
	}
</style>
