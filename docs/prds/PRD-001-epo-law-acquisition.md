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
discovery and parsing. The prototype is not production-clean: it hardcodes the edition
year (`YEAR = "2026"`), carries a typo in its part-title table
(`PART_TITLES["c"] = "Procedureal aspects of substantive examination"`), and was written
to discover-and-dump rather than to validate. These must be reconciled before the code
is promoted — see Non-Goals and the Phase 2 launch criteria.

**The acquisition layer is also not wired into any documented build path.** This is a
third defect, independent of the two acquisition bugs and just as fatal to the product
promise. Verified against the CLI: `setup_command` (`cli.py:432`) downloads only
MPEP / 35 USC / 37 CFR / Subsequent Publications and never calls
`download_all_epo_documents`; `rebuild_index_command` (`cli.py:851`) downloads nothing
at all; `download_all_command` (`cli.py:889`) is MPEP + 35 USC + 37 CFR only. The
*only* code path that invokes EPO acquisition is in `server.py:507-519`, gated behind
`--download-epo` / `--download-all` flags that `setup` never passes. The consequence is
decisive: even if `download_epc()` and `scrape_epo_guidelines()` were fixed perfectly
today, a clean `patent-creator setup` would still produce an **empty European corpus**,
because nothing on the documented install path ever triggers the acquisition. Fixing the
two acquisition bugs is necessary but not sufficient; the acquisition must be wired into
the command an operator actually runs.

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
- A clean, from-scratch index build **run via a documented command** ingests genuine,
  in-force EPC text and in-force EPO Guidelines text with zero manual artifact placement.
  This explicitly includes *wiring* EPO acquisition into whichever documented command
  the operator runs to build the corpus — fixing the downloaders alone does not satisfy
  this goal (see Background and Phase 3).
- `download_epc()` reliably acquires a real EPC PDF (resolving the WIPO Lex signed
  CloudFront URL), not an HTML landing page.
- The EPO Guidelines acquisition produces `epo_guidelines.txt` — the artifact the
  indexer actually reads — from the **in-force edition selected deterministically**
  (discovered from the EPO's canonical current-Guidelines entry point, not a hardcoded
  year), in the format the indexer parses.
- No orphaned or non-authoritative artifacts (draft PDFs, HTML-as-PDF) are produced.
- Acquisition is resilient to transient network failures and polite to external hosts,
  given the Guidelines scrape is on the order of ~1,887 requests.
