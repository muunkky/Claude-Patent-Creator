# NOM-001: EPO/EPC Law Acquisition Architecture — Validate-Then-Persist, Discover-In-Force, Deferred-Default Acquisition

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
URL on WIPO's asset host (`wipolex-res.wipo.int`, path `/edocs/lexdocs/treaties/en/ep001/
trt_ep001_001en.pdf`) carrying CloudFront-style `Expires`/`Signature`/`Key-Pair-Id` query
parameters that expire. The bare asset path returns HTML. The only durable, fetchable thing
is the landing page, which embeds the *current* signed URL in its markup — and embeds it
HTML-entity-encoded (`&#x3D;`→`=`, `&amp;`→`&`), so the extracted string must be unescaped
before it can be fetched. The EPO Guidelines are a different shape: the in-force edition is
also published as a single *consolidated, hyperlinked PDF* (verified live:
`https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-2026-hyperlinked.pdf`
returns HTTP 200 `application/pdf`, alongside a `-showing-modifications.pdf`), **and** as
~1,887 server-rendered HTML section pages reachable from the entry page's embedded
navigation. The edition is re-published on a roughly annual cadence under a year-stamped URL
prefix (`/legal/guidelines-epc/{YEAR}/`). The consolidated PDF's existence matters: it means
the choice to scrape the HTML cannot rest on "there is no PDF" — it must rest on what the
already-landed indexer can actually parse and what PRD-001 scopes in (see Alternative 6).
Both sources must be treated as fragile, changeable web surfaces — not as static download
links.

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
`pdfs/epc_convention.pdf`) and `extract_text_from_epo_guidelines` (`mpep_search.py:553`,
which reads `pdfs/epo_guidelines.txt` and parses the `PART X - TITLE` / `### Section` *text*
contract — it has no PDF reader at all) already landed on `main` (commit `c9b8779`). This is
load-bearing for the Guidelines decision below: the landed extractor cannot consume the
consolidated Guidelines PDF, and writing a new Guidelines-PDF parser is scoped OUT by PRD-001.
This ADR decides only how the acquisition layer produces artifacts those parsers accept.
`docs/adr/` is otherwise empty; there are no prior decisions in this area.

PRD correction flagged: PRD-001 line ~57–58 states the in-force Guidelines "are published
HTML-only — there is no consolidated PDF." That is false (the consolidated hyperlinked PDF is
live, verified above). PRD-001 should be corrected to read that a consolidated PDF *does*
exist but is out of scope because the landed indexer parses the HTML-derived `PART/###` text
contract, not a PDF. This ADR does not depend on the false premise; see Alternative 6.

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
  structural probe extracts more than a minimum number of EPC provisions (i.e. it finds the
  article-numbering structure the indexer keys on). Magic-bytes alone is insufficient because a
  valid-but-wrong PDF would pass; the provision-count probe is what makes the predicate mean
  "real EPC," not "some PDF." **The probe reuses the landed `extract_text_from_epc` extractor —
  it does not re-implement a lighter independent parse** (see B4 reasoning below). This is a
  deliberate, named coupling: `validate_epc` calls the same extractor the indexer will use, so
  the predicate asserts exactly "the indexer will get ≥ N provisions from this file," with zero
  drift between validation and ingestion. The factual basis for accepting the coupling rather
  than fearing a layout-mismatch false-negative: the WIPO PDF `trt_ep001_001en.pdf` (D2's
  source) **is** the EPO official 906-page trilingual (DE|EN|FR) two-column publication — the
  exact document family the landed `extract_text_from_epc` was written for and verified against
  (two-column layout, `MIDX=235`, "European Patent Convention" / "Implementing Regulations"
  headers, ~995 clean English chunks). D2's source and the landed extractor are therefore the
  same document; there is no separate-parser drift to manage and no layout mismatch to guard
  against. Single source of truth wins here.
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
2. Extract the embedded signed asset URL with a **targeted-pattern-with-fallback** parse. The
   primary pattern keys on the **WIPO asset host + signing-param triple**, NOT on the literal
   string `cloudfront`: match an `href`/`src` (verified live: it is a `src=` on
   `wipolex-res.wipo.int` under the `/edocs/lexdocs/…/trt_ep001_001en.pdf` path) whose query
   string carries `Signature`, `Expires`, **and** `Key-Pair-Id`. The host is a WIPO vanity
   domain (`wipolex-res.wipo.int`); only the *signing scheme* is CloudFront's, so matching the
   literal "cloudfront" would miss the real link. The fallback widens to "any `.pdf` link/src
   carrying the `Signature`/`Expires`/`Key-Pair-Id` triple" without a fully general HTML model.
