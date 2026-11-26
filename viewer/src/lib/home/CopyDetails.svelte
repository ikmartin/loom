<script lang="ts">
	// The small bordered button that copies a report for whoever helps the person (`report.ts`): loom and this machine, and with `quilt` that quilt's last lines of output; once copied it says so in its place.
	import { copyText } from '$lib/clipboard';
	import { call } from './api';
	import { reportOf, type Check } from './report';
	import { home as words } from '$lib/words/home';

	let { quilt = '', said = '' }: { quilt?: string; said?: string } = $props();

	let done = $state<'' | 'copied' | 'not'>('');

	async function copy(): Promise<void> {
		const r = await call<Check>('quilt-check', quilt ? { quilt } : {});
		done = (await copyText(reportOf(r.ok ? r.value : {}, said))) ? 'copied' : 'not';
	}
</script>

{#if done === 'copied'}
	<span class="copy done" data-testid="copy-details-done">{words.control.copied}</span>
{:else}
	<button type="button" class="btn copy" title={quilt ? words.control.copyTip : words.control.copyMachineTip} onclick={() => void copy()} data-testid="copy-details">{done === 'not' ? words.control.notCopied : words.control.copy}</button>
{/if}

<style>
	.copy {
		font-size: 11px;
		padding: 2px 9px;
		margin-top: 2px;
		border-radius: 7px;
	}
	.copy.done {
		display: inline-block;
		padding: 3px 0;
		color: var(--state-accepted);
	}
</style>
