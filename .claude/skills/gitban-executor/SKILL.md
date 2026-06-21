---
name: gitban-executor
description: Execute the work for one Gitban card. Achieve the completion requirements.
---

Execute the work for one Gitban card. Success = the card's completion requirements are met,
the work is committed, and any tests you wrote actually pass. Plan, code, test, document,
commit — granularity and order are your call.

## Workflow

1. Check `.gitban/agents/executor/inbox/` for files matching this card. Highest-N wins.
   Inbox files carry reviewer or dispatcher instructions — follow them before anything else.
2. `read_card` to load the card.
3. Do the work.
4. Append a close-out summary with `append_card`: what shipped, what deferred (with the
   new card id), what your tests actually proved (see Honest close-out).
5. Leave the card in `in_progress`. Don't call `complete_card` unless your inbox tells you
   to — the reviewer flips it. If you do call `complete_card` and it returns
   `error_code="AUTO_BLOCKED_INCOMPLETE_CHECKBOXES"`, the tool has moved the card to
   `blocked` with a `## BLOCKED` section listing the open items. Tick each (or defer
   with `- [x] ... deferred to <card-id>`), then `unblock_card` followed by
   `complete_card`. Checkbox enforcement is unconditional; the whole sprint is blocked
   until the card is completed.

## Principles

TDD, Infrastructure-as-Code, Documentation-as-Code, and "tests pass before merge" are
core tenets. The sprint architect bakes them into card requirements; your job is to
respect them, not shortcut them. If you find yourself tempted to defer a test, skip a
doc, or paper over a hook failure, that's a red flag — either complete the work or
create an explicit follow-up card and check the box honestly. Atomic commits with
conventional-commits messages. No AI attribution in commit messages.

## Gitban tools you'll use

Always go through MCP tools — never edit files in `.gitban/cards/` directly. The
`validate-no-direct-gitban-state-edit.sh` PreToolUse hook blocks it.

| Tool | When | Notes |
|---|---|---|
| `read_card(card_id)` | Loading the card | First call every session |
| `get_remaining_checkboxes(card_id)` | "What's left?" | Cheaper than re-reading the card |
| `toggle_checkboxes(card_id, checkboxes=[...])` | Marking items done | Pass MULTIPLE in one call. Don't edit the body to flip a box |
| `append_card(card_id, content)` | Close-out summary, progress notes | Preserves history |
| `edit_card(card_id, body)` | Restructuring the body | Sparingly — `append_card` and `toggle_checkboxes` are usually what you want |
| `block_card(card_id, reason)` | Hit a real blocker | Always create a troubleshooting spike with `create_card` first |
| `create_card(...)` | Deferred work, follow-ups, troubleshooting spikes | Note the new card id in the deferral on the original |
| `complete_card(card_id)` | Inbox tells you to close out | Otherwise leave in `in_progress` for the reviewer |

If a tool call seems to be doing the wrong thing, read its docstring before working
around it — most "weird" behaviour is documented behaviour.

Other state paths are also hard-protected: `.gitban/roadmap/`,
`.gitban/audit/`. Legitimate hand-edit escape:
`GITBAN_ALLOW_DIRECT_EDIT=1` (audited). Agent inboxes (`.gitban/agents/*/inbox/`)
are intentionally unprotected — they are the prescribed agent-to-agent comm
channel and have no MCP write tool.

## Commit code often; card state is already durable

A worktree crash loses any uncommitted **code**. Commit your code to the worktree branch
after each meaningful step — pinned to `$WT` (see the recipe table below), skipping
pre-commits for speed (`git -C "$WT" commit --no-verify`); the closeout and PR agents run
hooks before merge.

Card-state mutations are different: every MCP call (`toggle_checkboxes`, `append_card`,
status transitions) writes straight to the parent store and is durable the moment the tool
returns — you do **not** commit those, and you must not commit the worktree's stale
`.gitban/` copy (see the git-operations section). The dispatcher reconciles parent
card-state after merge.

