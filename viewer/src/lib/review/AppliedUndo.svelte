<script lang="ts">
	// The Undo beside Apply's answer on an agent's copy (`applied.ts`): puts the document back as it was before Apply, and hands what to say to `onanswer`, whose answer replaces Apply's and this with it.
	import { review as words } from '$lib/words/review';
	import { undoApplied, type Answer, type Applied } from './applied';

	let { undo, onanswer }: { undo: Applied; onanswer: (a: Answer) => void } = $props();
	let busy = $state(false);

	async function back(): Promise<void> {
		busy = true;
		const said = await undoApplied(undo);
		busy = false;
		onanswer(said);
	}
</script>

<button class="btn" disabled={busy} title={words.applied.hover(undo.document)} onclick={back} data-testid="applied-undo">{busy ? words.applied.undoing : words.applied.undo}</button>
