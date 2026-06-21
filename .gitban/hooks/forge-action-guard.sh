#!/bin/bash
# Forge-action guard hook (ADR-070, FORGEMVP1 step 6B) -- PreToolUse:Bash.
#
# Rejects raw `gh` *write* invocations against forge state so that every
# forge mutation has to go through the gitban forge port, where the scope
# gate and the audit trail fire. A hand-written `gh issue create` or a
# `gh api -X POST` would mutate the forge with no gate and no audit row;
# this hook stops it at the Bash boundary with a teaching message pointing
# at the port.
#
# Scans the *masked* command text (heredoc bodies, single/double-quoted
# regions, $(...) and backticks are replaced with neutral placeholders before
# scanning -- same model as cwd-pin-check.sh), so a `gh issue create` inside a
# heredoc or a quoted string is not a false positive.
#
# BLOCKS (exit 2):
#   * `gh issue <write>`   -- create, edit, close, reopen, delete, comment,
#                             lock, unlock, pin, unpin, transfer, develop, ...
#   * `gh release <write>` -- create, edit, delete, upload, ...
#   * `gh api` with a write method: `-X POST|PATCH|PUT|DELETE` or the long form
#     `--method post|patch|put|delete` (case-insensitive).
#   * `gh api graphql` whose query body contains a `mutation` *operation*
#     (the `mutation` keyword in operation position -- optionally named -- with
#     a following selection-set `{` or variable-definitions `(`). A bare
#     `mutation` substring naming the Mutation type in a read, in a comment, in
#     a filename, or in a piped grep is NOT an operation and is permitted.
#
# PERMITS (exit 0):
#   * `gh api ... GET` and default-GET (no `-X`/`--method`), and
#     `gh api graphql` *queries* -- there is no port replacement for reads yet
#     (Phase-1 staging). Method-discrimination is MANDATORY: because `gh api`
#     is the same surface for reads and writes, allow-listing `gh api`
#     wholesale would be a write bypass in disguise (design D10). The read
#     carve-out can never authorize a write because the method is parsed.
#   * `gh issue list|view|status`, `gh release list|view|download`, and any
#     other read verb.
#   * `gh pr create` (and every other `gh pr` subcommand). This is the Phase-1
#     staging lock (S2): the PR agent's `gh pr create` has NO port replacement
#     until `create_pr` lands, so blocking it would brick the PR flow. The
#     Phase-1 pattern set carries NO `gh pr <write>` rule at all -- this is a
#     SOURCE property (the rule is simply absent), not a runtime gate. The
#     `gh pr` write-block flip lands later, with `create_pr` (a two-line source
#     change, out of MVP scope).
#   * Any non-`gh` command, and any `gh` command not matched by a block rule.
#
# Honest framing: this is a TRIPWIRE against accidental regrowth (an agent
# hand-writing a raw `gh` write), not an adversarial filter. An evader who
# base64-decodes the command or paraphrases it slips through; a green scan
# proves only that the obvious write forms were caught. The durable defense is
# the port's ergonomics, not this regex.
#
# Environment-variable contract:
#   GITBAN_FORGE_GUARD_MODE
#     `enforce` (default; rejects write-class `gh` with exit 2)
#     `advisory` (logs to .gitban/audit/forge_guard_advisory.jsonl, exits 0)
#     any other value is treated as `enforce`. Migration mode for one release
#     cycle so adopters can see what would block before it does.
#
# Bypass: a one-shot `forge-action-guard` sentinel written by
#   mcp__gitban__allow_hook_bypass_once(hook_name="forge-action-guard",
#                                       target="<the command text>", reason=...)
# is consumed on the next firing and allows exactly that one blocked
# invocation. The consume side keys on the command text as the target.
#
# Portability: bash + grep + sed + awk only (no jq required), MSYS2/Git Bash
# compatible. The shared library handles cross-platform decoding.

