// The formalize panel's one state: the results it is open for, from Docs' margin or the Web, and which of the person's results are to be assumed for now. Kept here so that the panel, drawn over the view by the frame, and the places that open it share it.

class Formalize {
	/** The results the panel is open for; none while it is closed. */
	targets = $state<string[] | null>(null);
	/** Results of the person's chosen to be assumed for now rather than proved. */
	assume = $state<string[]>([]);

	open(targets: string[]): void {
		this.targets = targets;
		this.assume = [];
	}

	close(): void {
		this.targets = null;
	}
}

export const formalize = new Formalize();
