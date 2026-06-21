# step 4 Phase 4 — Deferred-default, non-blocking, background EPO/PCT wiring

> **Sprint**: EPODL | **Type**: feature | **Step**: 4 | **Priority**: P1
>
> Design doc Phase 4 (PRD Phase 3, ADR-001 D4 + B1b/KD6/KD7 + B3 + S2). Depends on: step 3A (`ihuscq` — `download_epc`), step 3B (`y9ulpc` — `scrape_epo_guidelines`), AND step 3C (`a5aivr` — reader-atomic `build_index`; the trigger relies on the atomic publish). Final substantive card before closeout (step 5).
>
> **Packed-card note (sprint-architect packed-card rule):** this card wires three independently-observable surfaces (deferred background trigger on `search_patent_law`; analyzer chokepoint; `--with-epo`/`--skip-epo` CLI flags) onto ONE shared `trigger_/ensure_epo_pct_corpus` machinery. They are not independently shippable — they only make sense composed as "the single way EU law is acquired on demand" (semantic atomicity) and share the same integration fixture (clean `MPEP_DIR` + monkeypatched downloaders). Per the rule, each user-visible sub-feature STILL carries its own capstone below; the shared fixture is not a license to share a capstone.

## Required Reading

| What | Where | Why |
| :--- | :--- | :--- |
| Design doc Phase 4 | `docs/designs/epo-law-acquisition.md` lines 802-866 | Deliverables, test strategy, DoD |
| KD6/KD7 (non-blocking bg trigger) + orchestration interface | `docs/designs/epo-law-acquisition.md` lines 338-370, 560-593 | `ensure_/trigger_epo_pct_corpus` signatures + guard semantics |
| B3 wiring | `docs/designs/epo-law-acquisition.md` lines 138-149, 813-814 | `register_patent_law_tools` gains `mpep_dir`; server.py:407; `MPEP_DIR` from `mpep_search` to avoid `tools → server` cycle |
| S2 analyzer chokepoint | `docs/designs/epo-law-acquisition.md` lines 151-154, 239-244 | Analyzers call the same trigger before `mpep_index.search(...)` |
| CLI surface | `docs/designs/epo-law-acquisition.md` lines 595-605 | `--with-epo`/`--skip-epo` mutually exclusive; `PATENT_SKIP_EPO` |
| Trigger site rationale | `docs/designs/epo-law-acquisition.md` lines 351-362 | Why `search_patent_law` (not `build_index`/`search`); `jurisdiction=None` does NOT trigger |
| `search_patent_law` | `mcp_server/tools/patent_law_tools.py`; call site `server.py:407` | Deferred trigger insertion + registration signature |
| Analyzer tools | `mcp_server/tools/epo_analyzer_tools.py:78,113,171,208` | Direct `mpep_index.search` calls to gate |
| CLI commands | `mcp_server/cli.py` `setup_command:432`, `rebuild_index_command:851`, `download_all_command:889`; `server.py:507-519` | Flag wiring + dedupe |

## Feature Overview & Context

* **Associated Ticket/Epic:** EPODL sprint; roadmap `m2/s1/epo-downloaders-fix`; design doc Phase 4
* **Feature Area/Component:** EPO/PCT acquisition wiring — `epo_downloaders.py`, `cli.py`, `server.py`, `tools/patent_law_tools.py`, `tools/epo_analyzer_tools.py`
* **Target Release/Milestone:** EPODL sprint

**Required Checks:**
* [ ] **Associated Ticket/Epic** link is included above.
* [ ] **Feature Area/Component** is identified.
* [ ] **Target Release/Milestone** is confirmed.

## Documentation & Prior Art Review

* [ ] `README.md` or project documentation reviewed.
* [ ] Existing architecture documentation or ADRs reviewed.
* [ ] Related feature implementations or similar code reviewed.
* [ ] API documentation or interface specs reviewed [if applicable].

| Document Type | Link / Location | Key Findings / Action Required |
| :--- | :--- | :--- |
| **Design Doc** | `docs/designs/epo-law-acquisition.md` Phase 4 | Non-blocking bg trigger, analyzer chokepoint, B3 wiring, CLI flags, integration test |
| **ADR** | `docs/adr/ADR-001-...md` D4 | Deferred-default "capability on demand" |
| **CLAUDE.md** | `CLAUDE.md` Quick Reference / Skills | Document EPO/PCT acquires in background on first use; `--with-epo`/`--skip-epo`; correct PRD-001 "no consolidated PDF" line |
| **Similar Code** | `epo_downloaders.py` spine + flows (steps 2/3A/3B); atomic `build_index` (step 3C) | `ensure_epo_pct_corpus` calls `build_index(force_rebuild=True)` (atomic) |

## Design & Planning

### Initial Design Thoughts & Requirements

