# step 3A Phase 1 — EPC acquires as a real PDF from WIPO Lex

> **Sprint**: EPODL | **Type**: feature | **Step**: 3A | **Priority**: P1
>
> Design doc Phase 1 (PRD Phase 1, ADR-001 D2). Depends on: step 2 (`wp8iqb` — spine + `validate_epc` + `fetch_validate_promote`). Parallel-safe with step 3B (`epo_downloaders.py`, different functions) and step 3C (`mpep_search.py`). Unblocks: step 4.

## Required Reading

| What | Where | Why |
| :--- | :--- | :--- |
| Design doc Phase 1 | `docs/designs/epo-law-acquisition.md` lines 677-710 | Deliverables, test strategy, DoD |
| KD2/D2 EPC acquisition | `docs/designs/epo-law-acquisition.md` lines 474-495 | `download_epc`/`extract_signed_epc_url` signatures + behavior |
| ADR-001 D2 | `docs/adr/ADR-001-epo-law-acquisition-architecture.md` | Why the signed-URL extraction approach |
| Current `download_epc` | `mcp_server/epo_downloaders.py:125` | Stale docstring + landing-page URL to replace |
| Spine + `validate_epc` | `mcp_server/epo_downloaders.py` (from step 2) | `fetch_validate_promote`, `validate_epc`, `WIPO_EPC_LANDING_URL`, `EPC_FILE` |

## Feature Overview & Context

* **Associated Ticket/Epic:** EPODL sprint; roadmap `m2/s1/epo-downloaders-fix`; design doc Phase 1
* **Feature Area/Component:** EPO/EPC law acquisition — `mcp_server/epo_downloaders.py`
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
| **Design Doc** | `docs/designs/epo-law-acquisition.md` Phase 1 | Signed-URL extraction (host `wipolex-res.wipo.int`, `/edocs/` path, `Signature`/`Expires`/`Key-Pair-Id` triple, HTML-unescape); fail-loud, no junk |
| **ADR** | `docs/adr/ADR-001-...md` D2 | Single documented repair point if WIPO markup changes |
| **Similar Code** | `epo_downloaders.py` spine from step 2 | `download_epc` rewrites onto `fetch_validate_promote` + `validate_epc` |
| **Stale docstring** | `epo_downloaders.py:125` | "The EPO HTML version is more current" must be removed |

## Design & Planning

### Initial Design Thoughts & Requirements

* Requirement: `download_epc(dest_dir)` GETs `WIPO_EPC_LANDING_URL` (durable, unsigned HTML), extracts the embedded signed asset URL via `extract_signed_epc_url`, `html.unescape`es it (`&#x3D;`→`=`, `&amp;`→`&`), fetches, validates with `validate_epc`, and atomically promotes via `fetch_validate_promote` to `dest_dir/EPC_FILE`.
* Requirement: `extract_signed_epc_url(landing_html) -> Optional[str]` — primary pattern keys on host `wipolex-res.wipo.int` + `/edocs/` path + the `Signature`/`Expires`/`Key-Pair-Id` triple; fallback widens to any `.pdf` src/href carrying the triple; does NOT `html.unescape` (caller does).
* Constraint: signed URL is ephemeral — extract + download in one flow.
* Constraint: on no signed URL found or non-EPC body, fail loud (logged, EPC-named) and persist nothing.

### Acceptance Criteria

* [ ] `extract_signed_epc_url` returns the signed URL from the saved landing-page fixture, still entity-encoded; `html.unescape` of it yields a fetchable query string with `Signature`/`Expires`/`Key-Pair-Id` intact.
* [ ] `extract_signed_epc_url` returns `None` for a landing page with no signed link (drives fail-loud); fallback matches a `.pdf` href carrying the triple even when the host differs.
* [ ] `download_epc` (monkeypatched fetch) promotes when the fetched bytes pass `validate_epc` (good fixture) and persists nothing + returns `False` when the body is HTML.
* [ ] The stale "EPO HTML version is more current" docstring is gone.

## Definition of Done

### Intent

A fresh install that needs European law gets a genuine EPC PDF from WIPO Lex instead of a 28 KB HTML landing page saved with a `.pdf` extension. The acquisition resolves the ephemeral signed CloudFront-style URL embedded (HTML-entity-encoded) in the durable landing page, downloads the real PDF, and only promotes it if it validates as real EPC law; any failure leaves no junk file behind and logs a clear EPC-named reason. If this breaks, an operator would notice EPC search returns nothing (or the indexer ingests a single junk chunk) and the logs name WIPO extraction as the failure point.

