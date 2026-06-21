---
name: gitban-pr
description: Writes a well-structured draft Pull Request for the current branch targeting main. Sizes the PR — its sections, depth, and length — to the scale of the diff: a one-paragraph note for a trivial change, a single five-beat arc for one capability, and a full program report (background, decision spine, risks, asks) for a monolithic feature push.
hooks:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "bash ./.gitban/hooks/validate-no-direct-gitban-state-edit.sh"
---

Write a Pull Request that lands a gitban sprint or feature branch on main.

You start with clean context — you were not involved in executing the work. Read the finished work objectively and write for a human reviewer who knows nothing about your internal workflow. That clean-context stance is a feature: it stops you reliving the journey ("first we tried X, then Y…") and stops you defending estimates you didn't make. Report the result, not the diary.

## What a good PR is for

A PR is not a change log. A change log is a flat list, ordered by file or commit, and it answers "what got touched." A reviewer can reconstruct that themselves from the diff in thirty seconds. They cannot reconstruct **why this change exists, why it took this shape, and what is now true about the system that wasn't true yesterday** — that's the work the PR has to do.

So the PR is a short piece of technical writing whose job is to make a stranger feel the journey: the constraint that motivated the work, the capability that lands, the design fork that was chosen and the one that was rejected, and finally the concrete shape of the thing and the evidence it works. A reviewer who finishes reading should be able to (a) state in their own words what's now possible, (b) name the design choice you made and the alternative you rejected, and (c) point to the artefact that proves it works. If they can do all three, the diff review becomes verification, not investigation.

This is not literary indulgence. It's how reviewers stay fast on PRs they didn't author. The frame ("here's what's now possible, here's the choice we made, here's the thing") loads the reviewer's working memory in the right order so the diff makes sense as soon as they open it.

## Size the document to the change

The single most common way a PR fails is **mismatched scale**. A one-line constant change wrapped in eight ceremonial sections wastes the reviewer and reads as cargo-culting the template. A monolithic feature push — a PRD's worth of work, several architectural decisions, weeks of effort — summarised in a one-paragraph lede *buries the reasoning the reviewer most needs* and reads as a team that completed tickets without owning the architecture. Neither is acceptable. The document's length and section-set are a **function of the change**, not a fixed form.

Think of the PR as growing in **two independent dimensions**:

- **Breadth — how many distinct capabilities ship.** Each capability gets its own five-beat arc (below). One capability, one arc. Five capabilities, five arcs. Breadth is why a sprint PR is longer than a feature PR.
- **Altitude — how much blast radius and reasoning the change carries.** A bigger, riskier, more-decided change needs *connective tissue above the arcs*: a real Background, a decisions spine, explicit risks, explicit asks. Altitude is why a platform PR is shaped differently from a five-bug-fix sprint even when both have five arcs.

The five-beat arc is the **atom**. Everything else is how many atoms you have (breadth) and how much scaffolding sits above them (altitude). Place the PR on this ladder before you write a word:

| Tier | What it is | Signals | Shape |
| :--- | :--- | :--- | :--- |
| **1 — Trivial** | One self-evident change with no design fork at any level. | Typo, constant bump, dep pin, one-line guard, mechanical rename. ~1–3 files. No behaviour change a user would describe beyond the fix itself. | **1–3 sentences.** What was wrong / what's now true / the test that proves it. No lede, no TL;DR, no sections. Don't pad. |
| **2 — Single capability** | One coherent feature, fix, or refactor that *did* involve a fork. | A handful to a couple dozen files, one theme. | **One five-beat arc.** Beat 1 is the lede. Add a scope-driven section (risks / breaking / rollback / assumptions) only when it genuinely applies. |
| **3 — Multi-capability branch** | A sprint: several distinct capabilities cut together. | 2+ capabilities, ~20–80 files, usually a sprint tag. | **Lede + TL;DR + one arc per capability + cross-cutting validation + risks + follow-up + gitban-details collapsible.** |
| **4 — Program / monolith** | An entire feature or platform landing at once. | A PRD's worth of work, multiple ADRs, weeks of effort, many capabilities, often 100+ files, real production blast radius. | **Everything in Tier 3, plus the altitude sections**: a multi-paragraph Background, a Decisions spine, Goals/non-goals, mandatory Risks, explicit Asks/decisions-owed, and a reading guide. The altitude sections are the point — see "Scaling up." |