* `ensure_epo_pct_corpus(mpep_dir, index, mode="background")`: validate each target (EPC/Guidelines/PCT); acquire absent-or-invalid; if anything acquired call `index.build_index(force_rebuild=True)` (atomic, KD9); return `{"acquired":[...],"skipped":[...],"failed":[{source,reason}],"rebuilt":bool}`. Non-fatal: per-source failures collected/logged, never raised. `mode="eager"` is the synchronous `--with-epo`/`download-all` path.
* `trigger_epo_pct_corpus(mpep_dir, index, jurisdiction)`: honors `PATENT_SKIP_EPO` (returns None — hard US-only); returns None if corpus already valid; else under the process-lifetime lock, if no acquisition started set the started-flag and spawn a `daemon` Thread running `ensure_epo_pct_corpus(mode="background")` (reset flag on failure so a later call retries); return the "acquiring in background" notice. Called by BOTH `search_patent_law` and `epo_analyzer_tools`.
* `search_patent_law`: on `jurisdiction in {EPO,PCT}` against an absent/invalid corpus and not `PATENT_SKIP_EPO`, call the trigger and RETURN IMMEDIATELY with US results + the notice. `jurisdiction=None` does NOT trigger.
* B3: widen `register_patent_law_tools(...)` to accept `mpep_dir`; update `server.py:407` to pass it, sourced from `mpep_search.MPEP_DIR` (no `tools → server` import cycle).
* CLI: `--with-epo`/`--skip-epo` mutually-exclusive on `setup`/`rebuild-index`; synchronous eager call in those commands; `download_all_command` runs `ensure_epo_pct_corpus(mode="eager")`; `server.py` `--download-epo` path delegates to `ensure_epo_pct_corpus` (dedupe). `--skip-epo` sets `PATENT_SKIP_EPO=true`.

### Acceptance Criteria

* [ ] Default `setup` runs no EPO scrape and leaves no EU artifacts.
* [ ] First `search_patent_law(jurisdiction="EPO")` against an empty corpus returns immediately (before the stubbed slow acquisition finishes) with US results + an "acquiring in background" notice and spawns exactly one acquisition thread.
* [ ] After the background acquisition completes (thread joined deterministically), a subsequent EPO query returns non-empty EU results.
* [ ] Analyzer tools (`epo_analyzer_tools.py`) call the shared `trigger_epo_pct_corpus` chokepoint and surface the "still acquiring / run an EPO search first" hint on an empty corpus (S2).
* [ ] `register_patent_law_tools` receives `mpep_dir` (B3); the `server.py:407` call site passes it; no import cycle.
* [ ] Re-trigger with valid artifacts re-acquires nothing and does not rebuild (network call count 0); a corrupted artifact re-acquires.
* [ ] `--with-epo` forces synchronous eager acquisition; `--skip-epo`/`PATENT_SKIP_EPO` disables acquisition (hard US-only, even in background).
* [ ] The process-lifetime guard spawns exactly one thread across two near-simultaneous EPO queries; a failed background attempt resets the flag so a later query retries (KD7).

## Definition of Done

### Intent

A user who installs the package and never touches European law pays nothing — `setup` finishes at US speed with no EU files. The moment a user actually asks for European law (an EPO/PCT search or an EPO analyzer call), the system answers instantly with whatever US results it has plus an honest "I'm fetching the EU corpus in the background, try again in a few minutes" notice, and kicks off a single background acquisition; once that finishes, the next EU query returns real EPC and EPO Guidelines text. An operator who wants to pre-pay can pass `--with-epo` for a synchronous build, or `--skip-epo` to stay US-only forever. If this breaks, a user would notice either that their first EPO query hangs for minutes (background trigger failed to defer) or that EPO queries forever return empty with no explanation (acquisition never fires or never recovers).

### Observable outcomes

- [ ] `ensure_epo_pct_corpus` validates each source, acquires only absent-or-invalid ones, calls `build_index(force_rebuild=True)` iff anything was acquired, and returns the structured per-source result; per-source failures are collected, not raised.
- [ ] `register_patent_law_tools` accepts `mpep_dir`; `server.py:407` passes `mpep_search.MPEP_DIR`; importing the tools package raises no circular-import error.
- [ ] The process-lifetime guard spawns exactly one background thread across two near-simultaneous EPO queries; a forced background failure resets the started-flag so a later query retries.
- [ ] `PATENT_SKIP_EPO=true` (and `--skip-epo`) makes the trigger a no-op (US-only, no background spawn); `mode="eager"` forces synchronous acquisition.
- [ ] CLAUDE.md and the relevant skill/slash-command docs state EPO/PCT acquires in the background on first use (first query returns a notice; retry after it completes), `--with-epo` for synchronous eager, `--skip-epo` for US-only; the PRD-001 false "no consolidated PDF" line is corrected.
- [ ] Capstone (deferred background trigger): given a clean `MPEP_DIR` with US-only artifacts and an artificially-slow stubbed acquisition, `search_patent_law(jurisdiction="EPO")` returns BEFORE the acquisition finishes, carrying US results plus the "acquiring in background" notice and having spawned exactly one daemon thread; after the thread is joined (synthetic EPC/Guidelines fixtures + the real atomic `build_index` on tiny corpora), a second `search_patent_law(jurisdiction="EPO")` returns non-empty EU results.
- [ ] Capstone (analyzer chokepoint, S2): given the same empty EU corpus, calling an `epo_analyzer_tools` tool that reaches EU law calls `trigger_epo_pct_corpus` (spawning/observing the same single acquisition) and returns the "still acquiring / run an EPO search first" hint rather than a blank analysis; after acquisition completes, the analyzer returns real EU-law-grounded output.
- [ ] Capstone (CLI flags): `setup --with-epo` against a clean `MPEP_DIR` (monkeypatched downloaders) runs `ensure_epo_pct_corpus(mode="eager")` SYNCHRONOUSLY and the command does not return until EU artifacts are present and valid; `setup --skip-epo` sets `PATENT_SKIP_EPO=true`, performs no acquisition, leaves no EU artifacts, and a subsequent EPO query (with the skip env still set) returns US-only with no background spawn; `setup` with neither flag performs no eager acquisition and leaves no EU artifacts.

