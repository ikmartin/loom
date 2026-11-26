# Mode: formalize

When it fits: stating a result of the quilt in Lean and proving it there, or stating again a Lean the person said gets something wrong (a `formalize` or `restate` task in `loom tasks`, or "formalize Lemma 4.2").

## What it is for

A Lean statement the person can attest says what they wrote, and a proof Lean accepts. Loom checks the Lean itself and records what Lean said; nothing you report about Lean counts, and you never write that record.

Work only in the quilt's Lean project, `lean/`, which exists once the person turned formalization on (`loom formal` says whether it is on here and whether there is a project; turning it on is theirs alone). Your modules go under `lean/Formal/`, each imported from `lean/Formal.lean` so `lake build` builds it, and each importing `Loom` for the marker. Never edit `lean/Loom.lean`, `lakefile.toml`, `lean-toolchain` or `lake-manifest.json`, and never fetch: Mathlib is pinned by the person's switch, and loom refuses to check a project that names anything else.

A `formalize` task names its `target` and its boundary: results to `state`, to `prove`, and to `assume`. Take it (`loom tasks take TASK`) and read the target's closure (`loom source KEY --closure`) before writing anything. For each result:

1. **State it first**, faithful to its text in the quilt and to every definition it uses, and search Mathlib for each notion before defining your own. Mark the declaration that states it with `@[loom "LABEL"]`, LABEL its label in the quilt or a library node's id; a result with no label cannot be named, so ask the person to add one (`loom ask`) rather than inventing it. A helper with no marker only supports.
2. **A result to assume** is an `axiom` with its marker: the proof rests on it and the person attests it like any statement.
3. **Prove it**, building as you go with `lake build` or `lake env lean FILE` in `lean/`. No `sorry`, and no axiom of your own beyond the assumed ones.
4. **Ask loom to check**: `loom formal check`, through loom's tool where your shell runs in a sandbox, in which loom cannot put up its own and refuses. It rebuilds the project from clean, replays it in Lean's kernel, and records each result a marker names; `loom evidence LABEL` says how it now stands. The task closes once that record shows Lean accepting the target, with no `loom tasks done`.

A `restate` task carries what the person says the Lean gets wrong (`differs`): state it again to say what they wrote, and check again. Never change a statement to make a proof go through: where the text and the Lean cannot agree, ask the person.

## Report

Core: [could-not-do]. Optional: [notation], [gaps-and-ambiguities].

For each result, its declaration's name and how its Lean reads it, in a sentence of mathematics, so the person reads what they will attest; and each definition of yours that stands in for one of the quilt's.
