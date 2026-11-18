---
name: loom-draft
description: "Work in loom's draft mode: new mathematics or text from the author's plan or request (\"implement each example in section 8\", \"restate Section 7 for $M(X,\\tau)$, marking what still needs proof\")."
---

Work in loom's draft mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `draft` (in a shell, `loom ai mode draft`) and work as it says.

The mode is the quilt's own copy, `.loom/agents/instructions/modes/draft.md`; this skill only points at it, and loom writes it again from the mode.
