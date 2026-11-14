<script lang="ts">
	// The dialog that adds a work by hand, where the publisher writes the library. It stands at the column's own level and not in the Library's shelf, which is taken down whenever the column folds: a dialog open while the window narrows stays open. It is also what asks the publisher whether a work can be added, once, for the shelf's button and for itself.
	import AddWork from '$lib/components/AddWork.svelte';
	import { can } from '$lib/write';
	import { onMount } from 'svelte';
	import { libraryShelf } from './library.svelte';

	onMount(() => {
		void can('library-add').then((yes) => (libraryShelf.canAdd = yes));
	});
</script>

{#if libraryShelf.canAdd}<AddWork bind:open={libraryShelf.adding} />{/if}