3. **HTML-unescape the extracted URL before fetching.** The URL is HTML-entity-encoded in the
   page markup (verified live: `&#x3D;` for `=`, `&amp;` for `&`); the raw match must be run
   through `html.unescape` (or equivalent) or the signed query string will be malformed and the
   fetch will fail or return a wrong body.
4. Download the PDF from the unescaped signed URL **in the same flow**, immediately, to a temp
   path (signed URLs expire; extraction and download must not be separated by other work).
5. Validate via the D1 EPC predicate, then atomically promote on pass.
6. On any failure (page unreachable, no signed URL extractable, unescape yields a malformed
   URL, non-PDF body, predicate fail), log a clear EPC-named error, leave no junk `.pdf`, and
   report EPC as not-acquired.

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
the EPO's canonical, stable, unversioned entry page (`https://www.epo.org/en/legal/
guidelines-epc`). Discovery is a **parse, not a redirect**: verified live, that entry URL
returns HTTP 200 with no 3xx — it does not redirect to a year-stamped URL. Instead its
markup embeds year-stamped links into the in-force edition (e.g.
`…/guidelines-epc/2026/index.html`, `…/2026/j.html`, etc.). The concrete resolution rule is:
**fetch the entry page's raw HTML, extract every `…/legal/guidelines-epc/(\d{4})/…` link, and
take the highest year as the in-force edition prefix `/legal/guidelines-epc/{edition}/`.**
Raw HTML is required — a markdown- or JS-reduced rendering of the page drops these links
(observed: the reduced view shows only the language-switcher links, not the year-stamped
nav), so the fetch must read the unreduced server response. Note that more than one edition
can be simultaneously live on the EPO site (e.g. 2025 and 2026 both reachable); the rule
selects the highest-year prefix *linked from the entry page*, which is the edition the EPO
presents as current. The hardcoded `YEAR = "2026"` is removed. Section discovery keeps the
prototype's proven approach: seed from a section page and extract all section URLs from
embedded navigation, scoped to the resolved edition prefix (see S-note in D-resilience and the
part-set scope below for the exact section-letter range).

**Part-set scope (in/out).** Substantive examination Guidelines are Parts **A–H** (Formalities,
Search, Substantive-examination procedure, Opposition, General procedure, The application,
Patentability, Amendments). The prototype's discovery regex is `[a-h]`-scoped. That is correct
and intentional: the live site also exposes Parts **I/J/K/M** (front-matter/foreword, annexes,
and PCT-EPO/national-law material — verified live: `j.html`, `k.html`, `m.html` are linked from
the entry page), and these are **deliberately excluded** as non-substantive or PCT-EPO content
outside this corpus's scope. The success-ratio denominator (D5) is therefore the **intended A–H
part set**, not "every section letter the site exposes." A consequence worth stating: a sudden
change in the *count* of discovered A–H sections — up or down — is itself a signal (the EPO
restructured a part, or discovery scope drifted) and should be surfaced in the build summary,
not silently absorbed.

The scrape emits `epo_guidelines.txt` in the indexer's exact `PART X - TITLE` / `### {title}
[{stem}]` format (the prototype already does this), and writes the D1 manifest sidecar
recording the resolved edition and per-section outcome. The orphaned draft-PDF download path
(`…-draft-{year}.pdf` → `epo_guidelines_{year}.pdf`) is **removed entirely**; no draft or
consolidated-PDF artifact is produced. The prototype's `PART_TITLES["c"]` typo
("Procedureal aspects…") is fixed during promotion.

If discovery fails — the entry page is unreachable, or its HTML contains **no**
`…/guidelines-epc/(\d{4})/…` link to parse — the build **fails loud** for the Guidelines
source with a message naming the discovery step and the URL it parsed. It does **not** fall
back to a hardcoded year, and it does **not** silently proceed with a default edition: a
silent fallback to a possibly-stale or absent edition is the exact defect this decision exists
to prevent. A `--guidelines-edition` override is provided as a documented manual escape hatch
for the maintainer (the explicit-and-logged path to force an edition when discovery is
broken), but it is never the default and its use is logged prominently.

### D4 — Wiring: default-on but **deferred/lazy** — acquire EPO on first EPO use, not at setup

EPO acquisition will be **wired into the documented path and on by default, but acquisition is
deferred to first EPO use rather than run eagerly at `setup`.** This is the middle path the PRD
floated and the prior revision of this ADR had dropped; on the honest cost accounting below, it
is the right call.

Concretely:

- `setup_command` and `rebuild_index_command` **register** EPO/PCT acquisition as part of the
  documented corpus, but do **not** pay the ~1,887-request Guidelines scrape + WIPO fetch on the
  setup critical path by default. A clean `setup` completes at US-corpus speed.
- The first time an EPO surface is exercised — the first `search_patent_law(jurisdiction="EPO")`
  / `jurisdiction="PCT"` query, or first invocation of an EPO/PCT skill — the acquisition layer
  runs *then*, guarded by D1's validity predicate (acquire iff the artifact is absent or
  invalid). The cost is paid once, by the user who actually wants EPO, at the moment they ask
  for it. Subsequent EPO queries validate-and-skip.
- An **eager** mode is available for operators who *want* the full corpus built at setup time
  (offline-first, air-gapped-after-setup, CI image baking): a `--with-epo` flag on
  `setup`/`rebuild-index` forces acquisition during the build. Symmetrically, `--skip-epo`
  remains for "never acquire EPO, even lazily" (hard US-only).
- The deferred acquisition must be **loud and bounded**: when an EPO query triggers a first-time
  scrape, the tool reports that it is acquiring the EU corpus (so a multi-minute pause is
  explained, not mysterious), and a scrape failure surfaces as a clear "EPO law not acquired —
  <reason>" to the caller, never a silent empty result.

Why deferred rather than eager-default-on: the honest cost the prior revision under-priced is
that the user base is US-majority, and **every fresh `setup` — including the large US-only
majority who will never issue an EPO query — would otherwise pay a multi-minute scrape against a
public institution's site and inherit its failure surface (a rate-limit or markup change becomes
an error wall on an install that never needed EPO).** Idempotency makes the scrape *cheap on
repeat*, but it does nothing for the *first* install, which is exactly where the US-only user
lives and never leaves. Deferring acquisition to first EPO use preserves the product promise
(EPO is "Ready" — it acquires automatically and invisibly the moment you use it, zero manual
steps) while moving the cost and the external-dependency risk off the path of users who don't
touch EPO. The "Ready" label is honored by *capability on demand*, not by *eager population*;
for a legal-research tool whose EU corpus is only meaningful to EU/PCT users, capability-on-
demand is the more honest reading of "Ready."

This keeps the validity-predicate spine (D1) doing the same work — it just moves the *trigger*
for first acquisition from setup-time to first-EPO-use, and adds `--with-epo` for operators who
genuinely want eager population.

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
  complete one by a later build.
- **Ordered, not jointly-atomic, sidecar write**: two `os.replace` calls are **not** jointly
  atomic, so we do not claim "atomic co-writing." Instead we define an **order** that is safe
  under a crash between the two: write `epo_guidelines.manifest.json` **first** (atomic rename),
  then write `epo_guidelines.txt` (atomic rename). The D1 predicate treats **`.txt`-present-
  without-a-consistent-manifest as INVALID** — so a crash after the manifest but before the
  `.txt` leaves no `.txt` (nothing to mis-ingest), and a crash after the `.txt` is impossible to
  reach without the manifest already on disk. The only orderings the predicate can observe are
  "neither," "manifest only" (→ no `.txt`, treated as not-acquired), and "both" (→ validated
  against the manifest). A stray `.txt` with no/again-stale manifest is rejected, not trusted.
- **No partial artifact survives a crash**: every file write is temp + atomic rename, so an
  interrupted scrape leaves no half-file that the D1 predicate would later accept.

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

4. **Deferred-default acquisition honors the product promise *and* prices the US-majority cost
   honestly.** The PRD's "zero manual steps" criterion and the "Ready" EPO label require that
   EPO law appears without the operator hunting for a flag — but they do *not* require eager
   population at `setup`. Flag-gated opt-in (Alternative 4) fails the promise: the operator must
   *know* to pass `--download-epo`, so EPO silently doesn't work by default. Eager default-on
   (the prior revision) honors the promise but over-charges: the US-majority user base — most of
   whom never issue an EPO query — would each pay a multi-minute ~1,887-request scrape on every
   fresh `setup` and inherit its external-failure surface (a WIPO/EPO rate-limit or markup change
   becomes an error wall on an install that never needed EPO). Idempotency (D1) makes the scrape
   cheap *on repeat*, but the first install is precisely where the US-only user lives, and they
   never reach the cheap repeat. **Deferred-default (D4) resolves the tension**: acquisition is
   automatic and flag-free (promise honored), but it fires on first EPO use rather than at
   setup, so the cost and the dependency risk land only on users who actually want EPO. The
   `--with-epo` eager flag serves offline/CI baking; `--skip-epo` serves hard US-only. We charge
   the cost where the value is *and* at the moment it is wanted, rather than taxing the majority
   up front for a corpus they may never query.

5. **The EPC validator deliberately couples to the indexer's extractor (single source of
   truth).** D1's EPC predicate could either (a) call the landed `extract_text_from_epc` or
   (b) run an independent, lighter probe. Option (b) introduces drift: a validator that says
   "valid" while the indexer extracts nothing (or vice versa) is worse than no validator,
   because it lies precisely where it is meant to assure. We choose (a) and name the coupling.
   The usual worry with reusing the heavy extractor is a layout-mismatch false-negative — but
   that worry is resolved by fact: the WIPO source PDF is the same 906-page two-column EPO
   trilingual publication the landed extractor was authored and verified against (~995 clean
   English chunks). Because validator and indexer parse the same document with the same code,
   "validate_epc passes" is definitionally "the indexer will succeed." If the EPC source ever
   diverges from that document family, the coupling makes the failure loud and shared rather
   than splitting it across two probes; a shared test fixture (the known-good EPC PDF) pins both
   call sites to the same expectation.

6. **The 0.95 success-ratio floor is calibrated, not arbitrary.** ~1,887 pages against a live
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

- **First EPO query is slower** by the wall-clock of the ~1,887-request scrape plus the WIPO
  fetch — the cost moves off `setup` (D4 deferral) and onto the first EPO/PCT use. Accepted
  because it is a one-time cost (D1 idempotency), it lands only on users who actually want EPO,
  it is announced (the tool reports it is acquiring the EU corpus, so the pause is explained),
  and `--with-epo` lets operators who prefer eager population pay it at setup instead. The
  US-majority `setup` is no longer taxed for a corpus it may never query.
- **The manifest sidecar is new surface area.** `epo_guidelines.txt` now has a companion
  `epo_guidelines.manifest.json` that must stay consistent with it. The sidecar is justified,
  not decorative: the section-success ratio is *scrape-time* metadata (`with_content /
  discovered`) **not recoverable from the `.txt` alone** — a from-file chunk-count floor cannot
  distinguish "intentionally short edition" from "a broken partial scrape that happened to clear
  the chunk floor," which is the exact failure D5 must catch. The cheaper alternative (drop the
  sidecar, gate only on a from-file chunk-count floor) was considered and rejected for that
  reason. Consistency is maintained **not** by a (false) joint-atomic write of two files — two
  `os.replace` calls are not jointly atomic — but by the **manifest-first write order** (D5) and
  the predicate rule that **`.txt`-without-a-consistent-manifest is invalid**. The cost is one
  small JSON file and one ordering rule.
- **Two extraction/discovery patterns (WIPO signed URL, EPO entry-page year-link parse) remain
  maintenance liabilities.** Accepted and mitigated by D1's backstop: when they break, they
  break loudly at documented points, not silently.
- **External-source dependency risk**: correctness depends on WIPO's landing-page structure
  (signed-URL `src` on `wipolex-res.wipo.int`, HTML-entity-encoded) and the EPO entry page's
  year-stamped section links continuing to exist. This is irreducible for any approach that
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
a softer re-run of today's defect (the trigger exists, but nobody invokes it). Deferred-default
acquisition (D4) keeps the flag-free, automatic behavior the promise requires while still
sparing US-only installs the scrape — it acquires on first EPO use, not at setup. So D4 captures
this alternative's one real virtue (don't tax US-only installs) without its fatal flaw (EPO
silently broken unless you know a flag).

**Note — eager default-on was the prior recommendation and is now demoted to an explicit
`--with-epo` flag.** Eagerly running the scrape at every `setup` honors the "Ready" promise but
over-charges the US-majority user base, each of whom pays a multi-minute scrape and inherits its
external-failure surface on an install that may never issue an EPO query. D4's deferral keeps the
promise and removes that tax; eager population remains available for operators who explicitly
want it (`--with-epo`, for offline/air-gapped/CI-image use).

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

### Alternative 6: Consume the official consolidated Guidelines PDF instead of scraping HTML

**Description**: Rather than scraping ~1,887 HTML section pages, download the single official
consolidated, hyperlinked Guidelines PDF that the EPO publishes
(`https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-2026-hyperlinked.pdf`,
verified live: HTTP 200 `application/pdf`), plus its `-showing-modifications` companion. Parse
that one PDF into the corpus.

**Pros**:
- **One HTTP request, not ~1,887.** No politeness pacing, no per-section retry/backoff, no
  success-ratio floor, no rate-limit exposure against a public institution. The entire
  resilience contract (D5) and most of the manifest machinery (S2) would be unnecessary.
- **Authoritative and self-consistent**: it is the EPO's own consolidated in-force edition,
  hyperlinked — arguably a cleaner source of truth than reassembling section pages.
- **Faster first install**, directly addressing the default-on cost objection.

**Why not chosen** (on true grounds, not "no PDF exists"):
- **The landed indexer cannot read it.** `extract_text_from_epo_guidelines`
  (`mpep_search.py:553`) reads `pdfs/epo_guidelines.txt` and parses a `PART X - TITLE` /
  `### Section` *text* contract; it has no PDF reader. Consuming the consolidated PDF would
  require a **new Guidelines-PDF parser** (PDF text extraction + reconstruction of the part/
  section structure from a 1,800-page two-column document), which **PRD-001 scopes OUT** — the
  indexer is fixed and out of scope for this ADR.
