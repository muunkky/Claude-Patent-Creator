# PRD-001: Reliable EPC & EPO Guidelines Law Acquisition

> **Status**: Draft | **Date**: 2026-06-21 | **Author**: cameronrout
> **Roadmap**: m2/s1/epo-downloaders-fix

## Problem Statement

A patent professional installs Claude Patent Creator, builds the search index from
scratch, and asks `search_patent_law(jurisdiction="EPO")` for the EPC clarity
requirement (Art. 84) or the corresponding EPO Guidelines passage. They get nothing
useful back. The European and international law that the product advertises as
"Ready" is, in a clean install, effectively absent: the European Patent Convention
indexes as a single chunk of junk HTML, and the EPO Guidelines never get indexed at
all. The user has no way to know this short of inspecting the index — the system
silently returns empty or irrelevant results for an entire jurisdiction. For a tool
whose core promise is cross-jurisdiction patent-law RAG, a jurisdiction that quietly
fails to ingest is a broken promise that erodes trust in every answer the tool gives.

## Background & Context

Claude Patent Creator ingests legal corpora in two stages. First,
`mcp_server/epo_downloaders.py` acquires source documents into `pdfs/` (the
`MPEP_DIR`). Second, `mcp_server/mpep_search.py:build_index()` chunks and embeds each
source into the FAISS + BM25 index that `search_patent_law` queries. The US side of
this pipeline (MPEP / 35 USC / 37 CFR) works and is the reference standard: a clean
`rebuild-index` produces a rich, searchable US corpus with no manual intervention.
The PCT side (Treaty, Regulations, ISPE Guidelines) also works, because those sources
are genuine, stable PDFs at fixed URLs.

The European side does not work. The acquisition layer for the two most important EU
sources — the EPC and the EPO Guidelines for Examination — produces artifacts that the
indexer either rejects or never reads. This was discovered while verifying the law
index and is the reason story `m2/s1` exists: to bring European/international ingestion
up to the same "complete, in-force, out-of-the-box" standard as the already-working US
ingestion.

Two acquisition bugs in `epo_downloaders.py` are the entire problem (both verified
against the live code and the live external sites):

1. **EPC is an HTML landing page, not a PDF.** `EPC_DOWNLOAD_URL` points at
   `https://www.wipo.int/wipolex/en/text/312166`, which is a WIPO Lex HTML landing
   page — not the PDF it is assumed to be. `download_epc()` saves roughly 28 KB of
   HTML to `epc_convention.pdf`. `extract_text_from_epc()` then yields a single junk
   chunk. The genuine EPC PDF on WIPO Lex is served via a signed, ephemeral CloudFront
   URL; requesting the bare asset path returns HTML, not the file. The signed asset URL
   is embedded in the landing-page HTML. Any working fix must fetch the landing page
   and extract the signed URL before downloading the actual PDF.

2. **EPO Guidelines download the wrong artifact, in the wrong format, that the
   indexer never reads.** `scrape_epo_guidelines()` downloads the annual *draft
   consultation* PDF (`…guidelines-draft-{year}.pdf`) and saves it as
   `epo_guidelines_{year}.pdf`. This fails the product on two counts. First, the
   indexer's `extract_text_from_epo_guidelines()` reads only `epo_guidelines.txt` — so
   the downloaded PDF is orphaned and never indexed. Second, a draft consultation
   document is *not in-force law*; indexing it (even if the indexer read it) would
   surface non-authoritative text as if it were binding examination guidance. The
   in-force EPO Guidelines (2026 edition) are published HTML-only — there is no
   consolidated PDF. They comprise roughly 1,887 server-rendered section pages,
   discoverable from any section page's embedded navigation, and must be scraped into
   `epo_guidelines.txt` in the `PART X - TITLE` / `### Section` format that the indexer
   parses.

