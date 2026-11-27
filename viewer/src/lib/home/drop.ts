// What was dropped on the home page, read off the drop: its files with their paths, whether it is a PDF to read or a paper, the name it suggests for its quilt, and how the window names it. A folder is walked through the browser's entries (`webkitGetAsEntry`), since a dropped folder is no file of its own.

/** One file to send, by its path within what was dropped. */
export interface Dropped {
	file: File;
	path: string;
}

/** What a drop holds, for the window. */
export interface Drop {
	files: Dropped[];
	/** A PDF to read, or a paper (a `.tex`, a folder, an archive). */
	kind: 'pdf' | 'paper';
	/** The name a quilt from it is given at first. */
	name: string;
	/** How the window says what was dropped. */
	shown: { folder: boolean; name: string; count: number };
}

/** Folders and files of a machine's, never of the paper: walked past. */
const SKIPPED = new Set(['.git', '.DS_Store', '__MACOSX', '.loom', '.Trash']);

/** The endings an archive or a paper's file carries, longest first, taken off to name its quilt. */
const ENDINGS = ['.tar.gz', '.tar.bz2', '.tar.xz', '.tgz', '.tar', '.zip', '.gz', '.tex', '.pdf'];

/**
 * The name a dropped file or folder gives its quilt.
 *
 * Parameters
 * ----------
 * name : str
 *     The file's or folder's name.
 *
 * Returns
 * -------
 * str
 *     The name without its ending.
 */
export function quiltName(name: string): string {
	const low = name.toLowerCase();
	const end = ENDINGS.find((e) => low.endsWith(e) && low.length > e.length);
	return end ? name.slice(0, -end.length) : name;
}

/** Whether a file is a PDF, by its type or its name. */
export function isPdf(f: { type: string; name?: string }): boolean {
	return f.type === 'application/pdf' || !!f.name?.toLowerCase().endsWith('.pdf');
}

/** Whether what is being dragged is all PDFs, read from a drag's items, whose names a browser does not give until the drop. */
export function draggingPdf(items: DataTransferItemList | null | undefined): boolean {
	const all = Array.from(items ?? []).filter((i) => i.kind === 'file');
	return all.length > 0 && all.every((i) => i.type === 'application/pdf');
}

/** A folder entry's children, every batch of them. */
async function children(dir: FileSystemDirectoryEntry): Promise<FileSystemEntry[]> {
	const reader = dir.createReader();
	const out: FileSystemEntry[] = [];
	for (;;) {
		const batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
		if (!batch.length) return out;
		out.push(...batch);
	}
}

/** Every file under an entry, with its path below `prefix`. */
async function walk(entry: FileSystemEntry, prefix: string, out: Dropped[]): Promise<void> {
	if (SKIPPED.has(entry.name)) return;
	const path = prefix ? `${prefix}/${entry.name}` : entry.name;
	if (entry.isFile) {
		const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
		out.push({ file, path });
	} else if (entry.isDirectory) {
		for (const child of await children(entry as FileSystemDirectoryEntry)) await walk(child, path, out);
	}
}

/**
 * Read a drop.
 *
 * Parameters
 * ----------
 * data : DataTransfer
 *     The drop's data.
 *
 * Returns
 * -------
 * Drop or null
 *     Null when it held no file. One folder dropped alone gives its files' paths within it; several things dropped keep their own names.
 */
export async function readDrop(data: DataTransfer): Promise<Drop | null> {
	const entries = Array.from(data.items ?? [])
		.filter((i) => i.kind === 'file')
		.map((i) => i.webkitGetAsEntry?.())
		.filter((e): e is FileSystemEntry => !!e);
	const files: Dropped[] = [];
	const folders = entries.filter((e) => e.isDirectory);
	if (entries.length) {
		const alone = entries.length === 1 && folders.length === 1;
		if (alone) for (const child of await children(folders[0] as FileSystemDirectoryEntry)) await walk(child, '', files);
		else for (const e of entries) await walk(e, '', files);
	} else for (const file of Array.from(data.files ?? [])) files.push({ file, path: file.name });
	if (!files.length) return null;
	const first = entries[0]?.name ?? files[0].file.name;
	const one = entries.length ? entries.length === 1 : files.length === 1;
	const pdf = files.every((f) => isPdf(f.file)) && !folders.length;
	return {
		files,
		kind: pdf ? 'pdf' : 'paper',
		name: one ? quiltName(first) : '',
		shown: { folder: one && folders.length === 1, name: one ? first : '', count: files.length }
	};
}