- **The PDF lacks the per-section URL stems the HTML scrape yields.** The scrape emits
  `### {title} [{stem}]` where `{stem}` is the section's source page (e.g. `[a_ii_1.html]`),
  giving each chunk a stable, citable EPO URL. A consolidated PDF has page numbers, not
  per-section web stems, so citations back to the live EPO Guidelines would be lost.
- This alternative is genuinely attractive and could *win* a future revision — but only paired
  with a deliberate decision to build a Guidelines-PDF parser and to give up per-section URL
  citations. Under the current indexer contract and PRD-001 scope, the HTML scrape is the
  correct producer because it emits exactly the text contract the landed parser already accepts.
  The scrape decision rests on the indexer contract + PRD scope + citation stems — **not** on
  the false claim that no consolidated PDF exists.

## Implementation Notes

- **Module shape**: introduce a small `validate_epc(path)` / `validate_guidelines(path,
  manifest)` pair (or a `ValidationResult` dataclass) in `epo_downloaders.py`, called by both
  the download/scrape functions (pre-persist) and the build wiring (pre-skip). One predicate
  per source, two call sites each. `validate_epc` **calls the landed `extract_text_from_epc`**
  (single source of truth; provision count from the real extractor), and a shared test fixture
  (a known-good EPC PDF) pins both `validate_epc` and the indexer to the same expectation so the
  coupling cannot silently drift.