# Source the canonical input-parsing library (ADR-054 Decision 1). The library
# is shipped alongside this hook under hooks/lib/.
LIB_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)/lib"
if [ -z "$LIB_DIR" ] || [ ! -f "$LIB_DIR/gitban-hook-input.sh" ]; then
  # Library missing -- degrade-open. The hook cannot reliably mask/classify
  # without the library, so it MUST NOT block (fail-open against legitimate
  # ops). The settings merger guarantees the library ships with the hook, so
  # this branch is defensive only. Note: this guard's failure-open posture is
  # deliberately the same as cwd-pin-check.sh -- a forge write slipping through
  # un-audited is a tripwire miss, not a data-loss event.
  echo "forge-action-guard: WARNING -- gitban-hook-input.sh library not found; degrading to allow-all." >&2
  exit 0
fi
# shellcheck source=lib/gitban-hook-input.sh
. "$LIB_DIR/gitban-hook-input.sh"

# Wire up hook-invocation audit. The EXIT trap emits exactly one row to
# .gitban/audit/hook_invocations.jsonl per invocation regardless of exit path.
gitban_audit_init "forge-action-guard" "Bash"

INPUT=$(cat)

# ---------------------------------------------------------------------------
# Tool-name extraction -- bash-native (no subprocess), same hot-path technique
# cwd-pin-check.sh uses. Only `Bash` payloads reach the scan.
# ---------------------------------------------------------------------------
TOOL_NAME=""
_after_tn="${INPUT#*\"tool_name\"}"
if [ "$_after_tn" != "$INPUT" ]; then
  _after_tn="${_after_tn#*:}"
  _after_tn="${_after_tn#"${_after_tn%%[!  ]*}"}"  # trim leading whitespace
  _after_tn="${_after_tn#\"}"
  TOOL_NAME="${_after_tn%%\"*}"
fi

# Out-of-scope tools dispatch via the shared classifier. Only `command`
# dispatch (Bash, PowerShell) reaches the scan; PowerShell is then filtered
# out explicitly (a bash tokeniser cannot meaningfully parse PowerShell).
DISPATCH=$(gitban_classify_tool_dispatch "$TOOL_NAME")
if [ "$DISPATCH" != "command" ]; then
  exit 0
fi
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

# Decode the Bash command field. Escape-aware regex first, then a simple
# fallback for unescaped strings -- identical to cwd-pin-check.sh.
COMMAND=$(printf '%s' "$INPUT" \
  | grep -oE '"command"[[:space:]]*:[[:space:]]*"(\\.|[^"\\])*"' \
  | head -1 \
  | sed 's/^"command"[[:space:]]*:[[:space:]]*"//;s/"$//')
if [ -z "$COMMAND" ]; then
  COMMAND=$(printf '%s' "$INPUT" \
    | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -1 \
    | sed 's/.*: *"//;s/"//')
fi
[ -z "$COMMAND" ] && exit 0

# Decode JSON-string escape sequences (\" \\ \n \t \r) before masking, so the
# masker operates on real bash syntax. The \\ placeholder trick prevents `\\"`
# from being mis-decoded.
COMMAND=$(printf '%s' "$COMMAND" | sed -e 's/\\\\/\x01/g; s/\\"/"/g; s/\\n/\n/g; s/\\t/\t/g; s/\\r/\r/g; s/\x01/\\/g')

# Build the masked-command text used for the scan. Heredoc bodies, quoted
# strings, $(...) and backticks become neutral placeholders so a `gh` inside
# prose never matches.
MASKED_COMMAND=$(gitban_mask_command_text "$COMMAND")

# Flatten newlines so per-segment `gh ...` scans see the full argument run of
# each invocation. Newlines are equivalent to spaces for the scan.
SCAN_TEXT=$(printf '%s' "$MASKED_COMMAND" | tr '\n' ' ')

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

# Write-verbs for `gh issue` and `gh release`. Anything not in the read set is
# treated as a write (conservative-when-in-doubt) so a future `gh issue
# <newverb>` write is caught automatically. Read verbs are explicitly allowed.
_ISSUE_READ_RE='^(list|view|status)$'
_RELEASE_READ_RE='^(list|view|download)$'