- Idempotency is keyed on an **artifact-validity predicate**, not file existence: a
  valid existing artifact is skipped; an invalid one (HTML-as-PDF, stub `.txt`) is
  re-acquired. The current `dest_path.exists()` short-circuits are replaced.
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
[INFO] Extracted N EPC chunks (hundreds — articles + Implementing Regulations)
[INFO] Processing EPO Guidelines for Examination...
[INFO] Extracted M EPO Guidelines chunks (thousands)
```

The user did not place any file by hand. The log states which jurisdiction was
acquired, how much content was retrieved, and how many chunks were indexed. Chunk
counts are deliberately shown as placeholders (`N`, `M`) rather than fixed numbers:
the EPC currently lands ~hundreds of chunks (the parser already in `main` splits the
PDF into article and Implementing-Regulations chunks) and the Guidelines land
thousands. The launch criteria below define the *floors* that matter — do not treat any
specific number in this PRD as a regression target.

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
Acquisition recognizes the existing artifacts as *valid by the artifact-validity
predicate* (defined in the Success Criteria and Phase 3) — not merely as *present* — and
skips re-fetching them. A *bad* existing artifact (a 28 KB HTML-as-PDF, an empty or stub
`.txt`) does **not** satisfy the predicate, so it is treated as needing re-acquisition.
This is a deliberate departure from today's behavior: the current `_download_file`
(`epo_downloaders.py:92`) and `scrape_epo_guidelines` (`epo_downloaders.py:185`)
short-circuit on `dest_path.exists()` alone, which is exactly why a 28 KB HTML file
saved under `epc_convention.pdf` counts as "already downloaded" and is never repaired.
Those existence short-circuits must be replaced by the validity predicate.

### Scenario 4: The build acquires the in-force Guidelines edition without a code change

A user installs in a year *after* the prototype was written. The EPO has published a
new annual Guidelines edition since. The build still acquires the *currently in-force*
edition — because acquisition discovers the in-force edition from the EPO's canonical
"current Guidelines" entry point and reads where it points, rather than from a hardcoded
`YEAR` constant. The operator does not have to know which edition is current, and the
system does not silently scrape a superseded edition (the "stale law presented as
binding" defect this PRD exists to prevent). If the project instead chooses to pin the
edition for this cycle, the build emits the pinned edition in its log *and* a drift
check flags when the EPO's published in-force edition no longer matches the pin — so the
staleness is loud, not silent.

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
| EPC artifact satisfies the validity predicate | `pdfs/epc_convention.pdf` after a clean build | PDF magic bytes (`%PDF`) **and** size ≥ a defined floor **and** parser extracts more than a defined minimum number of EPC provisions — not just "file exists" |
| EPC indexes richly | EPC chunk count reported by `build_index` | Many chunks (hundreds — articles + Implementing Regulations), not 1 junk chunk; floor defined in Phase 1 launch criteria, not pinned to a specific number here |
| Guidelines artifact satisfies the validity predicate | `pdfs/epo_guidelines.txt` after a clean build | Present, in `PART/###` format, size ≥ a defined floor, parses into ≥ a defined minimum number of Guidelines chunks, and section-success ratio ≥ the Phase 2 floor — not just "file exists" |
| Guidelines are the in-force edition, selected deterministically | Edition actually scraped vs. the edition the EPO's canonical "current Guidelines" entry point resolves to | Scraped edition **==** the EPO's currently-published in-force edition (resolved at build time); **no** `…-draft-…` consultation artifact present. (Not "e.g. 2026" — the check is equality against whatever is in force on the build date.) |
| No orphaned artifacts | Files left in `pdfs/` after build | No `epo_guidelines_{year}.pdf` draft, no HTML-as-PDF |
| End-to-end EU search works | `search_patent_law(query="claim clarity requirement", jurisdiction="EPO")` after a from-scratch build | Returns real EPC Art. 84 text and an EPO Guidelines clarity passage |
| Zero manual steps, on a command that actually triggers acquisition | Operator actions required to populate the EU corpus, running the *documented post-fix command* (after wiring lands — see Phase 3) | None beyond running that single documented command; the EU corpus is non-empty afterward. Today this fails: `setup` / `rebuild-index` / `download-all` never invoke EPO acquisition. |
| Acquisition is observable | Build log on success and on failure | States per-source acquisition outcome and counts; failures are logged, not silent |

## Scope & Boundaries

### In Scope
- Fixing `download_epc()` to fetch the WIPO Lex landing page, extract the signed
  CloudFront asset URL, download the genuine EPC PDF, and validate it is a PDF before
  persisting it as `epc_convention.pdf`. (Also: refresh the stale
  `download_epc` docstring, which currently claims "The EPO HTML version is more current"
  — written for the abandoned approach.)
- Replacing the EPO Guidelines acquisition so it produces an in-force
  `epo_guidelines.txt` (building on `scripts/_epo_guidelines_scrape.py`) in the
  indexer's expected format, and removing the orphaned-draft-PDF behavior.
- **Deterministic in-force-edition selection**: discover the in-force Guidelines edition
  from the EPO's canonical current-Guidelines entry point at build time rather than the
  prototype's hardcoded `YEAR = "2026"`. (If the project elects to pin the edition for a
  given cycle instead, the pin becomes a tracked maintenance obligation with drift
  detection — see Open Questions.)
- **Promoting the prototype to production quality**: clean up
  `scripts/_epo_guidelines_scrape.py` before it ships — fix the
  `PART_TITLES["c"]` typo (`"Procedureal aspects of substantive examination"`) and
  reconcile the Part C wording, and remove the hardcoded edition assumption.
- **Replacing the existence short-circuits with an artifact-validity predicate.** Tie
  idempotency (skip-if-valid) to the predicate defined in Success Criteria — PDF magic
  bytes + size floor + parsed-provision floor for EPC; size floor + chunk-parse floor +
  section-success ratio for the Guidelines — not to `dest_path.exists()` at
  `epo_downloaders.py:92` and `:185`.
- Resilience (retry/backoff), politeness (request pacing), and validation (the
  artifact-validity predicate above) for both acquisition paths.
