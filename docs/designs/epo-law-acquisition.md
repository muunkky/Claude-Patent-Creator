# Design Doc: EPO/EPC Law Acquisition — Validate-Then-Persist, Discover-In-Force, Deferred-Default

> **ADR**: [ADR-001](../adr/ADR-001-epo-law-acquisition-architecture.md) | **PRD**: [PRD-001](../prds/PRD-001-epo-law-acquisition.md) | **Date**: 2026-06-21 | **Author**: cameronrout

## Overview

This design implements ADR-001's five coordinated decisions for the EPO/EPC acquisition layer
(`mcp_server/epo_downloaders.py`). Today a clean install ships an **empty European corpus**:
`download_epc()` saves a ~28 KB HTML landing page under `epc_convention.pdf` (the indexer ingests
it as one junk chunk), `scrape_epo_guidelines()` downloads an orphaned *draft* PDF the indexer
never reads, both functions skip re-acquisition on `dest_path.exists()` alone (so junk is never
repaired), and no documented CLI command ever invokes acquisition at all.

The architecture is organized around a single primitive — a per-source **artifact-validity
predicate** that answers "is what I have (or just fetched) real, in-force law?" That predicate is
the gate for persistence (never save junk), the gate for idempotency (skip valid, re-acquire
invalid), the signal for observability, and the floor that lets a partial scrape fail loudly. On
top of it: EPC acquires by fetching the WIPO Lex landing page and extracting an HTML-entity-encoded
signed asset URL; the EPO Guidelines edition is *discovered* from the EPO entry page rather than
hardcoded; and acquisition is wired into the documented build path but **deferred** — it fires on
first EPO/PCT use, not on every `setup`, sparing the US-majority install a multi-minute scrape
against a public institution's site.

The indexer *parsers* are fixed: `extract_text_from_epc` (a trilingual two-column PDF parser) and
`extract_text_from_epo_guidelines` (reads `epo_guidelines.txt` in `PART X - TITLE` / `### Section`
format) already landed on `main` (commit `c9b8779`). This design decides how acquisition produces
artifacts those parsers accept, and how acquisition is triggered. It does **not** treat
`mpep_search.py` as untouched: two surgical changes there are in scope and on the critical path —
(1) `MPEPIndex.build_index` is made **reader-atomic** so a background rebuild cannot tear a
concurrent `search` (the trigger publishes a new corpus while readers are live), and
(2) `extract_text_from_epc` is refactored to a **module-level free function** so the validity
predicate can call it without instantiating an `MPEPIndex` (which eagerly loads two ML models in
`__init__`). The bound method delegates to the free function, so the indexer's behavior is unchanged.

## Requirements

The implementation is complete when:

1. **R1 — Junk is never persisted.** No acquisition path writes an artifact under its real filename
   without it first passing the source's validity predicate; an invalid fetch leaves no junk file.
2. **R2 — Idempotency keys on validity, not existence.** A build/trigger re-acquires iff the target
   artifact is absent **or** present-but-invalid, and skips iff present-and-valid. Both
   `dest_path.exists()` short-circuits (`epo_downloaders.py:92`, `:185`) are gone.
3. **R3 — EPC acquires as a real PDF.** `download_epc()` resolves the WIPO Lex signed asset URL
   (host + `Signature`/`Expires`/`Key-Pair-Id` triple, HTML-unescaped), downloads, validates, and
   atomically promotes; on any failure it fails loud and leaves no junk `.pdf`.
4. **R4 — Guidelines acquire the in-force edition, discovered.** The edition is resolved at run time
   from a raw-HTML parse of the EPO entry page (highest year-stamped `…/guidelines-epc/(\d{4})/…`
   link); the hardcoded `YEAR` and the draft-PDF path are removed; no `…-draft-…` or
   `epo_guidelines_{year}.pdf` artifact is produced.
5. **R5 — A partial scrape fails, not ships.** The Guidelines scrape writes `epo_guidelines.txt`
   only when the section-success ratio over the intended A–H part set is ≥ the floor (0.95); below
   it, nothing is written. A `epo_guidelines.manifest.json` sidecar is written manifest-first, and a
   `.txt` without a consistent manifest is invalid.
6. **R6 — Acquisition is wired, deferred-default, and the user's query never blocks on it.**
   `setup`/`rebuild-index` register but do not eagerly run EPO/PCT acquisition by default. The first
   `search_patent_law(jurisdiction in {EPO,PCT})` against an absent/invalid corpus returns
   **immediately** with whatever US results exist plus an honest "EU corpus not yet acquired —
   acquisition started in background, retry in a few minutes" notice, and kicks off acquisition +
   rebuild on a **background thread** (guarded by a process-lifetime flag so only one runs).
   `--with-epo` forces a *synchronous* eager acquisition at setup; `--skip-epo` disables it entirely.
   The synchronous heavy path is reserved for the operator-controlled `--with-epo` / `download-all`
   route, never the interactive query path.
7. **R7 — Index publication is atomic w.r.t. readers.** A rebuild triggered by acquisition builds the
   new FAISS index, BM25, chunks, and metadata into local variables and publishes them under a lock
   in a single critical section; a concurrent `search` either sees the entire old corpus or the
   entire new one, never a new index paired with stale chunks/metadata. No reader ever crashes or
   returns mismatched rows because of an in-flight rebuild.
8. **R8 — The validity check loads no ML models.** Computing `validate_epc` (which delegates to the
   EPC extractor) does not construct an `MPEPIndex` and therefore loads neither the SentenceTransformer
   nor the CrossEncoder. Every idempotency check is model-load-free.
9. **R9 — Failure is loud, never silent.** Every per-source outcome (resolved edition, sizes,
   fetched/with-content counts, pass/fail) is logged; an EPO/PCT acquisition failure is non-fatal to
   the overall build but surfaces a clear source-named message, never a silently-empty result. EPO/PCT
   analyzer tools that reach EU law surface a "run an EPO search first / corpus still acquiring" hint
   when the corpus is empty rather than returning a blank analysis (S2).
10. **R10 — Validators and acquisition are TDD-covered.** Validators, signed-URL extraction,
    edition discovery, success-ratio gating, the reader-atomic index swap, and the non-blocking
    background trigger each have tests against saved fixtures; an integration test proves a clean
    build (after the background acquisition completes) yields a non-empty EU corpus.

## Current State

`mcp_server/epo_downloaders.py` is a flat module of download functions. The relevant surface:

- `_download_file(url, dest_path, description, timeout)` (`:76`) — streams a URL to disk. **Skips on
  `dest_path.exists()` (`:92`)**; on exception, unlinks the partial file. No content validation: a
  200-OK HTML body saved under a `.pdf` name "succeeds."
- `download_epc(dest_dir)` (`:125`) — calls `_download_file(EPC_DOWNLOAD_URL, …)` where
  `EPC_DOWNLOAD_URL = "https://www.wipo.int/wipolex/en/text/312166"` is the **HTML landing page**,
  not a PDF. Docstring is stale ("The EPO HTML version is more current").
- `scrape_epo_guidelines(dest_dir, year)` (`:169`) — **skips on `dest_path.exists()` (`:185`)**,
  then tries the draft-PDF URL (`EPO_GUIDELINES_DRAFT_PDF_PATTERN`), and only on failure falls back
  to `_scrape_epo_guidelines_html`, which fetches eight `…/2024/part-{x}` pages with a regex HTML
  strip — it does **not** emit the `### {title} [{stem}]` per-section format the indexer needs.
- `download_all_epo_documents(dest_dir)` (`:342`) → `{epc, epo_guidelines}`; `check_epo_pct_sources`
  (`:373`) reports **existence only**.

The proven prototype is `scripts/_epo_guidelines_scrape.py`: it discovers `[a-h]*.html` section URLs
from a seed page's nav, fetches each `<main>` with 3-attempt backoff, strips share/breadcrumb chrome,
and emits the exact `PART X - TITLE` / `### {title} [{stem}]` format. It hardcodes `YEAR = "2026"`
(`:15`), carries the `PART_TITLES["c"]` "Procedureal" typo (`:21`), and was written to discover-and-dump,
not validate.

The indexer (`mcp_server/mpep_search.py`) — **parsers fixed; two surgical seams in scope** (see
KD2, KD9):

