# step 2 Phase 0 — Validity-predicate spine + extractor free-function refactor

> **Sprint**: EPODL | **Type**: refactor | **Step**: 2 | **Priority**: P0
>
> Design doc Phase 0 (ADR-001 D1 spine + B2 seam). Prerequisite for ALL acquisition flows. Depends on: step 1 (planning). Unblocks: step 3A, step 3B, step 3C, step 4.

## Required Reading

| What | Where | Why |
| :--- | :--- | :--- |
| Design doc Phase 0 | `docs/designs/epo-law-acquisition.md` lines 623-675 | Deliverables, test strategy, DoD for this card |
| KD2 (free-function refactor) | `docs/designs/epo-law-acquisition.md` lines 294-309 | Why a module-level pure function (R8: zero model loads) |
| Interface: constants/validators/spine | `docs/designs/epo-law-acquisition.md` lines 399-472, 563-570 | Exact signatures and floor values |
| ADR-001 D1 | `docs/adr/ADR-001-epo-law-acquisition-architecture.md` | Validity predicate is the prerequisite for D2/D3/D4 |
| `extract_text_from_epc` | `mcp_server/mpep_search.py:458` | Bound method to extract; only `self.` ref is `_chunk_text_with_metadata` (`:223`) |
| `MPEPIndex.__init__` model loads | `mcp_server/mpep_search.py:149-153` | Why an instance route forces SentenceTransformer + CrossEncoder loads (R8 violation) |
| Existence short-circuits to remove | `mcp_server/epo_downloaders.py:92`, `:185` | Both `dest_path.exists()` short-circuits are deleted |
| Draft-PDF constants to delete | `mcp_server/epo_downloaders.py` (`EPO_GUIDELINES_DRAFT_PDF_PATTERN`) | Removed in this card |

## Refactoring Overview & Motivation

* **Refactoring Target:** `extract_text_from_epc` (bound method → module-level free function); new validity-predicate spine in `epo_downloaders.py`
* **Code Location:** `mcp_server/mpep_search.py`, `mcp_server/epo_downloaders.py`, `tests/`
* **Refactoring Type:** Extract function (decouple pure extraction from `MPEPIndex` so the validator calls it with zero ML model loads); introduce shared persistence spine + pure validity predicates
* **Motivation:** A validity predicate must answer "is what I have real, in-force law?" without constructing an `MPEPIndex` (which eagerly loads two ML models). Today idempotency is keyed on `dest_path.exists()`, so junk is never repaired. This card lands the testable spine all later phases build on.
* **Business Impact:** Enables validity-keyed idempotency (junk never persisted, invalid re-acquired) and model-load-free validation; without it Phases 1, 2, 4 cannot be built correctly.
* **Scope:** `extract_text_from_epc`/`_chunk_text_with_metadata` extraction + delegating method; `validate_epc`/`validate_guidelines`/`validate_pct`/`fetch_validate_promote` + config constants in `epo_downloaders.py`; remove two `dest_path.exists()` short-circuits; delete draft-PDF constants; new `tests/fixtures/` + `tests/test_epo_validators.py`.
* **Risk Level:** Medium — touches the indexer's extraction path (must stay behaviorally identical) and the two acquisition entry points.
* **Related Work:** ADR-001 D1/KD2; landed `extract_text_from_epc`/`extract_text_from_epo_guidelines` on `main` (commit `c9b8779`).

**Required Checks:**
* [ ] **Refactoring motivation** clearly explains why this change is needed.
* [ ] **Scope** is specific and bounded (not open-ended "improve everything").
* [ ] **Risk level** is assessed based on code criticality and usage.

## Pre-Refactoring Context Review

