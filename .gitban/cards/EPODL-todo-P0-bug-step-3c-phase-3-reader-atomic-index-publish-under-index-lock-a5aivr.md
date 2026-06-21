# step 3C Phase 3 — Reader-atomic index publish under `_index_lock`

> **Sprint**: EPODL | **Type**: bug | **Step**: 3C | **Priority**: P0
>
> Design doc Phase 3 (B1a / KD9). Depends on: step 2 (`wp8iqb` — the other `mpep_search.py` seam, the extractor free-function refactor). Parallel-safe with step 3A/3B (they touch `epo_downloaders.py`; this touches `build_index`/`search`). MUST precede step 4 — the deferred trigger introduces concurrent-rebuild-during-live-search, which this fix makes safe; the two cards must not be dispatched in parallel.

## Bug Overview & Context

* **Ticket/Issue ID:** EPODL sprint; design doc Phase 3; ADR-001 B1a/KD9
* **Affected Component/Service:** `MPEPIndex.build_index` / `MPEPIndex.search` in `mcp_server/mpep_search.py`
* **Severity Level:** P0 — a torn read returns wrong rows or crashes the search tool once the Phase 4 background rebuild lands
* **Discovered By:** Adversarial design review of the deferred-default trigger
* **Discovery Date:** 2026-06-21
* **Reporter:** cameronrout

**Required Checks:**
* [ ] Ticket/Issue ID is linked above
* [ ] Component/Service is clearly identified
* [ ] Severity level is assigned based on impact

## Bug Description

### What's Broken

`build_index` publishes the rebuilt corpus field-at-a-time with no lock: it assigns `self.index` (`:957`), adds to it (`:958`), then `self.chunks` (`:960`), `self.metadata` (`:962-987`), and `self.bm25` (`:993`) one at a time. `search` reads `self.index` (`:1064`), `self.chunks` (`:1079`), and `self.metadata` (`:1080`) with no lock. A `search` interleaved with a `build_index(force_rebuild=True)` can pair a NEW FAISS index with the OLD `self.chunks` → wrong rows or an `IndexError`.

### Expected Behavior

A `build_index(force_rebuild=True)` running concurrently with live `search` calls never tears: a reader sees the entire old corpus or the entire new one, never a new index paired with stale chunks/metadata. No reader crashes or returns mismatched rows because of an in-flight rebuild (R7).

### Actual Behavior

Today the race is latent — `build_index` only runs at process startup inside `LazyMPEPIndex._load`'s lock before any tool serves a query — but the Phase 4 deferred trigger introduces exactly the concurrent-rebuild-during-live-search scenario. Without this fix, the first background rebuild can tear a concurrent EPO/US search.

### Reproduction Rate

* [ ] 100% - Always reproduces
* [ ] 75% - Usually reproduces
* [ ] 50% - Sometimes reproduces
* [x] 25% - Rarely reproduces
* [ ] Cannot reproduce consistently

(Race — surfaced reliably only by hammering `search` against a concurrent `build_index` over many iterations.)

## Steps to Reproduce

**Prerequisites:**
* An `MPEPIndex` with a built corpus (tiny synthetic, models stubbed)
* Two threads: one running `search` in a tight loop, one running `build_index(force_rebuild=True)` that changes corpus size

**Reproduction Steps:**

1. Build an `MPEPIndex` on a tiny synthetic corpus (models stubbed).
2. Spawn a thread that calls `search(...)` in a loop.
3. Concurrently call `build_index(force_rebuild=True)` with a different corpus size.
4. Observe an `IndexError` or a result row whose metadata source disagrees with its chunk.

**Error Messages / Stack Traces:**

```
IndexError: list index out of range   # new FAISS index returns an id beyond old self.chunks
# or: a result row whose metadata.source does not match its chunk content
```

## Environment Details

