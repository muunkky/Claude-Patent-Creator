# EPODL Sprint Closeout

> **Sprint**: EPODL | **Type**: chore | **Step**: 5 (final)
>
> Mandatory closeout card for sprint EPODL. Dispatched last. Walks accumulated retrospective items using the four-type deferral grid (see planner/SKILL.md per-item block format for the grid definitions).

## Purpose

Close out sprint EPODL: archive done cards, generate the sprint summary, update `CHANGELOG.md`, mark roadmap stories complete (`m2/s1` story / `m2/s1/epo-downloaders-fix` project), and process every item in the Sprint Retrospective section below using the four-type deferral grid each item carries.

## Cleanup Scope & Context

* **Sprint/Release:** EPODL — EPO/EPC law acquisition
* **Primary Feature Work:** Validate-then-persist, discover-in-force, deferred-default EPO/PCT acquisition
* **Cleanup Category:** Sprint closeout (archive, summary, CHANGELOG, roadmap, retrospective)

**Required Checks:**
* [ ] Sprint/Release is identified above.
* [ ] Primary feature work that generated this cleanup is documented.

## Sprint Retrospective

<!-- planner appends items below this line during the sprint. Each item is a self-contained block with its own classification grid per planner/SKILL.md. Leave this section empty if no items accumulate. -->

## Deferred Work Review

* [ ] Reviewed commit messages for "TODO" and "FIXME" comments added during sprint.
* [ ] Reviewed PR comments for "out of scope" or "follow-up needed" discussions.
* [ ] Reviewed code for new TODO/FIXME markers (grep for them).
* [ ] Checked team chat/standup notes for deferred items.

| Cleanup Category | Specific Item / Location | Priority | Justification for Cleanup |
| :--- | :--- | :---: | :--- |
| **Retrospective** | Items appended under `## Sprint Retrospective` during the sprint | P1 | Each processed via the four-type deferral grid |
| **Roadmap** | story `m2/s1`, project `m2/s1/epo-downloaders-fix` | P1 | Mark complete if sprint objectives met end-to-end |
| **CHANGELOG** | `CHANGELOG.md` | P1 | EPO/PCT background acquisition is a user-visible change |

## Cleanup Checklist

### Documentation Updates (optional)

| Task | Status / Details | Done? |
| :--- | :--- | :---: |
| **CHANGELOG** | Add EPODL user-visible entries (background EPO/PCT acquisition, `--with-epo`/`--skip-epo`) | - [ ] |
| **Roadmap** | Update `m2/s1` story / `epo-downloaders-fix` project status | - [ ] |
| **Sprint summary** | `generate_archive_summary` | - [ ] |
| **Other:** Retrospective | Walk each `## Sprint Retrospective` item via the deferral grid | - [ ] |

### Code Quality & Technical  (optional)

| Task | Status / Details | Done? |
| :--- | :--- | :---: |
| **Cards archived** | All EPODL sprint cards via `archive_cards` | - [ ] |
| **Other:** Verify objectives | Clean build yields non-empty EU corpus; junk never persisted; no torn reads | - [ ] |

## Validation & Closeout

### Pre-Completion Verification

| Verification Task | Status / Evidence |
| :--- | :--- |
| **All P0 Items Complete** | step 2 (spine) + step 3C (atomicity) closed |
| **All P1 Items Complete or Ticketed** | step 3A, 3B, 4 closed |
| **Tests Passing** | Full `pytest tests/` green across the sprint |
| **No New Warnings** | Lint clean |
| **Documentation Updated** | CLAUDE.md + skills + CHANGELOG + PRD-001 correction |
| **Code Review** | All sprint cards reviewed |

### Follow-up & Lessons Learned

| Topic | Status / Action Required |
| :--- | :--- |
| **Remaining P2 Items** | None planned |
| **Recurring Issues** | Incremental index-add (design Open Q2) — explicit follow-up, not in scope |
| **Process Improvements** | Holder-object corpus snapshot (KD9) cleaner long-term shape — follow-up |
| **Technical Debt Tickets** | Created as needed from retrospective items |

## Acceptance Criteria

- [ ] Every item under `## Sprint Retrospective` has exactly one deferral-type row marked `true` in its inline grid (exactly-one-true constraint)
- [ ] Every item has its `Action taken:` field filled in matching the chosen deferral type (card id for backlog/sprint, prose for note-only, commit hash for fixed-with-note)
- [ ] Every item's two per-item checkboxes (`Item {N} classified`, `Item {N} actioned`) are ticked
- [ ] Sprint summary generated via `generate_archive_summary`
- [ ] Roadmap updated for any stories this sprint completed
- [ ] `CHANGELOG.md` updated for any user-visible changes landed this sprint
- [ ] All sprint cards archived via `archive_cards`

### Completion Checklist

<!-- gate0: upper-checklist -->

* [ ] All P0 items are complete and verified. <!-- cite: -->
* [ ] All P1 items are complete or have follow-up tickets created. <!-- cite: -->
* [ ] P2 items are complete or explicitly deferred with tickets. <!-- cite: -->
* [ ] All tests are passing (unit, integration, and regression). <!-- cite: -->
* [ ] No new linter warnings or errors introduced. <!-- cite: -->
* [ ] All documentation updates are complete and reviewed. <!-- cite: -->
* [ ] Code changes (if any) are reviewed and merged. <!-- cite: -->
* [ ] Follow-up tickets are created and prioritized for next sprint. <!-- cite: -->
* [ ] Team retrospective includes discussion of cleanup backlog (if significant). <!-- cite: -->

### Note on validation

This card follows a structured template. Keep its sections, checkboxes, and tables and fill them in rather than removing them.
