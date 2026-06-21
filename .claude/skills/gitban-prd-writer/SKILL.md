---
name: gitban-prd-writer
description: >
  Generates a Product Requirements Document (PRD) for a roadmap story or major project, written
  to docs/prds/. Takes a product goal, user problem, or strategic initiative and produces a PRD that
  bridges product vision with technical execution. Use this skill whenever the user mentions writing
  a PRD, defining product requirements, documenting a feature vision, planning a story's strategy,
  or needs to articulate what to build and why before diving into architecture. Also trigger when the
  user says "product requirements", "feature spec", "product spec", "what should we build", or wants
  to define the scope and success criteria for a body of work at the roadmap level.
---

You produce Product Requirements Documents that sit at the top of the planning hierarchy. The user
gives you a product goal — sometimes just a sentence about a problem or opportunity — and you
research, reason, and deliver a PRD that makes the vision concrete enough to drive ADRs, design
docs, and sprint work.

## Where this fits

```
**PRD** → ADR → Design Doc → Roadmap → Gitban → Execution
^^^^^^^^
you are here
```

The full development pipeline — and the skills that drive each phase — is documented in
`.gitban/docs/development-lifecycle.md`.

The PRD answers **what** to build and **why it matters** — from both the user's perspective and the
business/project perspective. It doesn't make architectural decisions (that's the ADR) or plan
implementation (that's the design doc). It defines the product surface: who it's for, what problems
it solves, what success looks like, and in what order to deliver value.

A good PRD makes ADR writing mechanical — the architectural questions become obvious because the
product constraints are clear. A bad PRD (or no PRD) means the team argues about scope and
priorities inside technical discussions where those arguments don't belong.

## Why PRDs matter

PRDs are the connective tissue between "we should do X" and "here's the plan." Without them,
roadmap items are just titles — nobody knows what "authentication hardening" actually means in
terms of user experience, scope boundaries, or success criteria. Teams end up discovering product
requirements mid-sprint, which causes scope creep, rework, and misaligned expectations.

A PRD doesn't need to be long. It needs to be clear. The test: could someone who wasn't in the
room when the idea was discussed read this document and understand what we're building, who it's
for, why it matters, and how we'll know it worked?

## Process

### Phase 1: Understand the opportunity

The user's input might be a vague idea, a specific pain point, a strategic directive, or a
well-formed feature concept. Your job is to find the underlying product opportunity.

1. **Parse the user's statement** for the core need. Who has a problem? What's the problem?
   What's the current workaround? What's the cost of not solving it?
2. **Challenge the framing**. The user often describes a solution when they mean a problem.
   - Is this the right problem to solve, or a symptom of a deeper issue?
   - Is the scope right — too narrow (treating symptoms) or too broad (boiling the ocean)?
   - Are there assumptions about users, usage patterns, or priorities baked into the request?
   Surface these before committing to a direction.
3. **Research the codebase and roadmap** to understand context:
   - Check the roadmap (use `read_roadmap`) for where this fits strategically — is it a new
     story, part of an existing one, or a project within an existing story? **Record
     the exact roadmap path** (e.g., `m1.2/s2/project-name`) and use it in the PRD header.
     Do not guess the path from memory — verify it.
   - Search existing PRDs in `docs/prds/` for related product decisions
   - Search ADRs in `docs/adr/` for prior technical decisions that constrain or inform this
     work. **If accepted ADRs exist in this area, the PRD's scope must align with them.** A
     PRD that contradicts an accepted ADR sends engineers into a conflict they shouldn't have
     to resolve. If you disagree with the ADR, flag it as an open question — don't silently
     override it in the PRD scope.
   - Look at existing cards for related in-flight or completed work
   - **Read the actual code** in the affected area. This is not optional and cannot be skimmed.
     The current state description in the PRD is the foundation every downstream artifact
     builds on — if it's wrong, the entire plan is wrong. Specifically:
     - Verify any quantitative claims (file counts, line counts, duplication estimates) by
       counting the actual files or lines in the codebase. Off-by-one errors in inventory
       tables erode confidence in the entire analysis.
     - Check whether any of the proposed work has already been partially implemented. A PRD
       that reads as entirely future-tense when half the infrastructure already exists will
       cause engineers to either duplicate work or waste time discovering what's already built.
     - Note the exact function names, file paths, and module structures that the PRD's scope
       affects — this grounds the document in verifiable reality.
4. **Research the market and ecosystem** using available documentation tools:
   - How do comparable tools/projects handle this problem space?
   - What do users of similar tools expect? What's table-stakes vs. differentiating?
   - Are there standards, conventions, or ecosystem norms that apply?
   - What can we learn from projects that solved this well — or poorly?
5. **Identify the user segments**. Who actually needs this? Be specific. "Developers" is not
   a user segment. "Solo developers using MCP servers for personal project management" is.
   Different segments have different needs, and the PRD must be clear about who it prioritizes.

If critical context is missing and you can't infer it, ask the user — but keep questions
focused. Prefer one round of 2-3 targeted questions over a long interview.

### Phase 2: Define the product surface

This is where you make the vision concrete. Work through these elements:

1. **Problem statement**: One paragraph that captures the core problem in terms the user
   (not the developer) would recognize. This is the "elevator pitch" for why this work exists.

2. **User stories / jobs to be done**: What does the user want to accomplish? Frame these as
   outcomes, not features. "As a team lead, I can see which agents are blocked so I can
   unblock them" — not "add a blocked status filter to the dashboard."

3. **Scope boundaries**: What's IN and what's OUT. This is one of the most valuable parts of
   a PRD. Being explicit about what you're NOT building prevents scope creep and sets
   expectations. Include the reasoning — "X is out of scope because Y, but could be revisited
   in Z timeframe."

4. **Success criteria**: How will we know this worked? Define metrics or observable outcomes
   that are specific enough to evaluate. "Users can complete the workflow" is weak. "A new
   user can go from zero to a working board with cards in under 5 minutes without reading
   documentation" is strong.

5. **User experience flow**: Walk through the key interactions. Not wireframes — but the
   narrative of what happens when a user encounters this feature. What do they see? What do
   they do? What feedback do they get? Where do they go next? For CLI/API tools, this means
   the command sequences, the output formats, the error messages.

### Phase 3: Sequence the delivery

PRDs aren't just feature specs — they define how value gets delivered over time. This is what
makes them strategic rather than just descriptive.

1. **Identify the value milestones**: What's the minimum that delivers real value? What comes
   next? Break the work into phases where each phase is independently useful — not just
   "technically complete" but actually valuable to the user.

2. **Define the launch criteria** for each phase: What must be true before this phase ships?
   This includes quality bars, documentation requirements, migration needs, and any
   prerequisites from other work.

3. **Map dependencies**: What existing work, decisions, or infrastructure does each phase
   depend on? What ADRs need to be written? What design docs are needed? Call out the
   decision points explicitly — "Phase 2 requires an ADR on the storage model before
   implementation can begin."

4. **Identify risks and open questions**: Product risks, not just technical risks. Will users
   actually want this? Is the adoption path clear? Are there regulatory, compatibility, or
   ecosystem risks? What questions need answers before committing to later phases?

### Phase 4: Write the PRD

Write to `docs/prds/PRD-XXX-{slug}.md`. Number sequentially based on existing PRDs. The slug
should be lowercase, hyphenated, and descriptive of the product capability — not the
implementation approach.

If writing more than one PRD, dispatch each to a separate worktree agent so they can be
written in parallel.

### Phase 5: Present and connect

After writing:

1. **Link to the roadmap.** Use `upsert_roadmap` to set `docs_ref` on the relevant story
   or project pointing to the PRD. PRDs typically live at the story level — they describe
   a body of work, not a single card.
2. Present the user with:
   - The file path of the created PRD
   - A brief summary of the product vision and key scope decisions
   - The phasing strategy and what Phase 1 delivers
   - Recommended next steps: which ADRs need writing, which design docs are needed
   - Any open questions or risks that need stakeholder input

## PRD structure

```markdown
# PRD-XXX: [Product Capability Title]

> **Status**: Draft | **Date**: [today] | **Author**: [handle]
> **Roadmap**: [path in roadmap, e.g., m1/s2/project-name]

## Problem Statement

[One paragraph: What problem exists? Who has it? What's the cost of not solving it?
Written from the user's perspective — they should recognize their own pain here.
Avoid technical jargon unless the users are technical.]

## Background & Context

[Why now? What changed — in the project, the ecosystem, or user needs — that makes
this the right time to address this problem? Include relevant prior art: what we've
tried before, what competitors/peers do, what users have asked for.

This section grounds the PRD in reality. A reviewer should finish it understanding
the landscape well enough to evaluate whether the proposed solution makes sense.]

## User Segments

[Who specifically benefits from this work? Define each segment concretely:]

### [Segment Name]
- **Who**: [Specific description]
- **Current pain**: [What they struggle with today]
- **Desired outcome**: [What they want to be true]
- **Priority**: [Primary / Secondary / Tertiary]

## Goals & Non-Goals

### Goals
- [Outcome-oriented goal, not a feature description]
- [Each goal should be independently evaluable]

### Non-Goals
- [What this work explicitly does NOT address, and why]
- [Non-goals prevent scope creep — be generous here]

## User Experience

[Walk through the key interactions for the primary user segment. This isn't a UI
spec — it's the narrative of how the feature works from the user's perspective.

For CLI tools: show the command sequences, inputs, outputs, and error cases.
For APIs: show the request/response flow and key decision points.
For workflows: show the end-to-end journey with decision branches.

Use concrete examples with realistic data. Abstract descriptions like "the user
configures their settings" fail to surface real design questions.]

### Scenario 1: [Name]
[Concrete walkthrough]

### Scenario 2: [Name]
[Concrete walkthrough]

### Error & Edge Cases
[What happens when things go wrong? How does the user recover?]

## Success Criteria

[Specific, measurable outcomes that define "this worked." Each criterion should be
evaluable without subjective judgment:]

| Criterion | Measurement | Target |
|-----------|-------------|--------|
| [What] | [How measured] | [Threshold] |

## Scope & Boundaries

### In Scope
- [Capability with brief justification]

### Out of Scope
- [Capability] — [Why it's excluded and when it might be revisited]

### Future Considerations
- [Things we're intentionally deferring but want to design for]

## Delivery Phases

### Phase 1: [Value Statement — what the user can do after this phase]

**What ships:**
- [Concrete deliverable]

**Launch criteria:**
- [What must be true before this phase is considered complete]

**Decisions needed:**
- [ADRs, design docs, or stakeholder decisions required]

**Dependencies:**
- [What must exist first]

### Phase 2: [Value Statement]
[Same structure]

## Technical Considerations

[Product-relevant technical context — not architecture (that's the ADR) but
constraints and opportunities the product vision needs to account for:

- Platform constraints that affect the user experience
- Performance characteristics users will notice
- Compatibility requirements (backward compat, migration paths)
- Security or privacy implications for the user
- Integration points with existing workflows
- Observability: how will the team know this feature is working after launch?
  For pipelines, background processes, or anything that runs without a user
  watching, monitoring and alerting requirements are product requirements —
  silent failure is a product failure.

This section gives ADR authors the product context they need to make good
architectural decisions.]

## Risks & Open Questions

### Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| [Product/adoption risk] | [Impact] | [Likelihood] | [Strategy] |

### Open Questions
- [Question that needs answering before or during implementation]
- [Include who should answer it and what the decision affects]

## Related Documents

- [Links to related PRDs, ADRs, design docs, or external references]
- [This section must be exhaustive. An engineer using this PRD as their starting point
  will follow these links to understand the full decision chain. A missing ADR reference
  means the engineer may re-derive a decision that was already made — or worse, make a
  conflicting one. Search docs/adr/ for every ADR that touches this product area.]

---

## Revision History

| Date | Author | Notes |
|------|--------|-------|
| [today] | [handle] | Initial draft |
```

## Quality standards

The ultimate test of a PRD: **could an engineer who has never discussed this feature read
this document and build the right thing?** Not because the PRD is prescriptive about
implementation, but because the problem, the users, the desired experience, the scope
boundaries, and the success criteria are unambiguous enough that two independent engineers
would build roughly the same product from it. Every quality standard below serves this test.

These separate a useful PRD from a feature wishlist:

**Problem Statement**: A user who doesn't know the project should understand the pain after
reading this section. If they can't, the problem isn't well-articulated. The test: would the
target user read this and say "yes, that's exactly my frustration"?

**User Experience section**: This is the PRD's secret weapon. Abstract requirements hide design
questions. Walking through concrete scenarios surfaces them. If you can write the UX section
without making difficult choices, the PRD isn't detailed enough.

**Scope boundaries**: Every PRD should have more non-goals than goals. The discipline of saying
"no" is what makes a product vision actionable. A PRD that includes everything is a wish list,
not a plan. Each non-goal should explain the reasoning — "not now because X" gives future
readers the context to revisit the decision.

**Success criteria**: Specific enough that two people would agree on whether they've been met.
"Improved developer experience" is not a criterion. "New users can create their first card
without consulting documentation" is.

**Delivery phases**: Each phase must deliver user-visible value, not just technical progress.
"Set up the database schema" is not a product phase — it's an implementation step. "Users can
create and view items" is a product phase that happens to require a database schema.

**Technical considerations**: This section is the handoff to ADR authors. It should capture
every product constraint that has architectural implications — without prescribing the
architecture. "Users expect sub-second response times for board operations" is a product
constraint. "Use Redis for caching" is an architectural prescription that belongs in an ADR.

## What to avoid

- **Solutioning too early**: The PRD describes the problem and the desired outcome. Specific
  technical approaches belong in ADRs. If you're writing "we will use X framework" in a PRD,
  you've crossed the line.
- **Vague user segments**: "Developers" or "teams" aren't segments. Be specific about who,
  what they do, and why they care.
- **Feature lists masquerading as requirements**: "Add a dashboard" is a feature. "Team leads
  can see blocked work at a glance" is a requirement. PRDs deal in requirements.
- **Ignoring the current state**: A PRD that doesn't acknowledge what exists today will
  produce unrealistic plans. The delta between current and desired state is the actual work.
  This is the single most common failure mode. Verify every factual claim about the current
  system against the codebase — file counts, feature availability, API behavior. A PRD that
  says "the system cannot do X" when the code shows it can is worse than no PRD at all.
- **Contradicting accepted ADRs**: If an ADR has been accepted for this product area, the
  PRD's scope must be consistent with it. A PRD that says "convert all 7 agent files to
  templates" when the ADR decided agent files stay static sends engineers into a conflict.
  Check every accepted ADR in the affected area and ensure alignment.
- **Incomplete Related Documents**: Every ADR, PRD, and design doc that touches this product
  area should be linked. An engineer using the PRD as their entry point will follow these
  links to build their understanding. A missing link means a missing decision.
- **Phases without independent value**: If Phase 1 only makes sense once Phase 2 ships, the
  phasing is wrong. Each phase must be worth shipping on its own.
- **Missing the "why now"**: Every PRD should justify its timing. If there's no compelling
  reason to do this now, it might not be the right priority.

## Scaling the document

Not every product decision needs a 10-page PRD:

**Small feature** (single capability, clear scope):
- Problem statement, goals/non-goals, UX walkthrough, success criteria
- Single phase, light technical considerations
- Total: 1-3 pages

**Medium initiative** (multiple capabilities, cross-cutting concern):
- Full structure, 2-3 phases
- Detailed UX scenarios and edge cases
- Total: 3-8 pages

**Major milestone** (strategic initiative, multi-phase delivery):
- Full structure, 3+ phases
- Multiple user segments with prioritization
- Comprehensive risk analysis and competitive context
- Total: 8-15 pages

The test: does an ADR author have enough product context to make architectural decisions
without guessing at requirements? Does a sprint architect know what to build first and why?
If yes, the PRD is detailed enough.

## Relationship to other documents

- **Roadmap**: The PRD elaborates on a roadmap story or project. The roadmap stays lean
  (titles, statuses, sequencing). The PRD provides the depth. Link them via `docs_ref`.
- **ADRs**: ADRs resolve architectural questions that arise from PRD requirements. The PRD's
  technical considerations section is the input to ADR writing. A PRD might spawn multiple
  ADRs for different architectural questions.
- **Design docs**: Design docs translate ADR decisions into implementation plans. They
  reference the PRD for product context but don't duplicate it.
- **Sprint cards**: Cards reference the roadmap (which links to the PRD). Cards don't
  reference PRDs directly — the roadmap is the connection point.