| Environment Aspect | Required | Value | Notes |
| :--- | :--- | :--- | :--- |
| **Environment** | Optional | Local / CI | Concurrency test, models stubbed |
| **Runtime/Framework** | Optional | Python 3.11 | `threading.RLock` |
| **Dependencies** | Optional | FAISS + BM25 | `MPEPIndex` |
| **Application Version** | Optional | sprint branch | — |

## Impact Assessment

| Impact Category | Severity | Details |
| :--- | :--- | :--- |
| **User Impact** | High | Wrong search rows or a crash on the first EPO query once Phase 4 lands |
| **Business Impact** | Medium | Undermines the deferred-default value (EU law on demand) if it crashes |
| **System Impact** | High | `search` tool can raise `IndexError` under concurrent rebuild |
| **Data Impact** | None | No data loss; read-correctness only |
| **Security Impact** | None | — |

**Business Justification for Priority:**

P0 because Phase 4 (the trigger) DEPENDS on this fix existing — they both touch `build_index`/`MPEPIndex` and would collide if dispatched in parallel. The atomicity fix is independent of EPO acquisition (it benefits any concurrent rebuild), so it lands and is verified on its own first.

## Documentation & Code Review

| Item | Applicable | File / Location | Notes / Evidence | Key Findings / Action Required |
|---|:---:|---|---|---|
| README or component documentation reviewed | yes | `CLAUDE.md` | Note that `build_index` is reader-atomic; a background rebuild is safe | Add Critical Gotchas note |
| Related ADRs reviewed | yes | `docs/adr/ADR-001-...md`, design doc KD9 (lines 372-390) | Lock-around-four-assignments chosen over holder-object (smaller diff; holder noted as cleaner follow-up) | Follow KD9 |
| API documentation reviewed | yes | `mcp_server/mpep_search.py` `build_index`/`search` | `build_index:801`, publish `:957-993`; `search:1013`, reads `:1064`/`:1079-1081` | Implement lock |
| Test suite documentation reviewed | yes | `tests/`, `tests/conftest.py` | No atomicity test exists | Add `tests/test_index_atomicity.py` |
| IaC configuration reviewed | no | N/A | — | N/A |
| New Documentation (Action Item) | N/A | **N/A** | publish-under-lock invariant in module docstring | DaC |

## Root Cause Investigation

| Iteration # | Hypothesis | Test/Action Taken | Outcome / Findings |
| :---: | :--- | :--- | :--- |
| **1** | Publish is non-atomic | Read `build_index:957-993` | Confirmed — fields assigned one at a time, no lock |
| **2** | `search` reads unsynchronized | Read `search:1064, :1079-1081` | Confirmed — reads `index`/`chunks`/`metadata` without a lock |
| **3** | Interleaving pairs new index with old chunks | Reasoned through the race | Root cause: a reader between the index swap and the chunks swap sees mismatched generations |

### Hypothesis testing iterations

**Iteration 1:** Non-atomic publish

**Hypothesis:** `build_index` does not publish the four corpus fields atomically.

**Test/Action Taken:** Inspected `mpep_search.py:957-993`.

**Outcome:** Confirmed — `self.index`, `self.chunks`, `self.metadata`, `self.bm25` are assigned sequentially with no lock.

**Iteration 2:** Unsynchronized read

**Hypothesis:** `search` reads the corpus fields without synchronization.

**Test/Action Taken:** Inspected `mpep_search.py:1064, :1079-1081`.

**Outcome:** Confirmed — no lock on the read path.

**Iteration 3:** Cross-generation pairing

**Hypothesis:** A reader can pair a new FAISS index with old chunks.

**Test/Action Taken:** Reasoned through interleavings.

**Outcome:** Root cause identified — atomic publish + snapshot-read under a shared lock is required.

### Root Cause Summary

**Root Cause:** `build_index` publishes the corpus field-at-a-time and `search` reads it unsynchronized, so a concurrent rebuild can expose a new FAISS index paired with the old `chunks`/`metadata`.

**Code/Config Location:** `mcp_server/mpep_search.py` — `build_index` publish `:957-993`; `search` reads `:1064`, `:1079-1081`.