### Observable outcomes

- [ ] `extract_signed_epc_url(landing_fixture)` returns the embedded signed URL with entities intact; `html.unescape(result)` carries `Signature`, `Expires`, and `Key-Pair-Id`.
- [ ] `extract_signed_epc_url` returns `None` for a no-signed-link page; the fallback pattern still matches a `.pdf` href bearing the triple on a different host.
- [ ] `download_epc` with a monkeypatched fetch returning the good EPC fixture promotes a valid PDF to `dest_dir/EPC_FILE` and returns `True`.
- [ ] `download_epc` with a monkeypatched fetch returning HTML returns `False` and leaves no `.pdf` under `dest_dir`.
- [ ] The stale "EPO HTML version is more current" docstring is removed; the WIPO extraction point is documented inline as the single repair location.
- [ ] Capstone: given the saved `tests/fixtures/wipo_epc_landing.html` and a monkeypatched fetch wired to return the committed good EPC PDF for the extracted+unescaped URL, `download_epc(tmp_dir)` returns `True` and `tmp_dir/epc_convention.pdf` passes `validate_epc`; with the fetch wired to return HTML bytes instead, `download_epc` returns `False` and `tmp_dir` contains no `.pdf` and no temp file.

## Feature Work Phases

| Phase / Task | Status / Link to Artifact or Card | Universal Check |
| :--- | :--- | :---: |
| **Design & Architecture** | Design doc Phase 1 + KD2/D2 | - [ ] Design Complete |
| **Test Plan Creation** | `tests/test_epo_extract_urls.py` (written first) | - [ ] Test Plan Approved |
| **TDD Implementation** | `extract_signed_epc_url` + rewritten `download_epc` | - [ ] Implementation Complete |
| **Integration Testing** | Monkeypatched `download_epc` end-to-end | - [ ] Integration Tests Pass |
| **Documentation** | `download_epc` docstring + inline repair-point note | - [ ] Documentation Complete |
| **Code Review** | Sprint reviewer | - [ ] Code Review Approved |
| **Deployment Plan** | Merged to sprint branch | - [ ] Deployment Plan Ready |

## TDD Implementation Workflow

| Step | Status/Details | Universal Check |
| :---: | :--- | :---: |
| **1. Write Failing Tests** | `tests/test_epo_extract_urls.py` (extraction + None + download) | - [ ] Failing tests are committed and documented |
| **2. Implement Feature Code** | `extract_signed_epc_url`, `download_epc` on the spine | - [ ] Feature implementation is complete |
| **3. Run Passing Tests** | Suite green | - [ ] Originally failing tests now pass |
| **4. Refactor** | Tidy patterns; inline repair-point doc | - [ ] Code is refactored for clarity and maintainability |
| **5. Full Regression Suite** | `pytest tests/` green | - [ ] All tests pass (unit, integration, e2e) |
| **6. Performance Testing** | N/A (single fetch) | - [ ] Performance requirements are met |

### Implementation Notes

**Test Strategy:** `tests/fixtures/wipo_epc_landing.html` is a saved real landing page with the entity-encoded signed `src`. All network is monkeypatched; no live WIPO call in CI. Reuses `validate_epc` and the good EPC fixture from step 2.

**Key Implementation Decisions:** `extract_signed_epc_url` does not unescape (caller does); primary + fallback pattern per KD2; `download_epc` flows through `fetch_validate_promote` so crash-safety/atomic-promote is inherited from the spine.

## Validation & Closeout

| Task | Detail/Link |
| :--- | :--- |
| **Code Review** | Sprint reviewer |
| **QA Verification** | `tests/test_epo_extract_urls.py` |
| **Staging Deployment** | N/A (verified via tests) |
| **Production Deployment** | Sprint branch |
| **Monitoring Setup** | EPC-named log lines on acquisition outcome |

### Follow-up & Lessons Learned

| Topic | Status / Action Required |
| :--- | :--- |
| **Postmortem Required?** | No |
| **Further Investigation?** | WIPO markup changes → single documented repair point |
| **Technical Debt Created?** | No |
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