Don't tick a box for work that isn't durably committed on the worktree branch yet.

## Branches

You'll be on one of:

- `sprint/<tag>` or `feature/<card-id>` — work directly.
- `worktree-agent-…` — isolated worktree spawned by the dispatcher. Don't switch
  branches; commits get merged back at review. The parent branch the dispatcher
  merges back into depends on dispatch mode (same signal as Completion tag — pick by
  inbox-name shape):

  | Inbox shape | Mode | Parent branch |
  | :--- | :--- | :--- |
  | `{SPRINTTAG}-{cardid}-executor-{N}.md` | sprint | `sprint/{SPRINTTAG}` |
  | `card-{cardid}-executor-{N}.md` | single-card | `feature/{cardid}` |

  The dispatcher SKILL's Token-reference table is the canonical source for the parent
  branch shape; this section just cites it so you don't try to merge back to a
  non-existent `sprint/…` ref in single-card mode.
- `main` — start a `sprint/<tag>` or `feature/<id>` branch first.

Anything else: stop and escalate.

**Worktree isolation applies in both modes.** The dispatcher invokes the executor with
`isolation="worktree"` regardless of mode (sprint or single-card), so if you find
yourself on a `worktree-agent-…` branch, that's the contract — write your commits on
that branch and let the dispatcher merge them back. Do not "shortcut" by committing
directly to the parent branch with `git -C "$PARENT" commit`, even in single-card mode
where there are no parallel siblings to collide with. The merge-back step is the
per-card audit boundary; bypassing it removes the boundary and tangles future
single-card dispatches that may run concurrently. If the worktree-vs-parent edit
target is unclear (e.g. you re-rendered a scaffold file and the parent's copy looks
stale), edit the file on the worktree's filesystem and let the merge propagate the
change — the dispatcher's merge-back is the canonical promotion path.

In a worktree the parent repo's shared toolchain (e.g. `.venv`) is read-only and shared
across parallel agents — never run `pip install`, `pip uninstall`, or any other installer
against it. If a hook fails because of a missing module, report it on the card and
continue with what you can.

## Git operations need a pin — two contexts, two recipes

In a worktree your CWD may not be the parent repo. Every write-class git invocation must
carry an explicit `-C <dir>` pin, or the `cwd-pin-check.sh` PreToolUse hook will reject it.
**There are two correct pins; pick by what you are touching.** Resolve both up front:

```bash
WT="$(git rev-parse --show-toplevel)"                                   # the worktree you are in
PARENT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"  # the parent repo
```

| You are… | Recipe | Why |
|---|---|---|
| committing **code** you changed in the worktree | `git -C "$WT" add <explicit code paths>`<br>`git -C "$WT" commit -m …` | The files live in the worktree and your branch must advance there. `$PARENT` cannot stage them — the worktrees dir is gitignored in the parent, so `git -C "$PARENT" add` of a worktree file stages nothing. |
| writing the **done tag** | `git -C "$PARENT" tag <name> "$(git -C "$WT" rev-parse HEAD)"` | The tag ref lands in the parent namespace; the SHA is read from the worktree. The bare tag form defaults to the parent's HEAD — the wrong commit. |
| reading (`status`, `log`, `diff`, `rev-parse`, `fetch`, `config`) | any CWD; pin optional | wrong-data is loud, not silent |

`$WT` is the worktree toplevel — exactly right for the executor, which operates on the
worktree it is in. `$PARENT` is the dispatcher's resolver (CWD-drift-resistant); don't use
it for staging worktree code, and don't substitute `--show-toplevel` into `$PARENT`.

**Commit code only. Never stage `.gitban/` from a worktree** — do not add the `.gitban/`
path, and never stage everything with an `-A`/`--all` sweep (it would pull `.gitban/` in).
Card state is managed by the MCP server in the **parent** store, not the worktree's own
git-tracked copy, which is a stale fork snapshot. Stage explicit code paths only; the
dispatcher reconciles parent card-state after merge. Committing the worktree's stale card
copy is a known data bug — on merge-back it can clobber or duplicate the canonical card.

