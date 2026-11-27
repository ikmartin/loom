// What the address the home page opens a new quilt at says of how it was made: `?made=differs` when its working copy does not typeset as the paper did, which the quilt's first page then says (`PageNote.svelte`). Read once, as the page loads, before the workspace writes its own address in place of the one opened.

/** How the quilt was made, as the address opened said it; '' when it said nothing. */
function opened(): string {
	try {
		return typeof location === 'undefined' ? '' : (new URLSearchParams(location.search).get('made') ?? '');
	} catch {
		return '';
	}
}

class Made {
	/** Whether the quilt's working copy differs from the paper, until the note is put away. */
	differs = $state(opened() === 'differs');
}

export const made = new Made();
