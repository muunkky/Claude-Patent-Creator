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

The indexer is fixed and out of scope: `extract_text_from_epc` (a trilingual two-column PDF parser)
and `extract_text_from_epo_guidelines` (reads `epo_guidelines.txt` in `PART X - TITLE` / `### Section`
format) already landed on `main` (commit `c9b8779`). This design decides only how acquisition
produces artifacts those parsers accept, and how acquisition is triggered.

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
6. **R6 — Acquisition is wired and deferred-default.** `setup`/`rebuild-index` register but do not
   eagerly run EPO/PCT acquisition by default; the first `search_patent_law(jurisdiction in {EPO,PCT})`
   call triggers acquisition (announced to the caller) when the corpus is absent/invalid. `--with-epo`
   forces eager acquisition; `--skip-epo` disables it entirely.
7. **R7 — Failure is loud, never silent.** Every per-source outcome (resolved edition, sizes,
   fetched/with-content counts, pass/fail) is logged; an EPO/PCT acquisition failure is non-fatal to
   the overall build but surfaces a clear source-named message, never a silently-empty result.
8. **R8 — Validators and acquisition are TDD-covered.** Validators, signed-URL extraction,
   edition discovery, and success-ratio gating each have unit tests against saved fixtures; an
   integration test proves a clean build yields a non-empty EU corpus.

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

The indexer contract (`mcp_server/mpep_search.py`, **fixed/out of scope**):

- `extract_text_from_epc(pdf_path)` — opens the PDF with PyMuPDF, keys on two-column trilingual
  layout (`MIDX` English column, `Article N` / `Rule N` headers), returns provision chunks. The
  WIPO `trt_ep001_001en.pdf` is the exact 906-page document this parser targets.
- `extract_text_from_epo_guidelines(text_path)` — reads `epo_guidelines.txt`, splits on
  `^PART\s+([A-H])\s*[-–]\s*(.+)` and `^(?:###+|####)\s*(.+)`, returns chunks.
- `build_index(force_rebuild)` (`:801`) — loads the FAISS index if present and `force_rebuild` is
  false; otherwise re-extracts **every** source present in `MPEP_DIR` (each guarded by
  `file.exists()`) and rebuilds. EPC at `:882`, Guidelines at `:892`. A built index is a snapshot:
  **adding a corpus file after build requires `build_index(force_rebuild=True)` to make it
  searchable.**

CLI wiring (`mcp_server/cli.py`): `setup_command` (`:432`), `rebuild_index_command` (`:851`,
downloads nothing), `download_all_command` (`:889`, US-only). None call `download_all_epo_documents`.
The only EPO trigger is `server.py:507-519` behind `--download-epo`/`--download-all`, which `setup`
never passes.

The search tool (`mcp_server/tools/patent_law_tools.py`): `search_patent_law(query, jurisdiction,
top_k)` maps `jurisdiction` → source filters (`JURISDICTION_SOURCES`) and queries the shared
`mpep_index`. EPO sources are `["EPC", "EPC_RULES", "EPO_GUIDELINES"]`; PCT is `["PCT", "PCT_RULES"]`.
When a filtered source has no chunks, the per-source search silently yields nothing.

Tests live in `tests/` (pytest, `testpaths = ["tests"]`), with shared fixtures in
`tests/conftest.py`. There is no `tests/fixtures/` directory yet and no test touching
`epo_downloaders.py`.

## Target State