- Observability: per-source success/failure logging with content/section/chunk counts.
- **Wiring the corrected acquisition into the documented build path** so that the single
  command an operator runs (`setup` and/or `rebuild-index`, per the default-on vs.
  flag-gated decision in Open Questions) invokes EPO acquisition automatically. Today no
  documented command does — `setup_command`, `rebuild_index_command`, and
  `download_all_command` all skip EPO entirely; the only EPO path is behind the
  `--download-epo` / `--download-all` flags on `server.py`, which `setup` never passes.
  This is a first-class deliverable, not a footnote.

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
  stability is understood. (Distinct from the EPO Guidelines edition selection, which is
  an in-scope requirement, not a future consideration — the EPC's WIPO PDF is far more
  stable than the EPO's annually-republished Guidelines.)

## Delivery Phases

This is a focused fix, not a multi-quarter initiative. It splits into two
source-repair phases — each repairs one jurisdiction-critical source on its own — plus a
hardening-and-wiring phase that is **load-bearing, not cosmetic**: without it, the fixed
downloaders are never invoked by any command an operator runs, so the European corpus
stays empty on a clean install. Phases 1 and 2 each fix an acquisition function in
isolation and are individually verifiable; Phase 3 is what turns those fixes into a
product the documented install path actually delivers.

### Phase 1: EPC acquires as a real PDF

**What ships:**
- `download_epc()` fetches the WIPO Lex landing page, extracts the signed CloudFront
  asset URL, downloads the genuine EPC PDF, and validates it is a PDF before saving it
  as `epc_convention.pdf`.
- A clean build indexes EPC into many chunks; `search_patent_law(jurisdiction="EPO")`
  returns real EPC Art. 84 text.

**Launch criteria:**
- After a from-scratch build, `epc_convention.pdf` satisfies the EPC artifact-validity
  predicate (PDF magic bytes + size floor + parser extracts more than the minimum
  provisions) and the EPC chunk count is in the hundreds, not 1.
- A failure to resolve/download the PDF is logged clearly and leaves no junk `.pdf`.

**Decisions needed:**
- ADR on the EPC acquisition strategy: how the signed CloudFront URL is extracted
  (and how robust that is to WIPO markup changes), the EPC artifact-validity predicate
  (the gate that replaces `dest_path.exists()`), and the failure-handling contract.

**Dependencies:**
- The already-landed `extract_text_from_epc` rewrite on `main` (present).

### Phase 2: EPO Guidelines acquire as in-force `epo_guidelines.txt`

**What ships:**
- EPO Guidelines acquisition that scrapes the in-force HTML edition into
  `epo_guidelines.txt` in the indexer's `PART/###` format, built from
  `scripts/_epo_guidelines_scrape.py`, with retry/backoff and request pacing.
- **Deterministic in-force-edition selection**: the edition is discovered from the EPO's
  canonical current-Guidelines entry point at build time — replacing the prototype's
  hardcoded `YEAR = "2026"`. (If the project pins instead, the pin is logged and a drift
  check is added per Open Questions.)
- **Prototype cleanup for promotion**: the `PART_TITLES["c"]` typo
  (`"Procedureal aspects of substantive examination"`) and Part C wording are fixed and
  reconciled before the scraper ships.
- The orphaned draft-PDF download path is removed; no `epo_guidelines_{year}.pdf` is
  produced.
- A clean build indexes the Guidelines into thousands of chunks;
  `search_patent_law(jurisdiction="EPO")` returns a real Guidelines clarity passage.

**Launch criteria:**
- After a from-scratch build, `epo_guidelines.txt` satisfies the artifact-validity
  predicate (present, `PART/###` format, size ≥ floor, parses into ≥ the minimum chunk
  count, section-success ratio ≥ the defined floor).
- The edition scraped equals the EPO's currently-published in-force edition (resolved at
  build time) — verified deterministically, not against a hardcoded year.
- No draft/consultation artifact remains in `pdfs/`.
- The scrape completes within an acceptable wall-clock and request-rate budget.

**Decisions needed:**
- ADR on the Guidelines acquisition strategy: section discovery method, **in-force-edition
  selection mechanism (discover-from-canonical-entry-point vs. pin-with-drift-detection)**,
  the artifact-validity predicate and success-ratio threshold for declaring the scrape
  valid, politeness/rate budget, and how a partial scrape is prevented from masquerading
  as complete.

**Dependencies:**
- The indexer's `extract_text_from_epo_guidelines()` `PART/###` contract (present on
  `main`), which acquisition must match exactly.