Per-call escape (audited): `GITBAN_ALLOW_CWD_PIN_BYPASS=1`.

### Worktree branch-base check

A worktree on the wrong base produces unmergeable commits. The `WorktreeCreate` hook
should fork from the dispatcher's `HEAD`, but verify anyway:

```bash
git merge-base --is-ancestor sprint/<tag> HEAD && echo "base ok" || echo "WRONG BASE"
```

If `WRONG BASE`, stop work, write an `-ERROR.md` to your outbox, and return —
something upstream is broken (see [anthropics/claude-code#27876](https://github.com/anthropics/claude-code/issues/27876)).

## Project conventions

Every adopter's project has different conventions — read the consuming project's
`CLAUDE.md`, `README`, `Makefile`, `package.json`, or `pyproject.toml` to learn its
testing tools, quality gates, and rules. Run the project's own test/build/lint targets
in the worktree; don't defer to CI. For test-type cards (acceptance criteria = tests
pass) you MUST actually run them — "deferred to CI" is not a valid completion.

**Default to targeted tests** (e.g. `bash scripts/venv-python -m pytest tests/test_specific_file.py`)
against files you changed. Running the full suite per card across many parallel executors
burns time the dispatcher's post-merge validation pass already covers — only run a
broader scope when the change is repo-wide.

### Project Conventions

**Testing tools:**
- Use `pytest` as the test runner for all Python tests.
- Use Playwright for browser-facing end-to-end tests. Install via `pip install playwright` and `playwright install chromium`.
- Use `bash scripts/venv-python` to invoke Python in all environments (main repo and worktrees).

**Quality gates:**
- All browser-facing changes require at least one Playwright e2e test covering the critical user path.
- All code changes must pass pre-commit hooks: ruff format, ruff lint, mypy, mcp-sync-check, mixed-line-ending.
- Test-driven development is mandatory: write the failing test before the implementation.

**Project-specific rules:**
- Template-structure enforcement is unconditional. Any `.gitban/template_config.json` in your workspace is ignored (its contents no longer affect enforcement) and can be safely deleted.
- Never run `pip install` in a worktree — the shared venv is read-only.
- No co-authored-by lines in commits. No AI attribution.
- Executor / reviewer / planner / router agents may use `--no-verify` (e.g. `git -C "$PARENT" commit --no-verify`) for intermediate commits. The PR agent and sprint-closeout-reviewer must run hooks before merge.
- Cards may reference the roadmap, and the roadmap may optionally reference sprints and cards via its `sprints_ref` and `cards_ref` metadata fields on any node (open strings modeled on `docs_ref`, no format validation, stale refs allowed).
- **Never directly edit gitban-managed state.** The following paths are hard-protected — no direct `Write`, `Edit`, `sed`, `cat >>`, `cd`-prefixed `mv`, or any other non-MCP mutation: `.gitban/cards/` (including `archive/`), `.gitban/roadmap/` (the whole directory, including `roadmap.yaml` and the schema), and `.gitban/audit/`. All mutations go through gitban MCP tools (`create_card`, `edit_card`, `move_to_todo`, `upsert_roadmap`, etc.). The scaffold ships a `validate-no-direct-gitban-state-edit.sh` PreToolUse hook that blocks direct writes and normalises `cd`-prefixed Bash commands before matching. If you have a legitimate reason to hand-edit (triage, merge-conflict resolution), set `GITBAN_ALLOW_DIRECT_EDIT=1` in your shell; the edit is allowed but audited. Soft-protected paths (`.gitban/templates/`, `.gitban/handle.json`, `.gitban/validation_config.json`, `*.example.{json,yaml}`, `.gitban/examples/`) emit an advisory but do not block. Agent inboxes (`.gitban/agents/*/inbox/`) are intentionally unprotected — they are the prescribed file-based agent-to-agent comm channel where scaffold SKILLs (dispatcher, executor, reviewer, router, planner) write directives directly; no MCP write tool exists for them.


## Honest close-out

In the close-out summary, name what your tests actually verified. If the smoke test only
exercised a fixture, say so explicitly:

> Smoke test PASSED against `tests/fixtures/x.yml` — NOT verified against live
> `./production/path/`. Integration verification pending.

A confident "clean pass" line on fixture-only evidence is how broken integrations slip
through review. Be honest about scope.

## Completion tag

When all work is done and tests pass, tag the dispatcher's recovery signal. Resolve the
SHA from the worktree first (correct read), then write the tag from the parent (correct
ref namespace). The bare tag form (no commit argument) defaults to HEAD, which resolves
to the parent's branch HEAD when called via the `-C "$PARENT"` pin — wrong commit.
Always pass the SHA explicitly:

```bash
WT="$(git rev-parse --show-toplevel)"
PARENT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
git -C "$PARENT" tag "<completion-tag>" "$(git -C "$WT" rev-parse HEAD)"
```

**Pick the tag form by inbox-name shape.** The dispatcher's single-card-mode section
(`dispatcher/SKILL.md`) defines two dispatch modes; the inbox file your prompt named
tells you which one is in effect:

| Inbox shape | Mode | `<completion-tag>` |
| :--- | :--- | :--- |
| `{SPRINTTAG}-{cardid}-executor-{N}.md` | sprint | `{SPRINTTAG}-{cardid}-done` |
| `card-{cardid}-executor-{N}.md` | single-card | `card-{cardid}-done` |

The `card-` prefix in single-card mode is literal (not a placeholder for the string
`card`) — it keeps the tag self-documenting and prevents collision with sprint-tag
patterns. Always write a tag; the dispatcher's recovery path relies on it regardless
of mode.

## Internal error recovery

If a tool returns `[Tool result missing due to internal error]`, the platform crashed —
do NOT retry. Retrying will burn context and fail the same way.

1. Commit any completed work immediately.
2. Write the error file to your inbox. Pick the name by mode — the inbox file your
   prompt named is the same signal that selects the completion tag, so the error-file
   name mirrors the same two-row table:

   | Inbox shape | Mode | Error-file name |
   | :--- | :--- | :--- |
   | `{SPRINTTAG}-{cardid}-executor-{N}.md` | sprint | `{SPRINTTAG}-{cardid}-executor-{N}-ERROR.md` |
   | `card-{cardid}-executor-{N}.md` | single-card | `card-{cardid}-executor-{N}-ERROR.md` |

   The error file describes which tool failed, what was committed, and what's left.
3. Return `INTERNAL_ERROR: {tool} failed. Partial work at {commit}. Details in
   {error-file}.`

Silence is the worst outcome — the dispatcher hangs waiting on you. Always exit
informatively over retrying a broken tool.

## Sub-agent output

When you're spawned as a sub-agent, your Bash output is buffered until the command
exits. Don't pipe long-running tests through `tail`, `head`, or `Select-Object` — a hung
test will look like a hung agent. Use the runner's own verbosity controls (e.g. pytest
`-q`, `--timeout=N`).

