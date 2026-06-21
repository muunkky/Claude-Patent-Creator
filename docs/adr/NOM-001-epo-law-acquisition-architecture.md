# NOM-001: EPO/EPC Law Acquisition Architecture — Validate-Then-Persist, Discover-In-Force, Default-On

> **Status**: Proposed | **Date**: 2026-06-21 | **Deciders**: TBD

## Context

`mcp_server/epo_downloaders.py` is the acquisition layer that pulls European and
international legal corpora into `pdfs/` so that `mpep_search.build_index()` can chunk and
embed them. The US side (MPEP / 35 USC / 37 CFR) and the PCT side (Treaty, Regulations,
ISPE Guidelines) work because their sources are genuine, stable PDFs at fixed URLs. The two
most important European sources — the European Patent Convention (EPC) and the EPO
Guidelines for Examination — do not, and the reasons are structural, not incidental. PRD-001
(`docs/prds/PRD-001-epo-law-acquisition.md`) establishes the product requirements; this ADR
decides the acquisition architecture that satisfies them.

Four forces are in tension, and they are not independent — they share a single root cause:

**1. The sources are not files; they are interactive web surfaces that *yield* files.**
The genuine EPC PDF on WIPO Lex (`text/312166`) is delivered through a signed, ephemeral
CloudFront URL that embeds `Expires`, `Signature`, and `Key-Pair-Id` query parameters and
expires. The bare asset path returns HTML. The only durable, fetchable thing is the landing
page, which embeds the *current* signed URL in its markup. The EPO Guidelines are worse:
there is no consolidated PDF at all. The in-force edition is ~1,887 server-rendered HTML
section pages, discoverable from any section page's embedded navigation, and the edition is
re-published on a roughly annual cadence under a year-stamped URL prefix
(`/legal/guidelines-epc/{YEAR}/`). Both sources must be treated as fragile, changeable web
surfaces — not as download links.

**2. Success is silent and failure is silent — and that is exactly backwards.** The current
code skips on `dest_path.exists()` (`epo_downloaders.py:92`, `:185`). A 28 KB HTML landing
page saved under `epc_convention.pdf` therefore counts as "already downloaded" forever; the
indexer ingests it as a single junk chunk and no one notices until a practitioner queries
`search_patent_law(jurisdiction="EPO")` and gets nothing. The product advertises EPO
features as "Ready." A jurisdiction that quietly fails to ingest is a broken promise that
erodes trust in *every* answer the tool gives. The acquisition layer runs unattended during
install/rebuild; there is no human watching corpus quality, so the layer must watch its own.

**3. "Current" is a moving target that the code currently hardcodes.** The reference
prototype `scripts/_epo_guidelines_scrape.py` pins `YEAR = "2026"`. The EPO publishes a new
edition roughly annually. A hardcoded year does not fail — it rots, silently scraping a
*superseded* edition and presenting last year's examination guidance as binding. Indexing
draft-consultation text (the current `scrape_epo_guidelines` downloads
`…-draft-{year}.pdf`) is the same correctness defect from the other direction:
non-authoritative text presented as in-force law. In-force-ness is a correctness property of
a legal-research tool, not a nicety.

**4. None of it is wired into a command an operator runs.** `setup_command`
(`cli.py:432`), `rebuild_index_command` (`cli.py:851`), and `download_all_command`
(`cli.py:889`) never call `download_all_epo_documents`. The only trigger lives behind
`server.py`'s `--download-epo` / `--download-all` flags, which `setup` never passes. Even a
perfectly-fixed `download_epc()` and Guidelines scraper would still leave a clean install
with an empty EU corpus. But wiring acquisition into the documented path forces a cost
decision: the Guidelines scrape is ~1,887 HTTP requests against a public institution's site.
Putting that on every fresh install's critical path is a real tradeoff against keeping
US-only installs fast.

The unifying observation: **all four forces resolve through a single primitive — a
per-source *artifact-validity predicate* that answers "is what I have (or just fetched) real,
in-force law?"** That predicate is the gate for persistence (don't save junk), the gate for
idempotency (skip valid, re-acquire invalid), the signal for observability (report what the
predicate saw), and the floor that lets a partial scrape fail loudly instead of shipping a
thin file. The architecture below is organized around making that predicate the spine and
hanging the acquisition strategy off it.