```
                       FIRST EPO/PCT search_patent_law()                CLI: setup --with-epo
                       (deferred-default trigger)                       download-all (eager)
                                 │                                              │
                                 ▼                                              ▼
                    ┌────────────────────────────────────────────────────────────────┐
                    │   ensure_epo_pct_corpus(mpep_dir, index, mode)  [new]            │
                    │   for each source: validate(dest); if absent|invalid → acquire   │
                    │   if anything acquired → index.build_index(force_rebuild=True)    │
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
EPO/PCT query (or `setup --with-epo`) acquires the EU corpus, rebuilds the index, and returns genuine
EPC Art. 84 text plus an in-force Guidelines clarity passage; rebuilds with valid artifacts re-acquire
nothing; corrupted artifacts re-acquire; every outcome is logged.

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

The **orchestration + lazy trigger** lives in a new helper `ensure_epo_pct_corpus(...)` (also in
`epo_downloaders.py`, to keep acquisition logic in one module). It is called from three sites:

- **Lazy (default):** `search_patent_law` in `mcp_server/tools/patent_law_tools.py`, the first time
  it is called with `jurisdiction in {"EPO","PCT"}` and the corpus is absent/invalid.
- **Eager (`--with-epo`):** `setup_command` / `rebuild_index_command` in `cli.py`.
- **Explicit-all:** `download_all_command` in `cli.py` and the existing `server.py` flag path.

`ensure_epo_pct_corpus` validates each target artifact; for any that is absent-or-invalid it runs the
acquisition function; if **anything** was acquired it calls `index.build_index(force_rebuild=True)` so
the new chunks become searchable in the live index. It returns a structured per-source result for
logging and caller-facing messages.

```
mcp_server/
  epo_downloaders.py        # validators, spine, flows, ensure_epo_pct_corpus, config
  cli.py                    # --with-epo / --skip-epo wiring; eager call; download-all
  server.py                 # flag path delegates to ensure_epo_pct_corpus (dedupe)
  mpep_search.py            # UNCHANGED (fixed indexer contract)
  tools/patent_law_tools.py # lazy trigger before EPO/PCT search
scripts/
  _epo_guidelines_scrape.py # DELETED (promoted into module)
tests/
  fixtures/                 # saved landing page, entry page, good/junk PDFs, stub txt
  test_epo_validators.py
  test_epo_extract_urls.py
  test_epo_edition_discovery.py
  test_epo_scrape_gating.py
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

**KD2 — `validate_epc` reuses the landed extractor (named coupling, single source of truth).**
`validate_epc` calls `extract_text_from_epc` and asserts the provision count ≥ floor, after the
cheap gates (magic bytes, size). *Alternative considered:* a lighter independent PDF probe.
*Rejected per ADR-001 D1/Key-Factor-5:* an independent probe can say "valid" while the indexer
extracts nothing (or vice-versa) — drift precisely where the predicate must assure. The WIPO source
**is** the document the extractor was authored against, so there is no layout-mismatch false-negative
to fear. A shared fixture (a known-good EPC PDF) pins both `validate_epc` and the indexer to the same
expectation. To call the instance method without standing up a full index, `validate_epc` constructs
a minimal `MPEPIndex` (or calls the extractor as a bound method on a lazily-created singleton) — the
extractor reads only the PDF, not the index, so this is cheap.

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