A reference scraper for the Guidelines has already been prototyped at
`scripts/_epo_guidelines_scrape.py` (committed on `main`). It discovers all
`a.html … h*.html` section URLs from a seed page's embedded links, fetches each
`<main>` block with retry/backoff, strips the social-share and breadcrumb chrome, and
emits the exact `PART X - TITLE` plus `### {title} [{stem}]` layout that
`extract_text_from_epo_guidelines()` keys on (it matches `^PART\s+([A-H])\s*[-–]\s*…`
for parts and `^(?:###+|####)\s*(.+)` for sections). It is a proven starting point,
not throwaway exploration — the production fix should build from it rather than reinvent
discovery and parsing.

**Why now.** The indexer-side fixes that made this work *possible* already landed on
`main`: the `extract_text_from_epc` trilingual-PDF parser was rewritten, and the
`build_index` `KeyError: 'page'` was fixed. The indexer is now ready to consume a real
EPC PDF and a real `epo_guidelines.txt` — the only thing standing between a clean build
and a searchable European corpus is the acquisition layer. This is the last mile.

## User Segments

### Patent practitioner running EPO/PCT review workflows
- **Who**: Patent attorneys, agents, and drafters using the EPO and PCT skills
  (`epo-patent-analyzer`, `epc-search`, `pct-application`, `/review-epo-claims`) to
  check applications against Art. 84 / Art. 83 EPC and the EPO Guidelines.
- **Current pain**: `search_patent_law(jurisdiction="EPO")` returns empty or junk
  results because the EPC indexed as one garbage chunk and the Guidelines were never
  indexed. EPO compliance features have no authoritative corpus underneath them.
- **Desired outcome**: A fresh install gives them real, in-force EPC articles and EPO
  Guidelines text on the first query — the same quality they already get for US law.
- **Priority**: Primary

### Operator installing or rebuilding the system
- **Who**: A developer or end user running the documented install path
  (`patent-creator setup`, `rebuild-index`) on a clean machine.
- **Current pain**: There is no working path to a complete EU corpus. Getting one
  today requires manually stashing a hand-acquired EPC PDF and a hand-scraped text
  file into `pdfs/` — undocumented, fragile, and unknowable without reading source.
- **Desired outcome**: One clean rebuild populates EPC and EPO Guidelines automatically,
  with no manual artifact placement.
- **Priority**: Primary

### Maintainer of the ingestion pipeline
- **Who**: The engineer who owns `epo_downloaders.py` and the index build.
- **Current pain**: When acquisition silently produces a bad artifact (HTML-as-PDF,
  orphaned draft), nothing fails loudly. The breakage is invisible until someone
  queries the corpus and notices it is empty.
- **Desired outcome**: Acquisition validates what it produced and fails loudly when it
  did not get real, in-force law — so silent corpus rot cannot recur.
- **Priority**: Secondary

## Goals & Non-Goals

### Goals
- A clean, from-scratch index build ingests genuine, in-force EPC text and in-force
  EPO Guidelines text with zero manual artifact placement.
- `download_epc()` reliably acquires a real EPC PDF (resolving the WIPO Lex signed
  CloudFront URL), not an HTML landing page.
- The EPO Guidelines acquisition produces `epo_guidelines.txt` — the artifact the
  indexer actually reads — from the in-force HTML edition, in the format the indexer
  parses.
- No orphaned or non-authoritative artifacts (draft PDFs, HTML-as-PDF) are produced.
- Acquisition is resilient to transient network failures and polite to external hosts,
  given the Guidelines scrape is on the order of ~1,887 requests.
- A failed or partial acquisition is observable, not silent.

### Non-Goals
- **Rewriting `extract_text_from_epc` or fixing the `build_index` `KeyError: 'page'`.**
  Both already landed on `main`. This work is scoped strictly to the
  download/acquisition layer in `epo_downloaders.py`; re-litigating the parser is out.
- **Changing the indexer's expected input contract.** The `epo_guidelines.txt`
  `PART/###` format and the `epc_convention.pdf` PDF input are fixed targets that
  acquisition must produce — not interfaces to redesign here.
- **US, PCT, or other jurisdiction ingestion.** Those work today and are untouched.
  Only the EPC and EPO Guidelines acquisition paths are in scope.