- **Persistence pattern**: every acquisition writes to a temp path in the same directory, runs
  the predicate, and `os.replace()`-promotes on pass; failures `unlink` the temp and return
  False with a logged, source-named reason. `_download_file`'s `dest_path.exists()` short-circuit
  (`:92`) and `scrape_epo_guidelines`'s (`:185`) are deleted in favor of validate-then-skip.
- **EPC flow** (`download_epc`): `GET` landing page → extract signed URL (targeted regex on the
  WIPO download-link/JSON, fallback to any CloudFront-signed `.pdf` link) → `GET` signed URL to
  temp → `validate_epc` → promote. Correct the stale docstring.
- **Guidelines flow** (`scrape_epo_guidelines`): resolve in-force edition from the canonical
  entry point → discover section URLs (prototype's nav-extraction, scoped to the resolved
  prefix; discovery regex stays `[a-h]`-scoped — Parts I/J/K/M are out of scope, see D3) → fetch
  with pacing/retry/backoff, recording per-section outcome → if ratio ≥ floor, write
  `.manifest.json` **first** then `.txt` (each via temp + atomic rename; ordered, not jointly
  atomic — D5); else fail without writing either. Delete the draft-PDF path. Fix the
  `PART_TITLES["c"]` typo. Build from `scripts/_epo_guidelines_scrape.py` rather than reinventing
  discovery/parsing; promote it out of `scripts/_…` into the module.