Scope note: the indexer is fixed and out of scope. `extract_text_from_epc` (real PDF at
`pdfs/epc_convention.pdf`) and `extract_text_from_epo_guidelines` (the `PART X - TITLE` /
`### Section` text contract at `pdfs/epo_guidelines.txt`) already landed on `main` (commit
`c9b8779`). This ADR decides only how the acquisition layer produces artifacts those parsers
accept. `docs/adr/` is otherwise empty; there are no prior decisions in this area.

## Decision

We will restructure EPO/EPC acquisition around five coordinated decisions. They are presented
as one ADR because they share the validity-predicate spine and decisions D3–D5 are meaningless
without D1; splitting them would scatter one architecture across documents that have to be read
together anyway.

### D1 — The artifact-validity predicate is the architectural spine

We will define a per-source `validate(path) -> ValidationResult` predicate for each acquired
artifact and route **both** persistence and idempotency through it. No code path may save an
artifact, skip an artifact, or report success without consulting the predicate.

- **EPC** (`epc_convention.pdf`): valid iff the file begins with the `%PDF-` magic bytes
  **and** its size is ≥ a configured floor (a real EPC PDF is on the order of 1–2 MB; an HTML
  landing page is ~28 KB — the floor sits well above the latter, e.g. 200 KB) **and** a
  cheap structural probe extracts more than a minimum number of EPC provisions (e.g. it finds
  the article-numbering structure the indexer keys on). Magic-bytes alone is insufficient
  because a valid-but-wrong PDF would pass; the provision-count probe is what makes the
  predicate mean "real EPC," not "some PDF."
- **EPO Guidelines** (`epo_guidelines.txt`): valid iff the file is present, parses under the
  indexer's `^PART\s+([A-H])\s*[-–]\s*(.+)` / `^(?:###+|####)\s*(.+)` contract into ≥ a
  minimum chunk count, its size is ≥ a floor, **and** the recorded section-success ratio
  (sections-with-content ÷ sections-discovered) for the run that produced it is ≥ a floor
  (proposed 0.95; see D5). The success ratio is metadata of the *scrape*, not derivable from
  the file alone, so the scrape persists a sidecar manifest (`epo_guidelines.manifest.json`)
  recording `{edition, discovered, fetched, with_content, ratio, completed_at}`, and the
  predicate reads it.

The predicate replaces both `dest_path.exists()` short-circuits. Persistence flow: fetch to a
temp path, validate the temp path, and **only on pass** atomically move it into place (junk is
never persisted under the real filename). Idempotency flow: on build, validate the existing
artifact; skip iff valid; re-acquire iff absent **or** present-but-invalid.

The concrete floor values (size floors, minimum provision/chunk counts, the success ratio)
are configuration, defaulted in code and documented, not hardcoded magic numbers buried in
control flow. PRD launch criteria own their exact values; the architecture owns that they
*exist and gate everything*.

### D2 — EPC: fetch landing page, extract signed URL, download, validate (single flow)

`download_epc()` will:

1. Fetch the WIPO Lex landing page HTML (`text/312166`) — the durable, unsigned surface.
2. Extract the embedded signed CloudFront asset URL with a **targeted-pattern-with-fallback**
   parse: match the known WIPO download-link shape (an `href`/JSON field pointing at a
   `…cloudfront…` or WIPO asset host carrying `Signature=`/`Expires=`/`Key-Pair-Id=`), and if
   the primary pattern yields nothing, fall back to "any link to a `.pdf` on a signed/asset
   host whose query string carries those CloudFront params." The fallback widens the catch
   without the cost of a fully general HTML model.
3. Download the PDF from the signed URL **in the same flow**, immediately, to a temp path
   (signed URLs expire; extraction and download must not be separated by other work).
4. Validate via the D1 EPC predicate, then atomically promote on pass.
5. On any failure (page unreachable, no signed URL extractable, non-PDF body, predicate
   fail), log a clear EPC-named error, leave no junk `.pdf`, and report EPC as not-acquired.

The stale `download_epc` docstring ("The EPO HTML version is more current," written for the
abandoned approach) is corrected as part of this change.

