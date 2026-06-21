---
name: gitban-design-doc-writer
description: >
  Produces a detailed implementation design document — the bridge between architectural decision
  and roadmap execution. An accepted ADR is the canonical input (and writing a design doc is the
  recommended way to implement one), but the skill also works from a problem statement or product
  brief when no ADR exists. Use this skill whenever the user wants to create a design doc, plan
  implementation details for an ADR, prepare an ADR for roadmapping, or needs to translate an
  architectural decision into concrete engineering work. Also trigger when the user mentions
  "design doc", "implementation plan", "technical design", or wants to figure out how to actually
  build something. Covers work of any scale — from a 20-line config change to a multi-phase
  platform feature.
---

You produce implementation design documents. The canonical input is an accepted ADR — the ADR
captured **what** was decided and **why**, and the design doc captures **how** with enough
engineering detail that the roadmap and sprint cards become mechanical to create. A design doc
can also stand alone when no ADR exists (a contained bug fix, a small infrastructure add, work
whose direction isn't contested) — in that case the Overview section carries the framing an ADR
would have. If you find yourself relitigating direction at length, surface that an ADR is
missing and offer to write it first.

## Where this fits

```
ADR Nomination → ADR → **Design Doc** → Roadmap → Gitban → Execution
                        ^^^^^^^^^^^^
                        you are here
```

The full development pipeline — and the skills that drive each phase — is documented in
`.gitban/docs/development-lifecycle.md`.

The ADR already resolved the strategic question. The design doc doesn't relitigate alternatives or
justify the direction — it takes the decision as given and works out the implementation in enough
detail that anyone reading it could roadmap the work, create sprint cards, and start building.

The sprint-architect creates cards from roadmap items. This skill creates the material that makes
the sprint-architect's job straightforward rather than creative.

## Principles

These principles shape every section of the design doc. They're not aspirational — they're
structural constraints on what "done" means for the implementation.

### Done is done

Every deliverable in the design doc must have a clear, binary definition of completion. Not
"implement authentication" but "OAuth 2.1 flow works end-to-end: user clicks login, authorizes
via provider, receives access token, token is validated on subsequent requests, expired tokens
trigger re-auth." If you can't describe what "done" looks like concretely, the design isn't
detailed enough yet.

### Pure TDD

Tests are designed before implementation, not after. The design doc specifies test strategy at
every level — what's tested, what kind of test (unit, integration, contract, E2E), and what the
tests prove about the system. Implementation sections describe the test first, then the code that
makes it pass. This isn't a checkbox — it's the ordering principle for all implementation detail.

### Infrastructure as Code (IaC)

Any infrastructure the implementation requires — containers, CI/CD changes, deployment configs,
environment setup — is defined in code, version-controlled, and reproducible. The design doc calls
out every infrastructure artifact and how it's managed.

### Documentation as Code (DaC)

Documentation lives in the repo and evolves with the code. The design doc specifies what documentation
changes each phase requires — not as a trailing "update docs" task, but integrated into each
deliverable. If a phase changes behavior, the documentation update is part of that phase's definition
of done.

### Take the long route

Prefer the approach that's correct and maintainable over the approach that's fast and fragile. No
shortcuts that create tech debt. No "we'll clean this up later." If the right approach takes three
phases instead of one, the design doc should show three phases. The design doc is the place to
catch and prevent shortcuts before they become sprint cards.

## Process

### Phase 1: Absorb the ADR

Read the ADR thoroughly. Extract:

1. **The decision**: What was decided? What's the concrete outcome?
2. **The scope**: What's in and what's out? (The ADR's boundaries section and consequences)
3. **Implementation notes**: ADRs often include preliminary implementation thinking — capture it
   but don't assume it's complete or correct
4. **Validation criteria**: What the ADR says success looks like
5. **Constraints**: Related ADRs, existing patterns, or architectural boundaries that must be respected
6. **Scale assessment**: Is this a small, focused change (single phase, few files) or a large,
   multi-phase effort? The design doc's depth should match the work's complexity — don't over-engineer
   the document for a simple change, and don't under-specify a complex one.

If the ADR references other ADRs, read those too. Design decisions compound — ignoring a referenced
ADR often means violating a constraint the team already agreed to.

### Phase 2: Research the codebase

The ADR describes the target state. The codebase is the current state. The design doc bridges them.

1. **Map the affected surface**: Which files, modules, and interfaces does this work touch? Read
   the actual code — grep for the systems mentioned in the ADR, trace the call paths, understand
   the current abstractions.
2. **Identify integration points**: Where does new code connect to existing code? What interfaces
   exist? What needs to change vs. what can be extended?
3. **Find existing patterns**: How does the codebase handle similar concerns today? The implementation
   should extend existing patterns where they fit, and introduce new ones only when justified.
4. **Check the roadmap**: Use `read_roadmap` (drill one bounded level at a time) to understand where this work sits
   strategically. What story or project does it serve? What depends on it?
5. **Search for prior work**: Use `search_cards` with `include_archive: true` to find previous cards
   in this area. Check if work was started and deferred, or if there are lessons from earlier attempts.
6. **Assess test infrastructure**: What testing patterns exist? What test utilities are available?
   Understanding the test infrastructure shapes the TDD strategy.

### Phase 3: Design the implementation

This is the core of the design doc. Work through these sections in order — each builds on
the previous. The key insight: **design comes before planning**. Before you can break work
into phases, you need to know what you're building. The Design section is where the
engineering thinking happens. The Implementation Phases section is where it gets sequenced.

#### 3a: Requirements

Before designing anything, distill the ADR's decision and validation criteria into 4-8 hard
requirements. These are the top-level acceptance criteria for the entire implementation — the
things that must be true when all phases are complete. They sit above the per-phase definitions
of done and serve as the vision statement for the work.

Write them as "the implementation is complete when..." statements. Each must be binary and
testable. Derive them from:

- The ADR's **Decision** section (what was decided)
- The ADR's **Validation** section (what success looks like)
- The ADR's **Consequences** section (what trade-offs were accepted — negative consequences
  often imply requirements like "backward compatibility maintained for X")
- Your codebase research (what constraints does the current system impose)

These requirements anchor the rest of the design. Every phase should trace back to at least
one requirement. If a phase doesn't advance any requirement, it probably doesn't belong.

#### 3b: Design

This is the heart of the document. Before listing implementation steps, work out **what**
you're building and **why it's shaped this way**. This section captures the engineering
thinking that separates a design doc from a task list.

Three components, scaled to the complexity of the work:

1. **Architecture**: Component structure, data flows, integration points. Use ASCII diagrams.
   Name actual modules and interfaces, not abstract boxes. For small changes, this might be
   a paragraph. For large changes, it could be a full component diagram with data flow.

2. **Key design decisions**: The implementation-level choices you made and their rationale.
   These aren't ADR-level decisions (already resolved) — they're choices like "the CLI
   delegates to _main() via env vars to keep a single startup codepath" or "we fail fast on
   invalid GITBAN_WORKSPACE rather than falling back to walk-up." For each, explain what
   alternatives you considered and why this path wins. This is what makes the doc valuable
   beyond just "a list of things to do" — it captures reasoning that would otherwise be lost.

3. **Interface design**: For any new or modified interfaces (APIs, function signatures, env
   vars, file formats, CLI commands), define them with concrete signatures, types, error
   cases, and invariants. Code examples are more valuable than prose here. This is the
   contract that implementation must satisfy and consumers can depend on.

The design section should feel like the natural bridge between "here's what we need"
(Requirements + Target State) and "here's how we build it" (Implementation Phases). A reader
should finish the Design section understanding the shape of the solution well enough that
the implementation phases feel like obvious sequencing of work they already understand.

#### 3c: Implementation phases

Break the work into ordered phases. Each phase must be:

- **Independently deployable**: The system works after each phase (maybe with reduced functionality,
  but it works). No phase leaves the system in a broken state.
- **Testable in isolation**: Each phase has its own test suite that proves its deliverables.
- **Vertically complete**: Each phase includes its code, tests, infrastructure, and documentation.
  No separate "write tests" or "update docs" phases at the end.

For each phase, specify:

1. **Goal**: One sentence — what's true after this phase that wasn't before?
2. **Deliverables**: Concrete artifacts (files created/modified, tests added, docs updated)
3. **Test strategy**: What tests are written first? What do they prove? What kind of tests
   (unit, integration, E2E)?
4. **Infrastructure changes**: Any IaC artifacts this phase produces
5. **Documentation changes**: Any DaC artifacts this phase produces
6. **Dependencies**: What must be complete before this phase starts?
7. **Definition of done**: Binary checklist — every item is verifiable without subjective judgment

#### 3d: Migration, rollback, and risks

After the design and phases are laid out, address:

- **Migration path**: How does the system move from current to target state? If behavior
  changes, what backward compatibility is maintained? For pure additions, state explicitly.
- **Rollback plan**: Is it a clean git revert, or are there side effects?
- **Risks**: What could go wrong (technical, scope, sequencing) and specific mitigations.

### Phase 4: Write the design doc

Write the document to `docs/designs/{slug}.md`. The slug should be lowercase, hyphenated, and
descriptive of the implementation — for example, an ADR adopting an HTTP transport might map to a design doc named `remote-server-http-transport.md`.

Use the structure from Phase 3 as the document skeleton. The design doc should read as a
self-contained document — someone who hasn't read the ADR should understand what's being built
and how, though a link to the ADR provides the "why."

### Phase 5: Present and connect

After writing:

1. **Link to the roadmap.** Use `upsert_roadmap` to set `docs_ref` on the relevant feature pointing to the design doc. If the parent project already has a `docs_ref` (e.g., an ADR), link the design doc at the feature level instead.
2. **Summary**: The ADR reference, the implementation approach in 2-3 sentences, and phase count
3. **Roadmap connection**: Which roadmap items this advances, and whether the roadmap needs updating
4. **Next step**: The design doc is ready for roadmapping — the user can feed it to the
   sprint-architect or update the roadmap directly
5. **Open questions**: Anything surfaced during research that needs a decision before implementation

## Document structure

```markdown
# Design Doc: [Title matching ADR decision]

> **ADR**: [link to ADR] | **Date**: [today] | **Author**: [handle]

## Overview

[2-3 paragraphs: what this implements, what the ADR decided, and the high-level approach.
Someone skimming should know what this document covers after reading this section.]

## Requirements

[The hard requirements this implementation must satisfy. These come from the ADR's decision
and validation criteria, translated into concrete engineering terms. Each requirement is
binary — it's met or it isn't. This section is the top-level "done is done" for the entire
design, above the per-phase definitions of done.

Frame these as "the implementation is complete when..." statements:
- "All MCP tools respond identically over HTTP and stdio transports"
- "No agent skill file references deprecated profiling functions as mandatory"
- "Config file fallback chain reads both new and legacy formats"

Keep this section short — 4-8 requirements. If you have more, the scope may be too broad
for a single design doc. These requirements should be testable and directly traceable to
the ADR's decision and validation sections.]

## Current State

[How the system works today in the areas this implementation touches. Concrete — name files,
modules, patterns. This is the "before" picture.]

## Target State

[How the system will work after all phases are complete. This is the "after" picture. ASCII
diagrams for architecture, data flow, or component relationships where they clarify.

The difference between Requirements and Target State: requirements are the pass/fail
criteria (what must be true). Target state is the architectural vision (what the system
looks like). A requirement might be "HTTP transport responds within 50ms of stdio." The
target state shows the architecture diagram with both transport paths.]

## Design

[This is the heart of the document — the engineering design that bridges "where we need
to be" with "how we get there." Before listing implementation steps, explain what you're
actually building and why it's shaped this way.

### Architecture

Component structure, data flows, and how the pieces fit together. Use ASCII diagrams.
Name actual modules, files, and interfaces — not abstract boxes. Show how new components
integrate with existing ones.

### Key Design Decisions

The choices you made during design and their rationale. These aren't ADR-level decisions
(those were already made) — they're implementation-level choices:
- "The CLI command delegates to _main() via env vars rather than passing args directly,
  because this keeps a single startup codepath for both Docker and CLI usage."
- "We check GITBAN_WORKSPACE before the walk-up rather than after, because a misconfigured
  override should fail fast, not silently fall back."

Each decision should explain the alternatives you considered and why you chose this path.
This is what distinguishes a design doc from a task list — it captures the engineering
thinking that would otherwise live only in someone's head.

### Interface Design

For any new or modified interfaces (APIs, function signatures, env vars, file formats,
CLI commands), define them here with concrete signatures, types, error cases, and
invariants. Code examples are valuable — a function signature communicates more than prose.

For small designs, this section might be a few paragraphs with code snippets. For large
designs, it could include detailed interface contracts, protocol flows, and schema
definitions. Scale it to the complexity.]

## Implementation Phases

### Phase 1: [Goal]

**Deliverables:**
- [concrete artifact 1]
- [concrete artifact 2]

**Test strategy:**
- [test type]: [what it proves]

**Infrastructure:**
- [IaC artifact, or "none"]

**Documentation:**
- [DaC artifact, or "none"]

**Dependencies:** [what must exist first]

**Definition of done:**
- [ ] [verifiable condition 1]
- [ ] [verifiable condition 2]

### Phase 2: [Goal]
[same structure]

## Migration & Rollback

[Migration path, backward compatibility, rollback plan — or "N/A: pure addition"]

## Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| [risk] | [impact] | [likelihood] | [specific action] |

## Roadmap Connection

[Which story/project/feature this serves, roadmap updates needed]

## Open Questions

[Unresolved items that need decision before or during implementation]

---

## Revision History

| Date | Author | Notes |
|------|--------|-------|
| [today] | [handle] | Initial design |
```

## Scaling the document

The structure above is the full version. Scale it to match the work:

**Small ADR** (config change, single-file refactor, utility addition):
- Overview, Current State, Target State can be a paragraph each
- One phase, possibly no interface contracts section
- Migration & Rollback might be "N/A"
- Risk table might have 1-2 rows
- Total: 1-3 pages

**Medium ADR** (new feature, multi-file change, new pattern):
- Full structure, 2-4 phases
- Interface contracts for new APIs or patterns
- Total: 3-8 pages

**Large ADR** (platform feature, multi-phase initiative, new subsystem):
- Full structure, 4+ phases
- Detailed interface contracts with code examples
- Migration strategy with backward compatibility timeline
- Comprehensive risk analysis
- Total: 8-20 pages

The test is always: does the sprint-architect have enough detail to create cards without
needing to make design decisions? If yes, the design doc is detailed enough. If no, add detail
where the gaps are.

## What this is NOT

- **Not an ADR**: When an ADR exists, the decision is already made — don't relitigate alternatives.
  When no ADR exists, the Overview does a compressed version of ADR work (problem framing, a
  brief alternatives note) but stops short of a full ADR. If it grows past that, write the ADR.
- **Not a tutorial**: The audience is engineers who will build this. Don't explain fundamentals.
- **Not a sprint plan**: The design doc describes the implementation architecture. The
  sprint-architect creates the cards. Don't include card IDs, sprint tags, or step numbers.
- **Not implementation code**: Code examples illustrate interfaces and patterns. They're not
  the final implementation — the executor writes that.
