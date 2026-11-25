---
name: loom-referee
description: "Work in loom's referee mode: whether the mathematics is right, before anyone relies on it — new or changed mathematics, a computation to check (\"run it through referee\")."
---

Work in loom's referee mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `referee` (in a shell, `loom ai mode referee`) and work as it says.

The mode is the quilt's own copy, `.loom/agents/instructions/modes/referee.md`; this skill only points at it, and loom writes it again from the mode.