### Phase 3: Wiring + hardening — make a clean install actually populate the EU corpus

This phase is what makes the story *true* for a real operator. Phases 1 and 2 can be
"done" and the product still ship an empty EU corpus, because no documented command
invokes EPO acquisition. This phase closes that gap and locks in the validity/idempotency
guarantees the earlier phases depend on.

**What ships:**
- **EPO acquisition wired into the documented build path.** Whichever command the
  operator is told to run to build the corpus invokes `download_all_epo_documents` (and
  the PCT equivalent already gated the same way) — closing the gap where `setup_command`,
  `rebuild_index_command`, and `download_all_command` skip EPO entirely and the only
  trigger lives behind `server.py`'s `--download-epo` / `--download-all` flags. This is
  the deliverable that turns Phases 1–2 into out-of-box behavior.
- The artifact-validity predicate (defined in Success Criteria) implemented for both
  sources, **replacing** the `dest_path.exists()` short-circuits at
  `epo_downloaders.py:92` and `:185`.
- Idempotency keyed on that predicate: existing *valid* artifacts are skipped on rebuild;
  existing *invalid* artifacts (HTML-as-PDF, stub `.txt`) are re-acquired.
- Per-source acquisition logging with counts surfaced through the build flow.

**Launch criteria:**
- Running the single documented command on a clean machine produces a **non-empty EU
  corpus** with no manual artifact placement — the end-to-end search criterion passes
  from a from-scratch install, not just from a hand-run `server.py --download-epo`.
- A rebuild with valid artifacts present (per the predicate) does not re-download/re-scrape.
- A rebuild with a bad artifact present re-acquires it (existence alone does not satisfy
  skip).
- Every acquisition outcome (success or failure, with counts) appears in the build log.

**Decisions needed:**
- **Product decision — default-on vs. flag-gated EPO acquisition in `setup`.** Should a
  fresh `patent-creator setup` acquire EPO law by default (adding the ~1,887-request
  Guidelines scrape and its wall-clock to *every* clean install's critical path), or be
  opt-in via a flag (preserving fast US-only installs for users who never touch EPO)?
  - *Default-on* maximizes out-of-box completeness — the advertised "Ready" EPO features
    work on first query with zero extra steps — at the cost of setup wall-clock and
    rate-limit/blocking exposure for users who never need EPO.
  - *Flag-gated* keeps the baseline install fast and low-risk but means the EU corpus is
    still empty after a default `setup`, so the "zero manual steps" promise only holds for
    users who know to pass the flag — which re-creates a softer version of today's defect.
  - A reasonable middle path (default-on for `setup`, with an explicit `--skip-epo`
    escape hatch, or default-on only when EPO skills are detected as in use) is in scope
    for the ADR to weigh. The choice determines which command the "zero manual steps"
    success criterion is measured against.
- Whether `setup` and `rebuild-index` are *both* wired, or only one is the canonical
  corpus-build command (today `rebuild_index_command` downloads nothing, so it would also
  need wiring to be a complete path).

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
- **In-force vs. draft — and in-force vs. *superseded* — is a correctness property, not a
  nicety.** Indexing draft consultation text would present non-authoritative guidance as
  binding examination practice. Equally bad: scraping last year's edition because the
  edition was hardcoded (`YEAR = "2026"`). The EPO publishes a new Guidelines edition
  roughly annually, so a pinned year silently rots into "stale law presented as binding"
  on a predictable schedule. The acquisition must select the in-force edition
  *deterministically* — discover it from the EPO's canonical current-Guidelines entry
  point, or pin it with explicit drift detection — never assume a fixed year.
- **Idempotency must key on validity, not existence.** Today the downloaders skip on
  `dest_path.exists()` alone (`epo_downloaders.py:92`, `:185`), which is precisely why a
  28 KB HTML-as-PDF and an orphaned/stale text file are treated as "already downloaded"
  and never repaired. The skip decision must be gated on an artifact-validity predicate
  (PDF magic bytes + size + parsed-provision floor for EPC; size + chunk-parse floor +
  section-success ratio for the Guidelines). A full re-scrape is ~1,887 requests, so a
  *valid* artifact should be skipped to keep rebuilds cheap — but a *present-but-invalid*
  one must be re-acquired.
- **Fixing acquisition is necessary but not sufficient — it must be invoked.** The
  acquisition functions are dead code from the operator's perspective until the
  documented build command calls them. The product constraint is end-to-end: a single
  documented command on a clean machine must yield a non-empty EU corpus. The ADR must
  decide where that wiring lives and whether it is default-on or flag-gated (see Open
  Questions), because that choice determines the install-time cost every user pays.
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
| **Hardcoded Guidelines edition (`YEAR = "2026"`) silently scrapes a superseded edition after the EPO publishes the next annual edition** | Stale, non-binding law presented as in-force — the exact correctness defect this PRD forbids | **High** (the EPO publishes ~annually, so the hardcode rots on a known schedule) | Discover the in-force edition from the EPO's canonical current-Guidelines entry point at build time; OR, if pinned, treat the pin as a tracked maintenance obligation with drift detection that fails/warns when the published in-force edition no longer matches |
| **Fixed downloaders never wired into the documented build path** | Clean install ships an empty EU corpus despite the acquisition bugs being fixed | **High if not explicitly delivered** (current state — no documented command invokes EPO acquisition) | Phase 3 makes wiring a first-class deliverable; the "non-empty EU corpus from one documented command" launch criterion gates it |

### Open Questions
- **Should EPO acquisition be default-on in `setup`, or flag-gated (opt-in)?** This is the
  central product decision the wiring work forces. Default-on adds the ~1,887-request
  Guidelines scrape to every clean install's critical path (slower setup, rate-limit
  exposure) but delivers the advertised "Ready" EPO features out of the box; flag-gated
  keeps US-only installs fast but leaves the EU corpus empty after a default `setup`,
  weakening the "zero manual steps" promise. The answer decides which command the
  zero-manual-steps success criterion is measured against. (Phase 3 ADR / product owner.)