**Why This Happened:** The publish path was written assuming `build_index` only ever runs at startup before any query; the deferred-default trigger breaks that assumption.

## Solution Design

### Fix Strategy

Per KD9: `MPEPIndex.__init__` gains `self._index_lock = threading.RLock()`. `build_index` assembles the new FAISS index, BM25, `chunks`, and `metadata` into LOCAL variables across the whole extract/embed pass, then publishes all four under `self._index_lock` in a single critical section (replacing the field-at-a-time assignments). `search` snapshots `(index, chunks, metadata, bm25)` into locals under the same lock, then runs the FAISS/BM25 query lock-free against the snapshot. Chosen over the immutable holder-object form because it is the smaller diff against the existing field layout; the holder form is noted as the cleaner long-term follow-up.

### Code Changes

* `mcp_server/mpep_search.py` — add `self._index_lock` in `__init__`; rewrite `build_index` publish to a single locked critical section; add the snapshot-under-lock to `search`.
* `tests/test_index_atomicity.py` — concurrency test.

### Rollback Plan

`git revert` restores the unlocked publish/read. No persisted-state shape change.

## TDD Implementation Workflow

| Step | Status/Details | Universal Check |
| :---: | :--- | :---: |
| **1. Write Failing Test** | `tests/test_index_atomicity.py` — search-during-rebuild race | - [ ] A failing test that reproduces the bug is committed |
| **2. Verify Test Fails** | Run against unlocked code; observe tear/`IndexError` | - [ ] Test suite was run and the new test fails as expected |
| **3. Implement Code Fix** | `_index_lock` + locked publish + snapshot read | - [ ] Code changes are complete and committed |
| **4. Verify Test Passes** | Race no longer reproduces over many iterations | - [ ] The original failing test now passes |
| **5. Run Full Test Suite** | `pytest tests/` green; single-threaded query semantics unchanged | - [ ] All existing tests still pass (no regressions) |
| **6. Code Review** | Sprint reviewer | - [ ] Code review approved by at least one peer |
| **7. Update Documentation** | Module docstring invariant + CLAUDE.md gotcha | - [ ] Documentation is updated (DaC) |
| **8. Deploy to Staging** | N/A (library; verified via tests) | - [ ] Fix deployed to staging environment |
| **9. Staging Verification** | Concurrency test green | - [ ] Bug fix verified in staging environment |
| **10. Deploy to Production** | Sprint branch | - [ ] Fix deployed to production environment |
| **11. Production Verification** | Phase 4 background rebuild does not tear | - [ ] Bug fix verified in production environment |

### Test Code (Failing Test)

```python
# tests/test_index_atomicity.py (sketch — models stubbed)
def test_search_during_rebuild_never_tears(stub_models, tiny_corpora):
    idx = MPEPIndex(...)            # built on corpus A
    errors, mismatches = [], []
    def hammer():
        for _ in range(2000):
            try:
                for row in idx.search("q", top_k=5):
                    if row.metadata["source"] not in row.chunk_sources_allowed:
                        mismatches.append(row)
            except IndexError as e:
                errors.append(e)
    t = threading.Thread(target=hammer); t.start()
    idx.build_index(force_rebuild=True)   # corpus B, different size
    t.join()
    assert not errors and not mismatches
```

## Definition of Done

### Intent

A background rebuild of the search corpus can run while users are actively searching, and no search ever crashes or returns a row stitched from two different corpus generations. From the outside, searches stay correct and never raise `IndexError` even at the exact moment a rebuild swaps in a larger or smaller corpus. If this is broken, an engineer would see intermittent `IndexError`s from the search tool, or search results whose metadata source does not match the returned text, appearing only when a rebuild happens to overlap a query.

### Observable outcomes

