---
name: loom-simplify
description: "Work in loom's simplify mode: shorter text with the same mathematics (\"simplify\", \"tighten this\")."
---

Work in loom's simplify mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `simplify` (in a shell, `loom ai mode simplify`) and work as it says.

The mode is the quilt's own copy, `.loom/agents/instructions/modes/simplify.md`; this skill only points at it, and loom writes it again from the mode.
