// A kind's internal views (plan 0.13.3, plan 0.16 decision 10): several readings of one thing, drawn at the head of its pane's tab strip, before the tabs, rather than in a band the renderer draws for itself.

export interface View {
	id: string;
	label: string;
	/** Why the view cannot be read now, when it cannot: it is drawn greyed, with this as its title, rather than dropped, so the others keep their places. */
	off?: string;
}

/** The item's default view: its first that can be read. */
export function defaultView(views: View[]): string | undefined {
	return (views.find((v) => !v.off) ?? views[0])?.id;
}

/** The view shown: the one the item names when it is listed and can be read, else the default. */
export function currentView(views: View[], named: string | undefined): string | undefined {
	return views.some((v) => v.id === named && !v.off) ? named : defaultView(views);
}
