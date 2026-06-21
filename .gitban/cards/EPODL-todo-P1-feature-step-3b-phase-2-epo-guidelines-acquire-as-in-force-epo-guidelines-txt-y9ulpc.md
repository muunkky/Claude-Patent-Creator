# step 3B Phase 2 — EPO Guidelines acquire as in-force epo_guidelines.txt

> **Sprint**: EPODL | **Type**: feature | **Step**: 3B | **Priority**: P1
>
> Design doc Phase 2 (PRD Phase 2, ADR-001 D3/D5). Depends on: step 2 (`wp8iqb` — spine + `validate_guidelines` + constants `MIN_DISCOVERED`/`SUCCESS_RATIO_FLOOR`/`RESUME_MAX_ROUNDS`/`PART_LETTERS`). Parallel-safe with step 3A (`epo_downloaders.py`, different functions) and step 3C (`mpep_search.py`). Unblocks: step 4.

## Required Reading

| What | Where | Why |
| :--- | :--- | :--- |
| Design doc Phase 2 | `docs/designs/epo-law-acquisition.md` lines 712-760 | Deliverables, test strategy, DoD |
| KD4/KD5/S1/S3 + Guidelines flow | `docs/designs/epo-law-acquisition.md` lines 319-336, 497-558 | Edition discovery, seed strategy, ratio gate, manifest schema, GONE/resume |
| ADR-001 D3/D5 | `docs/adr/ADR-001-epo-law-acquisition-architecture.md` | Why discover-in-force + manifest-first |
| Prototype to promote | `scripts/_epo_guidelines_scrape.py` | Source of discovery/fetch/format; `YEAR` hardcode (`:15`), `PART_TITLES["c"]` typo (`:21`) |
| Current `scrape_epo_guidelines` | `mcp_server/epo_downloaders.py:169` | Draft-PDF path + existence skip to delete; spine rewire |
| Guidelines extractor (round-trip target) | `mcp_server/mpep_search.py:553` | Emitted `.txt` must parse under `PART X - TITLE` / `### {title} [{stem}]` |

## Feature Overview & Context

* **Associated Ticket/Epic:** EPODL sprint; roadmap `m2/s1/epo-downloaders-fix`; design doc Phase 2
* **Feature Area/Component:** EPO Guidelines acquisition — `mcp_server/epo_downloaders.py`
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
| **Design Doc** | `docs/designs/epo-law-acquisition.md` Phase 2 | Discover edition (raw-HTML, highest year, fail-loud), discover A-H sections (seed strategy + `MIN_DISCOVERED`), fetch with pacing/retry, ratio gate, manifest-first write |
| **ADR** | `docs/adr/ADR-001-...md` D3/D5 | Entry page parse is the second documented repair location |
| **Prototype** | `scripts/_epo_guidelines_scrape.py` | Promote in; fix `YEAR` hardcode + `PART_TITLES["c"]` typo; add validation; then DELETE the script |
| **Manifest schema** | `docs/designs/epo-law-acquisition.md` lines 540-558 | `{edition, discovered, gone_404, fetched, with_content, failed_sections, resume_rounds, ratio, completed_at}` |

## Design & Planning

### Initial Design Thoughts & Requirements

