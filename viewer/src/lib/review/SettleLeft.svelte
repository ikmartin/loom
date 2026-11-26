<script lang="ts">
	// "Settle as it stands" on the notice of a write loom could neither finish nor undo (`loom:write-left`): the button asks `write-settle-preview`, which writes nothing, and draws what settling would leave and record; only the person's confirmation calls `write-settle`. Every sentence is the viewer's (`settle.ts`); the act's id is sent and never shown. The caller offers it only where the publisher serves both endpoints.
	import { landed } from '$lib/manifest/updating.svelte';
	import { hovercard } from '$lib/shell/hovercards.svelte';
	import { review } from '$lib/words/review';
	import { write } from '$lib/write';
	import Said from './Said.svelte';
	import { PREVIEW, SETTLE, doneSays, drawPreview, refusedSays, type Drawn, type SettleAnswer } from './settle';

	let { act, onsettled }: { act: string; onsettled: (text: string) => void } = $props();
	const words = review.settle;

	let phase = $state<'idle' | 'reading' | 'shown' | 'settling'>('idle');
	let drawn = $state<Drawn | null>(null);
	let refused = $state('');
	let confirm = $state<HTMLButtonElement | null>(null);

	async function ask(): Promise<void> {
		phase = 'reading';
		refused = '';
		const answer = await write(PREVIEW, { act });
		if (!answer.ok) {
			[phase, refused] = ['idle', refusedSays(answer.error?.code)];
			return;
		}
		drawn = drawPreview(answer as unknown as SettleAnswer);
		phase = 'shown';
		queueMicrotask(() => confirm?.focus());
	}

	async function settle(): Promise<void> {
		phase = 'settling';
		const answer = await write(SETTLE, { act });
		if (!answer.ok) {
			[phase, drawn, refused] = ['idle', null, refusedSays(answer.error?.code)];
			return;
		}
		onsettled(doneSays(answer as unknown as SettleAnswer));
		[phase, drawn] = ['idle', null];
		await landed();
	}

	function cancel(): void {
		[phase, drawn] = ['idle', null];
	}
</script>

<div class="settle">
	{#if phase === 'idle' || phase === 'reading'}
		<button type="button" class="btn" disabled={phase === 'reading'} use:hovercard={{ text: words.buttonHover }} onclick={ask} data-testid="settle-open">{phase === 'reading' ? words.reading : words.button}</button>
	{/if}
	{#if refused}<Said text={refused} refused testid="settle-refused" />{/if}
	{#if drawn && (phase === 'shown' || phase === 'settling')}
		<div class="preview" role="group" aria-label={words.button} data-testid="settle-preview">
			<p class="lead" data-testid="settle-lead">{drawn.lead}</p>
			{#if drawn.files.length}
				<p>{drawn.filesHead}</p>
				<ul data-testid="settle-files">
					{#each drawn.files as f (f)}<li><code>{f}</code></li>{/each}
				</ul>
			{/if}
			{#if drawn.edits.length}
				<p>{drawn.editsHead}</p>
				<ul data-testid="settle-edits">
					{#each drawn.edits as e, i (i)}<li>{e}</li>{/each}
				</ul>
			{/if}
			{#if drawn.history}<p data-testid="settle-history">{drawn.history}</p>{/if}
			{#if drawn.nothing}<p data-testid="settle-nothing">{drawn.nothing}</p>{/if}
			<div class="buttons">
				<button type="button" class="btn primary" bind:this={confirm} disabled={phase === 'settling'} onclick={settle} data-testid="settle-confirm">{phase === 'settling' ? words.busy : words.confirm}</button>
				<button type="button" class="btn quiet" disabled={phase === 'settling'} onclick={cancel} data-testid="settle-cancel">{words.cancel}</button>
			</div>
		</div>
	{/if}
</div>

<style>
	.settle {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--gap-tight);
		margin: var(--gap-tight) 0;
	}
	.preview {
		max-width: var(--measure);
		padding: var(--gap-tight) var(--gap);
		border: 1px solid var(--rule);
		border-radius: 8px;
		background: var(--sheet);
		font-size: 13px;
		line-height: 1.55;
	}
	.preview p {
		margin: 0 0 4px;
	}
	.preview .lead {
		font-weight: 600;
	}
	.preview ul {
		margin: 0 0 var(--gap-tight);
		padding-left: 1.2em;
	}
	.preview code {
		font-family: var(--mono);
		font-size: 12px;
	}
	.buttons {
		display: flex;
		gap: var(--gap-tight);
		margin-top: var(--gap-tight);
	}
</style>