# Decide whether a `gh api ...` argument run is a write. Emits "write" or
# "read". Args are the tokens after `api`.
#   * `-X <method>` / `--method <method>` / `--method=<method>` with a method
#     other than GET/HEAD -> write.
#   * `graphql` with a body containing a `mutation` keyword -> write.
#   * otherwise (default GET, explicit GET, graphql query) -> read.
# The args here are taken from the MASKED command, so a GraphQL query body that
# was inside a single/double-quoted string is masked to QUOTEDARG -- we cannot
# see `mutation` inside it. We therefore additionally scan the RAW command's
# graphql body for the mutation keyword (see caller).
_classify_gh_api() {
  local args="$1"
  # Method flag: -X <m>, --method <m>, --method=<m>. Case-insensitive method.
  # Pull the method token if present.
  local method=""
  # -X / --method with a separated value.
  method=$(printf '%s' "$args" \
    | grep -oiE '(^|[[:space:]])(-X|--method)([[:space:]]+|=)[A-Za-z]+' \
    | head -1 \
    | grep -oiE '[A-Za-z]+$')
  if [ -n "$method" ]; then
    # Uppercase for comparison (bash 3.2 compatible: use tr).
    local up
    up=$(printf '%s' "$method" | tr '[:lower:]' '[:upper:]')
    case "$up" in
      GET|HEAD) echo "read" ;;
      *)        echo "write" ;;
    esac
    return 0
  fi
  # No explicit method -> default GET (read). graphql mutation detection is
  # handled by the caller against the raw command.
  echo "read"
}

# ---------------------------------------------------------------------------
# Main scan -- walk every `gh <subcmd>` occurrence in the masked command.
# ---------------------------------------------------------------------------
# Pattern captures `gh <subcmd>` and the run of args up to the next command
# separator. We process the FIRST blocking match.

REJECTED=0
REJECTED_MATCH=""

# Extract each `gh <subcmd> <args...>` segment. We split SCAN_TEXT on command
# separators first (so `foo && gh issue create` isolates the `gh ...` run),
# then inspect each segment whose first token is `gh`.
# Separators: ; | & ( ) and the masked-out newline (already flattened).
SEGMENTS=$(printf '%s' "$SCAN_TEXT" | sed -E 's/(&&|\|\||[;|&()])/\n/g')

while IFS= read -r seg; do
  # Trim leading whitespace.
  seg="${seg#"${seg%%[![:space:]]*}"}"
  [ -z "$seg" ] && continue
  # First token must be `gh` (skip env-assignment prefixes like FOO=bar gh ...).
  # Strip leading VAR=VALUE assignments.
  while printf '%s' "$seg" | grep -qE '^[A-Za-z_][A-Za-z0-9_]*='; do
    seg="${seg#* }"
    seg="${seg#"${seg%%[![:space:]]*}"}"
  done
  first="${seg%%[[:space:]]*}"
  [ "$first" = "gh" ] || continue

  # rest = everything after `gh`.
  rest="${seg#gh}"
  rest="${rest#"${rest%%[![:space:]]*}"}"
  subcmd="${rest%%[[:space:]]*}"
  args="${rest#"$subcmd"}"
  args="${args#"${args%%[![:space:]]*}"}"

  case "$subcmd" in
    issue)
      verb="${args%%[[:space:]]*}"
      if printf '%s' "$verb" | grep -qiE "$_ISSUE_READ_RE"; then
        continue
      fi
      # Empty verb (`gh issue` alone) is help/list-ish -> permit.
      [ -z "$verb" ] && continue
      REJECTED=1
      REJECTED_MATCH="gh issue $verb"
      break
      ;;
    release)
      verb="${args%%[[:space:]]*}"
      if printf '%s' "$verb" | grep -qiE "$_RELEASE_READ_RE"; then
        continue
      fi
      [ -z "$verb" ] && continue
      REJECTED=1
      REJECTED_MATCH="gh release $verb"
      break
      ;;
    api)
      cls=$(_classify_gh_api "$args")
      if [ "$cls" = "write" ]; then
        REJECTED=1
        REJECTED_MATCH="gh api (write method)"
        break
      fi
      # graphql mutation detection. The masked args hide a quoted body, so
      # scan the RAW command for a `gh api graphql` invocation carrying a
      # mutation. The keyword is anchored to a GraphQL *operation position* --
      # `mutation` followed by an optional operation name and then a `{` (the
      # selection set) or a `(` (variable definitions). This is the only place
      # `mutation` is the operation keyword. A bare `mutation` substring (the
      # Mutation type named in a `__type` introspection read, a trailing
      # `# see mutation docs` comment, a `mutation_notes.txt` filename, a
      # `grep mutation` in a piped read) is NOT an operation and is correctly
      # permitted. This clears the false-positive reads while still catching
      # anonymous (`mutation {`) and named (`mutation Foo {` / `mutation Foo(`)
      # real mutations.
      verb="${args%%[[:space:]]*}"
      if [ "$verb" = "graphql" ]; then
        if printf '%s' "$COMMAND" | grep -qiE 'mutation([[:space:]]+[A-Za-z][A-Za-z0-9_]*)?[[:space:]]*[({]'; then
          REJECTED=1
          REJECTED_MATCH="gh api graphql (mutation)"
          break
        fi
      fi
      # read -> permit.
      continue
      ;;
    pr)
      # Phase-1 staging lock (S2): NO `gh pr <write>` rule. `gh pr create` and
      # every other `gh pr` subcommand are PERMITTED until `create_pr` lands.
      continue
      ;;
    *)
      # Any other `gh` subcommand (auth, repo, run, workflow, label, ...) is
      # out of the Phase-1 block scope -> permit. The block set is the narrow
      # forge-state surface the port replaces in this phase.
      continue
      ;;
  esac