* Requirement: `discover_in_force_edition(entry_html=None)` GETs `EPO_GUIDELINES_ENTRY_URL` raw HTML, extracts every `…/legal/guidelines-epc/(\d{4})/…` link, returns the highest year; raises a source-named error on unreachable page or no year link (NO hardcoded fallback). `--guidelines-edition`/`edition=` is the logged override.
* Requirement: `discover_section_urls(edition, seed_html=None)` scopes to `GUIDELINES_PART_LETTERS` (`a-h`; `i/j/k/m` excluded). Seed from the edition index when it embeds the full part nav; else UNION one seed per part (`a.html..h.html`), dedup stems. Must satisfy `len(stems) >= GUIDELINES_MIN_DISCOVERED` else raise (S3 regression guard).
* Requirement: `fetch_section(url)` returns `(title, body)`, `None` for empty/exhausted retries, or `GONE` sentinel for a consistent HTTP 404; pacing `GUIDELINES_REQUEST_DELAY_S` + `GUIDELINES_MAX_RETRIES` exponential backoff; strips share/breadcrumb chrome.
* Requirement: `scrape_epo_guidelines(dest_dir, edition=None)` — resolve edition → discover sections → fetch each (record per-section outcome, distinguish GONE/FAILED) → RESUME up to `GUIDELINES_RESUME_MAX_ROUNDS` of only FAILED-non-404 sections → `ratio = with_content / (discovered - gone_404)` → if `< GUIDELINES_SUCCESS_RATIO_FLOOR` (0.95) FAIL write nothing; else write `manifest.json` FIRST (temp+rename) then `.txt` (temp+rename) in `PART X - TITLE` / `### {title} [{stem}]` format. `PART_TITLES["c"]` typo fixed; no draft-PDF path.

### Acceptance Criteria

* [ ] `discover_in_force_edition` returns the highest year from a multi-edition fixture (e.g. 2026 over 2025); raises a source-named error for no-year-link and unreachable (monkeypatched).
* [ ] `discover_section_urls` scopes to `[a-h]`, excludes `i/j/k/m`, and raises when seed yields fewer than `GUIDELINES_MIN_DISCOVERED` stems; both index-seed and union-per-part-seed strategies reach the full set on the fixture.
* [ ] `fetch_section` returns `GONE` on a consistent 404 and `None` on timeout/empty (distinguishable, S1).
* [ ] `scrape_epo_guidelines` computes `ratio = with_content / (discovered - gone_404)` (legitimate 404s excluded); FAILED-non-404 sections retried up to `RESUME_MAX_ROUNDS` and a resume-success is counted.
* [ ] `scrape_epo_guidelines` writes manifest THEN `.txt` when ratio ≥ floor; writes NEITHER and returns `False` when ratio < floor; a mid-scrape crash (manifest written, `.txt` not) leaves no `.txt` and `validate_guidelines` reports invalid.
* [ ] Emitted `.txt` round-trips through `extract_text_from_epo_guidelines`.
* [ ] `PART_TITLES["c"]` typo fixed; no hardcoded `YEAR`; no draft-PDF code path; `scripts/_epo_guidelines_scrape.py` deleted.

## Definition of Done

### Intent

A fresh install that needs European examination guidance gets the actual in-force EPO Guidelines edition — discovered at run time, not hardcoded — scraped into the `epo_guidelines.txt` the indexer actually reads, in the exact section format it parses. A partial or thin scrape never ships: the file is written only when the section-success ratio clears 0.95 over a discovered set that is itself sanity-floored, and a manifest sidecar records the scrape provenance so a `.txt` without a consistent manifest is treated as not-acquired. If this breaks, an operator would notice EPO Guidelines search returns nothing, or returns stale/draft text, and the logs would name edition discovery or the ratio gate as the failure.

### Observable outcomes

- [ ] `discover_in_force_edition(multi_edition_fixture)` returns the highest year; raises a source-named error on a no-year fixture and on an unreachable page.
- [ ] `discover_section_urls` returns only `[a-h]` stems (no `i/j/k/m`) and raises when the discovered set is below `GUIDELINES_MIN_DISCOVERED`; both seed strategies reach the full A-H set on the fixture.
- [ ] `fetch_section` returns the `GONE` sentinel for a consistent 404 and `None` for timeout/empty.
- [ ] `scrape_epo_guidelines` excludes consistent-404 sections from the ratio denominator and retries FAILED-non-404 sections up to `GUIDELINES_RESUME_MAX_ROUNDS`, counting resume-successes.
- [ ] `PART_TITLES["c"]` "Procedureal" typo is fixed; no hardcoded `YEAR`; no draft-PDF code path; `scripts/_epo_guidelines_scrape.py` is deleted.
- [ ] Capstone: with monkeypatched section fetches over a synthetic A-H set on the fixture, a run whose `with_content/(discovered - gone_404) >= 0.95` writes `epo_guidelines.manifest.json` BEFORE `epo_guidelines.txt` (write order asserted, both present), the emitted `.txt` parses through the real `extract_text_from_epo_guidelines` into `>= GUIDELINES_MIN_CHUNKS` chunks, and `validate_guidelines` returns `True`; a run forced below the ratio floor (after resume) writes NEITHER file, returns `False`, and a crash injected after the manifest write but before the `.txt` write leaves no `.txt` and `validate_guidelines` returns `False`.