**When you're between two tiers, size by blast radius and reasoning density, not file count.** File count lies: a 200-file generated-manifest bump with one idea behind it is Tier 2; a 12-file change to the auth path that turned on three architectural decisions is Tier 4. Ask "how much does a reviewer have to *understand and defend later*, not how much did the diff touch."

The rest of this skill gives you the atom (the arc), then the altitude (how Tiers 3–4 grow the top of the document), then the mechanics.

## The five-beat arc — the atom

For every distinct capability this PR ships, walk these five beats in this order. The first three set the stage; beats four and five make the change verifiable. Skip nothing — but match depth to significance.

1. **The constraint.** What was the world like before? What couldn't be done, or what kept biting people? One or two sentences for a small change; a full paragraph if the constraint itself is non-obvious. This is your hook into a stranger's head — without it, beat 2 has nothing to push against.
2. **What's now possible.** Voiced positively, in the reader's terms. *Not* "we added X" — "after this, X works" or "Y stops happening" or "Z is now expressible." This is the sentence the reviewer remembers and the line they'll quote when they explain the PR to a teammate. Land it cleanly.
3. **Why this design.** The fork in the road. What alternative would someone naturally reach for, and what made it worse? Every nontrivial change has a fork; surface it. If a reviewer can finish reading and still ask "but why didn't you just…?", the PR has skipped this beat. (If the design was genuinely forced — only one workable shape — say so in one sentence and move on. The bar for "forced" is high; "this seemed obvious to me" doesn't clear it.)
4. **What it looks like.** A concrete artefact. Code snippet, config block, transcript, error message before-and-after, screenshot, a representative diff hunk. If you can't show the thing in twenty lines or fewer, you don't understand it well enough to PR it. *No* "see the diff" or "as documented in the ADR" hand-offs — the reviewer is reading the PR before they open the diff.
5. **How we know it works.** Validation specific to *this* capability — the failing-then-passing test, the integration run, the worked example, the manual repro. Cross-cutting validation (full suite green) goes in a single trailing section, not repeated per beat. Distinguish *verified* from *asserted*: "tests prove X" and "I believe X but only smoke-tested it" are different claims, and the reviewer needs to know which one they're getting.

A PR that ships five capabilities walks this arc five times. There is no "lead with motivation" section that absolves the rest of the document — every shipped capability gets its own arc where it's introduced.

**At Tier 1, collapse the whole arc into a sentence or two.** A typo fix doesn't have a fork; forcing five beats onto it is the over-writing failure. The arc is a tool for changes that carry reasoning, not a tax on changes that don't.

### Why the order matters

The order is **constraint → capability → choice → shape → proof** because that's how a reader who doesn't yet care comes to care, then evaluates. Reverse any two and the writing degrades:

- Lead with shape (a code snippet) and the reader has no frame for what they're looking at.
- Lead with capability before constraint and the reader has no reason to want the capability.
- Bury the design choice after the artefact and the reader will mentally redesign the thing while reading the diff, then resent that you didn't address their alternative.
- Skip proof and the reviewer has to invent the validation themselves.

## Writing the design-choice beat

The design-choice beat is what most PRs miss, so it gets its own treatment. A good design-choice paragraph has three moves: **the alternative** (what someone would naturally reach for), **the deciding factor** (the cost or constraint that made the alternative worse), and **the price you accepted** (what trade-off the chosen design costs you in return). Naming the price is the move that signals you actually thought about it; without it, the paragraph reads like a sales pitch.

**Anaemic:**

> We chose typed dataclasses for the config because they're safer.

The reviewer learns nothing. "Safer than what? At what cost?" is unanswered.

**Strong:**

> The obvious shape was a flat dict — fewer files, no schema to maintain, easy to extend. We chose typed dataclasses because adopters hand-edit these YAML files in production, and with a dict an unknown field silently no-ops at parse time, then the feature mysteriously doesn't work three weeks later. Dataclasses fail at parse time with a path to the bad field. The price: every new field is a code change in two places (the dataclass and the parser), not one.

Three moves, named cleanly: alternative (flat dict), deciding factor (silent failure mode for end users), price (two-place edits).

The bar for "no design choice to write about" is high. Most genuinely-forced designs are forced because of an upstream choice that *was* a fork — surface that one. If the work is so trivial there's no fork at any level (a typo fix, a one-line constant change), that's a Tier 1 PR — collapse the arc into a sentence and move on.

## Scaling up: the altitude sections (Tiers 3–4)

This is where the PR grows from "a stack of arcs" into a document a department head could read. The per-capability arcs carry the *substance*; the altitude sections carry the *frame*. A multi-capability branch (Tier 3) needs a lede; a program-scale push (Tier 4) needs the full frame. Add these top-down, in this order.

### The lede (Tier 3+)

A PR that ships more than one capability needs **one paragraph above the per-capability sections** that does two things: it names the unifying capability at the scope of the whole PR ("after this branch, X is true"), and it signals **why these things ship together** — the insight, constraint, or theme that made them belong in one cut. Without this paragraph, the PR reads as a stapled list of unrelated work.

**Stapled-list lede (bad):**

> This branch ships three things: a config override system, a bug fix for empty YAML, and updated test fixtures.

**Unifying lede (good):**

> Until this branch, every adopter who customised a default forked the whole config file — diverging from upstream, missing future fixes, and forcing manual merges on every release. This branch closes that loop: adopters now ship a small override file that merges with upstream defaults at load time, with three resolution strategies (replace, deep-merge, append) chosen explicitly per field. The empty-YAML fix and fixture updates are scaffolding for that change — surfaced separately because they have value on their own and a reviewer will see them in the diff.

Same artefacts, but the second version tells the reader **what's now possible at the scope of the whole branch** and **why the smaller items belong here**. A reviewer who reads only the lede should be able to predict the per-capability sections that follow.

For a single-capability PR (Tier 2) you don't need a separate lede — beat 1 of the arc is the lede.

### Background & problem at depth (Tier 4)

At program scale, one paragraph of unifying lede is too thin. A reviewer (and the engineering leadership they answer to) has to internalise the *world before* to judge the *world after* — and for weeks of work across multiple decisions, that takes several paragraphs, not a sentence. This is the section most large PRs starve, and starving it is the tell that the author understood the tickets but not the system.

A good Background covers: what this system is and the state it was in; what was failing, missing, or blocking; the pressure that made this worth doing *now*; and the constraints you worked under. Someone who had never seen the project should be able to reconstruct *why this mattered* from this section alone. It is the heart of a Tier-4 PR, not its preamble — the results are almost the easy part by comparison.

Pair it with a short **Goals / non-goals** statement when scope was large: what you committed to and what you explicitly ruled out. Non-goals are load-bearing — they're the difference between "deferred on purpose" and "missed."

### The decisions spine (Tier 4)

This is what separates a program report from a feature report. A Tier-4 push usually turned on several architectural decisions — the ones recorded as ADRs. The per-capability beat-3 covers a fork *local to one capability*; the spine covers the **cross-cutting decisions that shaped the whole cut** and will outlive every line of code in the diff. These are what leadership has to defend upward in six months, so surface them as first-class content.

For each major decision: the choice, the alternative considered, why you chose as you did, and the price you accepted — the same three moves as the design-choice beat, lifted to document level. When ADRs recorded the reasoning, **translate them into reviewer terms; don't just cite them** — a reviewer reading the PR before the diff can't follow a bare pointer. A table works well when there are three or more:

| Decision | Chosen | Rejected alternative | Price accepted |
| :--- | :--- | :--- | :--- |
| Auth boundary | Per-tenant scoped tokens | One shared service token | Token rotation machinery; more moving parts |
| Topology source | Declarative YAML | Imperative setup script | A schema to maintain and validate |

### Risks, tradeoffs, and what you didn't do (mandatory at Tier 2+)

A report with no downsides is the least trustworthy kind. The absence of stated risk doesn't read as "clean" — it reads as *not done* or *not understood*, and it makes the reviewer audit everything to find what you didn't mention. So above Tier 1, a PR states what it took on: known gaps, partial coverage, debt accepted under deadline, deferred hardening, anything that could surprise someone after merge. **If you genuinely believe there are no risks on a Tier 3–4 change, treat that belief as a smell and look harder** — a weeks-long platform push with zero caveats almost always means a caveat went unsaid.

This is distinct from the per-capability "price you accepted" (which is local to one design choice). This section is the cross-cutting view: where the *whole cut* is thin, risky, or provisional.

### Asks and decisions owed (Tier 3+, when any exist)

The worst outcome of a PR is the reader finding out three weeks later there was an implicit "…and we needed you to decide X." If the work needs a decision, a ratification of a judgment call, a sign-off, or a heads-up to another team, **say so explicitly and put it near the top** — not buried in paragraph nine. This is different from Follow-up work: follow-up is deferred *work the team owns*; an ask is something *the reader owes back* before or at merge. Name it, name who it's for, and name what's blocked until it's answered.

### A reading guide (Tier 3–4, large diffs)

When the diff is large or mixes production with generated/boilerplate, give an ordered "How to review" list — the file reading order that makes the diff legible, and a note on which paths are mechanical and can be skimmed. This is a courtesy that turns a 200-file diff from intimidating into navigable.

## The failure mode this all prevents: name-but-don't-explain

The single most common bad-PR pattern is enumerating internal artefacts by their internal nomenclature without ever explaining what they do or why they exist. It happens because the author is *too close* to the work — every internal name feels self-evident.

**Bad:**

> Sprint-closeout reviewer Gate 0 — cite-affordance contract (`<!-- cite: kind=… ref=… -->` per ticked checklist row), 793-line `gate0.py` reconciler, 29-test suite including the `9padx1`-shaped fixture (which MUST FAIL — the regression bar).

The reader knows things exist. They do not know what those things do, what changes for them after merge, what alternative was rejected, or how they'd verify any of it. Every term is an internal pointer (`Gate 0`, `cite-affordance`, `9padx1`, "regression bar"). A reviewer who didn't work on this sprint cannot tell what the PR delivers.

**Good (full five-beat arc, with internal names mostly hidden):**

> **The constraint.** Closeout reviewers accepted prose. "All tests passing ✅" was a string, not a claim. A closeout could tick boxes that contradicted its own retrospective body and the review would notice nothing — a sprint could be marked done while its own retrospective said otherwise.
>
> **What's now possible.** A closeout that ticks "all tests passing" cannot be merged unless that claim resolves to a real CI run with the right shape. Three failure modes are now structurally unrepresentable: a tick with no evidence, a tick whose evidence resolves to contradicting state, and a tick whose only evidence is the closeout citing itself.
>
> **Why this design.** The natural alternative was an LLM-as-judge reviewer that reads the prose and flags inconsistencies. We rejected it because LLM judgement on its own retrospective is too easy to slip past — the model that wrote the contradiction is not reliably the one to catch it. A structural rule (every tick carries a typed cite that resolves to external state) is verifiable by a tiny script and cannot be talked around. The price: writers must learn the cite syntax, and we accept friction on the first few closeouts.
>
> **What it looks like.** Every ticked box on the upper checklist now carries a typed evidence cite:
>
> ```markdown
> - [x] All tests passing on sprint branch <!-- cite: kind=ci ref=run/12345 -->
> - [x] Card abc123 done and archived <!-- cite: kind=card ref=abc123 -->
> ```
>
> A reconciler walks the checklist, parses each cite, resolves it against external state (the CI API, the card store), and emits a per-row verdict. A self-citation (`kind=closeout ref=self`) is a hard error.
>
> **How we know it works.** The contract self-applied to its own installer card during closeout. First run found 1 real contradicted-cite — author corrected. Second run passed 14/14. The 29-test suite includes one fixture that *must fail* (`9padx1` — a closeout with a self-citing tick); a green run on that fixture would mean the reconciler is broken.

Same artefacts, same internal names available where they pull weight (the fixture name appears once, in the validation section, where it makes the test surface concrete). But every claim is anchored to a behaviour change a reviewer can verify, with the design choice surfaced and the alternative explicitly addressed.

**The tell:** if your draft section reads as a glossary entry — sentences whose subjects are internal compound nouns, IDs, or sprint tags ("the cite-affordance contract", "the packed-card rejection rule", "Gate 0") — you are naming, not explaining. Replace with the five-beat arc.

## Before you start

1. **Fetch the latest**: Run `git fetch origin` so your diff is against the current remote, not a stale snapshot. If the base branch has moved significantly ahead, note this in the PR so the reviewer knows a rebase may be needed.
2. **Check for an existing PR**: Run `gh pr list --head $(git branch --show-current)` to see if a draft already exists. If one does, read its comments with `gh api repos/{owner}/{repo}/pulls/{number}/comments` and `gh api repos/{owner}/{repo}/issues/{number}/comments`. Look for unaddressed reviewer feedback — anything not yet resolved should be acknowledged in the updated PR body or fixed before rewriting. Don't silently drop feedback someone took the time to leave.

## Gathering context

Your **first** task is to place the PR on the scale ladder — that decision drives how much context you need to mine. A Tier-1 fix needs almost none; a Tier-4 push needs you to read the PRD framing, every ADR, and the deferred cards. Gauge scale from `git diff origin/main..HEAD --stat`, the number of done cards, and whether the work touches ADRs/PRDs, then mine accordingly.

Build understanding from every source available. The five-beat arc is hungry — beat 3 (design choice) and beat 1 (constraint) need real material, not platitudes — and the Tier-4 altitude sections (Background, Decisions spine) are hungrier still. Mining for it is most of the work.

- **Cards**: `list_cards` with the sprint filter and `include_archived: true`. Read each done card — titles, types, acceptance criteria, review logs, executor summaries. Read deferred/backlog cards to understand what was explicitly *not* done (that feeds Goals/non-goals and Follow-up). Pay special attention to **comments and review notes** — that's where design forks and alternatives-rejected get recorded in plain language.
- **Changelog**: `CHANGELOG.md` for the curated version entry.
- **Roadmap**: `read_roadmap` if the sprint or card references a milestone — the milestone framing often *is* the unifying capability for the lede, and the Background for a Tier-4 push.
- **Code**: `git log origin/main..HEAD --oneline` and `git diff origin/main..HEAD --stat`. Use `origin/main` — local main may be stale.
- **Documentation**: `git diff origin/main..HEAD -- docs/adr/ docs/designs/ docs/prds/`. ADRs are gold for beat 3 and for the Tier-4 decisions spine — they were written precisely to record design choices and rejected alternatives. Translate them into reviewer terms; don't just cite them. The PRD, when one exists, is the source for the Background and Goals/non-goals.
- **Concrete artefacts**: actual code snippets, config files, error messages, command output. Beat 4 demands these. Find them now so you can quote them later.

The research powers the PR — the research artefacts themselves do not appear in the output. **Card titles and DoD bullets are not explanations.** They are pointers for people who already understand. Your job is to translate from artefact-pointer to behaviour-change.

### What gitban gives you that other PR authors don't have

- **Review logs** — what reviewers caught and what got fixed. Use this to populate beat 5 (validation) with non-fabricated evidence; also a rich source for beat 3 when the review caught a design alternative the author had to argue against.
- **Conscious deferrals with reasoning** — preempts "but why didn't you just…?" before the reviewer asks. Often the seed of beat 3, and the raw material for Goals/non-goals and Follow-up.
- **Root-cause analysis from bug cards** — multi-iteration investigation logs that make beat 1 (the constraint) precise rather than hand-wavy.
- **Scope boundaries** — what was explicitly rejected and why. Belongs in beat 3, or in the Risks/non-goals sections when the boundary is non-obvious.

Mine for these. Use what makes a particular section more concrete; drop the rest. Match depth to significance.

## Section reference

A PR organised around the five-beat arc lays out naturally as one or more H2/H3 sections per capability, plus connective sections that appear as the tier rises. The **Tier** column says the lowest tier at which a section earns its place — below that tier, omitting it is correct, not lazy. Use what fits; omit what's empty.

| Section | Purpose | Appears at |
| :--- | :--- | :--- |
| **Per-capability arc(s)** | The five-beat arc, one per shipped capability. H2 for a top-level theme, H3 for a sub-capability. | **All tiers.** This is the body. Tier 1 collapses it to a sentence or two. |
| **Lede** (untitled, top) | One paragraph naming the unifying capability and why these things ship together. | **Tier 3+** (any PR with >1 capability). |
| **TL;DR / Summary** | A compact bulleted headline of what shipped, for the skim-first reviewer. Sits below the lede. | **Tier 3+** (3+ capabilities or ~20+ files). |
| **Background & problem** | Multi-paragraph situation: the system, the world-before, the pressure, the constraints. | **Tier 4.** The heart of a program-scale PR. |
| **Goals / non-goals** | What you committed to and explicitly ruled out. | **Tier 4** (or Tier 3 when scope was contested). |
| **Decisions spine** | The cross-cutting architectural decisions (the ADRs), each with alternative + price, in reviewer terms. | **Tier 4.** |
| **Validation** | Cross-cutting verification (full-suite, integration, manual) that doesn't fit one capability. | **Tier 3+** (per-capability validation stays inside each arc). |
| **Risks & limitations** | What doesn't work yet, has caveats, or could surprise someone after merge. | **Tier 2+** — and effectively mandatory at Tier 3–4 (no-downsides is a smell). |
| **Asks / decisions owed** | What the reader must decide, ratify, sign off, or be warned about. Distinct from Follow-up. | **Tier 3+ when any exist.** Put near the top. |
| **How to review** | Ordered file reading order; flags mechanical/generated paths. | **Tier 3–4** with large or mixed diffs. |
| **Follow-up work** | Identified-but-not-done work the team owns, with destination (backlog vs. named sprint). | **Tier 2+ when work was descoped.** |
| **Breaking changes** | What downstream consumers must do differently. | **Any tier** the behaviour/API/interface changed. |
| **Linked issue** *(scope-driven)* | `Fixes #123` / `Closes #456` / `Refs #789` near the top so reviewers find the original ask. | Always for external repos; optionally when it helps reviewers find the originating discussion. |
| **Assumptions made** *(scope-driven)* | Judgment calls made where the spec was ambiguous, for the reader to sanity-check. | When the work interpreted underspecified requirements. |
| **Rollback / revert plan** *(scope-driven)* | How to revert cleanly; what reverts safely and what doesn't. | When the change touches production runtime, runs an irreversible op (migration, backfill, key rotation), alters a live API, or changes deploy config. Skip for docs / internal refactors / tooling. |

For a Tier-1 PR the whole thing is a few short paragraphs. Don't pad. Don't invent sections. Conversely, for a Tier-4 PR, omitting Background or Risks because "the arcs cover it" is the under-writing failure — the altitude sections exist precisely because the arcs don't carry the frame.

## Form follows enumeration

When a section lists three or more of-a-kind items — failure modes, follow-ups, validation checks, decisions, cite types, file groups, error codes, deferred cards — reach for a table. A bullet list with each line packed full of internal compound nouns reads like a glossary. A table with columns puts the comparison axes in the column headers, where the eye expects them, and frees each row to be short.

Code blocks (``` ```) for syntax, configs, CLI invocations, error messages, before/after snippets. They satisfy beat 4 of the arc more cleanly than prose.

Callouts (e.g. `**⚠️ Not yet live.**`) for risks the reviewer should not skim past.

## Adaptive shape by PR character

Tier sets the scaffolding; character sets how each arc reads:

- **Bug fix**: beat 1 is the bug (with reproducer if non-obvious), beat 2 is what now works, beat 3 is why this fix and not a more local patch (often "the local patch hides the class of bug; this fix prevents recurrence"), beat 4 is the failing-then-passing test or corrected output, beat 5 is regression coverage. A one-line fix is Tier 1 — collapse it.
- **Feature**: five-beat arc directly. Each feature is a section.
- **Refactor**: beat 1 is the constraint the old shape created, beat 2 is what the new shape unlocks, beat 3 is why this shape and not a milder rearrangement, beat 4 is a representative diff hunk showing the call-site improvement, beat 5 is "no behaviour changed; full suite green."
- **Sprint (Tier 3)**: lede + TL;DR + one arc per capability + cross-cutting validation + risks + follow-up + gitban-details.
- **Program / platform (Tier 4)**: the full altitude stack — Background, Goals/non-goals, decisions spine, then the per-capability arcs, then Risks, Asks, How-to-review, Follow-up, gitban-details.
- **Validation/test-only**: lead with the constraint (what was untestable or under-covered), then what's now covered. Each test surface gets its own arc; beat 4 is the test code, beat 5 is the run output.

## PR title

- Sprint: `sprint/{SPRINTTAG}: [what's now possible, in plain language]`
- Feature: `feature/{card-id}: [card title in natural language]`

The title should tell the reviewer what this PR makes true, not what cards were touched. If you can't write a plain-language title, beats 1–2 of the arc are incomplete somewhere — go fix that first.

## Submitting

1. Push the source branch, pinned to the parent worktree (the resolver recomputes the parent repo root regardless of worktree CWD drift): `PARENT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")" && git -C "$PARENT" push -u origin {branch}`.
2. Write the PR body to a project-local scratch file at `tmp/pr-body.md` using the Write tool. Project-local, never `/tmp/`: system temp is platform-dependent (missing on Windows, world-readable on shared boxes), can be wiped mid-session, and survives across unrelated repos. The `tmp/` directory at the project root is gitignored; the Write tool creates it on first use. Never use heredocs or shell quoting for PR bodies — they mangle markdown.
3. Create the PR as a draft: `gh pr create --draft --title "..." --body-file tmp/pr-body.md`. Always `--draft`.
4. Clean up the scratch file after successful creation.
5. If `gh` is unavailable, keep the draft markdown file and report the path.
6. Return the PR URL.

## Self-check before submitting

First, **confirm the tier**. Read your draft and ask: does its weight match the change? A monolithic push with a one-paragraph top and no Background/Decisions/Risks is under-written — add altitude. A typo fix with eight sections is over-written — collapse it. The most common failure is not a bad section; it's the wrong *amount* of document.

Then read your draft like a stranger who joined the project this week. For each capability arc:

- Beat 1: Can you point to a sentence that names the constraint? Not "we wanted to add X" but "X kept biting because Y."
- Beat 2: Can you point to a sentence whose subject is **the user or the system** and whose verb is positive ("can now", "no longer", "is expressible as") — not a sentence whose subject is "we" and whose verb is "added"?
- Beat 3: Can you point to the **rejected alternative** by name? If your design-choice paragraph mentions only the chosen design and not what it beat, beat 3 is missing.
- Beat 4: Can you point to a concrete artefact (code, config, transcript)? "See the diff" is not an answer.
- Beat 5: Can you point to validation specific to *this* capability, not just "all tests pass"? Did you distinguish what's *verified* from what's *asserted*?

Did you write any sentence whose subject is an internal name (`Gate 0`, `5oixhb`, "the cite-affordance contract") rather than a behaviour or a change? Rewrite it.

For Tier 3+: does the lede let a reviewer predict the sections below? If they couldn't write the section headings from the lede alone, the lede is describing but not unifying. Did you surface any **ask the reader owes you**, near the top, rather than burying it?

For Tier 4: is there a Background a newcomer could reconstruct the project's *why* from? Is the decisions spine present, with rejected alternatives named? Does the Risks section exist — and if it's empty, did you look harder before concluding a weeks-long push has no caveats?

For each scope-driven section (linked issue, assumptions made, rollback plan):

- **Linked issue**: contributing to an external repo or resolving a tracked issue? The `Fixes #N` line is one line — the cost of including it is zero, the cost of forgetting it is a manual issue close and a reviewer hunt.
- **Assumptions made**: did the work involve any interpretation of an ambiguous spec? If yes, did you write down the interpretations the reader should sanity-check?
- **Rollback plan**: does this PR touch production runtime, run a migration, change an API surface, or alter deploy config? If yes, can a reader name how to revert each affected piece without re-reading the diff?

If any answer is no on a section the tier calls for, fix it before submitting.

## Attribution

When gitban was used to organise the work, end the main body with:

```
---
Planned and tracked with [gitban](https://github.com/muunkky/gitban-mcp).
```

Visible to everyone, not buried in a collapsible. The quality of the PR is the advertisement; this line just tells curious readers where to look. Include it even when contributing to external repos that don't use gitban — if gitban organised the work, the attribution belongs. Omit it only if gitban wasn't used for the branch.

## Gitban details (collapsible)

Below the attribution, include a collapsed `<details>` section for teammates who use gitban. This is the only place where internal IDs (card IDs, sprint tags, roadmap paths) belong as the primary reading surface — the main body told the story; this section navigates the workflow context. It also keeps vanity metrics out of the main body: card counts and commit tallies are inputs, not outcomes, and leading with them signals you're measuring the wrong thing.

```markdown
---

<details>
<summary>Gitban details</summary>

### Sprint

{SPRINTTAG} — one-line origin or theme.

### Roadmap

`m2/s2 "Auth and Access Control"` — story purpose; how this PR advances it.

### Cards delivered

| ID | Type | Title | Key outcome |
|----|------|-------|-------------|
| `abc123` | feature | Config override system | Adopter YAML merges with defaults; 3 resolution strategies validated |
| `def456` | bug | YAML parse crash on empty input | Root cause: missing None guard; added error wrapping with file path + line |

### Deferred work

| ID | Title | Destination | Reason |
|----|-------|-------------|--------|
| `ghi789` | Path traversal guard | Backlog (unscheduled) | Needs design review before implementation |
| `jkl012` | Write lock for key store | `m2/s3` tenant isolation sprint | Deferred to database migration |

### Review insights

Cards `def456` and `mno345` went through rework cycles — reviewer caught a leaked private import and a silently dropped test during merge conflict resolution. Both fixed before approval.

### Sprint metrics

- **Completed**: 5 cards (2 feature, 2 bug, 1 chore)
- **Deferred**: 2 cards (1 backlogged, 1 scheduled for `m2/s3`)
- **Rework cycles**: 2
- **Changelog**: `v1.2.0-m5.1`

</details>
```

**Required content:**

- **Cards delivered table** — one row per done card. The "Key outcome" column is what makes this section pull its weight: a 1–2 phrase summary of what the card *actually accomplished*, drawn from the card's exit criteria. Not the title restated, not the DoD checklist verbatim.
- **Deferred work table** — for each deferred card, the **destination** (specific sprint or backlog with priority, not just "later"). If the destination is unclear, flag it ("destination unclear — may need triage").
- **Roadmap path** — full notation (`m2/s2 "Title"`), with the story's purpose and where this PR sits in it. Skip if the work isn't on a roadmap.
- **Sprint metrics** — completion counts by type, rework cycles, deferred counts with disposition.

**What does NOT belong here:** ADRs, design docs, runbooks. Those belong in the main body where every reviewer can see them (the decisions spine, for a Tier-4 PR). The collapsible is exclusively for gitban-internal organisational data.

**What to leave out:** handle assignments, timestamps (git log has these), raw card content, the attribution line.

For a single-card PR the section can be minimal — card ID, roadmap path if relevant, and any deferred follow-ups. Don't pad. Omit the entire section if gitban wasn't used for the branch.

## .gitban content in PRs

The `.gitban/` directory is a local/fork workflow artefact. Do not include `.gitban/` content in PRs targeting repositories that don't use gitban. A pre-push hook enforces this when isolation is configured. If the push is blocked, the hook says why and how to fix it. If isolation isn't configured for the target remote, run the MCP `isolate_remote_tool`.

## Anti-patterns

- **Scale mismatch (both directions).** A Tier-1 fix dressed in eight ceremonial sections, or a Tier-4 push summarised in a one-paragraph lede with no Background, Decisions, or Risks. Size the document to the change — under-writing a monolith buries the reasoning; over-writing a one-liner wastes the reviewer.
- **Change-log voice.** Sentences whose subject is "we" or "this PR" and whose verb is "adds/updates/refactors". Rewrite as "X now does Y" or "Y is now possible because of X" — subject the system, predicate the behaviour change.
- **Name-but-don't-explain.** Sentences whose subjects are internal compound nouns or IDs ("the cite-affordance contract", "Gate 0"). Replace with the five-beat arc.
- **Missing design choice.** A capability section that names the chosen design but never the rejected alternative. Surface the fork.
- **No-downsides report.** A Tier 3–4 PR with no Risks/limitations section, or one that lists only wins. Reads as not-done or not-understood. An empty risk section on a big change is a prompt to look harder, not a badge.
- **Buried ask.** A decision the reader owes — sign-off, ratification, cross-team heads-up — left implicit or sunk to the bottom. If you need something from the reader, it goes near the top.
- **Vanity metrics in the body.** "10k lines, 132 commits, 40 files." Volume is an input cost, not an achievement. Counts live in the gitban-details collapsible; the body holds outcomes.
- **Stapled-list lede.** A multi-capability PR opening with "this branch ships A, B, and C" instead of a paragraph that unifies them.
- **Process transcript.** "We read 18 cards, dispatched 5 executors…" The reviewer needs the result, not the workflow narrative.
- **Confidence laundering.** "Done" covering merged-and-verified, works-locally, and wrote-it-haven't-run-it without distinction. State what's verified vs. asserted.
- **Unread claims.** Never conclude something is "missing" without reading it. Metadata listings show structure, not content. Read the actual card/roadmap content before claiming absence.
- **Active-only summary on a sprint PR.** Inspect done/archived cards too. The PR covers all work on the branch, including finished items.
- **Beat-4 evasion.** "See the diff" or "as documented in the ADR" instead of a concrete artefact. The reviewer is reading the PR before the diff. Show the thing.

## Constraints

- Use gitban MCP tools for card interactions. Do not read or edit files in `.gitban/cards/` directly.
- No co-authored-by lines in commits.
- **Pre-commit hooks must run on every commit you make.** Executor / reviewer / planner / router skip hooks on intermediate commits during card work; the PR agent is the merge gate. Run hooks; never `--no-verify`. If hooks fail, fix the underlying issue.
- Use `origin/main` for diffs, not local `main`.
- Always create PRs as draft (`--draft`).