- **Improving EPO/EPC search ranking, chunking quality, or the `search_patent_law`
  query surface.** Once real text is indexed, search-quality tuning is separate, later
  work.
- **Mirroring or caching EPO/WIPO documents in the repo.** Sources are fetched from the
  authoritative hosts at build time; we are not vendoring legal text into version
  control.
- **Incremental / partial re-scrape of only changed Guidelines sections.** A full
  re-scrape on rebuild is acceptable for now; incrementality can be revisited if the
  full scrape proves too slow or rate-limited in practice.
- **Localizing to EPO Guidelines languages other than English (the `/en/` edition).**
  English is the indexed corpus; other languages are out of scope.

## User Experience

The user-facing surface here is a command-line build step and a downstream search
query. "Good UX" means: the build acquires real law without manual help, says clearly
what it did, and the resulting search returns authoritative European text.

### Scenario 1: Clean from-scratch build produces a searchable EU corpus

```
$ patent-creator setup        # or: patent-creator rebuild-index
...
[INFO] Downloading European Patent Convention (resolving WIPO Lex asset URL)...
[INFO] Downloaded European Patent Convention (1.8 MB)
[INFO] Scraping EPO Guidelines for Examination (2026 edition)...
[INFO]   discovered 1887 section URLs
[INFO]   200/1887 fetched (197 with content)
...
[INFO]   1887/1887 fetched (1881 with content)
[INFO] Wrote epo_guidelines.txt (4.9 MB, 1881/1887 sections with content)
[INFO] Processing EPC (European Patent Convention + Implementing Regulations)...
[INFO] Extracted 612 EPC chunks
[INFO] Processing EPO Guidelines for Examination...
[INFO] Extracted 7044 EPO Guidelines chunks
```

The user did not place any file by hand. The log states which jurisdiction was
acquired, how much content was retrieved, and how many chunks were indexed. (Exact
counts above are illustrative; the launch criteria define the floors that matter.)

### Scenario 2: The user queries European law and gets real, in-force text

```
> Search EPO patent law for the claim clarity requirement

search_patent_law(query="claim clarity requirement", jurisdiction="EPO")
→ EPC Article 84 — "The claims shall define the matter for which protection is
  sought. They shall be clear and concise and be supported by the description."
→ EPO Guidelines Part F, Chapter IV, 4 — "Clarity and interpretation of claims" …
```

The result is the genuine statutory text and the corresponding in-force Guidelines
passage — not a single junk chunk, not an empty result, not draft-consultation text.

### Scenario 3: Incremental rebuild does not re-pay the acquisition cost

A user who already has valid `epc_convention.pdf` and `epo_guidelines.txt` in `pdfs/`
and re-runs the build does not trigger a fresh ~1,887-request scrape or re-download.
Acquisition recognizes the existing valid artifacts and skips re-fetching them, while
still treating a *bad* existing artifact (HTML-as-PDF, empty/stub text) as needing
re-acquisition.

### Error & Edge Cases

- **WIPO landing page reachable but the signed asset URL cannot be extracted** (markup
  changed): acquisition fails loudly with a clear message naming the EPC step and does
  not leave a junk `.pdf` behind. The build reports EPC as not acquired rather than
  silently indexing garbage.
- **Signed CloudFront URL expired / returns non-PDF**: acquisition detects the content
  is not a PDF (content-type / magic bytes), discards it, and reports failure rather
  than persisting a bad file.