- `extract_text_from_epc(pdf_path)` (`:458`) — opens the PDF with PyMuPDF, keys on two-column
  trilingual layout (`MIDX` English column, `Article N` / `Rule N` headers), returns provision chunks.
  It is **a bound method but reads no instance state** beyond the pure helper
  `_chunk_text_with_metadata` (`:223`) — confirmed: its only `self.` reference is that stateless
  chunker. The WIPO trilingual PDF is the exact document this parser targets.
- `extract_text_from_epo_guidelines(text_path)` (`:553`) — reads `epo_guidelines.txt`, splits on
  `^PART\s+([A-H])\s*[-–]\s*(.+)` and `^(?:###+|####)\s*(.+)`, returns chunks.
- `MPEPIndex.__init__` (`:149-153`) **eagerly loads `SentenceTransformer("BAAI/bge-base-en-v1.5")`
  and `CrossEncoder("ms-marco-MiniLM-L-6-v2")`** before any index exists. Constructing an `MPEPIndex`
  purely to borrow the bound `extract_text_from_epc` would force both model loads on every idempotency
  check — the defect B2 fixes.
- `build_index(force_rebuild)` (`:801`) — loads the FAISS index if present and `force_rebuild` is
  false; otherwise re-extracts **every** source present in `MPEP_DIR` (each guarded by `file.exists()`)
  and rebuilds. EPC at `:885`, Guidelines at `:895`. The publish step is **not atomic**: it assigns
  `self.index` (`:957`), `self.add` to it (`:958`), then `self.chunks` (`:960`), `self.metadata`
  (`:962-987`), and `self.bm25` (`:993`) one field at a time, **with no lock**. `search` (`:1013`)
  reads `self.index` (`:1064`), `self.chunks` (`:1079`), and `self.metadata` (`:1080`) concurrently —
  so a `search` interleaved with a rebuild can see the *new* FAISS index returning indices into the
  *old* `self.chunks`, yielding wrong rows or an `IndexError`. The current code never hits this
  because `build_index` only runs at process startup inside `LazyMPEPIndex._load`'s lock (server.py
  `:134-153`) before any tool serves a query — but the deferred trigger introduces exactly the
  concurrent-rebuild-during-live-search scenario this design must make safe (B1a). A built index is a
  snapshot: **adding a corpus file after build requires `build_index(force_rebuild=True)` to make it
  searchable.**

CLI wiring (`mcp_server/cli.py`): `setup_command` (`:432`), `rebuild_index_command` (`:851`,
downloads nothing), `download_all_command` (`:889`, US-only). None call `download_all_epo_documents`.
The only EPO trigger is `server.py:507-519` behind `--download-epo`/`--download-all`, which `setup`
never passes.

The search tool (`mcp_server/tools/patent_law_tools.py`): `search_patent_law(query, jurisdiction,
top_k)` maps `jurisdiction` → source filters (`JURISDICTION_SOURCES`) and queries the shared
`mpep_index`. EPO sources are `["EPC", "EPC_RULES", "EPO_GUIDELINES"]`; PCT is `["PCT", "PCT_RULES"]`.
When a filtered source has no chunks, the per-source search silently yields nothing. The tool is
registered by `register_patent_law_tools(mcp, mpep_index, log_info, log_error, validate_input,
SearchPatentLawInput, track_performance)` — note its current signature captures **only** `mpep_index`,
*not* `MPEP_DIR`. The call site is `server.py:407`. `MPEP_DIR` is a module global defined identically
(`Path(__file__).parent.parent / "pdfs"`) in `server.py:94`, `mpep_search.py:89`, and
`health_check.py:26`; the `tools` package does not import it. The deferred trigger needs both the
rebuild handle (`mpep_index`, which is the `LazyMPEPIndex` proxy — confirmed) and `mpep_dir`, so the
registration signature must be widened (B3) — and to avoid a `tools → server` import cycle, the
canonical `MPEP_DIR` is taken from `mpep_search` (which `tools` already imports transitively).

The EPO/PCT **analyzer** tools (`mcp_server/tools/epo_analyzer_tools.py`) and the EPC/PCT skills do
**not** route through `search_patent_law` — they call `mpep_index.search(...)` directly for EPC/Art.
guidance (`:78`, `:113`, `:171`, `:208`). They therefore bypass any trigger placed only in
`search_patent_law` and would silently return blank EU analysis against an unacquired corpus (S2).

Tests live in `tests/` (pytest, `testpaths = ["tests"]`), with shared fixtures in
`tests/conftest.py`. There is no `tests/fixtures/` directory yet and no test touching
`epo_downloaders.py`.

## Target State

```
   FIRST EPO/PCT search_patent_law()  (deferred-default)         CLI: setup --with-epo
   ── returns US results + "acquiring in background" ──┐         download-all (eager, SYNCHRONOUS)
   spawns daemon thread (process-lifetime guard) ──────┤                 │
                                                       │                 │
                              mode="background"        ▼                 ▼ mode="eager"
                    ┌────────────────────────────────────────────────────────────────┐
                    │   ensure_epo_pct_corpus(mpep_dir, index, mode)  [new]            │
                    │   for each source: validate(dest); if absent|invalid → acquire   │
                    │   if anything acquired → index.build_index(force_rebuild=True)    │
                    │     └─ build_index now publishes the new corpus ATOMICALLY under  │
                    │        index._index_lock (KD9): readers see all-old or all-new    │
                    └───────────────┬──────────────────────────────┬─────────────────┘
                                    │                              │
                ┌───────────────────▼──────────┐   ┌───────────────▼───────────────────┐
                │ download_epc(dest)            │   │ scrape_epo_guidelines(dest)        │
                │  GET landing page            │   │  discover_in_force_edition()       │
                │  extract signed URL (host +  │   │   raw-HTML parse, highest year     │
                │   Sig/Exp/KPId triple)       │   │  discover_section_urls() [a-h]      │
                │  html.unescape()             │   │  fetch each (pace 0.15s, 3-retry)  │
                │  fetch_validate_promote(     │   │  ratio ≥ 0.95 ? else FAIL no-write │
                │    fetch, validate_epc, dest)│   │  write manifest.json THEN .txt      │
                └───────────────┬──────────────┘   └───────────────┬────────────────────┘
                                │                                  │
                                ▼                                  ▼
                    ┌──────────────────────────┐      ┌──────────────────────────────────┐
                    │ validate_epc(path)->bool │      │ validate_guidelines(path)->bool   │
                    │  %PDF- magic + size floor│      │  size floor + parses ≥ chunk floor│
                    │  extract_text_from_epc   │      │  under PART/### + manifest-        │
                    │   yields ≥ provision floor│      │  consistent                       │
                    └──────────────────────────┘      └──────────────────────────────────┘
                                │                                  │
                                ▼                                  ▼
                          pdfs/epc_convention.pdf          pdfs/epo_guidelines.txt
                                                           pdfs/epo_guidelines.manifest.json
```

Shared persistence spine: `fetch_validate_promote(fetch_fn, validate_fn, dest)` downloads to a temp
path in the same directory, runs `validate_fn`, and `os.replace`-promotes on pass (atomic single-file
promote); on fail it unlinks the temp and returns `False` with a logged, source-named reason. Junk is
never visible under the real filename.

After all phases: a default `setup` completes at US-corpus speed with no EU artifacts; the first
EPO/PCT query returns US results immediately with an honest "acquiring in background" notice and
spawns the acquisition; once the background acquisition + atomic rebuild finishes, a subsequent EPO/PCT
query returns genuine EPC Art. 84 text plus an in-force Guidelines clarity passage (`setup --with-epo`
does the same synchronously at setup time); rebuilds with valid artifacts re-acquire nothing;
corrupted artifacts re-acquire; concurrent searches during a rebuild never tear; every outcome is
logged.

## Design

### Architecture

All new acquisition code lives in `mcp_server/epo_downloaders.py` (the prototype is promoted out of
`scripts/_epo_guidelines_scrape.py` into this module — the script is deleted). The module gains four
layers:

1. **Configuration constants** — floors, pacing, retries, timeouts, URLs (top of module).
2. **Validity predicates** — `validate_epc(path)`, `validate_guidelines(path)`, each `-> bool`,
   each pure (filesystem-reading, no network).
3. **Persistence spine** — `fetch_validate_promote(fetch_fn, validate_fn, dest)`.
4. **Acquisition flows** — `download_epc`, `scrape_epo_guidelines` (and its helpers
   `discover_in_force_edition`, `discover_section_urls`, `fetch_section`), rewritten on the spine.

