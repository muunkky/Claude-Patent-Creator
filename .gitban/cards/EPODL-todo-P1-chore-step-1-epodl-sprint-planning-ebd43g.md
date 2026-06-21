# step 1: EPODL Sprint Planning

> **Sprint**: EPODL | **Type**: chore | **Step**: 1 (first)
>
> Plans the EPODL sprint: defines the goal, the card inventory, the execution sequencing and parallelization, and the backing docs. End state: the sprint is planned and all substantive cards are in todo. Completable before any feature work begins.

## Cleanup Scope & Context

* **Sprint/Release:** EPODL — EPO/EPC law acquisition (validate-then-persist, discover-in-force, deferred-default)
* **Primary Feature Work:** Decompose approved design doc `docs/designs/epo-law-acquisition.md` into executable cards
* **Cleanup Category:** Sprint planning (card inventory, sequencing, backing-doc references)

**Required Checks:**
* [ ] Sprint/Release is identified above.
* [ ] Primary feature work that generated this cleanup is documented.

## Sprint Goal

A clean install/`setup` completes at US-corpus speed with no EU artifacts; the first EPO/PCT `search_patent_law`/analyzer call against an absent-or-invalid corpus returns immediately with US results plus an honest "acquiring in background" notice and spawns a single background acquisition; once that background acquisition + an atomic index rebuild completes, EPO/PCT queries return genuine in-force EPC and EPO Guidelines text. Junk is never persisted (validity-keyed idempotency, not existence-keyed); acquisition never tears a concurrent search.

## Backing Documents

| Doc | Path |
| :--- | :--- |
| Design Doc | `docs/designs/epo-law-acquisition.md` (approved; this sprint decomposes its 5 phases) |
| ADR | `docs/adr/ADR-001-epo-law-acquisition-architecture.md` (D1–D5) |
| PRD | `docs/prds/PRD-001-epo-law-acquisition.md` (Phases 1–3) |
| Roadmap | story `m2/s1`; project `m2/s1/epo-downloaders-fix` |

## Deferred Work Review

* [ ] Reviewed commit messages for "TODO" and "FIXME" comments added during sprint.
* [ ] Reviewed PR comments for "out of scope" or "follow-up needed" discussions.
* [ ] Reviewed code for new TODO/FIXME markers (grep for them).
* [ ] Checked team chat/standup notes for deferred items.

| Cleanup Category | Specific Item / Location | Priority | Justification for Cleanup |
| :--- | :--- | :---: | :--- |
| **Card inventory** | step 2 (Phase 0 spine + extractor free-function refactor) — `mpep_search.py`, `epo_downloaders.py` | P0 | Validity predicates + promote spine + model-load-free extractor refactor; prerequisite for ALL flows |
| **Card inventory** | step 3A (Phase 1 EPC real-PDF acquisition) — `epo_downloaders.py` | P1 | `extract_signed_epc_url` + `download_epc` on the spine; depends on step 2 |
| **Card inventory** | step 3B (Phase 2 Guidelines in-force acquisition) — `epo_downloaders.py` | P1 | Edition/section discovery + ratio-gated scrape + manifest; depends on step 2, parallel with 3A |
| **Card inventory** | step 3C (Phase 3 reader-atomic index publish) — `mpep_search.py` | P0 | `build_index`/`search` atomic under `_index_lock`; depends on step 2, parallel with 3A/3B, MUST precede step 4 |
| **Card inventory** | step 4 (Phase 4 deferred-default non-blocking wiring) — `epo_downloaders.py`, `cli.py`, `server.py`, `tools/*` | P1 | `ensure_/trigger_epo_pct_corpus`, B3 wiring, CLI flags; depends on 3A + 3B + 3C |
| **Card inventory** | step 5 (EPODL Sprint Closeout) | P1 | Mandatory closeout; final step |

## Cleanup Checklist

### Documentation Updates (optional)

| Task | Status / Details | Done? |
| :--- | :--- | :---: |
| **Card inventory recorded** | 5 substantive cards (step 2, 3A, 3B, 3C, 4) + planning + closeout | - [ ] |
| **Sequencing recorded** | step 1 → step 2 (P0) → {3A, 3B, 3C(P0)} → step 4 → step 5 | - [ ] |
| **Backing docs linked** | design doc / ADR-001 / PRD-001 referenced on each card | - [ ] |
| **Other:** Roadmap connection | story `m2/s1`, project `m2/s1/epo-downloaders-fix` | - [ ] |

### Testing & Quality (optional)

| Task | Status / Details | Done? |
| :--- | :--- | :---: |
| **Test plan per card** | each substantive card carries a TDD test plan from the design doc's per-phase test strategy | - [ ] |
| **Fixtures planned** | `tests/fixtures/` (EPC PDFs, landing/entry HTML, guidelines txt + manifest) introduced in step 2 | - [ ] |
| **Other:** runner | cards default to `.venv/Scripts/python.exe -m pytest tests/` | - [ ] |

## Validation & Closeout

### Pre-Completion Verification

| Verification Task | Status / Evidence |
| :--- | :--- |
| **All P0 Items Complete** | step 2 and step 3C planned as P0 with explicit dependencies |
| **All P1 Items Complete or Ticketed** | step 3A, 3B, 4, 5 planned as P1 |
| **Tests Passing** | N/A for planning card — substantive cards carry test plans |
| **No New Warnings** | N/A for planning card |
| **Documentation Updated** | backing docs referenced on every card |
| **Code Review** | N/A for planning card |

### Follow-up & Lessons Learned

| Topic | Status / Action Required |
| :--- | :--- |
| **Remaining P2 Items** | None — sprint is P0/P1 only |
| **Recurring Issues** | Incremental index-add deferred per design doc Open Question 2 (not in scope) |
| **Process Improvements** | EPC fixture provenance (design doc Open Question 1) resolved in step 2 (trimmed PDF or injected floors) |
| **Technical Debt Tickets** | Holder-object corpus snapshot noted as cleaner long-term shape (KD9) — follow-up, not v1 |

### Completion Checklist

<!-- gate0: upper-checklist -->

* [ ] All P0 items are complete and verified. <!-- cite: -->
* [ ] All P1 items are complete or have follow-up tickets created. <!-- cite: -->
* [ ] P2 items are complete or explicitly deferred with tickets. <!-- cite: -->
* [ ] All tests are passing (unit, integration, and regression). <!-- cite: -->
* [ ] No new linter warnings or errors introduced. <!-- cite: -->
* [ ] All documentation updates are complete and reviewed. <!-- cite: -->
* [ ] Code changes (if any) are reviewed and merged. <!-- cite: -->
* [ ] Follow-up tickets are created and prioritized for next sprint. <!-- cite: -->
* [ ] Team retrospective includes discussion of cleanup backlog (if significant). <!-- cite: -->

### Note on validation

This card follows a structured template. Keep its sections, checkboxes, and tables and fill them in rather than removing them.
