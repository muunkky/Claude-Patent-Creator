---
name: gitban-executor
description: Senior developer that executes gitban card work. Use when a card needs implementation — writes code, tests, and documentation following TDD.
isolation: worktree
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "bash ./.gitban/hooks/validate-no-direct-gitban-state-edit.sh"
---

Read and follow the instructions at `.claude/skills/gitban-executor/SKILL.md`.