- **Wiring** (`cli.py` + server): EPO/PCT acquisition is registered as part of the documented
  corpus but **deferred** by default — `setup_command` / `rebuild_index_command` do **not** run
  `download_all_epo_documents` eagerly. The first `search_patent_law(jurisdiction in {EPO,PCT})`
  query (and EPO/PCT skill entry) checks the D1 predicate and triggers acquisition on
  absent/invalid, reporting "acquiring EU corpus…" and surfacing failure as a clear caller-
  facing error. `--with-epo` on `setup`/`rebuild-index` forces eager acquisition at build time;
  `--skip-epo` disables acquisition entirely (hard US-only). `download_all_command` runs the full
  acquisition eagerly (it is the explicit "build everything now" command). Per-source outcomes
  surface in the build/query summary.
- **Configuration**: floors (EPC size + provision count; Guidelines size + chunk count +
  success ratio), pacing delay, retry count, and timeouts live as documented module constants /
  settings with sane defaults — not inline literals in control flow.
- **Migration**: no data migration; the first post-change build re-validates any existing
  `pdfs/epc_convention.pdf` and `epo_guidelines.txt`. Existing 28 KB HTML-as-PDF and any
  orphaned `epo_guidelines_{year}.pdf` fail the predicate and are re-acquired / ignored. Operators
  need take no manual action.

