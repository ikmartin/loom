<script lang="ts">
	// A work, by its reference, opened in a pane by a link to a note on it. Its pages are read in `Reading`, given the stored PDF's hash, which the library knows and the manifest does not; until the Library opens a work's pages, the pane says where they open.
	import { library } from '$lib/words/library';
	import type { Item } from '../item';

	let { item }: { item: Item } = $props();
</script>

<div class="page item work" data-work={item.id}>
	<p class="muted" data-testid="work-unread">{library.work.unread}</p>
</div>