- **Some Guidelines section pages 404 or time out**: the scrape tolerates a bounded
  number of failed sections (per the reference prototype's retry/backoff) and still
  produces `epo_guidelines.txt`, provided the success ratio clears the launch-criteria
  floor. A scrape that retrieves too little content fails rather than writing a thin
  file that looks valid.
- **Transient network failure mid-scrape**: retries with backoff; an unrecoverable
  failure leaves no partial `epo_guidelines.txt` that a later build would mistake for a
  complete one.
- **EPO rate-limits the scrape**: the scrape is paced (politeness delay between
  requests) to stay within acceptable request rates for ~1,887 pages.

## Success Criteria

| Criterion | Measurement | Target |
|-----------|-------------|--------|
| EPC artifact is a real PDF | File type of `pdfs/epc_convention.pdf` after a clean build | Valid PDF (magic bytes / content-type), not HTML |
| EPC indexes richly | EPC chunk count reported by `build_index` | Many chunks (hundreds), not 1 junk chunk |
| Guidelines artifact is the one the indexer reads | `epo_guidelines.txt` exists and is non-trivial after a clean build | Present, in `PART/###` format, multi-MB |
| Guidelines are in-force, not draft | Source edition scraped | In-force current edition (e.g. 2026 `/en/`), no `…-draft-…` artifact present |
| No orphaned artifacts | Files left in `pdfs/` after build | No `epo_guidelines_{year}.pdf` draft, no HTML-as-PDF |
| End-to-end EU search works | `search_patent_law(query="claim clarity requirement", jurisdiction="EPO")` after a from-scratch build | Returns real EPC Art. 84 text and an EPO Guidelines clarity passage |
| Zero manual steps | Operator actions required to populate EU corpus | None beyond the documented `setup` / `rebuild-index` command |
| Acquisition is observable | Build log on success and on failure | States per-source acquisition outcome and counts; failures are logged, not silent |

## Scope & Boundaries

### In Scope
- Fixing `download_epc()` to fetch the WIPO Lex landing page, extract the signed
  CloudFront asset URL, download the genuine EPC PDF, and validate it is a PDF before
  persisting it as `epc_convention.pdf`.
- Replacing the EPO Guidelines acquisition so it produces an in-force
  `epo_guidelines.txt` (building on `scripts/_epo_guidelines_scrape.py`) in the
  indexer's expected format, and removing the orphaned-draft-PDF behavior.
- Resilience (retry/backoff), politeness (request pacing), and validation (artifact
  integrity checks) for both acquisition paths.
- Observability: per-source success/failure logging with content/section/chunk counts.
- Wiring the corrected acquisition into the existing `download_all_epo_documents()` /
  setup / rebuild path so a clean build invokes it automatically.

### Out of Scope
- `extract_text_from_epc` parser and `build_index` `KeyError: 'page'` — already fixed
  on `main`; this PRD does not touch the indexer.
- PCT and US acquisition paths — working today, untouched.
- Search-quality, chunking, and ranking improvements — separate, later work once real
  text is indexed.
- Vendoring/mirroring legal documents into the repo — sources fetched at build time.

### Future Considerations
- **Incremental Guidelines re-scrape** keyed on a published change/version marker, to
  avoid a full ~1,887-page fetch on every rebuild — design the acquisition so a future
  incremental mode can slot in without reworking discovery/parsing.
- **Source-drift detection / alerting**: a periodic check that the WIPO landing-page
  markup and the EPO Guidelines URL scheme still match assumptions, so the next silent
  breakage is caught proactively rather than at query time.
- **Pinning a known-good EPC edition** vs. always taking WIPO's "latest", once edition
  stability is understood.

## Delivery Phases

This is a focused fix, not a multi-quarter initiative. It splits into two
independently valuable phases — each repairs one jurisdiction-critical source on its
own — plus a small hardening pass. Either phase shipping alone is a real improvement;
together they complete the story.

### Phase 1: EPC acquires as a real PDF

**What ships:**
- `download_epc()` fetches the WIPO Lex landing page, extracts the signed CloudFront
  asset URL, downloads the genuine EPC PDF, and validates it is a PDF before saving it
  as `epc_convention.pdf`.
- A clean build indexes EPC into many chunks; `search_patent_law(jurisdiction="EPO")`
  returns real EPC Art. 84 text.

**Launch criteria:**
- After a from-scratch build, `epc_convention.pdf` is a valid PDF and the EPC chunk
  count is in the hundreds, not 1.
- A failure to resolve/download the PDF is logged clearly and leaves no junk `.pdf`.

**Decisions needed:**
- ADR on the EPC acquisition strategy: how the signed CloudFront URL is extracted
  (and how robust that is to WIPO markup changes), what artifact validation gate
  applies, and the failure-handling contract.

**Dependencies:**
- The already-landed `extract_text_from_epc` rewrite on `main` (present).

### Phase 2: EPO Guidelines acquire as in-force `epo_guidelines.txt`

**What ships:**
- EPO Guidelines acquisition that scrapes the in-force HTML edition into
  `epo_guidelines.txt` in the indexer's `PART/###` format, built from
  `scripts/_epo_guidelines_scrape.py`, with retry/backoff and request pacing.
- The orphaned draft-PDF download path is removed; no `epo_guidelines_{year}.pdf` is
  produced.
- A clean build indexes the Guidelines into thousands of chunks;
  `search_patent_law(jurisdiction="EPO")` returns a real Guidelines clarity passage.

**Launch criteria:**
- After a from-scratch build, `epo_guidelines.txt` is present, multi-MB, and parses
  into many Guidelines chunks; section success ratio clears a defined floor.
- No draft/consultation artifact remains in `pdfs/`.
- The scrape completes within an acceptable wall-clock and request-rate budget.

**Decisions needed:**
- ADR on the Guidelines acquisition strategy: section discovery method, success-ratio
  threshold for declaring the scrape valid, politeness/rate budget, and how a partial
  scrape is prevented from masquerading as complete.

**Dependencies:**
- The indexer's `extract_text_from_epo_guidelines()` `PART/###` contract (present on
  `main`), which acquisition must match exactly.