## Feature Work Phases

| Phase / Task | Status / Link to Artifact or Card | Universal Check |
| :--- | :--- | :---: |
| **Design & Architecture** | Design doc Phase 2 + KD4/KD5/S1/S3 | - [ ] Design Complete |
| **Test Plan Creation** | `tests/test_epo_edition_discovery.py`, `tests/test_epo_scrape_gating.py` (written first) | - [ ] Test Plan Approved |
| **TDD Implementation** | discovery + fetch + rewritten scrape + manifest | - [ ] Implementation Complete |
| **Integration Testing** | Monkeypatched scrape end-to-end + round-trip | - [ ] Integration Tests Pass |
| **Documentation** | Module docstring (discovery, scope, manifest, ratio gate) | - [ ] Documentation Complete |
| **Code Review** | Sprint reviewer | - [ ] Code Review Approved |
| **Deployment Plan** | Merged to sprint branch; prototype script deleted | - [ ] Deployment Plan Ready |

## TDD Implementation Workflow

| Step | Status/Details | Universal Check |
| :---: | :--- | :---: |
| **1. Write Failing Tests** | edition discovery + scrape gating tests | - [ ] Failing tests are committed and documented |
| **2. Implement Feature Code** | `discover_in_force_edition`/`discover_section_urls`/`fetch_section`/`scrape_epo_guidelines` | - [ ] Feature implementation is complete |
| **3. Run Passing Tests** | Suite green | - [ ] Originally failing tests now pass |
| **4. Refactor** | Promote prototype cleanly; delete script | - [ ] Code is refactored for clarity and maintainability |
| **5. Full Regression Suite** | `pytest tests/` green | - [ ] All tests pass (unit, integration, e2e) |
| **6. Performance Testing** | N/A (scrape monkeypatched in CI) | - [ ] Performance requirements are met |

### Implementation Notes

**Test Strategy:** `tests/fixtures/epo_entry_page.html` (multiple year-stamped links). Section fetches are monkeypatched — no live ~1,887-request scrape in CI. Round-trip test runs the emitted `.txt` through the real `extract_text_from_epo_guidelines`. Reuses `validate_guidelines` from step 2.

**Key Implementation Decisions:** Seed strategy per S3 (index-seed or union-per-part) + `MIN_DISCOVERED` guard; `ratio` denominator excludes consistent 404s (S1); manifest-first ordered write (KD5) makes "manifest-only" a not-acquired state, never a half-ingested `.txt`.

## Validation & Closeout

| Task | Detail/Link |
| :--- | :--- |
| **Code Review** | Sprint reviewer |
| **QA Verification** | `tests/test_epo_edition_discovery.py`, `tests/test_epo_scrape_gating.py` |
| **Staging Deployment** | N/A (verified via tests) |
| **Production Deployment** | Sprint branch |
| **Monitoring Setup** | Per-source log: resolved edition, discovered/fetched/with_content counts, ratio, pass/fail |

### Follow-up & Lessons Learned

| Topic | Status / Action Required |
| :--- | :--- |
| **Postmortem Required?** | No |
| **Further Investigation?** | EPO entry-page structure change → single documented repair point + logged override |
| **Technical Debt Created?** | No — prototype script deleted, not left dangling |
| **Future Enhancements** | None in scope |

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
