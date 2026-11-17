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

The door does not make loom read text better. Faults in which loom misjudges what someone else wrote (whether text the person typed is already the suggested edit, which block a key named by place means) are placement's, not the door's, and are handled where edits are placed (`records/edits.py`, "Where an edit goes" below).

## What counts as a person's file

Any file in the quilt outside `.loom/` and outside the history directory (`[quilt] history`). Loom's own records (logs, looks, the ledger, the build) are written by their own modules under their own locks, and are not person's files. `config.toml` is a person's file: they edit it, and Settings writes it.

## The act

A write is an act: `with writes.act(quilt, kind, actor) as w:`. Inside the block the caller reads the files it will write, decides, and stages what it will write; when the block ends without an exception the door writes it. Everything below happens while the act holds the lock.

1. **Recovery.** Whatever a crash left unsettled is settled first (below), so every decision that follows sees a quilt in which each earlier act happened whole or not at all.
2. **Decisions again.** The caller decides again what to do, by record and by the bytes now: whether a suggested edit is still open, whether loom has already written it (the journal says), whether an in-place change still waits, what a box says, what the config holds. A list made before the lock, and the scan a request was answered from, are advisory: another act may have run since.
3. **Reading.** `w.read(rel)` is the file's bytes now; the last read of a file before it is staged is what the act replaces. `w.text(rel)` is those bytes as UTF-8 with their own line endings, and refuses a file that is not UTF-8 (`not-utf8`). An act that writes into a file's text (Keep, Discard, a tick, Settings) reads it as text; an act that writes stored bytes whole (restore, put-back) reads bytes and never decodes them.
4. **Plans that are not stale.** A tick, Settings and Discard plan from the bytes they have just read, so there is nothing stale to check. Keep plans from a scan, which costs too much to repeat on every act, so `w.reads_as(rel, planned)` checks that the file, read now as the scan reads it (UTF-8, with CRLF and CR read as LF), is the text the plan came from (`w.expect` refuses outright when it is not). The offsets a plan holds are offsets in that reading, so this equality is exactly what makes them valid in the bytes on disk; a hash of the raw bytes would refuse a change of line endings alone and protect nothing more. When the check fails, Keep scans once more under the lock and plans again; if the file moves again it refuses with `changed`.
5. **Versions.** A version The Record shows ("Before keeping a suggested edit", "Before restoring …") is stamped inside the act, from the scan just confirmed, so two acts never stamp over each other and the version holds the text the act replaces. Stamping takes a moment in which the person's editor may save, so Keep checks its plan once more after the stamp, and splices into exactly the bytes that check read (`w.text(rel, again=False)`); a save after that is caught at the last read before the rename (step 7).
6. **Staging.** `w.replace(rel, data, splices)` stages the new bytes. Text goes in through `writes.splice`: each change is placed at offsets of the scan's reading, mapped onto the file's own text, and inserted text takes the file's own line ending, so every byte outside the change is kept. `w.log(log, line)` stages a record line that belongs to the act and is written with it; the log must be one of loom's own three (the edits', the annotations' and the ledger), or the act is refused with `outside-quilt`. `w.then(fn)` stages a follow-up: work that needs the files as written (a rescan, the person's look, carrying annotations onto changed words).
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

**The journal is this machine's.** It records loom's writes to the files on this machine, and its offsets, its unsettled acts and its lock mean nothing against another machine's files. So the journal, its index, its lock and any temporary file under the history directory are among the lines `.loom/.gitignore` keeps on one machine (`loom/src/loom/gitignore.py`), while the rest of the history, the `texts/` store among it, is committed as before. Were it committed, a co-author's pull would bring their unsettled acts to be settled against these files, offsets into a journal that differs here, and appends that conflict in git. What travels instead is the record: the `kept` line in the edits' log, written with the act, so on a second machine an edit kept on the first is no longer open and is never written again; and the before and after bytes in `texts/`, so a version restores anywhere. The one-step undo of a Keep reads the journal, so it is offered on the machine that wrote (not built yet). Where `[quilt] history` puts the history outside `.loom/`, `.loom/.gitignore` cannot reach the journal, and the person's own ignore must.

`<history>/writes-index.json` is a cache of the journal, never a second record: the byte offset of the journal read so far, the acts begun and not yet settled, and `wrote`, which maps each `<edit>:<generation>` loom wrote to the offset of its act's `begin` line. A reader takes the index, reads only the journal past its offset, and folds what it finds. An index that is missing, unreadable or past the journal's end is rebuilt from the start. So an act reads what was appended since the last one, not the whole journal: with 10,000 lines in it, an act took 112 ms once, while the index was built, and 11 to 12 ms after. The index itself grows with the edits loom has written, and 5,000 of them read in about a millisecond.

A reader outside the lock (the list of what waits on the person) judges an unsettled act as recovery will: what it wrote counts as written only when every one of its files holds its after bytes.

## Act ids, and why a repeat writes nothing

Every act gets a unique id. Ids made from an act's content would name a later act like an earlier one whenever a state recurs (tick, untick, tick again), and the third would be silently skipped.

What stops a write being made twice is a record read under the lock. The Keep of a suggested edit is named by `<edit id>:<generation>`, the generation being how many times the edit has been opened again; the journal's `wrote` holds every such name loom wrote, and no act writes one twice. An edit loom wrote whose `kept` line is missing (an act a crash left after its rename) is recorded kept, never written again. Every other act is either a state (a box, a setting, a version, a put-back: doing it twice leaves the same bytes) or is refused on repeat because its item, read under the lock, no longer waits (a discarded change).

A request id, which would let a viewer that lost an answer send the request again and get the first answer back, is not built. It belongs to the write that answers before the rebuild (below), and goes in `begin` when that is built.

## Recovery

Recovery runs at the start of every act, under the lock, and once when `loom serve` starts (not built yet: it is one line in `render/serve.py`).

**Nothing in a journal is taken on trust.** A quilt copied as a folder carries its journal, so one someone hands you can carry a journal written to do harm: a record line bound for a shell's startup file, or an act that looks cut short and names a file outside the quilt, which undoing would create from bytes the quilt's own store holds. Before recovery reads or writes anything for an act (`writes.untrusted`), every file it names must be a path in the quilt, in its normal form, that stays inside the quilt with every symlink followed; every digest must have a digest's shape; every record line must be one JSON object bound for one of loom's own three logs, which must themselves lie in `.loom/` or the history directory; and the act must name a file, since the door journals no act that writes none. An act that fails any of these is left as it is and reported, and nothing is done for it. A digest that does not have a digest's shape is never made into a path anywhere (`writes.fetch`, `records.snapshots.read_raw`), whoever sends it. A crash in an act that wrote through a symlink to a file outside the quilt is therefore left for the person, not settled.

For each act begun and neither done nor aborted, and trusted:

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

Every path an act names is relative to the quilt, normalised, never absolute and never through `..`; a file that does not exist yet must have its directory inside the quilt. Anything else is refused with `outside-quilt`, whatever named it: a request, a version's list of files, a record. A symlink the quilt already holds is written through to its target.

**Open.** Writing through a symlink is right for the person's own arrangement, a macro file they share between papers, and wrong for a link that arrived in someone else's repository and points out of the quilt: Keep would write through it, and a dangling one would let restore or put-back create its target outside the quilt. Refusing every link whose target is outside would refuse the first case. Recovery already refuses both (above); whether a live act should, or should ask, is not decided.

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

## Where an edit goes

The door makes sure loom never writes an edit twice by its own hand: the journal says what it wrote. It cannot say what someone else wrote. Text the person typed in, or an agent wrote in place, while an edit was open leaves no record, and the only evidence is the text. So where a suggested edit goes is decided by rules about the text at its place, in `records/edits.py`, which the door then writes.

**The words beside its place.** An insertion is written against the words beside its place when it was suggested: a quote's selector records up to 32 characters either side of the quote (`suffix` after it, `prefix` before it), and an insertion at the head or foot of a body records the body's first or last 32 characters (`edge`, written by `loom suggest`; `''` for a body that was empty), or, for a key with no text of its own (a file whose text all belongs to the blocks in it, which Keep writes at the file's end or start), the file's own. An insertion is placed only while those words still stand right beside its place, compared with whitespace normalised (`place`); a neighbour recorded as only whitespace says the block's own text ended there, and holds while nothing but whitespace lies between the quote and that end; otherwise it is unplaced, said in the person's words, and Keep writes nothing. Text the person wrote in at the place since, and then touched, cannot be told from the edit by any reading of the text, and refusing is what keeps it from being written beside again. An edit that recorded no `edge` is placed as before.

A replacement whose new text holds its quote adds words either side of the quote, and is judged as an insertion on each side it adds to.

**Taken is judged at the place.** Whether an edit's text is in already (`taken_how`) is asked at the very point Keep would write it, found as `place` finds it, never anywhere in its block. An insertion, and a replacement whose new text holds its quote, read as taken only when the new text stands right at the place, in the file's text so that text which opened a section or landed past an `\end{…}` is seen, and when the words recorded beside the place stand right beyond the new text or are gone from beside the place. A phrase that already stood where an edit goes reads with its neighbour where it always was, and is not the edit. A `\uses{…}` taken in at a body's head is read as the head, the body starting after it with the words it started with. A long text the person took in and worked inside (twenty words or more, nine in ten still in order) reads as taken, `edited`, as before. Any other replacement is taken when its text stands in the block and its quote no longer does, and a deletion when its quote is gone.

**A key named by place.** A key like `FILE#proof:3` names whichever block is third in its file, so an edit on one records the line above its block (`near`) beside the hash of the text it was suggested on (`against`), and goes only where those say (`records/store.py`, `filed_on`): to the one block of the file that still holds that text, or among several, the one under that line. Once the block's text has changed, an edit that quotes words goes to the block now at its place only while the line above it is the recorded one and no other block of the file holds the quoted words too (`place`); an edit on the body goes nowhere. It is never written into whatever block happens to hold the place.

`loom suggest` keeps two guards from before these rules, for what they still say:

| guard | what it refuses | why it stays |
|---|---|---|
| a quote that reaches the block's `\begin` or `\end`, or runs across a block inside it (`misplaced`) | the edit, at filing and at Keep | text beside a `\begin` or `\end` lands in the block around the one the edit names, and words in two pieces of the file cannot be replaced in one. It is no longer what stops a second write: an edit filed before the guard and written in by hand is read as taken where it stands |
| a block named by place that reads the same as another under the same line (`alike`) | the edit, at filing | nothing could tell the edit's block from the other afterwards (`filed_on`), so it would be unplaced from the moment it was filed |

A body is what lies inside an environment's head and before its `\end`, or below a section's heading and its labels (`body_span`), so a suggestion on a section's body never replaces its heading; a body replacement whose body runs across a block inside it, or holds a line that brings in another file (`\input`), is refused at filing and at Keep (`whole_body`), since those would go with it.

**Open.** Two insertions beside the same quote or body edge: once the first is kept, the second's recorded neighbour is gone and it is unplaced, rather than put in ahead of the first, out of the order they were suggested in; the agent suggests it again. A replacement of a whole body is still written over a body changed since it was suggested: Keep shows the words it replaces, and no second copy can come of it. Once its text has changed, a key named by place has only the line above its block and its quote to go by; the neighbours on both sides and the quote's count across the quilt are the context record of `docs/reports/v0.1-study/raw/check-labels.md` (KEY-13), not built yet. An edit whose new text is the very words already beside its place (a body's own last words suggested at its foot) can read either way, since written and not written look alike there; nothing is lost whichever it reads as.


## Where it stands

The door is being built in the steps of `docs/reports/v0.1-study/raw/spike-door.md` (DOOR-18).

| writer | step | through the door |
|---|---|---|
| ticking a box (`tasks.tick`), saving Settings (`config_edit.set_values`) | 1 | yes |
| Discard of an in-place change, put-back, restore | 2 | yes |
| Keep of a suggested edit | 3 | yes |
| undo of a Keep in one step, and a restore or put-back that reopens what it takes out | 5 | not built yet |
| taking in an agent's copy, a pull, `loom mv`, atomize, import, `init --from`, the agent layer, pages, new files; then a test that nothing else writes a person's file | 6 | not built yet |

Step 4 is placement, not the door ("Where an edit goes").

**Open.** The follow-ups run under the lock, so Keep holds it through two scans. Moving them out (making what they compute part of the plan) would shorten the hold for the rebuild; it waits until the rebuild's lock is measured.
