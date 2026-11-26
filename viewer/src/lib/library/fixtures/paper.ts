// The fixture's stand-in for a work's stored PDF: a paper as long as the work says, each page saying its number, so a place on page 7 stands on a page 7.

const made = new Map<number, string>();

/** The bytes of a paper of `pages` pages, in Helvetica, each with a heading and a few lines a reader can select. */
export function paperBytes(pages: number): Uint8Array {
	const objs: string[] = ['', '<< /Type /Catalog /Pages 2 0 R >>', '', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
	for (let i = 1; i <= pages; i++) {
		const lines = [`BT /F1 24 Tf 72 720 Td (Page ${i}) Tj ET`];
		for (let l = 0; l < 30; l++) lines.push(`BT /F1 11 Tf 72 ${680 - l * 20} Td (Line ${l + 1} of page ${i}, standing in for the text of the paper.) Tj ET`);
		const text = lines.join('\n');
		objs.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${objs.length + 1} 0 R >>`);
		objs.push(`<< /Length ${text.length} >>\nstream\n${text}\nendstream`);
	}
	objs[2] = `<< /Type /Pages /Kids [${Array.from({ length: pages }, (_, i) => `${4 + 2 * i} 0 R`).join(' ')}] /Count ${pages} >>`;
	let out = '%PDF-1.4\n';
	const at: number[] = [];
	for (let n = 1; n < objs.length; n++) {
		at.push(out.length);
		out += `${n} 0 obj\n${objs[n]}\nendobj\n`;
	}
	const xref = out.length;
	out += `xref\n0 ${objs.length}\n0000000000 65535 f \n${at.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')}trailer\n<< /Size ${objs.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
	return new TextEncoder().encode(out);
}

/** An address the reader can open for a paper of `pages` pages; one per length, made once. */
export function paperUrl(pages: number): string {
	let url = made.get(pages);
	if (!url) {
		url = URL.createObjectURL(new Blob([paperBytes(pages) as BlobPart], { type: 'application/pdf' }));
		made.set(pages, url);
	}
	return url;
}