WIPO markup change is handled by **defense in depth, not by a more brittle parser**: the
targeted+fallback extraction is the first line; the D1 predicate is the backstop. If WIPO
changes the page so that extraction returns the wrong link or HTML, the predicate rejects the
result and the build reports failure loudly. The system never silently indexes garbage; the
worst case is a loud "EPC not acquired" that a maintainer fixes by updating one extraction
pattern at a documented location.

### D3 — EPO Guidelines: discover the in-force edition; do not hardcode or pin

The in-force Guidelines edition will be **discovered deterministically at build time** from
the EPO's canonical current-Guidelines entry point (the stable, unversioned URL that the EPO
redirects/links to the current edition), resolving to the concrete year-stamped prefix
(`/legal/guidelines-epc/{edition}/`) actually in force on the build date. The hardcoded
`YEAR = "2026"` is removed. Section discovery keeps the prototype's proven approach: seed from
a section page and extract all `a.html … h*.html` section URLs from embedded navigation,
scoped to the resolved edition prefix.

The scrape emits `epo_guidelines.txt` in the indexer's exact `PART X - TITLE` / `### {title}
[{stem}]` format (the prototype already does this), and writes the D1 manifest sidecar
recording the resolved edition and per-section outcome. The orphaned draft-PDF download path
(`…-draft-{year}.pdf` → `epo_guidelines_{year}.pdf`) is **removed entirely**; no draft or
consolidated-PDF artifact is produced. The prototype's `PART_TITLES["c"]` typo
("Procedureal aspects…") is fixed during promotion.

If discovery of the canonical entry point fails (the EPO restructures that URL), the build
fails loudly for the Guidelines source with a message naming the discovery step — it does
**not** fall back to a hardcoded year, because a silent fallback to a possibly-stale edition
is the exact defect this decision exists to prevent. A `--guidelines-edition` override is
provided as a documented manual escape hatch for the maintainer, but it is never the default
and its use is logged prominently.

### D4 — Wiring: default-on in the documented build path, with `--skip-epo` escape hatch

EPO acquisition will run **by default** in the documented corpus-build path. Concretely:
`setup_command` and `rebuild_index_command` both invoke `download_all_epo_documents` (the PCT
sources, gated the same way today, are wired alongside so the documented path builds a
complete corpus). A `--skip-epo` flag is provided for operators who deliberately want a
US-only install.

Default-on is made affordable — rather than expensive — by D1's validity-keyed idempotency:
the ~1,887-request scrape and the WIPO fetch are paid **once**. Every subsequent rebuild
validates the existing artifacts and skips re-acquisition when they pass. The cost is borne by
the first clean install and by installs whose artifacts went invalid; it is not re-paid on
routine rebuilds. This is the "middle path" the PRD flags: default-on for completeness,
cheap-on-repeat via the predicate, skippable for the US-only minority.

### D5 — Resilience contract: pace, retry/backoff, success-ratio floor, fail-not-ship

The Guidelines scrape will operate under an explicit resilience contract:

- **Pacing**: a politeness delay between requests (prototype uses ~0.15 s; we treat the
  per-request delay and total wall-clock budget as configuration, tuned so ~1,887 requests
  stay within a courteous rate against a public institution's site).
- **Retry/backoff**: per-section retry with exponential backoff (prototype's 3-attempt,
  increasing-sleep pattern is the baseline), with a small bounded retry count so a flaky
  section doesn't stall the whole run.
- **Bounded tolerance**: a section that 404s or exhausts retries is recorded as failed and the
  scrape continues — a handful of dead sections must not abort an otherwise-complete corpus.
- **Success-ratio floor (the hard gate)**: after the run, `with_content / discovered` must be
  ≥ a floor (proposed **0.95**). Below the floor the scrape is declared **failed** — it does
  **not** write `epo_guidelines.txt`, so a thin/partial corpus can never be mistaken for a
  complete one by a later build. A successful run writes the file *and* the manifest atomically.
- **No partial artifact survives a crash**: write to temp + atomic rename, so an interrupted
  scrape leaves no half-file that the D1 predicate would later accept.

For build-level failure containment (an open question the PRD surfaces): EPO/PCT source
failure is **non-fatal to the overall build** (preserving today's contract — the US corpus
still builds), but it is **loud**: per-source outcome (resolved edition, sizes, fetched/
with-content counts, chunk counts, pass/fail) is logged, and the final build summary states
which jurisdictions were and were not acquired. "Non-fatal" means the build continues; it does
**not** mean the failure is quiet.

## Rationale

The decisions above flow from one judgment: **for a legal-research tool, a silently-wrong
corpus is strictly worse than a loudly-absent one.** A practitioner who sees "EPO not
acquired" knows not to trust EPO answers and can re-run; a practitioner who gets a confident
answer from a junk chunk or a superseded edition is actively misled. Every decision optimizes
for "fail loud, never lie."

### Key Factors

1. **The validity predicate is leverage, not overhead.** Four separate problems —
   persisting junk, skipping junk, shipping thin scrapes, and silent failure — collapse into
   one mechanism once you have a predicate that means "real, in-force law." Building four
   bespoke checks would be more code and more drift; centralizing on the predicate is the
   cheaper *and* more correct path. This is why D1 is the spine and the others hang off it.

2. **Defense in depth beats parser perfection for hostile sources.** We cannot make
   signed-URL extraction or HTML scraping immune to WIPO/EPO changing their markup — that is
   their prerogative and it will happen. What we *can* guarantee is that a markup change
   produces a loud, recoverable failure rather than silent corpus rot. The targeted+fallback
   extraction (D2) reduces how often a benign change breaks us; the predicate (D1) guarantees
   that when extraction *does* break, we report it instead of indexing the wrong bytes. The
   robustness budget is spent on the backstop, where it pays off unconditionally, rather than
   on an ever-more-defensive parser, where it has diminishing returns.

3. **Discover-don't-pin is the only option that is correct by construction.** A hardcoded
   year rots on a known schedule (the EPO's annual cadence). A pinned-with-drift-detection
   approach is *acceptable* (the PRD allows it) but it trades a maintenance obligation and a
   second moving part (the drift checker) for marginal control we don't need: the canonical
   entry point exists precisely to name the current edition. Discovery removes the failure mode
   rather than adding machinery to detect it. We keep a logged manual override (D3) for the
   rare case where a maintainer must force an edition, so we lose no control — we only lose the
   default rot.

4. **Default-on is honest about the product promise; idempotency makes it cheap.** The PRD's
   "zero manual steps" criterion and the "Ready" EPO label are only true if the documented
   command actually populates the EU corpus. Flag-gated acquisition re-creates a softer version
   of today's defect: the corpus is empty after a default `setup` and only the operator who
   *knows* to pass a flag gets EPO law. Default-on closes that gap. The reason this isn't a
   tax on every install is D1: a valid corpus is skipped on rebuild, so the ~1,887-request cost
   is a one-time first-install cost, and `--skip-epo` serves the genuine US-only user. We pay
   the cost where the value is and let those who don't want it opt out, rather than denying the
   majority the out-of-box experience to spare a minority a one-time scrape.

5. **The 0.95 success-ratio floor is calibrated, not arbitrary.** ~1,887 pages against a live
   site will occasionally see a transient 404 or timeout; demanding 100% would make the build
   flaky for no correctness gain. 0.95 tolerates ~94 missing sections — enough to absorb
   transient noise — while a scrape that loses more than that signals a real breakage (edition
   restructure, rate-limiting, discovery returning a wrong URL set) and should fail rather than
   ship a corpus missing whole chapters. The floor is configuration so it can be tuned against
   observed reality.

## Consequences

### Positive

- **Silent corpus rot becomes structurally impossible.** Junk is never persisted under the
  real filename; invalid existing artifacts are re-acquired; a thin scrape fails instead of
  shipping. The class of bug that motivated this work cannot recur without someone deleting the
  predicate.
- **In-force-ness is correct by construction**, surviving the EPO's annual republication with
  no code change and no scheduled maintenance ticket.
- **Out-of-box EU parity with US law**: a single documented command yields a non-empty,
  in-force EU corpus, matching the already-working US experience the PRD holds as the standard.
- **Cheap rebuilds**: the validity-keyed skip means the heavy scrape is paid once, so default-on
  does not punish iterative rebuilds.
- **Diagnosable failures**: per-source logging plus the manifest sidecar give a maintainer the
  resolved edition and exact fetch counts, turning "EPO search is empty" into a precise repair.

### Negative

- **First clean install is slower** by the wall-clock of the ~1,887-request scrape plus the
  WIPO fetch. Accepted because it is a one-time cost (D1 idempotency), it is skippable
  (`--skip-epo`), and it buys the advertised functionality; a fast install that silently lacks
  EPO law is the worse trade.
- **The manifest sidecar is new surface area.** `epo_guidelines.txt` now has a companion
  `epo_guidelines.manifest.json` that must stay consistent with it. Accepted because the
  success ratio genuinely is scrape-time metadata that cannot be recovered from the text file,
  and atomic co-writing keeps them consistent; the alternative (re-deriving validity from the
  file alone) cannot distinguish "intentionally short edition" from "broken partial scrape."
- **Two extraction/discovery patterns (WIPO signed URL, EPO entry point) remain maintenance
  liabilities.** Accepted and mitigated by D1's backstop: when they break, they break loudly at
  documented points, not silently.
- **Bus factor on external behavior**: correctness depends on WIPO's landing-page structure and
  the EPO's canonical entry point continuing to exist. This is irreducible for any approach that
  fetches live law; the PRD's own non-goal forbids vendoring the corpus into the repo.

### Neutral

- A full re-scrape (not incremental) on every *invalid-state* rebuild is accepted for now; the
  architecture leaves room for a future incremental mode (manifest already records per-section
  state) without reworking discovery/parsing.
- English-only (`/en/`) acquisition is retained per the PRD non-goal; multilingual would extend,
  not contradict, this design.

## Alternatives Considered

### Alternative 1: Hardcode / pin the EPC URL and the Guidelines edition

**Description**: Keep a fixed EPC PDF URL and a pinned Guidelines `YEAR`, updating both by hand
when they break.

**Pros**:
- Simplest possible code; no landing-page parse, no entry-point discovery.
- Fully deterministic — the build fetches exactly what the constant says.

**Why not chosen**: This is essentially the status quo, and it is the bug. The EPC signed
CloudFront URL *expires* — a hardcoded URL cannot work even momentarily. The pinned year *rots*
into stale-law-as-binding on the EPO's annual schedule. Both failures are silent, which is the
cardinal sin for a legal tool. Pinning trades a recurring, easy-to-forget maintenance
obligation for control we can get for free from discovery. Rejected outright; the PRD also
rejects the hardcoded year explicitly.

### Alternative 2: Vendor (mirror) the EPC PDF and a Guidelines snapshot into the repo

**Description**: Commit a known-good EPC PDF and a pre-scraped `epo_guidelines.txt` into version
control; the build copies them locally with no network fetch.

**Pros**:
- Zero install-time network dependency; fast, deterministic, offline-capable installs.
- Immune to WIPO/EPO markup changes at build time.

**Why not chosen**: The PRD names this an explicit non-goal — we do not vendor legal text into
version control. Beyond that, it converts an *acquisition* problem into a *staleness* problem:
the committed snapshot is in-force only until the next EPO edition, then someone must remember
to re-scrape and re-commit, with no signal when they're overdue. It also bloats the repo with
multi-megabyte binaries and a ~5 MB text file that change annually. The build-time fetch keeps
the corpus tied to the authoritative host, which is the correct source of truth for law. A
defensible middle (vendor only as an emergency offline fallback) is left as a future
consideration, not a default.

### Alternative 3: Existence-plus-size check instead of a full validity predicate

**Description**: Replace `dest_path.exists()` with `exists() and size > floor` — cheaper than a
parse-based predicate.

**Pros**:
- Catches the 28 KB-HTML-as-PDF case (it's under any reasonable floor) with almost no code.
- No PDF probe, no manifest, no chunk-parse — fast and simple.

**Why not chosen**: Size is necessary but not sufficient. A size check cannot tell a real EPC
PDF from an unrelated large PDF, cannot tell a complete Guidelines scrape from a thin-but-padded
one, and has no notion of the section-success ratio that is the only honest signal of scrape
completeness. The whole point is to assert "this is *real, in-force law*," and only a structural
probe (provision count / chunk parse / success ratio) makes that assertion. We adopt the size
floor as *one clause* of the predicate (D1), not as the whole thing.

### Alternative 4: Flag-gated (opt-in) EPO acquisition

**Description**: Leave `setup`/`rebuild-index` US-only by default; acquire EPO only when the
operator passes `--download-epo`.

**Pros**:
- Baseline install stays fast and low-risk; no ~1,887-request scrape for users who never touch
  EPO; no rate-limit exposure on the default path.
- Conservative — opts the heavy, externally-dependent work out of the critical path.

**Why not chosen**: It leaves the EU corpus empty after a default `setup`, so the "Ready" EPO
features and the "zero manual steps" promise hold only for operators who know to pass a flag —
a softer re-run of today's defect (the trigger exists, but nobody invokes it). Default-on with
`--skip-epo` (D4) inverts the default to match the advertised product while preserving the fast
US-only path for those who explicitly want it, and D1's idempotency removes the recurring-cost
objection that motivates opt-in in the first place. We chose the inversion because the cost is
one-time and opt-out-able, whereas the empty-corpus surprise is recurring and silent.

### Alternative 5: Headless-browser rendering for both sources

**Description**: Drive a real browser (Playwright/Selenium) to render the WIPO landing page and
the EPO Guidelines, reading the resolved signed URL and section content from the live DOM.

**Pros**:
- Robust against JS-driven markup; reads exactly what a human sees.
- One mechanism for both fragile sources.

**Why not chosen**: Massive dependency and operational cost (a browser binary, drivers, more
RAM, slower fetches ×1,887) for sources that are server-rendered HTML — the prototype already
extracts the signed URL and section content with `requests` + `BeautifulSoup`. Adding a browser
to a pip-installable patent tool's install path is disproportionate to the problem. If a source
ever moves to genuinely JS-rendered delivery, this becomes a live option; today it is overkill.

## Implementation Notes

- **Module shape**: introduce a small `validate_epc(path)` / `validate_guidelines(path,
  manifest)` pair (or a `ValidationResult` dataclass) in `epo_downloaders.py`, called by both
  the download/scrape functions (pre-persist) and the build wiring (pre-skip). One predicate
  per source, two call sites each.
- **Persistence pattern**: every acquisition writes to a temp path in the same directory, runs
  the predicate, and `os.replace()`-promotes on pass; failures `unlink` the temp and return
  False with a logged, source-named reason. `_download_file`'s `dest_path.exists()` short-circuit
  (`:92`) and `scrape_epo_guidelines`'s (`:185`) are deleted in favor of validate-then-skip.
- **EPC flow** (`download_epc`): `GET` landing page → extract signed URL (targeted regex on the
  WIPO download-link/JSON, fallback to any CloudFront-signed `.pdf` link) → `GET` signed URL to
  temp → `validate_epc` → promote. Correct the stale docstring.
- **Guidelines flow** (`scrape_epo_guidelines`): resolve in-force edition from the canonical
  entry point → discover section URLs (prototype's nav-extraction, scoped to the resolved
  prefix) → fetch with pacing/retry/backoff, recording per-section outcome → if ratio ≥ floor,
  write `.txt` + `.manifest.json` atomically; else fail without writing. Delete the draft-PDF
  path. Fix the `PART_TITLES["c"]` typo. Build from `scripts/_epo_guidelines_scrape.py` rather
  than reinventing discovery/parsing; promote it out of `scripts/_…` into the module.
- **Wiring** (`cli.py`): `setup_command` and `rebuild_index_command` call
  `download_all_epo_documents` (+ PCT) by default; add a `--skip-epo` flag threaded to both.
  `download_all_command` likewise. Per-source outcomes surface in the build summary.
- **Configuration**: floors (EPC size + provision count; Guidelines size + chunk count +
  success ratio), pacing delay, retry count, and timeouts live as documented module constants /
  settings with sane defaults — not inline literals in control flow.
- **Migration**: no data migration; the first post-change build re-validates any existing
  `pdfs/epc_convention.pdf` and `epo_guidelines.txt`. Existing 28 KB HTML-as-PDF and any
  orphaned `epo_guidelines_{year}.pdf` fail the predicate and are re-acquired / ignored. Operators
  need take no manual action.

## Validation

We will know this was the right call when, on a clean machine running the single documented
build command (no manual artifact placement):

- `pdfs/epc_convention.pdf` begins with `%PDF-`, exceeds the size floor, and the indexer reports
  EPC chunks in the **hundreds** (articles + Implementing Regulations), not 1.
- `pdfs/epo_guidelines.txt` exists in `PART/###` format with a manifest recording a
  section-success ratio **≥ 0.95** and the **resolved in-force edition equal to** what the EPO's
  canonical entry point resolves to on the build date; the indexer reports Guidelines chunks in
  the **thousands**; **no** `…-draft-…` or `epo_guidelines_{year}.pdf` artifact remains.
