<script lang="ts">
	// The foot of the column, in both of its views and folded.
	let { folded = false }: { folded?: boolean } = $props();
</script>

{#if folded}<span hidden></span>{/if}