The **orchestration + trigger** is a `trigger_epo_pct_corpus(...)` wrapper (the chokepoint) plus the
worker `ensure_epo_pct_corpus(...)`, both in `epo_downloaders.py` to keep acquisition logic in one
module (M1: orchestration *that touches the index handle and threading* is thin glue; the heavy
acquisition lives here, and the server/CLI own only the call sites — noted as a tolerable layering
choice, not an inversion, because `epo_downloaders` already owns `download_all_epo_documents`). It is
reached from four sites:

- **Deferred / background (default):** `search_patent_law` in `patent_law_tools.py`, the first time it
  is called with `jurisdiction in {"EPO","PCT"}` against an absent/invalid corpus. It does **not**
  block: it returns US results plus an "acquiring in background" notice and spawns a daemon thread
  running `ensure_epo_pct_corpus(mode="background")`, guarded by a process-lifetime flag so only one
  runs (KD6/KD7).
- **Analyzer chokepoint (S2 — chosen resolution):** the EPO/PCT analyzer tools in
  `epo_analyzer_tools.py` call the **same** `trigger_epo_pct_corpus(...)` chokepoint before their
  `mpep_index.search(...)`. We hoist the guarded trigger into one shared function that every
  EPO/PCT-jurisdiction tool calls, rather than scope it to `search_patent_law` only — analyzers that
  reach EU law must kick off acquisition the same way, and surface the same "still acquiring / run an
  EPO search first" hint when the corpus is empty.
- **Eager (`--with-epo`):** `setup_command` / `rebuild_index_command` in `cli.py` — **synchronous**.
- **Explicit-all:** `download_all_command` in `cli.py` and the existing `server.py` flag path —
  **synchronous**.

`ensure_epo_pct_corpus` validates each target artifact; for any that is absent-or-invalid it runs the
acquisition function; if **anything** was acquired it calls `index.build_index(force_rebuild=True)`,
which (after KD9) publishes the new corpus atomically. It returns a structured per-source result for
logging and caller-facing messages.

```
mcp_server/
  epo_downloaders.py        # validators, spine, flows, ensure_epo_pct_corpus,
                            #   trigger_epo_pct_corpus (chokepoint + bg thread), config
  cli.py                    # --with-epo / --skip-epo wiring; SYNCHRONOUS eager call; download-all
  server.py                 # flag path delegates to ensure_epo_pct_corpus (dedupe);
                            #   register_patent_law_tools call site (:407) gains mpep_dir arg
  mpep_search.py            # TOUCHED: (a) extract_text_from_epc -> module-level free function +
                            #   delegating method (B2/KD2); (b) build_index reader-atomic publish
                            #   under a new index._index_lock; search() reads under the same lock (B1a/KD9)
  tools/patent_law_tools.py # register_patent_law_tools(+ mpep_dir); deferred bg trigger before EPO/PCT search
  tools/epo_analyzer_tools.py # call shared trigger_epo_pct_corpus before EPC/Art. searches (S2)
scripts/
  _epo_guidelines_scrape.py # DELETED (promoted into module)
tests/
  fixtures/                 # saved landing page, entry page, good/junk PDFs, stub txt
  test_epo_validators.py
  test_epo_extract_urls.py
  test_epo_edition_discovery.py
  test_epo_scrape_gating.py
  test_index_atomicity.py        # NEW: concurrent search-during-rebuild never tears
  test_epo_acquisition_integration.py
```

### Key Design Decisions

**KD1 — One shared single-file promote helper, not per-source bespoke persistence.** Both sources
share `fetch_validate_promote(fetch_fn, validate_fn, dest)`. `fetch_fn(temp_path) -> None` performs
the source-specific download/scrape into `temp_path`; `validate_fn(temp_path) -> bool` is the source
predicate; the helper does temp-create / validate / `os.replace`-or-`unlink`. *Alternative considered:*
inline the temp-validate-promote into each flow. *Rejected:* it duplicates the crash-safety logic and
invites one flow to drift (e.g. forget the `unlink`). One helper, two `fetch_fn`s, is the long-route
choice. Note the Guidelines flow's *final* promote (the `.txt`) does **not** go through this helper
directly, because the Guidelines need a two-file manifest-first ordered write (KD5) — but each
individual file within that flow still uses temp + atomic rename.

**KD2 — `validate_epc` reuses the landed extractor *as a module-level free function* (single source
of truth, zero model loads).** `validate_epc` calls the EPC extractor and asserts the provision count
≥ floor, after the cheap gates (magic bytes, size). *Alternative considered:* a lighter independent
PDF probe. *Rejected per ADR-001 D1/Key-Factor-5:* an independent probe can say "valid" while the
indexer extracts nothing (or vice-versa) — drift precisely where the predicate must assure. The WIPO
source **is** the document the extractor was authored against, so there is no layout-mismatch
false-negative to fear. A shared fixture (a known-good EPC PDF) pins both `validate_epc` and the
indexer to the same expectation.

The decision (not a hand-wave): `extract_text_from_epc` is refactored into a **module-level pure
function** `extract_epc_provisions(pdf_path) -> list[dict]` in `mpep_search.py`. It is already pure
over `pdf_path` — its only `self.` reference is the stateless helper `_chunk_text_with_metadata`,
which is likewise extracted to (or invoked as) a module-level helper. `MPEPIndex.extract_text_from_epc`
becomes a one-line delegate `return extract_epc_provisions(pdf_path)` (preserving the indexer call
path), and `validate_epc` imports the free function directly. *Alternative considered (and rejected):*
construct a "minimal" `MPEPIndex` or a lazy singleton to borrow the bound method — but `MPEPIndex.__init__`
eagerly loads `SentenceTransformer(bge-base)` **and** `CrossEncoder` (mpep_search.py:149-153), so any
instance-based route forces two ML model loads at **every** idempotency check (R8 violation). The free
function loads nothing and is the only route that keeps validation cheap while staying single-source.
This is why `mpep_search.py` is in the file-touch list (KD9 is the other reason).

