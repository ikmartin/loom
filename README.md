# loom

Loom is a place to do mathematics with an AI agent beside you: to read papers, learn a subject, write and proofread your own. Your files stay as they are, a LaTeX paper, Markdown notes, the PDFs you read. Loom shows them typeset, lets you and your agent comment on exact words, and holds every edit the agent proposes until you keep or discard it.

## Install

On a Mac, paste this line into Terminal:

```sh
curl -LsSf https://github.com/ikmartin/loom/releases/latest/download/install.sh | sh
```

It needs no password and nothing installed first. It installs loom with its own TeX (about 400 MB), puts Loom in your Applications folder, and opens it. That is the only thing you type: from then on everything happens in Loom's window. To update, paste the same line again.

## Quilts

A quilt is a folder for one piece of research: the papers you write or read, and your notes on them. Loom opens on Your quilts, where New quilt makes one; open it and drop your paper's folder or a PDF on it. A quilt has four views:

- **Docs**: your documents, typeset, with comments on their words.
- **Library**: the papers you rely on, to read, annotate and cite.
- **Web**: every result and what it rests on.
- **Review**: what waits for your decision, such as edits proposed to your text.

## Your agent

Connect Claude, or another agent, from the chip at the foot of a quilt's column. Its edits to your documents wait in Review, and a kept edit can be undone. An agent you connect works with your permissions on your Mac, so connect only one you trust.

## Alpha

Loom is alpha: a quilt may break between versions, so keep your work backed up. To report a problem, open an issue on this repository.

Working on loom itself: read `AGENTS.md`, then `docs/contributing.md`. Licences: `LICENSE` and `loom/NOTICE`.
