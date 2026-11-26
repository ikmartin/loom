<script lang="ts">
	// Review: the list of what waits for the person (`ReviewView`) wherever the source serves Review's reads; today's Your Changes where it does not yet.
	import ReviewView from '$lib/views/review/ReviewView.svelte';
	import YourChanges from '$lib/review/YourChanges.svelte';
	import { rv } from '$lib/views/review/state.svelte';

	rv.ask();
</script>

{#if rv.served}
	<ReviewView />
{:else if rv.served === false}
	<YourChanges />
{/if}
