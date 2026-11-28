// What was dropped on an empty quilt's page, read off the drop: its files with their paths, and whether it is PDFs to read or a paper. A folder is walked through the browser's entries (`webkitGetAsEntry`), since a dropped folder is no file of its own.

/** Whether an empty quilt's drop area (`PaperDrop.svelte`) is on the page: while it is, every file dropped on the window is its own, and the library's drop (`DropZone.svelte`) stands aside, since a paper dropped beside the area is the quilt's paper, never a work of its library. */
export const held = { byStart: false };

/** One file to send, by its path within what was dropped. */
export interface Dropped {
	file: File;
	path: string;
}

/** What a drop holds. */
export interface Drop {
	files: Dropped[];
	/** PDFs to read, or a paper (a `.tex`, a folder, an archive). */
	kind: 'pdf' | 'paper';
}

/** Folders and files of a machine's, never of the paper: walked past. */
const SKIPPED = new Set(['.git', '.DS_Store', '__MACOSX', '.loom', '.Trash']);

/** Whether a file is a PDF, by its type or its name. */
export function isPdf(f: { type: string; name?: string }): boolean {
	return f.type === 'application/pdf' || !!f.name?.toLowerCase().endsWith('.pdf');
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
	const pdf = files.every((f) => isPdf(f.file)) && !folders.length;
	return { files, kind: pdf ? 'pdf' : 'paper' };
}