- **How is the in-force Guidelines edition selected** — discovered at build time from the
  EPO's canonical current-Guidelines entry point, or pinned per cycle with drift
  detection? A hardcoded year (the prototype's `YEAR = "2026"`) is rejected outright; the
  ADR must choose between the two acceptable contracts. (Phase 2 ADR.)
- **What is the section success-ratio floor** below which the Guidelines scrape is
  declared failed rather than written, and what are the concrete size/chunk floors that
  make up the artifact-validity predicate for each source? (Phase 2/Phase 1 ADRs; these
  define the predicate that replaces the existence short-circuits.)
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
  (`download_epc()`, `scrape_epo_guidelines()`, `download_all_epo_documents()`). The
  existence short-circuits to replace are at `_download_file` (line 92) and
  `scrape_epo_guidelines` (line 185); the stale "EPO HTML version is more current"
  docstring is on `download_epc` (around line 133).
- `mcp_server/cli.py` — the documented build commands that must be wired:
  `setup_command` (line 432, downloads MPEP/USC/CFR/Subsequent only),
  `rebuild_index_command` (line 851, downloads nothing), and `download_all_command`
  (line 889, US sources only). None currently invoke EPO acquisition.
- `mcp_server/server.py` — the *only* current EPO trigger, behind the `--download-epo` /
  `--download-all` flags (lines 507-519), which `setup` never passes.
- `mcp_server/mpep_search.py` — the indexer; `extract_text_from_epc()` and
  `extract_text_from_epo_guidelines()` (the `PART/###` contract), and `build_index()`
  EPC/Guidelines ingestion (around line 885, which logs the EPC chunk count).
- `scripts/_epo_guidelines_scrape.py` — committed reference prototype for the Guidelines
  scrape; emits the indexer's expected `PART/###` format. Carries the hardcoded
  `YEAR = "2026"` (line 15) and the `PART_TITLES["c"]` typo (line 21) that must be
  reconciled before promotion.
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
| 2026-06-21 | cameronrout | Adversarial-review revision: (B1) made wiring EPO acquisition into the documented build path a first-class Phase 3 deliverable and surfaced the default-on vs. flag-gated product decision; restated the zero-manual-steps criterion against a command that actually triggers acquisition. (S2) replaced the hardcoded edition year with a deterministic in-force-edition selection requirement + drift-detection fallback, and a deterministic success criterion. (S3) defined per-source artifact-validity predicates and required replacing the `dest_path.exists()` short-circuits. (M1) removed the phantom "612 EPC chunks" number. (M2) flagged the `PART_TITLES["c"]` typo, Part C wording, and stale `download_epc` docstring for cleanup before promotion. |
