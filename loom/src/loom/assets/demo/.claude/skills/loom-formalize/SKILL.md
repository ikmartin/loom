---
name: loom-formalize
description: "Work in loom's formalize mode: stating a result of the quilt in Lean and proving it there, or stating again a Lean the person said gets something wrong (a `formalize` or `restate` task in `loom tasks`, or \"formalize Lemma 4.2\"); or, asked only that, reading in ordinary mathematics a result's Lean that another agent wrote (`loom formal read`)."
---

Work in loom's formalize mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `formalize` (in a shell, `loom ai mode formalize`) and work as it says.

The mode is the quilt's own copy, `.loom/agents/instructions/modes/formalize.md`; this skill only points at it, and loom writes it again from the mode.
