---
name: loom-review
description: "Work in loom's review mode: improving a text before someone else reads it — errors, citations, wording and clarity, every finding graded, drop-in text for each (\"provide annotations on the document text\")."
---

Work in loom's review mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `review` (in a shell, `loom ai mode review`) and work as it says.

The mode is the quilt's own copy, `.loom/agents/instructions/modes/review.md`; this skill only points at it, and loom writes it again from the mode.