## Validation

We will know this was the right call when, on a clean machine:

- A default `setup` (no `--with-epo`) completes at **US-corpus speed** — it does **not** run the
  ~1,887-request scrape or the WIPO fetch — and leaves no EU artifacts yet.
- The **first** `search_patent_law(query="claim clarity requirement", jurisdiction="EPO")` query
  triggers deferred acquisition (announced to the caller), then returns genuine EPC Art. 84 text
  **and** an in-force Guidelines clarity passage. A `setup --with-epo` instead populates the EU
  corpus eagerly at build time.
- After acquisition (lazy or eager), `pdfs/epc_convention.pdf` begins with `%PDF-`, exceeds the
  size floor, and the indexer reports EPC chunks in the **hundreds** (articles + Implementing
  Regulations), not 1.
- `pdfs/epo_guidelines.txt` exists in `PART/###` format with a manifest recording a
  section-success ratio **≥ 0.95** over the intended **A–H** part set and the **resolved in-force
  edition equal to** the highest year-stamped prefix linked from the EPO entry page on the
  acquisition date; the indexer reports Guidelines chunks in the **thousands**; **no**
  `…-draft-…` or `epo_guidelines_{year}.pdf` artifact remains; and a `.txt` with no/stale
  manifest is rejected as invalid.
- Re-running acquisition with valid artifacts present performs **no** re-download/re-scrape (the
  scrape's request count is 0); a deliberately-corrupted artifact (truncated PDF, stub `.txt`,
  `.txt`-without-manifest) **does** re-acquire.
- A simulated WIPO markup change (extraction returns a non-PDF, or the entity-unescape yields a
  malformed URL) or an EPO discovery failure (entry page has no parseable year-stamped link)
  produces a **loud, source-named error** to the caller and leaves **no** junk artifact — never a
  silent pass and never a silently-empty EPO result.

Signals to revisit this decision:

- The success-ratio floor proves mistuned in practice (chronic false failures from transient
  noise, or false passes from a partial scrape) — adjust the floor or the validity probe.
- The first-EPO-query wall-clock from deferred acquisition draws sustained complaints (an EU
  user expects EPO to be ready instantly) — reconsider toward eager-by-default for EU-detected
  installs, pursue the incremental-scrape future consideration, or revisit Alternative 6
  (consolidated PDF) paired with a Guidelines-PDF parser to collapse the scrape to one request.