## Waiting on long-running tests and builds

**Do NOT use the `Monitor` tool to wait for a self-terminating process** — a `pytest`
run, a `make build`, a one-shot script. `Monitor` is for polling a condition that some
*other* process eventually satisfies; it keeps re-invoking you on a timer, and each
re-invocation burns a turn. Pointing it at a command that exits on its own means you sit
in a poll loop until your turn/context budget runs out — then you return mid-sentence
("Test still running. Let me wait for the notification.") with an empty worktree, no
commit, and no completion tag. The dispatcher sees a clean worktree and a silent return
and has to throw the whole session away. This failure was observed three times in a
single sprint; it is the most expensive way to fail.

**Canonical wait pattern** for any test or build that exits on its own:

1. Start it with `Bash` and `run_in_background: true`. This returns a `task_id`
   immediately without consuming turns while it runs.
2. Wait for it with `TaskOutput(task_id, block: true)`. This blocks until the process
   exits and hands you the full output and exit status in one shot — no polling, no
   turn-budget drain.

Reserve `Monitor` for genuinely external conditions (a file another agent will write, a
remote endpoint coming up) where nothing you started will terminate on its own.

## Before you return — self-check

A worktree crash or turn-budget exhaustion leaves the dispatcher with an empty worktree
and no signal. Before you end your turn, verify all three of these. If **any** fails and
you cannot fix it before returning, you are about to lose work silently:

- **Working tree clean of *intended* changes?** Run `git -C "$PARENT" status --short`.
  If files you meant to ship are still uncommitted, your work is not durable — commit
  them now.
- **At least one commit on the worktree branch for this card?** Run
  `git -C "$PARENT" log --oneline <parent-branch>..HEAD`. Zero commits means nothing
  will merge back — finish the work and commit, or surface the partial-work error file
  below.
- **Completion tag emitted?** See the Completion tag section. No tag means the
  dispatcher's recovery path can't confirm you finished.

If you genuinely cannot complete the work (real blocker, internal error, ran low on
budget mid-task), do **not** return silently. Write a partial-work error file to
`.gitban/agents/executor/inbox/<sprinttag>-<cardid>-executor-<N>-ERROR.md` naming what
landed, what's left, and why — exactly as in *Internal error recovery* above — and say
so in your final message. A surfaced partial-work file is recoverable; a silent
clean-worktree return is not.

## Bulk string manipulation

String manipulation through the LLM is expensive. Use `sed -i`, `Edit replace_all=true`,
or one Bash command for any change that lands in multiple places. Reserve per-file
Edit for surgical changes that genuinely need context.

## Profiling

Emit structured profiling logs so the dispatcher can track agent cost. At the start of your session, run:

```bash
export AGENT_LOG_DIR=".gitban/agents/executor/logs"
export AGENT_ROLE="executor"
export AGENT_SPRINT_TAG="<sprint-tag>"   # from card metadata
export AGENT_CARD_ID="<card-id>"         # from card metadata
export AGENT_CYCLE="<N>"                 # review cycle (1 if first run)
source .gitban/hooks/agent-log.sh
agent_log_init
```

Log key operations as events:

```bash
agent_log_event "read-card" '{"card_id":"<id>"}'
agent_log_event "code-change" '{"files":["src/foo.py","src/bar.py"]}'
agent_log_event "test-run" '{"file":"tests/test_foo.py","passed":15,"failed":0}'
agent_log_event "hook-fix" '{"attempt":2,"fix":"ruff format"}'
agent_log_event "commit" '{"hash":"abc1234","message":"feat: add widget"}'
```

The Claude Code Bash tool runs each call in a fresh shell, so the log path that `agent_log_init` set does not persist to your next Bash call. You don't need to combine init and logging into one shell: as long as the `AGENT_*` vars above are still exported, the log helpers re-derive the same log path automatically, so events from any later shell append to the same file. Re-running `agent_log_init` in a fresh shell is harmless but optional — it just re-writes the header.

Before finishing, write the summary and stage the log. The parent-worktree pin (`-C "$PARENT"`) is required on every write-class git invocation: in a worktree your CWD may have drifted into a subdirectory, so the resolver expression below recomputes the parent repo's working-tree root regardless of which worktree the shell is in.

```bash
agent_log_summary
PARENT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
git -C "$PARENT" add .gitban/agents/executor/logs/
```

The log file lands at `.gitban/agents/executor/logs/{SPRINT_TAG}-{CARD_ID}-executor-{CYCLE}.jsonl`. Commit it with your work.


## Escalation

If you're blocked by something outside your control, move the card to `blocked` via MCP,
create a troubleshooting spike with full context, and notify the Staff Engineer.
