// Whether the column's Files shelf is open. Kept here and not in the shelf, which is taken down whenever the column folds or shows Review or a page's own panel, so that it comes back as the reader left it; a reload opens it again.
export const filesShelf = $state({ open: true });
