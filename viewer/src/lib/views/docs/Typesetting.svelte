<script lang="ts">
	// In place of a document's text in Docs while TeX sets it for the first time (`typesettingFirst`): its source, and a formula drawn before its macros are known, are not shown meanwhile. The document hides its text while this stands.
	import { docs as words } from '$lib/words/docs';

	let { path }: { path: string } = $props();
	const file = $derived(path.split('/').pop() ?? path);
</script>

<div class="typesetting" role="status" data-testid="doc-typesetting">
	<svg class="spin" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="var(--rule)" stroke-width="1.6" /><path d="M8 1.5a6.5 6.5 0 0 1 6.5 6.5" fill="none" stroke="var(--ink)" stroke-width="1.6" stroke-linecap="round" /></svg>
	<span>{words.typesetting.text(file)}<span class="sub">{words.typesetting.sub}</span></span>
</div>

<style>
	.typesetting {
		display: flex;
		gap: 10px;
		align-items: flex-start;
		margin: var(--gap-wide, 24px) 0;
		color: var(--ink-soft);
		font-family: var(--sans);
		font-size: 14px;
	}
	.sub {
		display: block;
		margin-top: 2px;
		font-size: 12px;
		color: var(--ink-faint);
	}
	.spin {
		flex: none;
		margin-top: 2px;
		animation: spin 1.1s linear infinite;
		transform-origin: 50% 50%;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
