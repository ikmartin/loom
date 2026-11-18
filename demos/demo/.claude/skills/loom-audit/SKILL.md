---
name: loom-audit
description: "Work in loom's audit mode: what a result actually uses — which hypotheses are needed, whether a citation covers its use, whether a statement stands alone (\"what are the needed hypotheses on the target?\")."
---

Work in loom's audit mode on what the person named when they asked for it, or on what the conversation names; if it names nothing yet, ask them what to work on.

1. If you have not called `loom_ai_orient` in this conversation, call it first (in a shell, `loom ai orient`), and follow it.
2. Call `loom_ai_mode` with the name `audit` (in a shell, `loom ai mode audit`) and work as it says.

The mode is the quilt's own copy, `.loom/ai/modes/audit.md`; this skill only points at it, and loom writes it again from the mode.