### Phase 3: Hardening — validation, idempotency, observability

**What ships:**
- Artifact-integrity gates for both sources (don't persist non-PDF as PDF; don't
  persist a thin/empty `.txt` as a complete corpus).
- Idempotency: existing *valid* artifacts are skipped on rebuild; existing *invalid*
  artifacts are re-acquired.
- Per-source acquisition logging with counts surfaced through the setup/rebuild flow.

**Launch criteria:**
- A rebuild with valid artifacts present does not re-download/re-scrape.
- A rebuild with a bad artifact present re-acquires it.
- Every acquisition outcome (success or failure, with counts) appears in the build log.

**Decisions needed:**
- None expected beyond the Phase 1/2 ADR(s); this phase implements their contracts.

**Dependencies:**
- Phases 1 and 2.

## Technical Considerations

These are product constraints with architectural implications, handed to the ADR
author — not architecture prescriptions.

- **External, partially-uncooperative sources.** Acquisition depends on two third-party
  hosts (WIPO Lex, EPO) whose delivery mechanisms are non-trivial: WIPO serves the EPC
  via a signed, ephemeral CloudFront URL embedded in landing-page HTML (the bare asset
  path returns HTML); EPO publishes the Guidelines as ~1,887 HTML pages with no
  consolidated PDF. The acquisition design must treat both as inherently fragile and
  changeable, not as static download links.
- **Silent failure is a product failure.** This pipeline runs during install/rebuild
  with no human watching the corpus quality. The current breakage was invisible until a
  query came back empty. Acquisition must validate its own output (a saved file is
  actually a PDF; a saved text file actually contains many parsed sections) and report
  per-source outcomes — a bad artifact must be rejected at acquisition time, never
  persisted to be silently indexed as junk.
- **Politeness and resilience at ~1,887 requests.** The Guidelines scrape is a bulk
  fetch against a public institution's site. It must pace requests, retry transient
  failures with backoff, tolerate a bounded number of dead sections, and avoid leaving
  a partial output that a later build mistakes for complete.
- **Exact indexer input contract.** The indexer is fixed: EPC must be a real PDF at
  `pdfs/epc_convention.pdf`; the Guidelines must be `pdfs/epo_guidelines.txt` with
  `PART X - TITLE` headers (matched by `^PART\s+([A-H])\s*[-–]\s*(.+)`) and `###`
  section headers (matched by `^(?:###+|####)\s*(.+)`). Acquisition output that does not
  match these patterns indexes incorrectly even if the fetch "succeeds." The reference
  prototype already emits this format.
