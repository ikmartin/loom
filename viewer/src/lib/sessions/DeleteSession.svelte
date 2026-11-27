<script lang="ts">
	// The delete confirmation (plan 0.13.1, §18's mockup): what deleting a session does and does not touch. Erasing its transcript for good is an agent's, and is not offered here.
	import Popover from '$lib/components/Popover.svelte';
	import { review } from '$lib/words/review';

	const words = review.deleteSession;

	let { title, onCancel, onDelete }: { title: string; onCancel: () => void; onDelete: () => void } = $props();

	let box = $state<HTMLDivElement | null>(null);
	$effect(() => box?.querySelector<HTMLButtonElement>('[data-testid=delete-confirm]')?.focus());
</script>

<Popover modal open testid="delete-session" label={words.title(title)} onclose={onCancel}>
	<div class="modal" bind:this={box}>
		<h3 id="delete-title">{words.title(title)}</h3>
		<p>{words.ask}</p>
		<p data-testid="delete-says">{words.says}</p>
		<div class="buttons">
			<button type="button" data-testid="delete-cancel" onclick={onCancel}>{words.cancel}</button>
			<button type="button" class="destroy" data-testid="delete-confirm" onclick={onDelete}>{words.confirm}</button>
		</div>
	</div>
</Popover>

<style>
	.modal {
		padding: var(--gap-wide);
		width: min(460px, 100%);
		box-sizing: border-box;
	}
	h3 {
		margin: 0 0 var(--gap);
		font-family: var(--serif);
		font-size: 21px;
		font-weight: 400;
		text-wrap: balance;
	}
	p {
		margin: 0 0 var(--gap);
		font-size: 14px;
		line-height: 1.5;
		color: var(--ink-soft);
	}
	.buttons {
		display: flex;
		justify-content: flex-end;
		gap: var(--gap-tight);
		margin-top: var(--gap-wide);
	}
	button {
		font: inherit;
		font-size: 14px;
		padding: 7px 16px;
		border-radius: var(--rad-control);
		cursor: pointer;
		border: 1px solid var(--rule);
		background: var(--sheet);
		color: var(--ink);
	}
	button:hover {
		border-color: var(--rule-strong);
	}
	.destroy {
		background: var(--state-incomplete);
		border-color: var(--state-incomplete);
		color: #fff;
		font-weight: 500;
	}
</style>
