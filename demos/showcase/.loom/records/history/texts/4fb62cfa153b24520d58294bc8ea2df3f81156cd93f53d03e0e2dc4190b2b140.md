---
name: loom-flow
description: "Work in loom's flow mode: reading order and clarity for a named reader, with the same mathematics (\"edit for clarity and flow\", \"write it so it is clear to me\")."
---

Work in loom's flow mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `flow` (in a shell, `loom ai mode flow`) and work as it says.

The mode is the quilt's own copy, `.loom/agents/instructions/modes/flow.md`; this skill only points at it, and loom writes it again from the mode.
