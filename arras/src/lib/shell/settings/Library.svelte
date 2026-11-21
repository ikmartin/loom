<script lang="ts">
	// Whether the library may use the network; a draft until Save.
	import { draft } from './draft.svelte';
	import Row from './Row.svelte';
	import Toggle from './Toggle.svelte';

	let { editable }: { editable: boolean } = $props();
</script>

<div class="card">
	<Row id="library.online" refused={draft.refused['library.online']}>
		<Toggle label="Use the network" test="config-library.online" disabled={!editable} checked={draft.value('library.online') === true} set={(on) => draft.set('library.online', on)} />
	</Row>
</div>