- WIPO's signed-URL scheme or the EPO's entry point changes shape often enough that extraction/
  discovery breaks more than ~once a year — invest in source-drift detection (a PRD future
  consideration) or revisit the vendored-fallback alternative.

## Related Decisions

- None yet — `docs/adr/` is otherwise empty. This is the first ADR in the repository and the
  first to touch EPO/EPC acquisition.

## References

- `docs/prds/PRD-001-epo-law-acquisition.md` — the product requirements this ADR realizes
  (Phases 1–3, the artifact-validity predicate, default-on vs. flag-gated open question,
  in-force-edition selection). **Correction needed:** PRD line ~57–58 claims the in-force
  Guidelines are "published HTML-only — there is no consolidated PDF." That is false — a
  consolidated hyperlinked PDF is live (see Alternative 6). PRD-001 should be amended to say the
  PDF exists but is out of scope under the landed indexer's text contract.
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
  `YEAR = "2026"` at line 15, `PART_TITLES["c"]` typo at line 21, and the `[a-h]`-scoped
  discovery regex at line 36 — the part scope is correct/intentional per D3, only the hardcoded
  year is replaced by entry-page discovery).
- WIPO Lex EPC entry: `https://www.wipo.int/wipolex/en/text/312166`. The genuine EPC PDF is
  served (verified live) as a `src` on **`wipolex-res.wipo.int`** (a WIPO vanity asset host —
  **not** a `cloudfront.net` host) at `/edocs/lexdocs/treaties/en/ep001/trt_ep001_001en.pdf`,
  HTML-entity-encoded (`&#x3D;`, `&amp;`), carrying **CloudFront-style signing params**
  (`Expires`/`Signature`/`Key-Pair-Id`) — AWS CloudFront signed-URL *scheme*, WIPO *host*. This
  PDF is the EPO official 906-page trilingual two-column publication (`trt_ep001_001en.pdf`).
  EPO Guidelines entry page (HTTP 200, no redirect; year-stamped section links parsed from raw
  HTML): `https://www.epo.org/en/legal/guidelines-epc`. Consolidated in-force Guidelines PDF
  (verified live, out of scope — Alternative 6):
  `https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-2026-hyperlinked.pdf`.
- Prior context (out of scope): commit `c9b8779` — `extract_text_from_epc` rewrite and
  `build_index` `KeyError: 'page'` fix.

---

## Revision History

| Date | Status | Notes |
|------|--------|-------|
| 2026-06-21 | Proposed | Initial proposal — five coordinated decisions (validity-predicate spine, EPC signed-URL flow, discover-in-force Guidelines edition, default-on wiring with `--skip-epo`, scrape resilience contract) realizing PRD-001 Phases 1–3. |
| 2026-06-21 | Proposed (rev 2) | Revised after adversarial live-source review. B1: corrected false "no consolidated PDF" premise (the in-force hyperlinked Guidelines PDF is live, HTTP 200) and added Alternative 6, engaged honestly — scrape now justified on indexer text-contract + PRD scope + per-section citation stems, not on PDF nonexistence. B2: specified Guidelines edition discovery as a raw-HTML *parse* of the highest year-stamped entry-page link (not a redirect), fail-loud on no parseable link. B3: corrected EPC extraction to key on the WIPO asset host (`wipolex-res.wipo.int`) + signing-param triple (not the literal "cloudfront"), added an HTML-unescape step, fixed the References host conflation. B4: `validate_epc` reuses the landed `extract_text_from_epc` (named coupling, shared fixture); confirmed WIPO PDF == the 906-page EPO publication the extractor targets (no layout-mismatch risk). S1: stated A–H part scope in / I·J·K·M out, denominator = intended set. S2: justified the manifest sidecar over a from-file floor, replaced false "atomic co-writing" with manifest-first ordered write + `.txt`-without-manifest-is-invalid rule. **S3 (decision change): default-on flipped from eager to DEFERRED/LAZY — acquire EPO on first EPO use, not at every `setup`; `--with-epo` for eager, `--skip-epo` for hard US-only.** M1: "bus factor" → "external-source dependency risk". |