done <<< "$SEGMENTS"

if [ "$REJECTED" = "0" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# A write was matched. Decision: bypass-allow, advisory-log, or reject.
# ---------------------------------------------------------------------------

# Bypass sentinel: keyed on the command text as the target. If a matching
# unconsumed sentinel exists, consume it and allow this one invocation.
SENTINEL_ID=$(gitban_check_bypass_sentinel "forge-action-guard" "$COMMAND")
if [ -n "$SENTINEL_ID" ]; then
  gitban_audit_consumed_append "$SENTINEL_ID" "forge-action-guard" "$COMMAND"
  gitban_audit_mark_bypass "$SENTINEL_ID" "$REJECTED_MATCH"
  echo "NOTICE: forge-action-guard bypass sentinel consumed for this invocation." >&2
  echo "  Offending invocation: $REJECTED_MATCH" >&2
  exit 0
fi

MODE="${GITBAN_FORGE_GUARD_MODE:-enforce}"

if [ "$MODE" = "advisory" ]; then
  _ts=$(_gitban_timestamp)
  _row=$(printf '{"timestamp":"%s","tool_name":"Bash","command":"%s","offending":"%s","handle":"%s"}' \
    "$(_gitban_json_escape "$_ts")" \
    "$(_gitban_json_escape "$COMMAND")" \
    "$(_gitban_json_escape "$REJECTED_MATCH")" \
    "$(_gitban_json_escape "$(_gitban_handle)")")
  gitban_audit_append ".gitban/audit/forge_guard_advisory.jsonl" "$_row"
  gitban_audit_mark_advisory "$REJECTED_MATCH"
  echo "NOTICE: raw forge write in advisory mode (GITBAN_FORGE_GUARD_MODE=advisory)." >&2
  echo "  Offending invocation: $REJECTED_MATCH" >&2
  echo "  This will become an error in the next release. Route the write through" >&2
  echo "  the gitban forge port (create_issue / create_pr / ...) so the gate and" >&2
  echo "  audit fire." >&2
  exit 0
fi

# Default: enforce -> reject.
gitban_audit_mark_block "$REJECTED_MATCH"
echo "BLOCKED: raw forge write must go through the gitban forge port (ADR-070)" >&2
echo "  Offending invocation: $REJECTED_MATCH" >&2
echo "  Raw 'gh' forge writes bypass the gate and audit trail the port enforces." >&2
echo "  Use the gitban forge MCP tools instead (create_issue / find_issues /" >&2
echo "  resolve_forge_artifact; create_pr and the rest land in later phases)." >&2
echo "  Read-only 'gh api ... GET' and 'gh pr create' are still permitted." >&2
echo "  To allow a one-off legitimate raw invocation, call:" >&2
echo "    mcp__gitban__allow_hook_bypass_once(hook_name=\"forge-action-guard\", target=\"<command>\", reason=\"...\")" >&2
exit 2
