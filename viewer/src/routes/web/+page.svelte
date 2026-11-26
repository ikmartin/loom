<script lang="ts">
	// The Web view (`docs/specs/library-views.md` §5): every result and what it rests on, as a list or a graph, wherever the source serves the Web's reads; a line saying so where it does not yet.
	import WebView from '$lib/views/web/WebView.svelte';
	import { wb } from '$lib/views/web/state.svelte';
	import { web } from '$lib/words/web';

	wb.ask();
</script>

{#if wb.served}
	<WebView />
{:else if wb.served === false}
	<main class="page" data-testid="web-view"><p class="muted">{web.notServed}</p></main>
{/if}