* [ ] Existing code reviewed and behavior fully understood.
* [ ] Test coverage reviewed - current test suite provides safety net.
* [ ] Documentation reviewed (README, docstrings, inline comments).
* [ ] Style guide and coding standards reviewed for compliance.
* [ ] Dependencies reviewed (internal modules, external libraries).
* [ ] Usage patterns reviewed (who calls this code, how it's used).
* [ ] Previous refactoring attempts reviewed (if any - learn from history).

| Review Source | Link / Location | Key Findings / Constraints |
| :--- | :--- | :--- |
| **Existing Code** | `mpep_search.py:458` (`extract_text_from_epc`), `:223` (`_chunk_text_with_metadata`) | Method is pure over `pdf_path`; only `self.` ref is the stateless chunker — safe to extract |
| **Model loads** | `mpep_search.py:149-153` | `__init__` eagerly loads SentenceTransformer(bge-base) + CrossEncoder; any instance route violates R8 |
| **Test Coverage** | `tests/`, `tests/conftest.py` | No `tests/fixtures/` dir yet; no test touches `epo_downloaders.py` |
| **Dependencies** | `epo_downloaders.py` callers; indexer `build_index` calls `extract_text_from_epc` | Indexer call path must be preserved via a one-line delegate |
| **Usage Patterns** | `epo_downloaders.py:92`, `:185` | Both entry points short-circuit on `dest_path.exists()` — must be replaced by predicate checks |

## Refactoring Strategy & Risk Assessment

**Refactoring Approach:**
* Extract `extract_epc_provisions(pdf_path) -> list[dict]` as a module-level function in `mpep_search.py`; make `_chunk_text_with_metadata` callable without an `MPEPIndex` (module-level or static). `MPEPIndex.extract_text_from_epc` becomes `return extract_epc_provisions(pdf_path)`.
* Add config constants block (floors, pacing, retries, filenames, `MIN_DISCOVERED`, `RESUME_MAX_ROUNDS`, `PCT_MIN_SIZE_BYTES`) at top of `epo_downloaders.py`; delete `EPO_GUIDELINES_DRAFT_PDF_PATTERN` and related draft-PDF constants.
* Implement pure validity predicates (filesystem-reading, no network, return `False` not raise on invalidity, log a debug reason): `validate_epc` (magic bytes → size → `extract_epc_provisions` count ≥ `EPC_MIN_PROVISIONS`), `validate_guidelines` (size → consistent manifest with ratio ≥ floor + edition → `extract_text_from_epo_guidelines` chunks ≥ floor; `.txt` without consistent manifest is INVALID), `validate_pct` (exists + `%PDF-` + size ≥ `PCT_MIN_SIZE_BYTES`).
* Implement `fetch_validate_promote(fetch_fn, validate_fn, dest)`: download to temp in `dest.parent`, validate, `os.replace` on pass, unlink + log source-named reason + return `False` on fetch-raise or validate-fail.
* Remove both `dest_path.exists()` short-circuits (`:92`, `:185`); in the interim the entry points call the predicate (full rewire onto the spine lands in Phases 1-2).

**Incremental Steps:**
1. Add `tests/fixtures/` and write failing `tests/test_epo_validators.py` first (TDD).
2. Extract `extract_epc_provisions` + `_chunk_text_with_metadata`; make method delegate.
3. Add constants; delete draft-PDF constants.
4. Implement validators + `fetch_validate_promote`.
5. Remove the two existence short-circuits.

**Risk Mitigation:**
* Risk: extraction behavior drifts. Mitigation: identity test — free function returns the same chunks as the old bound method on the good fixture.
* Risk: validator accidentally loads a model. Mitigation: spy/monkeypatch on `SentenceTransformer`/`CrossEncoder` asserts neither is instantiated during `validate_epc` (R8).
* Risk: EPC fixture too large to commit (Open Question 1). Mitigation: use a trimmed/representative PDF sized just above floors, OR inject lower floors via a test constant.

**Rollback Plan:**
* `git revert` of the card's commits restores the bound method and the existence short-circuits; no persisted-state shape changes.

**Success Criteria:**
* `extract_epc_provisions` is module-level; `MPEPIndex.extract_text_from_epc` delegates; indexer behavior unchanged.
* `validate_epc` constructs no `MPEPIndex` and loads no model (spy-proven).
* All three validators pure (no network) and pass the fixture matrix.
* `fetch_validate_promote` temp/promote/unlink behavior unit-proven.
* Neither entry point short-circuits on `dest_path.exists()`.
* All floor/pacing values are named constants; no inline magic numbers in control flow.

## Definition of Done

### Intent

Anyone checking whether the saved EPC/Guidelines/PCT files on disk are real, in-force law can call a cheap, network-free predicate that does NOT spin up the two ML models the indexer loads — and any code that downloads a new artifact gets a crash-safe "validate before you publish" helper so a bad fetch never leaves junk under the real filename. The extraction logic the indexer uses and the logic the validator uses are literally the same function, so they can never disagree. If this is broken, a maintainer would notice either that an idempotency check is suddenly slow (model loads crept back in) or that a 28 KB HTML file saved as `epc_convention.pdf` is treated as "present and fine."

### Observable outcomes

- [ ] `extract_epc_provisions(pdf_path)` is a module-level function in `mpep_search.py`; `MPEPIndex.extract_text_from_epc` is a one-line delegate to it.
- [ ] Calling `validate_epc(good_fixture)` constructs no `MPEPIndex` and instantiates neither `SentenceTransformer` nor `CrossEncoder` (proven by a spy/monkeypatch that fails if either is constructed).
- [ ] `validate_epc` returns `True` for the good EPC fixture and `False` for: HTML-as-PDF (magic-byte fail), truncated PDF (size fail), and a valid-but-unrelated large PDF (provision-count fail).
- [ ] `validate_guidelines` returns `True` for valid `.txt`+manifest and `False` for: stub (size/chunk), `.txt`-without-manifest, and `.txt` with a ratio-below-floor manifest.
- [ ] `validate_pct` returns `True` for a real PDF above the size floor and `False` for HTML-as-PDF and a sub-floor file.
- [ ] `fetch_validate_promote` promotes (`os.replace`) on a passing `validate_fn`, leaves no `dest` and returns `False` on a failing one, and leaves no temp file behind when `fetch_fn` raises.
- [ ] Neither `epo_downloaders.py:92` nor `:185` short-circuits on `dest_path.exists()`; `EPO_GUIDELINES_DRAFT_PDF_PATTERN` and the other draft-PDF constants are deleted.
- [ ] Capstone: `extract_epc_provisions(good_fixture)` and `MPEPIndex().extract_text_from_epc(good_fixture)` return identical chunk lists (identity proof the refactor preserved indexer behavior), AND `validate_epc(good_fixture) is True` while `validate_epc(junk_html_as_pdf) is False` — both observed against the committed fixtures with no model load.

## Refactoring Phases

| Phase / Task | Status / Link to Artifact or Card | Universal Check |
| :--- | :--- | :---: |
| **Pre-Refactor Test Suite** | `tests/test_epo_validators.py` + `tests/fixtures/` (written first) | - [ ] Comprehensive tests exist before refactoring starts. |
| **Baseline Measurements** | Old bound-method chunk output on good fixture captured as golden | - [ ] Baseline metrics captured (extraction output, model-load count). |
| **Incremental Refactoring** | Extract free function → delegate method → validators → spine → remove short-circuits | - [ ] Refactoring implemented incrementally with passing tests at each step. |
| **Documentation Updates** | Module docstring documents the spine + floors; CLAUDE.md gotcha note | - [ ] All documentation updated to reflect refactored code. |
| **Code Review** | Sprint reviewer | - [ ] Code reviewed for correctness, style guide compliance, maintainability. |
| **Performance Validation** | Validator runs with zero model loads | - [ ] Performance validated - no regression, ideally improvement. |
| **Staging Deployment** | N/A (library refactor; verified via tests) | - [ ] Refactored code validated in staging environment. |
| **Production Deployment** | Merged on sprint branch | - [ ] Refactored code deployed to production with monitoring. |

## Safe Refactoring Workflow

| Step | Status/Details | Universal Check |
| :---: | :--- | :---: |
| **1. Establish Test Safety Net** | `tests/test_epo_validators.py` + fixtures, written first | - [ ] Comprehensive tests exist covering current behavior. |
| **2. Run Baseline Tests** | Existing indexer tests green before refactor | - [ ] All tests pass before any refactoring begins. |
| **3. Capture Baseline Metrics** | Golden chunk output from old bound method | - [ ] Baseline metrics captured for comparison. |
| **4. Make Smallest Refactor** | Extract `extract_epc_provisions` + chunker | - [ ] Smallest possible refactoring change made. |
| **5. Run Tests (Iteration)** | Identity test passes | - [ ] All tests pass after refactoring change. |
| **6. Commit Incremental Change** | Atomic commits per step | - [ ] Incremental change committed. |
| **7. Repeat Steps 4-6** | Validators, spine, short-circuit removal | - [ ] All incremental refactoring steps completed with passing tests. |
| **8. Update Documentation** | Module docstring + CLAUDE.md gotcha | - [ ] All documentation updated. |
| **9. Style & Linting Check** | Lint + type checks pass | - [ ] Code passes linting, type checking, and style guide validation. |
| **10. Code Review** | Reviewer approval | - [ ] Changes reviewed for correctness and maintainability. |
| **11. Performance Validation** | Zero model loads on validate | - [ ] Performance validated - no regression detected. |
| **12. Deploy to Staging** | N/A (library) | - [ ] Refactored code validated in staging environment. |
| **13. Production Deployment** | Merged to sprint branch | - [ ] Gradual production rollout with monitoring. |

## Refactoring Validation & Completion

| Task | Detail/Link |
| :--- | :--- |
| **Code Location** | `mcp_server/mpep_search.py`, `mcp_server/epo_downloaders.py`, `tests/test_epo_validators.py`, `tests/fixtures/` |
| **Test Suite** | `tests/test_epo_validators.py` — validator matrix + identity + no-model-load spy |
| **Baseline Metrics (Before)** | Existence-keyed idempotency; validation would require 2 model loads |
| **Final Metrics (After)** | Validity-keyed idempotency; validation loads zero models |
| **Performance Validation** | `validate_epc` instantiates no ML model (spy-proven) |
| **Style & Linting** | Lint/type checks pass |
| **Code Review** | Sprint reviewer |
| **Documentation Updates** | `epo_downloaders.py` module docstring; `CLAUDE.md` Critical Gotchas (validity-keyed idempotency) |
| **Staging Validation** | N/A (library refactor) |
| **Production Deployment** | Sprint branch |

### Follow-up & Lessons Learned

| Topic | Status / Action Required |
| :--- | :--- |
| **Further Refactoring Needed?** | Flows rewired onto the spine in step 3A (EPC) and step 3B (Guidelines) |
| **Design Patterns Reusable?** | `fetch_validate_promote` is the shared promote helper for both sources |
| **Test Suite Improvements?** | `tests/fixtures/` introduced here is reused by all later phases |
| **Documentation Complete?** | Module docstring + CLAUDE.md gotcha |
| **Performance Impact?** | Positive — idempotency checks no longer load ML models |
| **Team Knowledge Sharing?** | KD2 documents the single-source-of-truth rationale |
| **Technical Debt Reduced?** | Draft-PDF constants deleted; existence short-circuits removed |
| **Code Quality Metrics Improved?** | Pure functions, single extraction source of truth |

### Completion Checklist

* [ ] Comprehensive tests exist before refactoring (written first).
* [ ] All tests pass before refactoring begins (baseline established).
* [ ] Baseline metrics captured (extraction output, model-load count).
* [ ] Refactoring implemented incrementally (small, safe steps).
* [ ] All tests pass after each refactoring step (continuous validation).
* [ ] Documentation updated (module docstring, CLAUDE.md gotcha).
* [ ] Code passes style guide validation (linting, type checking).
* [ ] Code reviewed.
* [ ] No performance regression (validator loads zero models).
* [ ] Refactored code validated via test suite.
* [ ] Merged to sprint branch.
* [ ] Code quality metrics improved (single extraction source of truth).
* [ ] Rollback plan documented.

### Note on validation

This card follows a structured template. Keep its sections, checkboxes, and tables and fill them in rather than removing them.
