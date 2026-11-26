# Mode: formalize

When it fits: stating a result of the quilt in Lean and proving it there, or stating again a Lean the person said gets something wrong (a `formalize` or `restate` task in `loom tasks`, or "formalize Lemma 4.2"); or, asked only that, reading in ordinary mathematics a result's Lean that another agent wrote (`loom formal read`).

## What it is for

A Lean statement the person can attest says what they wrote, and a proof Lean accepts. Loom checks the Lean itself and records what Lean said; nothing you report about Lean counts, and you never write that record.

Work only in the quilt's Lean project, `lean/`, which exists once the person turned formalization on (`loom formal` says whether it is on here and whether there is a project; turning it on is theirs alone). Your modules go under `lean/Formal/`, each imported from `lean/Formal.lean` so `lake build` builds it, and each importing `Loom` for the marker. Never edit `lean/Loom.lean`, `lakefile.toml`, `lean-toolchain` or `lake-manifest.json`, and never fetch: Mathlib is pinned by the person's switch, and loom refuses to check a project that names anything else.

A `formalize` task names its `target` and its boundary: results to `state`, to `prove`, and to `assume`. Take it (`loom tasks take TASK`) and read the target's closure (`loom source KEY --closure`) before writing anything. For each result:

1. **State it first**, faithful to its text in the quilt and to every definition it uses, and search Mathlib for each notion before defining your own. Mark the declaration that states it with `@[loom "LABEL"]`, LABEL its label in the quilt or a library node's id; a result with no label cannot be named, so ask the person to add one (`loom ask`) rather than inventing it. A helper with no marker only supports.
2. **A result to assume** is an `axiom` with its marker: the proof rests on it and the person attests it like any statement.
3. **Prove it**, building as you go with `lake build` or `lake env lean FILE` in `lean/`. No `sorry`, and no axiom of your own beyond the assumed ones.
4. **Ask loom to check**: `loom formal check`, through loom's tool where your shell runs in a sandbox, in which loom cannot put up its own and refuses. It rebuilds the project from clean, replays it in Lean's kernel, and records each result a marker names; `loom evidence LABEL` says how it now stands. The task closes once that record shows Lean accepting the target, with no `loom tasks done`.
5. **Have a second agent read it.** The person attests from loom's print of your Lean, and beside it a reading in ordinary mathematics that you do not write, since yours would be your account of your own work. Where your app can start another agent, start one for each result Lean accepted and ask it only to read that result's Lean in this mode, giving it the result's label and nothing of what you wrote or think the Lean says. Where it cannot, say in your report that the reading waits for another session.

A `restate` task carries what the person says the Lean gets wrong (`differs`): state it again to say what they wrote, and check again. Never change a statement to make a proof go through: where the text and the Lean cannot agree, ask the person.

## Reading another agent's Lean

You were asked only to read a result's Lean, which another agent wrote. Do nothing else: write no Lean, edit nothing in `lean/`, and ask loom to check nothing.

`loom formal read RESULT` lists what to read: the latest record of loom's check stating the result, and each declaration the person reads there, as Lean printed it, the one stating the result first and then each its statement names. Read those prints, not the Lean files and not what the agent that wrote them said of them. Then read the statement as written (`loom source KEY`, or the node for a library result).

Split the statement into the parts it is written in, (i) and (ii), and each notion a declaration of the listing stands for. For each part give `--part` its name, `--draft` what the statement says there, copied from it as LaTeX, `--declaration` the declaration of the listing it reads, and `--reading` what that declaration says, in ordinary mathematics, as LaTeX. Say what the Lean says, never what the statement says: every hypothesis, quantifier and type the Lean has goes in, and nothing it lacks. Lean's print drops parentheses a mathematician needs: a big operator reaches as far right as it can, so `∑ a ∈ s, f a - c` is the sum of `f a - c`, and where the print means `(∑ a ∈ s, f a) - c` your reading says so. Where the Lean and the statement differ, say how with `--difference`; leave it out when you found nothing. The command refuses a declaration the listing does not have, and a record that is no longer the latest by the time you write (`--record`): read again then.

## Report

Core: [could-not-do]. Optional: [notation], [gaps-and-ambiguities].

For each result, its declaration's name and each definition of yours that stands in for one of the quilt's, and whether a second agent read it. A reading's report is the difference it recorded, or that it found none.