**KD6 — Lazy trigger lives in `search_patent_law`, gated on `{EPO,PCT}` jurisdiction, and rebuilds
the index.** The first EPO/PCT query is where the user signals they actually want EU law. The trigger
calls `ensure_epo_pct_corpus(MPEP_DIR, mpep_index, mode="lazy")`, which validates → acquires →
`build_index(force_rebuild=True)`. A **process-lifetime guard** (a module-level `_epo_corpus_checked`
flag, set after the first successful validation-pass) prevents re-validating on every subsequent EPO
query — the cost is a one-time per-process check. *Alternative considered:* trigger inside
`build_index` itself, or inside `MPEPIndex.search`. *Rejected:* `build_index` runs for US-only builds
too (would couple US builds to EPO acquisition), and `search` is jurisdiction-agnostic (it would fire
for US queries). `search_patent_law` is the one call site that knows "the user asked for EPO/PCT,"
which is the precise trigger condition ADR-001 D4 names. *Alternative considered:* a no-arg
`jurisdiction=None` (search-all) query. *Decision:* search-all does **not** trigger acquisition — the
trigger is scoped to an explicit `EPO`/`PCT` filter, so US-only users issuing broad queries are never
taxed; a `None` query simply searches whatever is indexed (ADR-001's "capability on demand").

**KD7 — Deferred trigger is announced and bounded.** When `ensure_epo_pct_corpus(mode="lazy")`
decides to acquire (something was absent/invalid), it emits a caller-visible message ("Acquiring EU
patent-law corpus (EPC + EPO Guidelines); this is a one-time step and may take several minutes…")
before the scrape, so the multi-minute pause is explained. On failure it returns a clear "EPO law not
acquired — <reason>" that `search_patent_law` surfaces to the caller (alongside whatever US results
exist), never an empty result with no explanation.

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
GUIDELINES_SUCCESS_RATIO_FLOOR = 0.95   # with_content / discovered over intended A-H set

# --- Scrape resilience ---
GUIDELINES_REQUEST_DELAY_S = 0.15   # politeness pacing between section fetches
GUIDELINES_MAX_RETRIES = 3          # per-section, exponential backoff
GUIDELINES_PART_LETTERS = "abcdefgh"  # intended A-H; I/J/K/M deliberately excluded

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
    /legal/guidelines-epc/{edition}/, scoped to GUIDELINES_PART_LETTERS (I/J/K/M excluded)."""

def fetch_section(url: str) -> Optional[tuple[str, str]]:
    """Return (title, body) for one section page or None (404/empty/exhausted retries).
    Pacing + GUIDELINES_MAX_RETRIES exponential backoff; strips share/breadcrumb chrome
    (promoted from the prototype's fetch_text)."""

def scrape_epo_guidelines(dest_dir: Path, edition: Optional[str] = None) -> bool:
    """Acquire in-force EPO Guidelines into epo_guidelines.txt (ADR-001 D3/D5).

    Resolve edition (discover unless overridden) -> discover A-H section URLs -> fetch each with
    pacing/retry, recording per-section outcome -> compute ratio = with_content / discovered over
    the intended A-H set. If ratio < GUIDELINES_SUCCESS_RATIO_FLOOR: FAIL, write nothing. Else:
    write manifest.json FIRST (temp+rename) then .txt (temp+rename), each in PART X - TITLE /
    ### {title} [{stem}] format. PART_TITLES['c'] typo fixed. No draft-PDF path."""
```

Manifest schema (`epo_guidelines.manifest.json`):

```json
{
  "edition": "2026",
  "discovered": 1887,
  "fetched": 1887,
  "with_content": 1881,
  "ratio": 0.9968,
  "completed_at": "2026-06-21T12:00:00Z"
}
```

#### Orchestration / trigger

```python
def ensure_epo_pct_corpus(mpep_dir: Path, index, mode: str = "lazy") -> dict[str, Any]:
    """Validate-then-acquire EPO/PCT artifacts and rebuild the index if anything changed.

    For EPC, EPO Guidelines, and PCT sources: validate(dest); if absent-or-invalid, acquire.
    If anything was acquired, call index.build_index(force_rebuild=True). Returns
    {"acquired": [...], "skipped": [...], "failed": [{source, reason}], "rebuilt": bool}.
    mode="lazy" emits the announced caller-facing acquiring message (KD7) before a scrape;
    mode="eager" is the --with-epo / download-all path. Non-fatal: per-source failures are
    collected and returned, never raised to abort the caller."""
```

#### CLI surface (`cli.py`)

```
setup            [--with-epo] [--skip-epo]   # default: register, do not eagerly acquire
rebuild-index    [--with-epo] [--skip-epo]   # default: register, do not eagerly acquire
download-all     # unchanged role: eager "build everything now" → also runs ensure_epo_pct_corpus(mode="eager")
```

`--with-epo` and `--skip-epo` are mutually exclusive (argparse mutually-exclusive group). `--skip-epo`
sets an env var (`PATENT_SKIP_EPO=true`) that the lazy trigger also honors (hard US-only: never
acquire, even lazily).

## Implementation Phases

The phases map directly to PRD-001's Phases 1/2/3. Each is independently deployable and testable.
Phase 0 lands the spine that Phases 1–2 depend on (ADR-001 makes D1 the prerequisite for D2/D3/D4).

### Phase 0: Validity-predicate spine (ADR D1 — prerequisite for all)

**Goal:** The validators and the single-file promote helper exist and are unit-tested, with the
existence short-circuits removed from the two acquisition entry points (so no junk is persisted or
skipped), before any flow is rewritten.

**Deliverables:**
- `validate_epc`, `validate_guidelines`, `fetch_validate_promote` in `epo_downloaders.py`.
- Configuration constants block (floors, pacing, retries, filenames); draft-PDF constants deleted.
- `_download_file:92` and `scrape_epo_guidelines:185` `dest_path.exists()` short-circuits removed
  (the functions are rewired onto the spine in Phases 1–2; in the interim they call the predicate).
- `tests/fixtures/`: a known-good EPC PDF (small real sample or trimmed), a junk HTML-as-PDF (~28 KB),
  a truncated PDF, a valid `epo_guidelines.txt` + matching manifest, a stub `.txt`, a `.txt` with no
  manifest, a `.txt` with a stale/low-ratio manifest.
- `tests/test_epo_validators.py`.

**Test strategy (written first):**
- Unit: `validate_epc` returns `True` for the good fixture, `False` for HTML-as-PDF (magic-byte
  fail), truncated PDF (size fail), and a valid-but-unrelated large PDF (provision-count fail).
- Unit: `validate_guidelines` returns `True` for valid `.txt`+manifest, `False` for stub (size/chunk),
  `.txt`-without-manifest (KD5), and `.txt` with ratio-below-floor manifest.
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
- [ ] `validate_epc` and `validate_guidelines` exist, are pure (no network), and pass the fixture matrix.
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
- Unit: `discover_section_urls` scopes to `[a-h]` and excludes `i/j/k/m` links present in the fixture.
- Unit: `scrape_epo_guidelines` with monkeypatched section fetches — ratio ≥ floor writes manifest
  **then** `.txt` (assert write order and both present); ratio < floor writes **neither** and returns
  `False`; a mid-scrape crash (manifest written, `.txt` not) leaves no `.txt` and `validate_guidelines`
  reports invalid.
- Unit: emitted `.txt` matches `^PART\s+([A-H])` and `^###` so `extract_text_from_epo_guidelines`
  parses it (round-trip through the real extractor on a small synthetic scrape).

**Infrastructure:** saved entry-page fixture; section fetches are monkeypatched (no live ~1,887-request
scrape in CI).

**Documentation:** module docstring documents discovery, the A–H-in / I·J·K·M-out scope, the manifest
schema, and the ratio gate; the EPO entry-page parse documented as the second repair location.

**Dependencies:** Phase 0.

**Definition of done:**
- [ ] `discover_in_force_edition` selects the highest year and fails loud on no link.
- [ ] `scrape_epo_guidelines` writes manifest-first, gates on 0.95, and writes nothing below floor.
- [ ] `PART_TITLES["c"]` fixed; no hardcoded `YEAR`; no draft-PDF code path; script deleted.
- [ ] Emitted `.txt` round-trips through `extract_text_from_epo_guidelines`.
- [ ] `tests/test_epo_edition_discovery.py` and `tests/test_epo_scrape_gating.py` pass.

### Phase 3: Deferred-default wiring + hardening (PRD Phase 3, ADR D4)

**Goal:** A clean `setup` is US-speed; the first EPO/PCT query acquires the EU corpus, rebuilds the
index, and returns real EU law; `--with-epo`/`--skip-epo` work; every outcome is logged.

**Deliverables:**
- `ensure_epo_pct_corpus(mpep_dir, index, mode)` in `epo_downloaders.py` (validate → acquire →
  `build_index(force_rebuild=True)` → structured result).
- Lazy trigger in `search_patent_law` (`patent_law_tools.py`): on `jurisdiction in {EPO,PCT}`, behind
  a process-lifetime guard and the `PATENT_SKIP_EPO` check, call `ensure_epo_pct_corpus(mode="lazy")`,
  surface the announced message and any failure to the caller.
- `--with-epo` / `--skip-epo` mutually-exclusive flags on `setup`/`rebuild-index`; eager call in those
  commands; `download_all_command` runs `ensure_epo_pct_corpus(mode="eager")`.
- `server.py` `--download-epo` path delegates to `ensure_epo_pct_corpus` (dedupe the logic).
- `tests/test_epo_acquisition_integration.py`.

**Test strategy (written first):**
- Integration (monkeypatched network, real index build on tiny synthetic corpora): a clean `MPEP_DIR`
  with US-only artifacts + a default trigger acquires synthetic EPC/Guidelines fixtures, rebuilds, and
  `search_patent_law(jurisdiction="EPO")` returns non-empty EU results — proving the clean-build-yields-
  non-empty-EU-corpus criterion end to end.
- Integration: with **valid** EPC/Guidelines already present, `ensure_epo_pct_corpus` acquires nothing
  and does not rebuild (network call count is 0); with a **corrupted** artifact it re-acquires.
- Integration: `PATENT_SKIP_EPO=true` makes the lazy trigger a no-op (US-only); `mode="eager"` forces
  acquisition regardless of trigger.
- Unit: the process-lifetime guard prevents a second EPO query from re-running validation.

**Infrastructure:** integration tests run with monkeypatched downloaders/scrape and a temp `MPEP_DIR`;
marked `slow` if the real embedding/index build is exercised, so CI can deselect with `-m "not slow"`.

**Documentation:** `CLAUDE.md` (Quick Reference / Skills) and the relevant slash-command/skill docs
updated to state EPO/PCT acquires lazily on first use, `--with-epo` for eager, `--skip-epo` for
US-only; PRD-001's false "no consolidated PDF" line corrected (ADR-001 flags it).

**Dependencies:** Phases 1 and 2.

**Definition of done:**
- [ ] Default `setup` runs no EPO scrape and leaves no EU artifacts.
- [ ] First `search_patent_law(jurisdiction="EPO")` triggers acquisition, rebuilds, returns EU results.
- [ ] Re-trigger with valid artifacts re-acquires nothing; corrupted artifacts re-acquire.
- [ ] `--with-epo` forces eager; `--skip-epo`/`PATENT_SKIP_EPO` disables lazy acquisition.
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
trigger it — documented in Phase 3's DaC.

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
| `validate_epc` calling `extract_text_from_epc` requires an `MPEPIndex` instance (heavy import) | Validator slow/coupled at call time | Low | Extractor reads only the PDF; construct a minimal/lazy singleton; cache it; it is invoked once per acquisition, not per query |
| Lazy trigger rebuilds the whole index on first EPO query (re-embeds US corpus too) | Multi-minute first-EPO-query pause beyond the scrape | Medium | Announced to caller (KD7); one-time per install (idempotent after); `--with-epo` lets operators pay it at setup; future: incremental index add |
| Live ~1,887-request scrape exercised in CI by accident | Slow/flaky CI, rate-limit exposure | Low | All section fetches monkeypatched in tests; integration marked `slow`; no test hits live EPO/WIPO |
| Two `os.replace` for manifest+`.txt` race a concurrent reader | Reader sees manifest-only state | Low | KD5 ordering makes manifest-only → not-acquired (predicate invalid), never a half-ingested `.txt` |
| Concurrent first EPO queries both trigger acquisition | Duplicate scrape | Low | Process-lifetime guard + a module-level lock around `ensure_epo_pct_corpus`; second waiter validates-and-skips |

## Roadmap Connection

- **Story:** `m2/s1` — "European & international law ingestion produces complete, in-force corpora."
- **Project:** `m2/s1/epo-downloaders-fix` (PRD-001's roadmap anchor).
- This design doc is the implementation bridge for ADR-001 and should be linked as the `docs_ref` on
  the `epo-downloaders-fix` feature (the parent project's `docs_ref` is the ADR/PRD).
- No roadmap restructuring needed; the three PRD phases map 1:1 to design Phases 1–3 (with Phase 0 as
  the D1 spine prerequisite the PRD folds into "the artifact-validity predicate").

## Open Questions

1. **EPC fixture provenance.** Can we legally/practically commit a trimmed EPC PDF as a test fixture,
   or do we generate a synthetic two-column PDF that the landed extractor parses into ≥ floor
   provisions? (Affects Phase 0 test infra; the design assumes a small committable fixture but
   tolerates injected floors as a fallback.)
2. **Index-rebuild cost on lazy trigger.** `build_index(force_rebuild=True)` re-embeds the entire
   corpus (US + EU). Is the one-time full rebuild on first EPO query acceptable for v1, or should an
   incremental "add EU chunks to the existing index" path be in scope here? (ADR-001 lists incremental
   as a Neutral/future consequence; this design defers it but flags it.)
3. **PCT under the same predicate.** ADR-001 D4 wires PCT acquisition under the same deferred trigger,
   but PCT sources are genuine fixed-URL PDFs that already work; do they need a `validate_pct`
   predicate, or is `validate` for PCT just "exists + %PDF- + size floor"? (Design assumes the lighter
   PCT check since PCT is not a problem source; confirm scope.)

---

## Revision History

| Date | Author | Notes |
|------|--------|-------|
| 2026-06-21 | cameronrout | Initial design from ADR-001 (D1–D5) and PRD-001 (Phases 1–3). |
