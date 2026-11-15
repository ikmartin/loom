# Writing a person's file

Loom writes a person's file only when the person asks it to (P7): keeping a suggested edit, discarding a change, restoring a version, putting back what a discard set aside, ticking a box, saving Settings. This page is the design of the one path all of those writes take, called the door: one lock shared by every loom process, a journal written before any file, the bytes of every file it replaces kept exactly, and recovery from a write that a crash cut short. It is written to be read on its own; what it builds on is named where it is used.

## Why there is one door

Each of those acts used to read the file, decide and write by itself. The v0.1 study (`docs/reports/v0.1-study/raw/safety.md`, `raw/spike-door.md`) measured what that did to a person's text on copies of real quilts:

- A save made by the person's editor while Keep ran was lost, because Keep wrote the file from the text it had scanned before.
- Two Keeps at once, from the viewer and an agent's shell, wrote one edit twice, or lost one edit while recording it kept.
- A crash between writing a file and recording the write left an edit in the file and still open, and the next Keep wrote it again.
- Keep and restore rewrote a file in the scan's reading, so Windows line endings became Unix ones; Discard in such a file spliced at offsets of one reading into the other and corrupted it.
- Restore overwrote a file that its document no longer reached without keeping it anywhere; Settings kept nothing of `config.toml` first and left it readable by its owner alone.
- Put-back wrote wherever the request's path pointed, outside the quilt included.

Each of these is the same fault: no lock across processes, no record before the write, and no exact copy of what was replaced. The door is the one place those three things are done (P4), so that every act gets them and none can forget one.

The door does not make loom read text better. Faults in which loom misjudges what someone else wrote (whether text the person typed is already the suggested edit, which block a key named by place means) are placement's, not the door's, and are handled where edits are placed (`records/edits.py`).

## What counts as a person's file

Any file in the quilt outside `.loom/` and outside the history directory (`[quilt] history`). Loom's own records (logs, looks, the ledger, the build) are written by their own modules under their own locks, and are not person's files. `config.toml` is a person's file: they edit it, and Settings writes it.

## The act

A write is an act: `with writes.act(quilt, kind, actor) as w:`. Inside the block the caller reads the files it will write, decides, and stages what it will write; when the block ends without an exception the door writes it. Everything below happens while the act holds the lock.

1. **Recovery.** Whatever a crash left unsettled is settled first (below), so every decision that follows sees a quilt in which each earlier act happened whole or not at all.
2. **Decisions again.** The caller decides again what to do, by record and by the bytes now: whether a suggested edit is still open, whether loom has already written it (the journal says), whether an in-place change still waits, what a box says, what the config holds. A list made before the lock, and the scan a request was answered from, are advisory: another act may have run since.
3. **Reading.** `w.read(rel)` is the file's bytes now, and the first read of a file is what the act replaces. `w.text(rel)` is those bytes as UTF-8 with their own line endings, and refuses a file that is not UTF-8 (`not-utf8`). An act that writes into a file's text (Keep, Discard, a tick, Settings) reads it as text; an act that writes stored bytes whole (restore, put-back) reads bytes and never decodes them.
4. **Plans that are not stale.** A tick, Settings and Discard plan from the bytes they have just read, so there is nothing stale to check. Keep plans from a scan, which costs too much to repeat on every act, so `w.expect(rel, planned)` checks that the file, read now as the scan reads it (UTF-8, with CRLF and CR read as LF), is the text the plan came from. The offsets a plan holds are offsets in that reading, so this equality is exactly what makes them valid in the bytes on disk; a hash of the raw bytes would refuse a change of line endings alone and protect nothing more. When the check fails, Keep scans once more under the lock and plans again; if the file moves again it refuses with `changed`.
5. **Versions.** A version The Record shows ("Before keeping a suggested edit", "Before restoring …") is stamped inside the act, from the scan just confirmed, so two acts never stamp over each other and the version holds the text the act replaces.
6. **Staging.** `w.replace(rel, data, splices)` stages the new bytes. Text goes in through `writes.splice`: each change is placed at offsets of the scan's reading, mapped onto the file's own text, and inserted text takes the file's own line ending, so every byte outside the change is kept. `w.log(log, line)` stages a record line that belongs to the act and is written with it. `w.then(fn)` stages a follow-up: work that needs the files as written (a rescan, the person's look, carrying annotations onto changed words).
7. **Commit.**
   - Every before and every after is stored in the history's `texts/`, named by the sha256 of its bytes (`<hex>.md` when the bytes are UTF-8, `<hex>.bin` otherwise; the names `records.snapshots.write_raw` gives).
   - A `begin` line naming the act, each file's before and after, its splices and its record lines is appended to the journal and flushed to the disk (`F_FULLFSYNC` where macOS offers it) **before any file is touched**.
   - Each file is written whole or not at all: a temporary file beside it, flushed; the file read once more and the act refused if it no longer holds the bytes read in step 3, which closes the window to the instant before the rename; the file's mode kept; a symlink's target written, so the link stays a link; `os.replace`; the directory flushed.
   - The act's record lines are appended, each under its own log's lock; then `done` is appended to the journal, and the index (below) brought up to it.
   - The follow-ups run, still under the lock.