- `search_patent_law(query="claim clarity requirement", jurisdiction="EPO")` returns genuine
  EPC Art. 84 text **and** an in-force Guidelines clarity passage.
- Re-running the build with valid artifacts present performs **no** re-download/re-scrape (the
  scrape's request count is 0); re-running with a deliberately-corrupted artifact (e.g. truncated
  PDF, stub `.txt`) **does** re-acquire it.
- A simulated WIPO markup change (extraction returns a non-PDF) or an EPO discovery failure
  produces a **loud, source-named build error** and leaves **no** junk artifact — never a silent
  pass.

Signals to revisit this decision:

- The success-ratio floor proves mistuned in practice (chronic false failures from transient
  noise, or false passes from a partial scrape) — adjust the floor or the validity probe.
- The first-install wall-clock from default-on draws sustained operator complaints despite
  idempotency — reconsider the default, or pursue the incremental-scrape future consideration.
- WIPO's signed-URL scheme or the EPO's entry point changes shape often enough that extraction/
  discovery breaks more than ~once a year — invest in source-drift detection (a PRD future
  consideration) or revisit the vendored-fallback alternative.

## Related Decisions

- None yet — `docs/adr/` is otherwise empty. This is the first ADR in the repository and the
  first to touch EPO/EPC acquisition.