**KD3 — Validators are pure booleans returning `False` (not raising) on invalidity.** Predicate
semantics are "is this artifact real law?" — a clean boolean. The *flows* decide what a `False` means
(don't promote / re-acquire) and own the loud logging. *Alternative considered:* raise a typed
`InvalidArtifact` exception. *Rejected:* the predicate is consulted in a skip-or-acquire branch where
`False` is an ordinary, expected outcome, not an error; reserving exceptions for genuine faults (file
unreadable mid-check) keeps call sites simple. Validators **do** log a reason at debug level so a
maintainer can see *why* an artifact was rejected.

**KD4 — Edition discovery is a raw-HTML parse, fail-loud, with a logged manual override.**
`discover_in_force_edition()` GETs `https://www.epo.org/en/legal/guidelines-epc` (raw, unreduced
HTML), extracts every `…/legal/guidelines-epc/(\d{4})/…` link, and returns the highest year. If the
page is unreachable or yields **no** year-stamped link, it raises a source-named error and the
Guidelines source fails (no silent fallback to a hardcoded year). A `--guidelines-edition` /
`edition=` override is the explicit, prominently-logged escape hatch. *Alternative considered:*
follow a redirect from the entry page. *Rejected per ADR-001 D3:* the entry page returns 200 with no
3xx; multiple editions are simultaneously live; only a raw-HTML parse selects the presented-current
edition.

**KD5 — Manifest-first ordered write; `.txt`-without-consistent-manifest is invalid.** Two
`os.replace` calls are not jointly atomic, so the scrape writes `epo_guidelines.manifest.json` first
(atomic rename), then `epo_guidelines.txt` (atomic rename). `validate_guidelines` treats a `.txt`
present without a consistent manifest as **invalid**. The only crash-observable states are "neither,"
"manifest only" (→ no `.txt`, treated as not-acquired), and "both" (→ validated against manifest).
The manifest carries `{edition, discovered, fetched, with_content, ratio, completed_at}` — the
section-success ratio is scrape-time metadata not recoverable from the `.txt` alone, which is exactly
why a from-file chunk-count floor cannot distinguish "short edition" from "broken partial scrape."

**KD6 — Deferred trigger never blocks the query: it returns immediately and acquires on a background
thread.** The defect (B1b): the original design ran the ~1,887-page scrape + full re-embed
*synchronously inside* `search_patent_law`, so the user's first EPO query would hang for many minutes.
The fix: `search_patent_law`, on `jurisdiction in {EPO,PCT}` against an absent/invalid corpus, returns
**immediately** with whatever US results exist plus a structured notice
(`{"notice": "EU corpus not yet acquired — acquisition started in background; retry in a few minutes",
"jurisdiction": <EPO|PCT>}`), and spawns a `threading.Thread(daemon=True)` running
`ensure_epo_pct_corpus(mpep_dir, mpep_index, mode="background")`. A **process-lifetime guard** (a
module-level `_epo_acquire_lock` + `_epo_acquire_started` flag) ensures only one background acquisition
ever launches; a second EPO query while acquisition is in flight returns the same "still acquiring"
notice without spawning a duplicate. After the background acquisition completes and publishes the
corpus (KD9), the *next* EPO/PCT query returns real EU law.

*Why `search_patent_law` is the trigger site:* `build_index` runs for US-only builds too (coupling US
builds to EPO is wrong) and `search` is jurisdiction-agnostic (would fire for US queries).
`search_patent_law` (and the analyzer chokepoint, S2) is where the user signals they want EU law —
the precise condition ADR-001 D4 names. A no-arg `jurisdiction=None` (search-all) query does **not**
trigger acquisition; it searches whatever is indexed (ADR-001's "capability on demand"), so broad
US-only queries are never taxed.

*Why background, not synchronous, for the interactive path:* a multi-minute hang inside an MCP tool
call is a worse UX than an honest "come back in a few minutes," and a synchronous trigger turns every
first-EPO-query into a timeout risk. The **synchronous** heavy path is retained for the
operator-controlled `--with-epo` and `download-all` routes (`mode="eager"`), where the operator has
explicitly asked to build everything now and a long wait is expected.

**KD7 — The background trigger is announced and its failure is surfaced, never silent.** The returned
notice explains the pause before any work blocks the user. On the background thread, every per-source
outcome is logged with a source name; if acquisition fails, the failure is logged loudly and the
process-lifetime flag is **reset** so a later query can retry (a failed background attempt must not
permanently wedge the corpus as "started"). The user sees, on the next EPO query, either real EU law
(success) or the same honest "EU corpus not yet acquired — <last reason>" notice (still-failing),
never a silently-empty result with no explanation.

**KD9 — `build_index` publishes the new corpus atomically under an index lock; `search` reads under
it.** The defect (B1a): `build_index` assigns `self.index`/`self.chunks`/`self.metadata`/`self.bm25`
one field at a time with no lock (mpep_search.py:957-993), and `search` reads `self.index`,
`self.chunks`, `self.metadata` with no lock (:1064, :1079-1081). A background rebuild interleaved with
a live search can pair a *new* FAISS index with the *old* chunk list → wrong rows or `IndexError`.
The fix: build the new FAISS index, BM25, `chunks`, and `metadata` into **local variables** for the
whole extraction/embedding pass, then publish them in **one critical section** guarded by a new
`self._index_lock = threading.RLock()` (created in `__init__`). `search` acquires the same lock only
for the brief window where it snapshots `(self.index, self.chunks, self.metadata, self.bm25)` into
locals before doing the (lock-free, read-only) FAISS/BM25 query — so a reader sees either the entire
old corpus or the entire new one, never a torn pair. *Alternative considered:* a single immutable
holder object (`self._corpus = CorpusSnapshot(index, chunks, metadata, bm25)`) swapped with one atomic
assignment, letting readers grab `self._corpus` lock-free. *Chosen:* the lock-around-the-four-assignments
form, because it is the smaller diff against the existing `MPEPIndex` field layout and the
snapshot-into-locals read keeps the hot path's lock-hold to nanoseconds; the holder-object form is
noted as the cleaner long-term shape (a follow-up refactor, not a v1 requirement). Either way the
publish is atomic w.r.t. readers (R7). This change is independent of EPO acquisition and benefits any
future concurrent rebuild — which is why B1a is split into its own card sequenced **before** the
trigger card (the trigger depends on the atomic swap existing).

**KD8 — Floors and pacing are documented module constants, not inline literals.** All gate values
live as named constants with docstrings (see Interface Design). They are the launch criteria from
PRD-001 Phases 1/2; the architecture owns that they *exist and gate everything*, the constants own
their values.

### Interface Design

#### Configuration constants (`epo_downloaders.py`, top of module)

```python
# --- EPC validity floors ---
EPC_MIN_SIZE_BYTES = 200_000        # real EPC PDF ~1-2 MB; HTML landing page ~28 KB
EPC_MIN_PROVISIONS = 100            # extract_text_from_epc yields hundreds; junk yields ~0-1

# --- Guidelines validity floors ---
GUIDELINES_MIN_SIZE_BYTES = 1_000_000   # in-force .txt is multi-MB; stub is bytes
GUIDELINES_MIN_CHUNKS = 500             # PART/### parse yields thousands; stub yields ~0
GUIDELINES_SUCCESS_RATIO_FLOOR = 0.95   # with_content / (discovered - gone_404) over A-H set

# --- PCT validity floor (M2: lighter check; PCT is not a problem source) ---
PCT_MIN_SIZE_BYTES = 50_000             # genuine PCT treaty/rules PDFs; HTML error page is smaller

# --- Scrape resilience ---
GUIDELINES_REQUEST_DELAY_S = 0.15   # politeness pacing between section fetches
GUIDELINES_MAX_RETRIES = 3          # per-section, exponential backoff
GUIDELINES_PART_LETTERS = "abcdefgh"  # intended A-H; I/J/K/M deliberately excluded
GUIDELINES_MIN_DISCOVERED = 1_500   # lower-bound sanity floor on discovered section URLs (S3):
                                    #   in-force editions present ~1,800+ A-H section pages; a
                                    #   discovery regression that finds far fewer must FAIL, not
                                    #   pass a 0.95 ratio over too-small a set
GUIDELINES_RESUME_MAX_ROUNDS = 2    # bounded retry of ONLY the failed-non-404 sections (S1)

# --- URLs ---
WIPO_EPC_LANDING_URL = "https://www.wipo.int/wipolex/en/text/312166"
EPO_GUIDELINES_ENTRY_URL = "https://www.epo.org/en/legal/guidelines-epc"

# Filenames
EPC_FILE = "epc_convention.pdf"
EPO_GUIDELINES_FILE = "epo_guidelines.txt"
EPO_GUIDELINES_MANIFEST_FILE = "epo_guidelines.manifest.json"
```

The draft-PDF constants (`EPO_GUIDELINES_DRAFT_PDF_PATTERN`) are **deleted**.

#### Validity predicates

```python
def validate_epc(path: Path) -> bool:
    """True iff `path` is a real, in-force EPC PDF the indexer can ingest.

    Gates, cheapest-first: file exists; first bytes are b"%PDF-"; size >= EPC_MIN_SIZE_BYTES;
    extract_text_from_epc(path) yields >= EPC_MIN_PROVISIONS provision chunks (single source of
    truth — same extractor the indexer uses). Returns False (logs a debug reason) on any miss;
    never raises for an ordinary invalid artifact.
    """

def validate_guidelines(path: Path) -> bool:
    """True iff `path` is a complete, in-force EPO Guidelines text file.

    Gates: file exists; size >= GUIDELINES_MIN_SIZE_BYTES; a consistent manifest sidecar
    (epo_guidelines.manifest.json) exists with ratio >= GUIDELINES_SUCCESS_RATIO_FLOOR and an
    edition; extract_text_from_epo_guidelines(path) parses >= GUIDELINES_MIN_CHUNKS chunks under
    the PART/### contract. A .txt without a consistent manifest is INVALID (KD5).
    """
```

#### Persistence spine

```python
def fetch_validate_promote(
    fetch_fn: Callable[[Path], None],
    validate_fn: Callable[[Path], bool],
    dest: Path,
) -> bool:
    """Download to a temp path in dest.parent, validate, os.replace into dest on pass.

    fetch_fn(temp) performs the source-specific fetch into temp. On validate pass: atomic
    os.replace(temp, dest), return True. On fetch exception or validate fail: unlink temp,
    log a source-named reason, return False. Never leaves junk under `dest`.
    """
```

#### EPC flow

```python
def download_epc(dest_dir: Path) -> bool:
    """Acquire the genuine EPC PDF from WIPO Lex (ADR-001 D2).

    1. GET WIPO_EPC_LANDING_URL (durable, unsigned HTML).
    2. extract_signed_epc_url(html) -> str   # host wipolex-res.wipo.int + /edocs/ path,
                                              # query carries Signature & Expires & Key-Pair-Id;
                                              # fallback: any .pdf src/href with the triple.
    3. html.unescape(url)                     # &#x3D;->=, &amp;->& before fetching.
    4. fetch_validate_promote(fetch=GET(unescaped_url)->temp, validate_epc, dest_dir/EPC_FILE)
       (extract + download in one flow; signed URL expires).
    Fails loud (logged, EPC-named) and persists nothing if no signed URL is found or the body
    is not a valid EPC PDF. Stale docstring corrected.
    """

def extract_signed_epc_url(landing_html: str) -> Optional[str]:
    """Return the embedded signed EPC asset URL, or None. Primary pattern keys on the WIPO asset
    host (wipolex-res.wipo.int, /edocs/ path) + the Signature/Expires/Key-Pair-Id triple; fallback
    widens to any .pdf src/href carrying the triple. Does NOT html.unescape (caller does)."""
```

#### Guidelines flow

```python
def discover_in_force_edition(entry_html: Optional[str] = None) -> str:
    """Return the in-force edition year (e.g. "2026") as the highest year-stamped
    …/legal/guidelines-epc/(\\d{4})/… link in the EPO entry page's RAW HTML.
    Fetches EPO_GUIDELINES_ENTRY_URL if entry_html is None. Raises a source-named error if the
    page is unreachable or contains no parseable year-stamped link (no hardcoded fallback)."""

def discover_section_urls(edition: str, seed_html: Optional[str] = None) -> list[str]:
    """Discover all A-H section page stems for the resolved edition prefix
    /legal/guidelines-epc/{edition}/, scoped to GUIDELINES_PART_LETTERS (I/J/K/M excluded).

    SEED STRATEGY (S3): the prototype seeded from a single page (a.html) and regexed [a-h], which
    only works if that one page embeds the FULL cross-part A-H tree — an unverified, load-bearing
    assumption behind the 0.95 denominator. Instead, seed from the edition INDEX
    (/legal/guidelines-epc/{edition}/index.html) when it embeds the full part nav; otherwise UNION
    one seed per part (a.html..h.html), deduplicating stems. The discovered set must satisfy
    len(stems) >= GUIDELINES_MIN_DISCOVERED, else raise a source-named error (a discovery regression
    cannot be allowed to pass a high success ratio computed over too few sections)."""

def fetch_section(url: str) -> Optional[tuple[str, str]]:
    """Return (title, body) for one section page, None for empty/exhausted retries, or the sentinel
    GONE for a consistent HTTP 404 (legitimately removed section). Pacing + GUIDELINES_MAX_RETRIES
    exponential backoff; strips share/breadcrumb chrome (promoted from the prototype's fetch_text).
    The GONE vs None distinction lets the caller treat a removed section differently from a
    timed-out one (S1)."""

def scrape_epo_guidelines(dest_dir: Path, edition: Optional[str] = None) -> bool:
    """Acquire in-force EPO Guidelines into epo_guidelines.txt (ADR-001 D3/D5).

    Resolve edition (discover unless overridden) -> discover A-H section URLs (>= MIN_DISCOVERED,
    S3) -> fetch each with pacing/retry, recording per-section outcome AND distinguishing
    GONE(404) from FAILED(timeout/empty). RESUME (S1): before declaring failure, run up to
    GUIDELINES_RESUME_MAX_ROUNDS bounded retries of ONLY the FAILED-non-404 sections (the manifest
    already records fetched/with_content per section). Compute ratio = with_content / (discovered -
    gone_404) — consistently-404 sections are EXCLUDED from the denominator, not counted as
    failures, so legitimately-removed sections don't sink an otherwise-complete scrape. If ratio <
    GUIDELINES_SUCCESS_RATIO_FLOOR after resume: FAIL, write nothing. Else: write manifest.json
    FIRST (temp+rename) then .txt (temp+rename), each in PART X - TITLE / ### {title} [{stem}]
    format. PART_TITLES['c'] typo fixed. No draft-PDF path."""
```

Manifest schema (`epo_guidelines.manifest.json`):

```json
{
  "edition": "2026",
  "discovered": 1887,
  "gone_404": 3,
  "fetched": 1884,
  "with_content": 1881,
  "failed_sections": [],
  "resume_rounds": 1,
  "ratio": 0.9984,
  "completed_at": "2026-06-21T12:00:00Z"
}
```

`ratio = with_content / (discovered - gone_404)` (S1). `failed_sections` lists the stems that were
still failing after `resume_rounds` bounded retries — empty on a clean pass. `discovered` must be
≥ `GUIDELINES_MIN_DISCOVERED` (S3) for the scrape to proceed at all.

#### Orchestration / trigger

```python
def validate_pct(path: Path) -> bool:
    """True iff `path` is a usable PCT source PDF (M2 — resolved, not an open question).

    PCT sources are genuine fixed-URL PDFs that already work, so the predicate is the lighter
    PDF check: file exists; first bytes are b"%PDF-"; size >= PCT_MIN_SIZE_BYTES. It does NOT run a
    structural extractor (PCT is not a problem source and has no scrape/edition-discovery failure
    mode). This is exactly enough to keep a clean PCT query from needlessly re-acquiring while still
    re-acquiring a truncated/HTML-as-PDF artifact."""

def ensure_epo_pct_corpus(mpep_dir: Path, index, mode: str = "background") -> dict[str, Any]:
    """Validate-then-acquire EPO/PCT artifacts and rebuild the index if anything changed.

    For EPC, EPO Guidelines (validate_epc/validate_guidelines) and PCT sources (validate_pct):
    validate(dest); if absent-or-invalid, acquire. If anything was acquired, call
    index.build_index(force_rebuild=True) (atomic publish, KD9). Returns
    {"acquired": [...], "skipped": [...], "failed": [{source, reason}], "rebuilt": bool}.
    mode="background" runs on the daemon thread spawned by the trigger; mode="eager" is the
    SYNCHRONOUS --with-epo / download-all path. Non-fatal: per-source failures are collected and
    returned/logged, never raised to abort the caller."""

def trigger_epo_pct_corpus(mpep_dir: Path, index, jurisdiction: str) -> Optional[dict[str, Any]]:
    """Shared chokepoint for the deferred-default trigger (KD6/KD7, S2).

    Honors PATENT_SKIP_EPO (returns None — hard US-only). If the EPO/PCT corpus for `jurisdiction`
    is already present-and-valid, returns None (caller proceeds normally). Otherwise, under the
    process-lifetime lock: if no acquisition has started, set the started-flag and spawn a daemon
    Thread running ensure_epo_pct_corpus(mode="background") (resetting the flag on failure so a
    later call can retry); either way return the structured "acquiring in background" notice for the
    caller to surface. Called by BOTH search_patent_law and the epo_analyzer_tools before their
    mpep_index.search(...) — so analyzers never silently hit an empty corpus."""
```

#### CLI surface (`cli.py`)

```
setup            [--with-epo] [--skip-epo]   # default: register, do not eagerly acquire
rebuild-index    [--with-epo] [--skip-epo]   # default: register, do not eagerly acquire
download-all     # unchanged role: eager "build everything now" → also runs ensure_epo_pct_corpus(mode="eager")
```

`--with-epo` and `--skip-epo` are mutually exclusive (argparse mutually-exclusive group). `--skip-epo`
sets an env var (`PATENT_SKIP_EPO=true`) that the deferred trigger also honors (hard US-only: never
acquire, even in the background).

## Implementation Phases

The phases are sequenced risk-first. Phase 0 lands the spine that Phases 1–2 depend on (ADR-001 makes
D1 the prerequisite for D2/D3/D4). **Phase 3 (index atomicity, B1a) is its own phase sequenced
*before* Phase 4 (the trigger, B1b)** — because the trigger card and the atomicity card both touch
`build_index`/`MPEPIndex`, and if dispatched in parallel they would collide on the same surface. The
atomicity fix is independent of EPO acquisition (it benefits any concurrent rebuild), so it lands and
is verified on its own before the trigger that *depends* on it is built. The B2 free-function
refactor of `extract_text_from_epc` (the other `mpep_search.py` seam) is pulled forward into Phase 0,
since the validators in Phase 0 depend on it.

Mapping to PRD-001: Phase 1 = PRD Phase 1, Phase 2 = PRD Phase 2, Phase 4 = PRD Phase 3; Phase 0 (D1
spine + B2 seam) and Phase 3 (B1a atomicity) are the engineering prerequisites the PRD folds into "the
artifact-validity predicate" and "deferred-default wiring," now made explicit and independently
sequenced.

### Phase 0: Validity-predicate spine + extractor free-function refactor (ADR D1 + B2 — prerequisite for all)

**Goal:** The validators (model-load-free) and the single-file promote helper exist and are
unit-tested, the EPC extractor is a module-level free function the validator imports, and the
existence short-circuits are removed from the two acquisition entry points — before any flow is
rewritten.

**Deliverables:**
- **B2 seam:** `extract_text_from_epc` refactored to a module-level `extract_epc_provisions(pdf_path)`
  in `mpep_search.py` (and the `_chunk_text_with_metadata` helper made module-level or otherwise
  callable without an `MPEPIndex`); `MPEPIndex.extract_text_from_epc` becomes a one-line delegate.
- `validate_epc` (imports `extract_epc_provisions` — no `MPEPIndex`, no model load), `validate_guidelines`,
  `validate_pct`, `fetch_validate_promote` in `epo_downloaders.py`.
- Configuration constants block (floors, pacing, retries, filenames, MIN_DISCOVERED, RESUME_MAX_ROUNDS,
  PCT_MIN_SIZE_BYTES); draft-PDF constants deleted.
- `_download_file:92` and `scrape_epo_guidelines:185` `dest_path.exists()` short-circuits removed
  (the functions are rewired onto the spine in Phases 1–2; in the interim they call the predicate).
- `tests/fixtures/`: a known-good EPC PDF (small real sample or trimmed), a junk HTML-as-PDF (~28 KB),
  a truncated PDF, a valid `epo_guidelines.txt` + matching manifest, a stub `.txt`, a `.txt` with no
  manifest, a `.txt` with a stale/low-ratio manifest.
- `tests/test_epo_validators.py`.

**Test strategy (written first):**
- Unit: `extract_epc_provisions` (free function) returns the same chunks as the old bound method on
  the good fixture; `MPEPIndex.extract_text_from_epc` delegates to it (identity check).
- Unit: calling `validate_epc` constructs **no** `MPEPIndex` and loads no model — assert via a
  monkeypatch/spy on `SentenceTransformer`/`CrossEncoder` that neither is instantiated (R8).
- Unit: `validate_epc` returns `True` for the good fixture, `False` for HTML-as-PDF (magic-byte
  fail), truncated PDF (size fail), and a valid-but-unrelated large PDF (provision-count fail).
- Unit: `validate_guidelines` returns `True` for valid `.txt`+manifest, `False` for stub (size/chunk),
  `.txt`-without-manifest (KD5), and `.txt` with ratio-below-floor manifest.
- Unit: `validate_pct` returns `True` for a real PDF above the size floor, `False` for HTML-as-PDF
  and a sub-floor file (M2).
- Unit: `fetch_validate_promote` promotes on a passing `validate_fn`, unlinks the temp and returns
  `False` (no `dest`) on a failing one, and leaves no temp file behind on `fetch_fn` raising.

**Infrastructure:** `tests/fixtures/` added under version control (small fixtures only; the good EPC
PDF must be small enough to commit — use a trimmed/representative sample, not the full 906-page file,
sized just above the floors with enough provisions to clear `EPC_MIN_PROVISIONS`, or lower the test's
floor via a constant injected in the test).

**Documentation:** Module docstring documents the validity-predicate spine and the floor constants;
`CLAUDE.md` "Critical Gotchas" gains a note that EPO/EPC idempotency is validity-keyed, not existence-keyed.

**Dependencies:** Landed `extract_text_from_epc` / `extract_text_from_epo_guidelines` on `main`.

**Definition of done:**
- [ ] `extract_epc_provisions` is a module-level function; `MPEPIndex.extract_text_from_epc` delegates to it; indexer behavior unchanged.
- [ ] `validate_epc` loads no ML model and constructs no `MPEPIndex` (spy-proven); `validate_epc`/`validate_guidelines`/`validate_pct` are pure (no network) and pass the fixture matrix.
- [ ] `fetch_validate_promote` exists and its temp/promote/unlink behavior is unit-proven.
- [ ] Neither `epo_downloaders.py` entry point short-circuits on `dest_path.exists()`.
- [ ] All floor/pacing values are named constants; no inline magic numbers in control flow.
- [ ] `tests/test_epo_validators.py` passes under `pytest tests/`.

### Phase 1: EPC acquires as a real PDF (PRD Phase 1, ADR D2)

**Goal:** `download_epc()` resolves the WIPO signed asset URL, downloads, validates, and atomically
promotes a genuine EPC PDF; failure leaves no junk.

**Deliverables:**
- `extract_signed_epc_url(landing_html)` and the rewritten `download_epc(dest_dir)` on the spine.
- Stale `download_epc` docstring corrected.
- `tests/fixtures/wipo_epc_landing.html` (a saved real landing page with the entity-encoded signed src).
- `tests/test_epo_extract_urls.py`.

**Test strategy (written first):**
- Unit: `extract_signed_epc_url` returns the signed URL from the saved landing-page fixture; the
  result still contains entities (`&#x3D;`/`&amp;`) and `html.unescape` of it yields a fetchable
  query string with `Signature`/`Expires`/`Key-Pair-Id` intact.
- Unit: `extract_signed_epc_url` returns `None` for a landing page with no signed link (drives the
  fail-loud path); the fallback pattern matches a `.pdf` href carrying the triple even when the host
  differs.
- Unit (no network): `download_epc` with a monkeypatched fetch promotes when the fetched bytes pass
  `validate_epc` (good fixture) and persists nothing + returns `False` when the body is HTML.

**Infrastructure:** none beyond the saved fixture.

**Documentation:** `download_epc` docstring rewritten; the WIPO extraction point documented inline
as the single repair location if WIPO markup changes (ADR-001's "fix one pattern at a documented
location").

**Dependencies:** Phase 0.

**Definition of done:**
- [ ] `extract_signed_epc_url` passes the fixture extraction + None-case tests.
- [ ] `download_epc` promotes a valid EPC PDF and leaves no junk on any failure (monkeypatched).
- [ ] The stale "EPO HTML version is more current" docstring is gone.
- [ ] `tests/test_epo_extract_urls.py` passes.

### Phase 2: EPO Guidelines acquire as in-force `epo_guidelines.txt` (PRD Phase 2, ADR D3/D5)

**Goal:** The Guidelines scrape discovers the in-force edition, scrapes A–H into `epo_guidelines.txt`
in `PART/###` format with manifest sidecar, gates on the 0.95 success ratio, and never writes a thin
file or a draft PDF.

**Deliverables:**
- Prototype promoted into `epo_downloaders.py`: `discover_in_force_edition`, `discover_section_urls`,
  `fetch_section`, rewritten `scrape_epo_guidelines` with manifest-first ordered write and ratio gate.
- `PART_TITLES["c"]` "Procedureal" typo fixed; hardcoded `YEAR` removed; draft-PDF path deleted.
- `scripts/_epo_guidelines_scrape.py` deleted.
- `--guidelines-edition` override threaded through (logged when used).
- `tests/fixtures/epo_entry_page.html` (saved entry page with multiple year-stamped links).
- `tests/test_epo_edition_discovery.py`, `tests/test_epo_scrape_gating.py`.

**Test strategy (written first):**
- Unit: `discover_in_force_edition` returns the **highest** year from the multi-edition fixture
  (e.g. picks 2026 over 2025); raises a source-named error for a fixture with no year-stamped link
  and for an unreachable page (monkeypatched).
- Unit: `discover_section_urls` scopes to `[a-h]`, excludes `i/j/k/m`, and **raises** when the seed
  yields fewer than `GUIDELINES_MIN_DISCOVERED` stems (S3 regression guard); the index-seed and
  union-of-per-part-seed strategies both reach the full set on the fixture.
- Unit: `fetch_section` returns the `GONE` sentinel on a consistent 404 and `None` on timeout/empty,
  so the two are distinguishable (S1).
- Unit: `scrape_epo_guidelines` — ratio computed as `with_content / (discovered - gone_404)` so a
  fixture with a few legitimate 404s still passes; FAILED-non-404 sections are retried up to
  `GUIDELINES_RESUME_MAX_ROUNDS` and a section that succeeds on resume is counted (S1).
- Unit: `scrape_epo_guidelines` with monkeypatched section fetches — ratio ≥ floor writes manifest
  **then** `.txt` (assert write order and both present); ratio < floor (after resume) writes
  **neither** and returns `False`; a mid-scrape crash (manifest written, `.txt` not) leaves no `.txt`
  and `validate_guidelines` reports invalid.
- Unit: emitted `.txt` matches `^PART\s+([A-H])` and `^###` so `extract_text_from_epo_guidelines`
  parses it (round-trip through the real extractor on a small synthetic scrape).

**Infrastructure:** saved entry-page fixture; section fetches are monkeypatched (no live ~1,887-request
scrape in CI).

**Documentation:** module docstring documents discovery, the A–H-in / I·J·K·M-out scope, the manifest
schema, and the ratio gate; the EPO entry-page parse documented as the second repair location.

**Dependencies:** Phase 0.

**Definition of done:**
- [ ] `discover_in_force_edition` selects the highest year and fails loud on no link.
- [ ] `discover_section_urls` enforces `>= GUIDELINES_MIN_DISCOVERED` (S3) and the seed strategy reaches the full A–H set.
- [ ] `scrape_epo_guidelines` resumes failed-non-404 sections (bounded), excludes 404s from the denominator (S1), writes manifest-first, gates on 0.95, and writes nothing below floor.
- [ ] `PART_TITLES["c"]` fixed; no hardcoded `YEAR`; no draft-PDF code path; script deleted.
- [ ] Emitted `.txt` round-trips through `extract_text_from_epo_guidelines`.
- [ ] `tests/test_epo_edition_discovery.py` and `tests/test_epo_scrape_gating.py` pass.

### Phase 3: Reader-atomic index publish (B1a — prerequisite for the Phase 4 trigger)

**Goal:** A `build_index(force_rebuild=True)` running concurrently with live `search` calls never tears:
a reader sees the entire old corpus or the entire new one. This lands and is verified **before** the
trigger that introduces concurrent rebuilds, so the two cards never collide on `build_index`/`MPEPIndex`.

**Deliverables:**
- `MPEPIndex.__init__` gains `self._index_lock = threading.RLock()`.
- `build_index` rewritten to assemble the new FAISS index, BM25, `chunks`, and `metadata` into **local
  variables** across the whole extract/embed pass, then publish all four under `self._index_lock` in a
  single critical section (replacing the field-at-a-time assignments at mpep_search.py:957-993).
- `search` snapshots `(index, chunks, metadata, bm25)` into locals under `self._index_lock`, then runs
  the FAISS/BM25 query lock-free against the snapshot (the only behavior change is the brief snapshot
  lock; query semantics are identical).
- `tests/test_index_atomicity.py`.

**Test strategy (written first):**
- Unit/concurrency: a thread hammering `search` while another thread runs `build_index(force_rebuild=True)`
  on the same `MPEPIndex` (tiny synthetic corpora, models stubbed) never raises `IndexError` and never
  returns a row whose metadata source disagrees with its chunk — run many iterations to surface the race.
- Unit: after a rebuild that changes corpus size, every `search` result indexes a chunk that exists in
  the *same* generation's `chunks`/`metadata` (no cross-generation pairing).
- Unit: `search` against a never-built index still raises the existing "Index not built" `ValueError`
  (no regression).

**Infrastructure:** models stubbed so the concurrency test is fast and CI-safe; no network.

**Documentation:** `mpep_search.py` docstring notes the publish-under-lock invariant; `CLAUDE.md`
"Critical Gotchas" gains a note that `build_index` is reader-atomic and a background rebuild is safe.

**Dependencies:** Phase 0 (the B2 free-function refactor is the other `mpep_search.py` change; this
phase is otherwise independent of Phases 1–2 and may run in parallel with them, but **must precede
Phase 4**).

**Definition of done:**
- [ ] `build_index` publishes index/chunks/metadata/bm25 atomically under `self._index_lock`.
- [ ] `search` reads a consistent snapshot under the same lock; query results are unchanged for the single-threaded case.
- [ ] The concurrency test passes repeatably (no tear, no `IndexError`) over many interleavings.
- [ ] `tests/test_index_atomicity.py` passes under `pytest tests/`.

### Phase 4: Deferred-default, non-blocking, background wiring + hardening (PRD Phase 3, ADR D4)

**Goal:** A clean `setup` is US-speed; the first EPO/PCT query returns US results immediately with an
"acquiring in background" notice and spawns acquisition; once the background acquisition + atomic
rebuild completes, EPO/PCT queries return real EU law; `--with-epo` does it synchronously;
`--skip-epo` disables it; every outcome is logged.

**Deliverables:**
- `ensure_epo_pct_corpus(mpep_dir, index, mode)` and `trigger_epo_pct_corpus(mpep_dir, index,
  jurisdiction)` in `epo_downloaders.py` (validate → acquire → atomic `build_index(force_rebuild=True)`
  → structured result; trigger owns the process-lifetime lock/flag and the daemon-thread spawn).
- B3 wiring: widen `register_patent_law_tools(...)` to accept `mpep_dir` and update the **server.py:407**
  call site to pass it (sourced from `mpep_search.MPEP_DIR` to avoid a `tools → server` import cycle).
- Non-blocking deferred trigger in `search_patent_law` (`patent_law_tools.py`): on
  `jurisdiction in {EPO,PCT}` against an absent/invalid corpus and not `PATENT_SKIP_EPO`, call
  `trigger_epo_pct_corpus(...)`, **return immediately** with US results + the "acquiring in background"
  notice; the trigger spawns the daemon acquisition thread under the process-lifetime guard.
- S2: the EPO/PCT analyzer tools (`epo_analyzer_tools.py`) call the same `trigger_epo_pct_corpus(...)`
  chokepoint before their `mpep_index.search(...)`, and surface the "still acquiring / run an EPO
  search first" hint when the corpus is empty.
- `--with-epo` / `--skip-epo` mutually-exclusive flags on `setup`/`rebuild-index`; **synchronous** eager
  call in those commands; `download_all_command` runs `ensure_epo_pct_corpus(mode="eager")` synchronously.
- `server.py` `--download-epo` path delegates to `ensure_epo_pct_corpus` (dedupe the logic).
- `tests/test_epo_acquisition_integration.py`.

**Test strategy (written first):**
- Unit: the deferred trigger in `search_patent_law` **returns without blocking** — assert the call
  returns before the (stubbed, artificially slow) acquisition finishes, and that the response carries
  the "acquiring in background" notice alongside US results.
- Unit: the process-lifetime guard spawns exactly **one** background thread across two near-simultaneous
  EPO queries; a failed background attempt resets the flag so a later query retries (KD7).
- Unit (B3): `register_patent_law_tools` accepts and threads `mpep_dir`; the trigger reaches the right
  directory (no `NameError`/`MPEP_DIR` capture gap).
- Unit (S2): an analyzer tool against an empty EU corpus calls `trigger_epo_pct_corpus` and returns the
  hint, not a blank analysis.
- Integration (monkeypatched network, real atomic index build on tiny synthetic corpora): a clean
  `MPEP_DIR` with US-only artifacts → deferred trigger spawns acquisition of synthetic EPC/Guidelines
  fixtures → after the background thread joins, `search_patent_law(jurisdiction="EPO")` returns
  non-empty EU results — proving the clean-build-yields-non-empty-EU-corpus criterion end to end.
- Integration: with **valid** EPC/Guidelines already present, `ensure_epo_pct_corpus` acquires nothing
  and does not rebuild (network call count is 0); with a **corrupted** artifact it re-acquires.
- Integration: `PATENT_SKIP_EPO=true` makes the deferred trigger a no-op (US-only); `mode="eager"`
  forces synchronous acquisition regardless of the trigger.

**Infrastructure:** integration tests run with monkeypatched downloaders/scrape and a temp `MPEP_DIR`;
the background thread is joined deterministically in tests (no sleeps); marked `slow` if the real
embedding/index build is exercised, so CI can deselect with `-m "not slow"`.

**Documentation:** `CLAUDE.md` (Quick Reference / Skills) and the relevant slash-command/skill docs
updated to state EPO/PCT acquires **in the background** on first use (first query returns a notice;
retry once acquisition completes), `--with-epo` for synchronous eager, `--skip-epo` for US-only;
PRD-001's false "no consolidated PDF" line corrected (ADR-001 flags it).

**Dependencies:** Phases 1, 2, and **3** (the trigger relies on the atomic publish from Phase 3).

**Definition of done:**
- [ ] Default `setup` runs no EPO scrape and leaves no EU artifacts.
- [ ] First `search_patent_law(jurisdiction="EPO")` against an empty corpus returns immediately with US results + an "acquiring in background" notice and spawns one acquisition thread (does not block).
- [ ] After the background acquisition completes, a subsequent EPO query returns EU results.
- [ ] Analyzer tools (`epo_analyzer_tools.py`) trigger acquisition via the shared chokepoint and surface the hint on an empty corpus (S2).
- [ ] `register_patent_law_tools` receives `mpep_dir` (B3); the server.py:407 call site passes it; no import cycle.
- [ ] Re-trigger with valid artifacts re-acquires nothing; corrupted artifacts re-acquire.
- [ ] `--with-epo` forces synchronous eager; `--skip-epo`/`PATENT_SKIP_EPO` disables acquisition.
- [ ] Per-source outcomes (edition, sizes, counts, pass/fail) appear in logs and caller messages.
- [ ] `tests/test_epo_acquisition_integration.py` passes.

## Migration & Rollback

**Migration:** No data migration. On the first post-change EPO/PCT trigger (or eager build), the
validity predicates re-evaluate any existing `pdfs/epc_convention.pdf` and `epo_guidelines.txt`: an
existing 28 KB HTML-as-PDF fails `validate_epc` and is re-acquired; an orphaned
`epo_guidelines_{year}.pdf` is simply never read (and never produced again); a `.txt` without a
manifest fails `validate_guidelines` and is re-scraped. Operators take no manual action. Behavior
change to be aware of: a default `setup` no longer attempts EPO at all (it deferred), so anyone who
relied on `setup` eagerly building EU law must now pass `--with-epo` or let the first EPO query
trigger a background acquisition (and retry once it completes) — documented in Phase 4's DaC.

**Rollback:** Clean `git revert` of the branch restores the prior `epo_downloaders.py`, the deleted
prototype script, and the unwired CLI. No persisted state changes shape that would survive a revert
(the manifest sidecar is additive and ignored by the reverted code). The only residue is any
EU artifact already acquired under the new code, which the reverted (existence-keyed) code would
treat as "present" — harmless, since those artifacts are valid by construction.

## Risks

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| WIPO changes landing-page markup; `extract_signed_epc_url` returns wrong/None | EPC fails to acquire | Medium | Targeted+fallback pattern; `validate_epc` backstop rejects non-EPC bytes; single documented repair point; fail-loud not silent |
| EPO changes entry-page structure; `discover_in_force_edition` finds no year link | Guidelines fail to acquire | Medium | Fail-loud with the URL parsed; `--guidelines-edition` logged override; `validate_guidelines` rejects thin output |
| Committing a real EPC PDF fixture is too large / licensing concern | Phase 0 test infra blocked | Medium | Use a trimmed/representative PDF sized just above floors, or inject lower floors in tests; do not commit the full 906-page file |
| Background rebuild tears a concurrent `search` (new index vs stale chunks) | Wrong results / `IndexError` crash | High (if unaddressed) | Phase 3 / KD9 makes publish reader-atomic under `_index_lock`; concurrency test proves no tear; Phase 3 sequenced **before** the trigger |
| Background acquisition + full re-embed still costs minutes | EU law not available on the *first* EPO query | Medium | Query returns immediately with an honest "acquiring in background, retry shortly" notice (KD6/KD7); not a hang; `--with-epo` lets operators pre-pay synchronously; future: incremental index add |
| Background acquisition thread fails silently | EU corpus never appears, no signal | Medium | KD7 logs the failure loudly and resets the process-lifetime flag so a later query retries; next query surfaces the last reason, never a blank result |
| Live ~1,887-request scrape exercised in CI by accident | Slow/flaky CI, rate-limit exposure | Low | All section fetches monkeypatched in tests; integration marked `slow`; no test hits live EPO/WIPO |
| Two `os.replace` for manifest+`.txt` race a concurrent reader | Reader sees manifest-only state | Low | KD5 ordering makes manifest-only → not-acquired (predicate invalid), never a half-ingested `.txt` |
| Analyzer tools bypass the `search_patent_law` trigger | Silent empty EU analysis | Medium | S2: analyzers call the shared `trigger_epo_pct_corpus` chokepoint and surface a "still acquiring" hint on empty corpus |
| Single-seed `discover_section_urls` misses cross-part sections | High ratio over too-small a set → thin corpus ships | Medium | S3: index-seed or union-per-part seed + `>= GUIDELINES_MIN_DISCOVERED` lower-bound guard fails loud on a discovery regression |
| Concurrent first EPO queries both trigger acquisition | Duplicate scrape | Low | Process-lifetime lock + started-flag in `trigger_epo_pct_corpus`; only one daemon thread spawns; second waiter returns the same notice |

## Roadmap Connection

- **Story:** `m2/s1` — "European & international law ingestion produces complete, in-force corpora."
- **Project:** `m2/s1/epo-downloaders-fix` (PRD-001's roadmap anchor).
- This design doc is the implementation bridge for ADR-001 and should be linked as the `docs_ref` on
  the `epo-downloaders-fix` feature (the parent project's `docs_ref` is the ADR/PRD).
- No roadmap restructuring needed; the three PRD phases map to design Phases 1, 2, and 4, with Phase 0
  (D1 spine + B2 free-function seam) and Phase 3 (B1a reader-atomic index publish) as the engineering
  prerequisites the PRD folds into "the artifact-validity predicate" and "deferred-default wiring." The
  five-phase split exists so the index-atomicity card (touching `build_index`/`MPEPIndex`) lands and is
  verified *before* the trigger card that depends on it — they must not be dispatched in parallel.

## Open Questions

1. **EPC fixture provenance.** Can we legally/practically commit a trimmed EPC PDF as a test fixture,
   or do we generate a synthetic two-column PDF that the landed extractor parses into ≥ floor
   provisions? (Affects Phase 0 test infra; the design assumes a small committable fixture but
   tolerates injected floors as a fallback.)
2. **Incremental index add (deferred, not blocking).** `build_index(force_rebuild=True)` re-embeds the
   entire corpus (US + EU). The background trigger (KD6) removes this from the user's critical path, so
   the full rebuild is acceptable for v1; an incremental "add EU chunks to the existing index" path is
   an explicit follow-up, not in scope here (ADR-001 lists incremental as a Neutral/future consequence).
   *No longer a gate on this design.*

**Resolved during this revision (were open questions, now decisions):**
- **PCT validator (was Q3, M2 — RESOLVED).** PCT gets a lighter `validate_pct` = "exists + `%PDF-` +
  size ≥ `PCT_MIN_SIZE_BYTES`" (no structural extractor), since PCT sources are genuine fixed-URL PDFs
  with no scrape/edition failure mode. This is exactly enough to stop a clean PCT query from needlessly
  re-acquiring while still catching a truncated/HTML-as-PDF artifact. See KD/Interface `validate_pct`.

---

## Revision History

| Date | Author | Notes |
|------|--------|-------|
| 2026-06-21 | cameronrout | Initial design from ADR-001 (D1–D5) and PRD-001 (Phases 1–3). |
| 2026-06-21 | cameronrout | Adversarial-review revision: B1 (reader-atomic `build_index` publish, KD9, new Phase 3; non-blocking background trigger, KD6/KD7); B2 (`extract_text_from_epc` → module-level free function, KD2, no model load on validate); B3 (`register_patent_law_tools` gains `mpep_dir`, server.py:407); S1 (bounded resume of failed-non-404 sections, 404s excluded from ratio denominator); S2 (shared `trigger_epo_pct_corpus` chokepoint for analyzer tools); S3 (seed strategy + `GUIDELINES_MIN_DISCOVERED` guard); M1 (orchestration layering note); M2 (`validate_pct` resolved). Phase 3 split out and sequenced before the trigger (now Phase 4). |
