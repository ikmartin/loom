// Where a pane's tools that write stand while Annotate is on: in the toolbar's own row after Annotate, or, for the groups that do not fit there, in the menu its ˅ opens. ItemToolbar renders the kind's tools twice, once for the row and once for the menu, and each group is drawn in exactly one of the two.

/** Which of the two places a rendering of the tools is, and how many groups, counted from the last, stand in the menu. */
export type ToolsAt = { menu: boolean; folded: number };

/** The row's place with nothing folded, for a bar drawn outside a toolbar. */
export const ROW: ToolsAt = { menu: false, folded: 0 };

/** How far the toolbar folds: 1 drops the words of Ask your agent and New note, `WORDS` those of Annotate, Changes, Comments and Notes too, and each step after it moves one more group of tools into the menu. */
export const WORDS = 2;
export const MOST = WORDS + 3;

/** How many groups of tools a fold puts in the menu. */
export function foldedAt(fold: number): number {
	return Math.max(0, fold - WORDS);
}

/**
 * Whether group `i` of `n` is drawn in the place `at`.
 *
 * The last groups go to the menu first, so the tools nearest Annotate stay in the row longest. Called by AnnotateBar and PdfBar for each of their groups.
 */
export function drawnAt(at: ToolsAt, i: number, n: number): boolean {
	return (i >= n - at.folded) === at.menu;
}