8. **An act that changes no file** writes no journal line. Its record lines are still appended, since a Keep of an edit whose text stands already writes nothing and records it kept.

An exception raised inside the block writes nothing. An exception during the commit, after `begin` (the file changed at the last read, a full disk), puts the before bytes back into each file already replaced, removes the temporary files, appends `aborted` with the reason, and is raised to the caller, which answers the person with it.

## One lock

The lock is `<history>/writes.lock`, taken with `loom.locks.locked`: an operating-system lock on the file, exclusive across processes and across threads, reentrant within a thread, gone when its holder dies (so there is never anything to clear), and refused with a message after `locks.WAIT` (120 seconds) of waiting. The viewer's server, every `loom` command in a shell and the MCP server's subprocesses all name the same file, because it is in the quilt's history directory, which every one of them reads from the quilt's configuration.

Locks are taken in one order, outer to inner: the server's `publication_lock` (one process's threads), then `writes.lock`, then the ledger's lock, the record logs' locks and the id lock. Nothing takes `writes.lock` while it holds an inner lock, so no two holders can wait on each other.

## The journal

`<history>/writes.jsonl` is append-only. An act that writes files appends:

- `begin`: `act` (a unique id), `kind` (`keep`, `discard`, `restore`, `put-back`, `tick`, `settings`), `actor`, `when`, `files` (each path with the digests of its before and after bytes, null for a file that is absent before or after), `splices` (for each file, each change as `{edit, at, old, new}`: what replaced what, where, and for which suggested edit), `edits` (each suggested edit the act writes, as `<edit id>:<generation>`), and `records` (each record line it appends, with the log it goes to);
- then `done`, or `aborted` with why.

It lives in the history directory, beside the `texts/` store its digests point into, because that directory is already one loom alone writes and agents are denied; a new directory under `.loom/` would change every quilt's agent permission files.

`<history>/writes-index.json` is a cache of the journal, never a second record: the byte offset of the journal read so far, the acts begun and not yet settled, and `wrote`, which maps each `<edit>:<generation>` loom wrote to the offset of its act's `begin` line. A reader takes the index, reads only the journal past its offset, and folds what it finds. An index that is missing, unreadable or past the journal's end is rebuilt from the start. So an act costs the same with fifty thousand acts in the journal as with ten.

A reader outside the lock (the list of what waits on the person) judges an unsettled act as recovery will: what it wrote counts as written only when every one of its files holds its after bytes.

## Act ids, and why a repeat writes nothing

Every act gets a unique id. Ids made from an act's content would name a later act like an earlier one whenever a state recurs (tick, untick, tick again), and the third would be silently skipped.

What stops a write being made twice is a record read under the lock. The Keep of a suggested edit is named by `<edit id>:<generation>`, the generation being how many times the edit has been opened again; the journal's `wrote` holds every such name loom wrote, and no act writes one twice. An edit loom wrote whose `kept` line is missing (an act a crash left after its rename) is recorded kept, never written again. Every other act is either a state (a box, a setting, a version, a put-back: doing it twice leaves the same bytes) or is refused on repeat because its item, read under the lock, no longer waits (a discarded change).

A request id, which would let a viewer that lost an answer send the request again and get the first answer back, is not built. It belongs to the write that answers before the rebuild (below), and goes in `begin` when that is built.

## Recovery

Recovery runs at the start of every act, under the lock, and once when `loom serve` starts (not built yet: it is one line in `render/serve.py`). For each act begun and neither done nor aborted:

- its temporary files are removed;
- if every file holds the act's after bytes, the act had written everything: whichever of its record lines are not already in their logs are appended (a line is compared whole, so no record needs a new field for this), and `done` is appended;
- else, if every file holds either its before or its after bytes, the act was cut short between files or before the first: the before bytes are written back into each file that holds its after, and `aborted` is appended;
- else someone changed a file since the crash. Recovery leaves the act as it is; both texts are in the store, and `loom doctor` reports it (not built yet: the doctor item `writes`).

So an act happens at its last file's rename: before that it is undone, never half kept. Recovery settles loom's own unfinished act, and only where every file still holds exactly what that act read or wrote; where the person has been at a file since, it reports and changes nothing (P13).

## Bytes, line endings and encodings

The door keeps every byte it is not asked to change. A splice maps the scan's offsets onto the file's own text, so a file with Windows line endings keeps them, and the text put in takes the line ending most of the file's lines use.

A file that is not UTF-8 is never spliced: the scan reads such a file as Mac Roman, which accepts any byte and is wrong for the Latin-1 files people have, so loom has no reading in which to place an edit or encode an agent's Unicode. Writing would guess; refusing damages nothing. The list says so on the edit before the person presses Keep, and the door refuses at the write (`not-utf8`). Restore and put-back write stored bytes back whole, so a version of a Latin-1 file comes back exactly.

A version keeps each file's bytes as they were (`history.steps.stamp_document`), so restoring it gives the bytes back, not the scan's reading of them. The text store under versions, looks and the journal reads and writes bytes: a text stored with CRLF comes back with CRLF.

## Where an act may write

Every path an act names is relative to the quilt, normalised, never absolute and never through `..`; a file that does not exist yet must have its directory inside the quilt. Anything else is refused with `outside-quilt`, whatever named it: a request, a version's list of files, a record. A symlink the quilt already holds is the person's own arrangement, and is written through to its target.

## Undo gives back the exact bytes

Every act's before and after are in the store and named in the journal, with the splices that made the after. The one-step undo of a Keep (`change-undo`, not built yet) writes back what that Keep's splices replaced, or the whole before when the file still holds exactly the act's after; restore and put-back take their bytes from the same store.

## What the rebuild may rely on

Writes from the viewer are to answer before the rebuild that publishes them (not built yet: `docs/plans/0.32-v0.1.md`, decision 8). The rebuild then takes this same lock to scan, and may rely on the following.

- A process holding `writes.lock` sees no other process's act between its `begin` and its `done`: a scan taken under the lock sees each act whole or not at all.
- Recovery has run before any act holds the lock. An act still unsettled after it is one recovery could not settle, and is reported rather than hidden.
- An act never takes `publication_lock`, never rebuilds and never runs TeX. It holds the lock for its reads, its plan, its versions, its writes, its records and its follow-ups, which scan the quilt at most twice (three times when Keep plans again). A scan inside an act's thread may take `writes.lock` again, since it is reentrant.
- An act's answer is final when it releases the lock, so the write API may answer then.
- The rebuild takes `writes.lock` after `publication_lock` and before any inner lock, and holds it only to scan, never through TeX: a command in a shell waits at most `WAIT` for it.

## Refusals

| code | means |
|---|---|
| `changed` | the file moved while the act was being decided, twice; nothing was written |
| `not-utf8` | the file is not UTF-8, so loom does not write into it |
| `outside-quilt` | the path an act would write is outside the quilt |

The write API answers each with status 409 (`docs/specs/write-api.md`).

## Where it stands

The door is being built in the steps of `docs/reports/v0.1-study/raw/spike-door.md` (DOOR-18).

| writer | step | through the door |
|---|---|---|
| ticking a box (`tasks.tick`), saving Settings (`config_edit.set_values`) | 1 | yes |
| Discard of an in-place change, put-back, restore | 2 | yes |
| Keep of a suggested edit | 3 | not built yet |
| undo of a Keep in one step, and a restore or put-back that reopens what it takes out | 5 | not built yet |
| taking in an agent's copy, a pull, `loom mv`, atomize, import, `init --from`, the agent layer, pages, new files; then a test that nothing else writes a person's file | 6 | not built yet |

Step 4 is placement, not the door: an insertion judged taken only at its own place, an edit refused when the words beside its place changed since it was filed, and a key named by place carrying the line above its block.

**Open.** The follow-ups run under the lock, so Keep holds it through two scans. Moving them out (making what they compute part of the plan) would shorten the hold for the rebuild; it waits until the rebuild's lock is measured.