- [ ] `MPEPIndex.__init__` creates `self._index_lock` (an RLock); `build_index` publishes `index`/`chunks`/`metadata`/`bm25` in one critical section under it.
- [ ] `search` snapshots the four fields under `self._index_lock` and runs the FAISS/BM25 query against the snapshot; single-threaded query results are byte-for-byte unchanged from before.
- [ ] `search` against a never-built index still raises the existing "Index not built" `ValueError` (no regression).
- [ ] Capstone: a thread hammering `search` (thousands of iterations) while another thread runs `build_index(force_rebuild=True)` that changes corpus size raises no `IndexError` and returns no row whose metadata source disagrees with its chunk, repeatably across the test's many interleavings.

## Infrastructure as Code (IaC) Considerations (optional)

* [ ] Infrastructure changes required
* [x] No infrastructure changes — library-internal concurrency fix

| IaC Component | Change Required | Status |
| :--- | :--- | :--- |
| **N/A** | None | N/A |

## Testing & Verification

### Test Plan

| Test Type | Test Case | Expected Result | Status |
| :--- | :--- | :--- | :--- |
| **Unit Test** | `search` against never-built index | raises existing `ValueError` | - [ ] Pass |
| **Concurrency Test** | hammer `search` during `build_index(force_rebuild=True)` | no `IndexError`, no cross-generation row, many iterations | - [ ] Pass |
| **Regression Test** | single-threaded `search` results before/after | identical | - [ ] Pass |
| **Edge Case 1** | rebuild that grows the corpus | reader sees all-old or all-new | - [ ] Pass |
| **Edge Case 2** | rebuild that shrinks the corpus | no out-of-range index into chunks | - [ ] Pass |
| **Manual Test** | run Phase 4 trigger after this lands | no tear on first background rebuild | - [ ] Pass |

### Verification Checklist

* [ ] Original race is no longer reproducible
* [ ] All new tests pass
* [ ] All existing tests still pass (no regressions)
* [ ] Code review completed and approved
* [ ] Documentation updated
* [ ] Staging environment verification complete
* [ ] Production environment verification complete
* [ ] Monitoring shows healthy metrics (no new errors)

## Regression Prevention

* [ ] **Automated Test:** concurrency test added in `tests/test_index_atomicity.py`
* [ ] **Integration Test:** Phase 4 integration exercises a real background rebuild (separate card)
* [ ] **Type Safety:** N/A
* [ ] **Linting Rules:** N/A
* [ ] **Code Review Checklist:** publish/read of corpus fields must be under `_index_lock`
* [ ] **Monitoring/Alerting:** N/A (no error expected post-fix)
* [ ] **Documentation:** publish-under-lock invariant documented in module docstring

## Validation & Finalization

| Task | Detail/Link |
| :--- | :--- |
| **Code Review** | Sprint reviewer |
| **Test Results** | `tests/test_index_atomicity.py` |
| **Staging Verification** | Concurrency test green |
| **Production Verification** | Phase 4 background rebuild does not tear |
| **Documentation Update** | `mpep_search.py` docstring + `CLAUDE.md` gotcha |
| **Monitoring Check** | No `IndexError` from search under rebuild |

### Follow-up gitban cards

| Topic | Action Required | Tracker | Gitban Cards |
| :--- | :--- | :--- | :--- |
| **Postmortem** | No | this card | — |
| **Documentation Debt** | CLAUDE.md gotcha added | this card | this card |
| **Technical Debt** | Holder-object corpus snapshot is the cleaner long-term shape (KD9) | note-only | follow-up |
| **Process Improvement** | None | — | — |
| **Related Bugs** | None | — | — |

### Completion Checklist

* [ ] Root cause is fully understood and documented
* [ ] Fix follows TDD process (failing test → fix → passing test)
* [ ] All tests pass (unit, integration, regression)
* [ ] Documentation updated (DaC)
* [ ] No manual infrastructure changes
* [ ] Deployed and verified
* [ ] Monitoring confirms fix is working (no new errors)
* [ ] Regression prevention measures added (tests)
* [ ] Postmortem completed (if required for P0/P1)
* [ ] Follow-up tickets created for related issues
* [ ] Associated ticket is closed

### Note on validation

This card follows a structured template. Keep its sections, checkboxes, and tables and fill them in rather than removing them.
