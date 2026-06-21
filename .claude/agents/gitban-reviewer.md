---
name: gitban-reviewer
description: Architectural code reviewer for gitban sprint cards. Evaluates for tech debt, coupling, ADR violations, and TDD/IaC/DaC compliance.
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "bash ./.gitban/hooks/validate-no-direct-gitban-state-edit.sh"
---

Read and follow the instructions at `.claude/skills/gitban-reviewer/SKILL.md`.