## References

- `docs/prds/PRD-001-epo-law-acquisition.md` — the product requirements this ADR realizes
  (Phases 1–3, the artifact-validity predicate, default-on vs. flag-gated open question,
  in-force-edition selection).
- `mcp_server/epo_downloaders.py` — `download_epc()` (~line 125, with the stale docstring at
  ~133), `scrape_epo_guidelines()` (line 169), and the `dest_path.exists()` short-circuits at
  `_download_file` (line 92) and `:185`.
- `mcp_server/cli.py` — `setup_command` (432), `rebuild_index_command` (851),
  `download_all_command` (889): the documented commands to wire.
- `mcp_server/server.py` — the only current EPO trigger, behind `--download-epo` /
  `--download-all` (lines 507–519).
- `mcp_server/mpep_search.py` — the fixed indexer contract: `extract_text_from_epc()`,
  `extract_text_from_epo_guidelines()` (`PART/###` patterns), `build_index()`.
- `scripts/_epo_guidelines_scrape.py` — the reference prototype to promote (hardcoded
  `YEAR = "2026"` at line 15 and `PART_TITLES["c"]` typo at line 21 to reconcile).
- WIPO Lex EPC entry: `https://www.wipo.int/wipolex/en/text/312166`. EPO Guidelines base:
  `https://www.epo.org/en/legal/guidelines-epc`. AWS CloudFront signed-URL semantics
  (`Expires`/`Signature`/`Key-Pair-Id`) — AWS CloudFront developer documentation.
- Prior context (out of scope): commit `c9b8779` — `extract_text_from_epc` rewrite and
  `build_index` `KeyError: 'page'` fix.

---

## Revision History

| Date | Status | Notes |
|------|--------|-------|
| 2026-06-21 | Proposed | Initial proposal — five coordinated decisions (validity-predicate spine, EPC signed-URL flow, discover-in-force Guidelines edition, default-on wiring with `--skip-epo`, scrape resilience contract) realizing PRD-001 Phases 1–3. |
