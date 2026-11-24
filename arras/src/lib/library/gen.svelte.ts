// The library's generation (`docs/specs/library-views.md` §2, "Freshness"): raised by the publisher whenever anything the views read changes, and told by the stream's `library` event, or by the fixture's writes. A view asks again for what it shows when it moves.

class LibraryGeneration {
	/** The latest generation heard; 0 before any. */
	gen = $state(0);

	/** Takes a generation heard from the stream or the fixture, keeping the highest. */
	heard(gen: number): void {
		if (gen > this.gen) this.gen = gen;
	}
}

export const library = new LibraryGeneration();