- **In-force vs. draft is a correctness property, not a nicety.** Indexing draft
  consultation text would present non-authoritative guidance as binding examination
  practice — a substantive correctness defect for a legal-research tool. The acquisition
  must target the in-force edition.
- **Idempotency interacts with the cost model.** A full re-scrape on every rebuild is
  ~1,887 requests; acquisition should skip re-fetching valid existing artifacts so
  routine rebuilds stay cheap, while still re-acquiring known-bad ones.
- **Observability for the build operator.** Success counts (PDF size, sections fetched,
  chunks produced) and clear per-source failure messages are the only signal the
  operator has that the EU corpus is healthy. These are product requirements, not
  debug niceties.

## Risks & Open Questions

### Risks
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| WIPO changes landing-page markup, breaking signed-URL extraction | EPC silently stops acquiring | Medium | Validate the downloaded artifact is a PDF and fail loudly; document the extraction point for fast repair; consider future drift-detection |
| EPO changes the Guidelines URL scheme or page structure | Guidelines scrape breaks | Medium | Build on the proven prototype's discovery-from-nav approach; require a success-ratio floor so a broken scrape fails rather than writes a thin file |
| EPO rate-limits or blocks the ~1,887-request scrape | Incomplete or failed Guidelines acquisition | Medium | Request pacing + backoff + bounded tolerance for failed sections; skip re-scrape when a valid artifact already exists |
| Scrape wall-clock makes a clean build feel slow | Operator friction during setup | Medium | Pace deliberately but acceptably; idempotency means the cost is paid once, not every rebuild |
| Signed CloudFront URL expires between extraction and download | Intermittent EPC download failure | Low | Extract and download in the same flow with retry; validate result |
| WIPO "latest" EPC edition shifts unexpectedly | Corpus changes without notice | Low | Acquire latest by default now; pin a known-good edition as a future consideration |

### Open Questions
- **What is the section success-ratio floor** below which the Guidelines scrape is
  declared failed rather than written? (Answer in the Phase 2 ADR; affects when a
  partial scrape is rejected.)
- **How robust must signed-URL extraction be** to WIPO markup variation — a single
  targeted pattern, or a more defensive parse? (Phase 1 ADR; trades fragility against
  complexity.)
- **What is the acceptable wall-clock / request-rate budget** for the scrape during a
  clean build? (Phase 2 ADR; affects pacing and operator experience.)
- **Should acquisition failure for one EU source be fatal to the whole build, or
  degrade gracefully** (build the rest of the corpus, report EU source missing)?
  Current build code treats EPO sources as optional/non-fatal — confirm that is the
  desired contract. (Phase 3 ADR / maintainer decision.)
- **Is English-only acquisition acceptable** for the indexed Guidelines corpus, or is
  multilingual a near-term need? (Product/maintainer; currently a non-goal.)

## Related Documents

- `mcp_server/epo_downloaders.py` — the acquisition layer this PRD scopes
  (`download_epc()`, `scrape_epo_guidelines()`, `download_all_epo_documents()`).
- `mcp_server/mpep_search.py` — the indexer; `extract_text_from_epc()` (line 458),
  `extract_text_from_epo_guidelines()` (line 553, the `PART/###` contract), and
  `build_index()` EPC/Guidelines ingestion (lines 879-899).
- `scripts/_epo_guidelines_scrape.py` — committed reference prototype for the Guidelines
  scrape; emits the indexer's expected `PART/###` format.
- Roadmap: `m2/s1` ("European & international law ingestion produces complete, in-force
  corpora") and project `m2/s1/epo-downloaders-fix`.
- ADRs to be written: EPC acquisition strategy (Phase 1); EPO Guidelines acquisition
  strategy (Phase 2). No existing ADRs touch this area (`docs/adr/` is empty at time of
  writing).
- Prior fixes on `main` (context, out of scope here): commit `c9b8779`
  ("Fix EPC and EPO Guidelines ingestion for the law index") — the
  `extract_text_from_epc` rewrite and `build_index` `KeyError: 'page'` fix.

---

## Revision History

| Date | Author | Notes |
|------|--------|-------|
| 2026-06-21 | cameronrout | Initial draft |
