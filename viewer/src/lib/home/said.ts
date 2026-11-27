// The home's own words, worded for the person before the page shows them. A quilt's `said` is the last lines its `loom serve` wrote, which hold its address lines ("Ctrl-C to stop"), loom's refusal wrapped to a terminal's width with full paths, and, when it lost its port, advice to pass a port. Each is reduced here to what it says of the quilt, with no command and with paths written short.

/** What a refused quilt's server said, as the row shows it. */
export type Refusal = { port: true } | { newer: { found: number; reads: number } } | { text: string };

/** Write paths short: inside the quilt as written from its folder, the rest under the home folder with `~`. */
function short(text: string, folder = '', home = ''): string {
	let out = text;
	for (const [from, to] of [
		[folder.replace(/\/+$/, ''), ''],
		[home.replace(/\/+$/, ''), '~']
	] as const) {
		if (!from) continue;
		out = out.split(from + '/').join(to ? to + '/' : '');
		out = out.split(from).join(to || '.');
	}
	return out;
}

/**
 * What a quilt's server said when it would not start, from the last lines it wrote.
 *
 * Parameters
 * ----------
 * said : str
 *     `quilt-list`'s `said` for the quilt.
 * folder : str, default ''
 *     The quilt's folder, which paths inside it are written from.
 * home : str, default ''
 *     The person's home folder.
 *
 * Returns
 * -------
 * Refusal
 *     `port` when its address was taken as it started, `newer` when a newer loom made the quilt, else the refusal's text.
 */
export function refusalOf(said: string, folder = '', home = ''): Refusal {
	const lines = said.split('\n').filter((l) => l.trim() && !/^loom serve:/.test(l.trim()));
	// loom's refusal is the last `Error:` line and the lines it wrapped onto
	const at = lines.map((l) => l.startsWith('Error: ')).lastIndexOf(true);
	const text = (at >= 0 ? lines.slice(at).join(' ').slice('Error: '.length) : (lines[lines.length - 1] ?? '')).replace(/\s+/g, ' ').trim();
	if (/cannot listen on port \d+/.test(text)) return { port: true };
	const format = /says (\d+), and this loom reads format (\d+)/.exec(text);
	if (format && Number(format[1]) > Number(format[2])) return { newer: { found: Number(format[1]), reads: Number(format[2]) } };
	return { text: short(text.replace(/: loom upgrade brings it forward.*$/, ''), folder, home) };
}

/**
 * Why loom could not start a quilt's server, as the row shows it: the system's reason, its error number left out and its path written short.
 *
 * Parameters
 * ----------
 * said : str
 *     `quilt-list`'s `said` for the quilt.
 * home : str, default ''
 *     The person's home folder.
 *
 * Returns
 * -------
 * str
 */
export function cannotStartOf(said: string, home = ''): string {
	return short(said.replace(/^\[Errno \d+\]\s*/, ''), '', home);
}
