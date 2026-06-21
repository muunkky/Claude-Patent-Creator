---
name: gitban-router
description: Parses code review reports and routes instructions to the executor and planner. Use after a reviewer completes a code review to decide next steps.
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "bash ./.gitban/hooks/validate-no-direct-gitban-state-edit.sh"
---

Read and follow the instructions at `.claude/skills/gitban-router/SKILL.md`.