## Feature Work Phases

| Phase / Task | Status / Link to Artifact or Card | Universal Check |
| :--- | :--- | :---: |
| **Design & Architecture** | Design doc Phase 4 + KD6/KD7/B3/S2 | - [ ] Design Complete |
| **Test Plan Creation** | `tests/test_epo_acquisition_integration.py` (written first) | - [ ] Test Plan Approved |
| **TDD Implementation** | `ensure_/trigger_epo_pct_corpus`; trigger in search; analyzer chokepoint; B3; CLI flags; server dedupe | - [ ] Implementation Complete |
| **Integration Testing** | Clean build → non-empty EU corpus; skip/eager/valid/corrupted paths | - [ ] Integration Tests Pass |
| **Documentation** | CLAUDE.md + skills/slash-commands; correct PRD-001 line | - [ ] Documentation Complete |
| **Code Review** | Sprint reviewer | - [ ] Code Review Approved |
| **Deployment Plan** | Merged to sprint branch | - [ ] Deployment Plan Ready |

## TDD Implementation Workflow

| Step | Status/Details | Universal Check |
| :---: | :--- | :---: |
| **1. Write Failing Tests** | non-blocking trigger, one-thread guard, B3, S2, integration | - [ ] Failing tests are committed and documented |
| **2. Implement Feature Code** | orchestration + trigger + wiring across 5 files | - [ ] Feature implementation is complete |
| **3. Run Passing Tests** | Suite green | - [ ] Originally failing tests now pass |
| **4. Refactor** | Dedupe server flag path through `ensure_epo_pct_corpus` | - [ ] Code is refactored for clarity and maintainability |
| **5. Full Regression Suite** | `pytest tests/` green; `-m "not slow"` deselects heavy embed | - [ ] All tests pass (unit, integration, e2e) |
| **6. Performance Testing** | First EPO query returns without blocking (asserted) | - [ ] Performance requirements are met |

### Implementation Notes

**Test Strategy:** Integration tests use monkeypatched downloaders/scrape and a temp `MPEP_DIR`; the background thread is joined deterministically (no sleeps). The real embedding/index build path is marked `slow` so CI can `-m "not slow"`. The "returns without blocking" assertion uses an artificially-slow stubbed acquisition and checks the call returns first.

**Key Implementation Decisions:** Single shared `trigger_epo_pct_corpus` chokepoint for both `search_patent_law` and the analyzers (S2). `MPEP_DIR` sourced from `mpep_search` to avoid a `tools → server` import cycle (B3). `ensure_epo_pct_corpus` calls the now-atomic `build_index` (depends on step 3C).

## Validation & Closeout

| Task | Detail/Link |
| :--- | :--- |
| **Code Review** | Sprint reviewer |
| **QA Verification** | `tests/test_epo_acquisition_integration.py` |
| **Staging Deployment** | N/A (verified via integration tests) |
| **Production Deployment** | Sprint branch |
| **Monitoring Setup** | Per-source log: edition, sizes, counts, pass/fail; bg-thread start/finish/failure |

### Follow-up & Lessons Learned

| Topic | Status / Action Required |
| :--- | :--- |
| **Postmortem Required?** | No |
| **Further Investigation?** | Incremental index-add (design doc Open Question 2) deferred — full re-embed acceptable for v1 |
| **Technical Debt Created?** | No |
| **Future Enhancements** | Incremental "add EU chunks" path (follow-up, not in scope) |

### Completion Checklist

* [ ] All acceptance criteria are met and verified.
* [ ] All tests are passing (unit, integration, e2e, performance).
* [ ] Code review is approved and PR is merged.
* [ ] Documentation is updated (README, API docs, user guides).
* [ ] Feature is deployed to production.
* [ ] Monitoring and alerting are configured.
* [ ] Stakeholders are notified of completion.
* [ ] Follow-up actions are documented and tickets created.
* [ ] Associated ticket/epic is closed.

### Note on validation

This card follows a structured template. Keep its sections, checkboxes, and tables and fill them in rather than removing them.
