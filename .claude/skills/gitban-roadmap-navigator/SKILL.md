---
name: gitban-roadmap-navigator
description: >
  This skill is used to interface with the gitban roadmap, a node tree that is accessible via the gitban mcp roadmap tools: read_roadmap, search_roadmap, upsert_roadmap, and delete_from_roadmap. Use this skill for any non-trivial task that interfaces with roadmap. Don't waste tokens by using it for single updates, simple searches, etc.
  
  explore the project roadmap, find specific projects or features, check milestone status,
  update roadmap items, or plan work from roadmap content. Also use it to build, generate, or enrich
  a roadmap from a corpus of documentation — turning a directory of PRDs, ADRs, design docs, READMEs,
  and specs into a structured, reviewable draft roadmap with docs_ref links. Trigger for any mention
  of "roadmap", "build/generate/enrich a roadmap from docs", milestone planning, project tracking,
  story status, or when the user wants to understand what's planned, in progress, or completed at a
  strategic level. Also use when creating sprint cards from roadmap features, or when updating roadmap
  status after completing work.
---

## What is the Gitban roadmap?
The gitban roadmap is a node tree with metadata fields on each node. It's a flexible / liquid structure used to organize future, current, and historical work by capturing helpful context that makes it easy to collaborate and guide development over the long term. The nodes and their metadata fields are the place to hang documents, concepts, ideas, dependencies, stubs, etc. to help inform the gitban sprints and cards when it's time to make them. The gitban nodes also provide a place to hang relevant cards and sprints once they are made.

## Key use cases:
  * **Capture a plan on the roadmap:** this means that the content of a document or task list (PRD, scratchpad, github issues, design doc, etc.) can be used to build, enrich, or reorganize the roadmap tree. Use your understanding of the roadmap schema to mine the document for improvements to the roadmap organization, create new nodes, rearrange nodes, assign dependencies, and enrich the metadata of the relevant nodes.
  * **Update the roadmap:** this means some work was done that probably isn't reflected in the node tree. After the fact enrichment of the roadmap is a great way to give the team detailed context about your work so they can find what they need in order to understand it. This usually involves reviewing the current or recent PRs and recognizing where the structure, detail and fidelity of the roadmap can be improved to reflect the work.
  * **What should I build next?** If the roadmap is up to date, it's a great place to pick up the next thing to work on. There is no enforced review or gating process, teams are free to implement their own, if any.
  * **Plan a card or sprint:** Designing a sprint or creating a gitban card is easier when all of the relevant documentation and context has been hung on the right node by the team in advance. Gather information from the node or branch using the search and list tools while architecting a sprint and then hang the card id or sprint tag on the node so that it is easier to find than scanning the entire gitban board.

##  Principles
* **Liquid roadmap:** The schema of the roadmap records, but does not enforce dependencies. Dependencies can be cross-referenced anywhere in the tree and sequencing is optional. It is a good record of work done, but not a replacement for an immutable changelog. It is a tool for developers to be helpful to themselves and others while they work. Since the roadmap source files are included in the git commits, they can be reviewed as part of the PR review process to keep teams informed and get approval for major changes like node rearrangements.
* **Extensible schema:** The schema has a lot of predefined metadata attributes but won't block custom fields. It shouldn't be necessary for general development, but if there is something that only makes sense to your domain that should be added, the system supports that.

## Hierarchy

```
milestones (m1, m2, ...)
  └─ stories (s1, s2, ...)
      └─ projects (kebab-case IDs)
          └─ features (kebab-case IDs)
```
## Naming conventions

* Milestones: A clear product-level objective. Like a specific release, a new product surface, a major initiative, etc.
* Stories: Plain english description of capabilities. "A user can create an account in a secure and compliant way.", "The latency of the slowest 3 endpoints is brought within SLA".
* Projects: A development initiative for a feature set, surface, etc. "Neumorphic search bar", "Latency audit", "Add objects Y from source X to the pipeline ingestion connector".
* Features: a focused feature or task. "lookahead autocomplete", "responsive search window", "clickable chips", "SLA documentation review", etc. 

Each level has a status: `todo`, `in_progress`, or `done`. These need to be manually updated as parent nodes are not automatically set based on the progress of children.

# Syntax Reference

## Metadata Fields

| Level | Field | Type/Format | Description |
|-------|-------|-------------|-------------|
| **Root** | `schema_version` | string | Version of the roadmap schema |
| | `document_version` | string | Version of this roadmap document |
| | `last_updated` | YYYY-MM-DD | Date of last update |
| | `metadata` | object | Object containing `maintained_by`, `review_frequency`, `related_docs`, `tools` |
| | `milestones` | object | Container for all milestone nodes |
| **Milestone** | `id` | string | Unique identifier (e.g., m1, m2) |
| | `title` | string | Human-readable milestone name |
| | `description` | string | What this milestone achieves |
| | `status` | enum | `todo`, `in_progress`, `verifying`, or `done` |
| | `stories` | object | Container for story nodes |
| | `docs_ref` | string | Path to primary reference document |
| | `start_date` | YYYY-MM-DD | When work began |
| | `target_completion` | YYYY-MM-DD | Target completion date |
| | `sprints_ref` | string | Back-reference to related sprint tags |
| | `cards_ref` | string | Back-reference to related card IDs |
| **Story** | `id` | string | Unique identifier (e.g., s1, s2) |
| | `title` | string | Outcome-focused statement of what's true when done |
| | `description` | string | Detailed explanation of the objective |
| | `status` | enum | `todo`, `in_progress`, `verifying`, or `done` |
| | `success_criteria` | array[string] | Array of measurable outcome statements |
| | `projects` | object | Container for project nodes |
| | `docs_ref` | string | Path to PRD or primary reference |
| | `due_date` | YYYY-MM-DD | Target completion date |
| | `depends_on` | array[string] | Array of story IDs this depends on |
| | `sprints_ref` | string | Back-reference to related sprint tags |
| | `cards_ref` | string | Back-reference to related card IDs |
| **Project** | `id` | string (kebab-case) | Unique identifier |
| | `title` | string | Human-readable project name |
| | `description` | string | What this project delivers |
| | `status` | enum | `todo`, `in_progress`, `verifying`, or `done` |
| | `features` | object | Container for feature nodes |
| | `docs_ref` | string | Path to ADR or design document |
| | `sprints_ref` | string | Back-reference to related sprint tags |
| | `cards_ref` | string | Back-reference to related card IDs |
| **Feature** | `id` | string (kebab-case) | Unique identifier |
| | `title` | string | Human-readable feature name |
| | `description` | string | What this feature does |
| | `sequence` | integer | Execution order within the project |
| | `status` | enum | `todo`, `in_progress`, `verifying`, or `done` |
| | `owner` | string | Team or individual responsible |
| | `tdd_spec` | string | Test-driven spec (Given/When/Then format) |
| | `docs_ref` | string | Path to design document |
| | `depends_on` | array[string] | Array of feature IDs this depends on |
| | `sprints_ref` | string | Back-reference to related sprint tags |
| | `cards_ref` | string | Back-reference to related card IDs |

**Common optional fields (every node level — milestone, story, project, feature):** `sequence` (int, ordering within the parent), `priority` (string), `notes` (free-form string), `actual_completion_date` (`YYYY-MM-DD`, set when the node reached `done`).

## Roadmap Tools Reference

### `read_roadmap`

The single roadmap read surface — there is no separate `list_roadmap`. `read_roadmap`
is **bounded by design**: it returns the addressed node's own fields plus **one level**
of its children (never a recursive dump), and the children are paginated. To explore the
tree, drill down a level at a time; to size a node first, look at `node_counts`.

Every call returns the same envelope, `{node, children, node_counts, pagination}`:

* `node` — the addressed node's own scalar fields (`description`, `status`, `docs_ref`,
  …). Child collections are *not* inlined. For `path=None` this is the document envelope
  (`schema_version`, `document_version`, `metadata`).
* `children` — the bounded one-level list of child nodes, each projected by `fields`.
  `path=None` → milestones; `path="m1"` → m1's stories; `path="m1/s1"` → projects;
  `path="m1/s1/proj"` → features. A feature is a leaf: its `children` is empty.
* `node_counts` — `{children, total_descendants}` for the addressed node.
* `pagination` — `{total, offset, limit, returned, has_more, next_offset}` for the
  `children` list. Pagination is enforced; there is no unbounded opt-out. Loop with
  `offset = next_offset` while `has_more` is true.

`fields` selects what each child item carries:

* `fields=None` (default) → **all** of each child's own metadata.
* `fields=[...]` → only those fields that are present, plus the anchors `id`/`title`.
  An unknown field name is silently omitted (never an error).

| Call | Returns |
|------|---------|
| `read_roadmap()` | Document envelope under `node`; all milestones as `children` |
| `read_roadmap(path="m1")` | m1's own fields under `node`; its stories as `children` |
| `read_roadmap(path="m1/s2")` | s2's fields; its projects as `children` |
| `read_roadmap(path="m1/s2/some-project")` | the project's fields; its features as `children` |
| `read_roadmap(path="m1/s1/some-project/some-feature")` | the feature's own fields under `node`; empty `children` |
| `read_roadmap(path="m1/s1", fields=["description"])` | stories projected to `description` + anchors |
| `read_roadmap(path="m1/s1/infra-core", fields=["tdd_spec", "owner"])` | features projected to those fields + anchors |
| `read_roadmap(path="m1", limit=50, offset=50)` | the next page of m1's stories |

### `search_roadmap`

Searches across all roadmap content (every node, including completed `status: done`
milestones — there is no visibility flag). Each match carries a breadcrumb, a snippet,
and the matched node's metadata. By default each match returns the node's **full**
metadata; pass `fields=[...]` to narrow the per-match payload (same semantics as
`read_roadmap`: anchors `id`/`title` always come back, unknown fields are silently dropped).

| Call | Returns |
|------|---------|
| `search_roadmap(query="terraform")` | All nodes containing "terraform", each with full metadata |
| `search_roadmap(query="oauth")` | All nodes containing "oauth" |
| `search_roadmap(query="in_progress")` | All nodes with in_progress status |
| `search_roadmap(query="terraform", fields=["status"])` | Matches projected to `status` + `id`/`title` anchors |

### `upsert_roadmap`

Creates or updates a node. Partial updates preserve existing fields.

| Call | Effect |
|------|--------|
| `upsert_roadmap({"status": "done"}, path="m1/s1/proj/feature")` | Update status only |
| `upsert_roadmap({"id": "new-proj", "title": "New Project", "description": "...", "status": "todo", "features": {}}, path="m1/s1/new-proj")` | Create new project |
| `upsert_roadmap({"docs_ref": "docs/adr/decision.md"}, path="m1/s1/proj")` | Add document reference |
| `upsert_roadmap({"depends_on": ["other-feature"]}, path="m1/s1/proj/feature")` | Add dependency |

### `delete_from_roadmap`

Removes a node and all descendants. Always preview with `dry_run` first.

| Call | Effect |
|------|--------|
| `delete_from_roadmap(path="m1/s1/old-project", dry_run=True)` | Preview deletion cascade |
| `delete_from_roadmap(path="m1/s1/old-project", confirm=True)` | Execute deletion |
| `delete_from_roadmap(path="m1/s1/proj/stale-feature", dry_run=True)` | Preview feature deletion |
| `delete_from_roadmap(path="m1/s1/proj/stale-feature", confirm=True)` | Execute feature deletion |


## Navigation Patterns

### Drilling Down

Start broad, narrow progressively. Each step returns one bounded level of children and
gives you the IDs you need for the next.

```
read_roadmap()                          → see milestones
read_roadmap(path="m1")                 → see stories in v1
read_roadmap(path="m1/s2")             → see projects in m2
read_roadmap(path="m1/s2/some-project") → see features in a project
```
**Example output** (`read_roadmap(path="m1/s2/some-project")`):

```json
{
  "node": {
    "id": "some-project",
    "title": "Some Project",
    "status": "in_progress"
  },
  "children": [
    {
      "id": "terraform-setup",
      "title": "Terraform Setup",
      "status": "in_progress",
      "sequence": 1
    },
    {
      "id": "ci-pipeline",
      "title": "CI Pipeline Configuration",
      "status": "todo",
      "sequence": 2
    }
  ],
  "node_counts": {"children": 2, "total_descendants": 2},
  "pagination": {"total": 2, "offset": 0, "limit": 50, "returned": 2, "has_more": false, "next_offset": null}
}
```

### Searching (when you know a keyword)

```
search_roadmap(query="terraform")
```
Each match carries `level`, `id`, a `breadcrumb` showing where it lives in the hierarchy,
the `matched_in` field, a `snippet`, and — by default — the matched node's full metadata:

```json
{
  "matches": [
    {
      "id": "terraform-setup",
      "title": "Terraform Setup",
      "description": "deploy infrastructure using terraform modules",
      "status": "in_progress",
      "owner": "platform-team",
      "level": "feature",
      "breadcrumb": "m1/s2/infra-core/terraform-setup",
      "matched_in": "description",
      "snippet": "...deploy infrastructure using terraform modules..."
    },
    {
      "id": "terraform-state",
      "title": "Terraform State Management",
      "description": "configure remote terraform state backend",
      "status": "todo",
      "level": "feature",
      "breadcrumb": "m1/s3/devops-automation/terraform-state",
      "matched_in": "description",
      "snippet": "...configure remote terraform state backend..."
    }
  ],
  "total_matches": 2
}
```
The `breadcrumb` shows where each match lives in the hierarchy, so you can jump straight to
the right node with `read_roadmap(path=...)`. Because each match already carries the node's
full metadata, you usually don't need that follow-up read at all. To trim the payload to
just the fields you care about, pass `fields=[...]`:

```
search_roadmap(query="terraform", fields=["status"])
```

```json
{
  "matches": [
    {
      "id": "terraform-setup",
      "title": "Terraform Setup",
      "status": "in_progress",
      "level": "feature",
      "breadcrumb": "m1/s2/infra-core/terraform-setup",
      "matched_in": "description",
      "snippet": "...deploy infrastructure using terraform modules..."
    }
  ],
  "total_matches": 1
}
```

### Selective Field Loading

Project each child down to only the fields you need with `fields=[...]` — anchors
`id`/`title` always come back, and unknown field names are silently dropped. Pass
`fields=None` (the default) to get all of each child's metadata.

```
read_roadmap(path="m1/s1", fields=["description"])
read_roadmap(path="m1/s1/infra-core", fields=["tdd_spec", "owner"])
```

**Example output with `fields=["tdd_spec", "owner"]`:**

```json
{
  "node": {"id": "infra-core", "title": "Infra Core", "status": "in_progress"},
  "children": [
    {
      "id": "terraform-setup",
      "title": "Terraform Setup",
      "owner": "platform-team",
      "tdd_spec": "Given valid AWS credentials, when terraform apply runs, then VPC and subnets are created"
    },
    {
      "id": "ci-pipeline",
      "title": "CI Pipeline Configuration"
    }
  ],
  "node_counts": {"children": 2, "total_descendants": 2},
  "pagination": {"total": 2, "offset": 0, "limit": 50, "returned": 2, "has_more": false, "next_offset": null}
}
```

A requested field that the node doesn't carry is simply omitted from that child (here
`ci-pipeline` has no `owner`/`tdd_spec`, so neither key appears). The anchors `id` and
`title` are always present regardless of `fields`.

### Paginated Reading

`read_roadmap` always paginates the `children` list — there is no unbounded mode. The
`pagination` envelope tells you when to stop; loop until `has_more` is false:

```
page = read_roadmap(path="m1", limit=50)              # first page of m1's stories
# while page["pagination"]["has_more"]:
read_roadmap(path="m1", limit=50, offset=50)          # next page (offset = next_offset)
```

Use `node_counts.total_descendants` to decide whether to drill in at all before you
start paging.

## Common Tasks

### "What's the current status?"

```
read_roadmap(path="m1", fields=["status"])
read_roadmap(path="m1/s1", fields=["status", "priority"])
```

**Example** (`read_roadmap(path="m1", fields=["status"])`):

```json
{
  "node": {"id": "m1", "title": "Initial Release", "status": "in_progress"},
  "children": [
    {"id": "s1", "title": "Frictionless agent onboarding", "status": "in_progress"},
    {"id": "s2", "title": "Multi-transport support", "status": "todo"}
  ],
  "node_counts": {"children": 2, "total_descendants": 18},
  "pagination": {"total": 2, "offset": 0, "limit": 50, "returned": 2, "has_more": false, "next_offset": null}
}
```

```
read_roadmap(path="m1/s1", fields=["status", "priority"])
```

```json
{
  "node": {"id": "s1", "title": "Frictionless agent onboarding", "status": "in_progress"},
  "children": [
    {"id": "credential-storage", "title": "Credential storage", "status": "in_progress", "priority": "high"},
    {"id": "transport-negotiation", "title": "Transport negotiation", "status": "todo", "priority": "medium"}
  ],
  "node_counts": {"children": 2, "total_descendants": 9},
  "pagination": {"total": 2, "offset": 0, "limit": 50, "returned": 2, "has_more": false, "next_offset": null}
}
```

Look at `node_counts.total_descendants` to gauge size before drilling deeper.
### "What's in progress right now?"

```
search_roadmap(query="in_progress")   → find all nodes with in_progress status
read_roadmap(path="m1")               → then drill into specific areas
read_roadmap(path="m1/s2")            → narrow to projects within a story
```

Filter results by status yourself — the tools return all items at the requested level.

### "Find everything related to X"

```
search_roadmap(query="X")
```

Then drill into specific matches with `read_roadmap(path=...)`.

### "Update a feature status"

```
upsert_roadmap({"status": "done"}, path="m1/s1/infra-core/terraform-setup")
```

Partial updates — only the fields you provide are changed. Everything else is preserved.

### "Add a new project or feature"

Read `roadmap://schema` (MCP resource) if you need to confirm required fields. Then:

```
upsert_roadmap({
  "id": "new-project",
  "title": "New Project Title",
  "description": "What it does and why",
  "status": "todo",
  "features": {}
}, path="m1/s2/new-project")
```

### "Delete something from the roadmap"

Preview first with dry_run, then confirm:

```
delete_from_roadmap(path="m1/s1/old-project", dry_run=True)   → see cascade
delete_from_roadmap(path="m1/s1/old-project", confirm=True)    → execute
```

### "Create sprint cards from roadmap features"

1. `read_roadmap(path="m1/s2/target-project")` — get the feature list (children)
2. `read_roadmap(path="m1/s2/target-project/specific-feature")` — get tdd_spec and details
3. Create gitban cards using the node ID in the sprint tag
4. The roadmap informs cards (by path); cards may reference the roadmap for context; and the roadmap may optionally back-reference cards/sprints via the `sprints_ref` and `cards_ref` metadata fields on the relevant node

## Roadmap and Documents

Any document can be hung on the docs_ref attribute. For reference, the gitban-native documents are PRD → story, ADR → project, design doc → feature.

- **Match content shape, not doc type.** The mapping table is a default, not a law. A narrowly-scoped ADR may belong on a feature; a tightly-scoped PRD may be a single project; a sprawling PRD may seed a whole milestone. Let the document's *scope* override its type when they disagree, and note why in the ledger.
- **Push detail down, not up.** When unsure whether something is a project or a feature, prefer the lower level. Promoting a feature to a project in review is cheap; discovering a "project" was really three is not.
- **Assume parent node fan-out.** One PRD with three delivery phases may seed three projects; one design doc may describe two features. Reference the document in the docs_ref of the parent node of the covered branch.

**Messy trees are allowed.** Real corpora are lumpy: a story with no PRD, an ADR with no design doc, three docs describing one project. Do not invent a missing parent just to make the hierarchy symmetric.

**Use stubs as placeholders.** A good way to handle a documented gap is to create a stub with the reasoning for its existance and hang it on the node. This will give the sprint architect a heads-up that there may be additional documentation that could be helpful before building the sprint.

## Upsert — bulk-write mechanics

`upsert_roadmap` works **one node at a time** — there is no bulk import, and `roadmap.yaml` is never wholesale-overwritten; each upsert is a surgical partial write. A child upsert needs its parent path to already exist, so write top-down: milestone, stories, projects, features.

1. **Validate shape first.** Read `roadmap://schema` and confirm required fields per level — milestone (`id, title, description, status, stories`), story (`id, title, description, status, success_criteria, projects`), project (`id, title, description, status, features`), feature (`id, title, description, sequence, status`). A failed upsert mid-build leaves a partial hierarchy.
2. **Create parents with an empty children map** (`"stories": {}`, `"projects": {}`, `"features": {}`); each child upsert fills it in by path.
3. **Verify between levels** with `read_roadmap(path=...)` before writing children — a child upsert to a missing parent fails.

## Anti-patterns
- **Story as work-list.** "Add HTTP transport, wire auth, ship docs" is three features wearing a story's title. Run the work-list test.
- **Invented specs.** A `tdd_spec` or `success_criteria` that reads well but appears in no source. Empty beats fabricated.


## Rules

- **Roadmap is strategic, Gitban is tactical.** The roadmap provides the context for which gitban sprints and cards should be dispatched and provides a place to organize and capture metadata that is helpful for the sprint-architect.
- **Stories are objectives, not work lists.** A story states what's true when done ("any agent can connect regardless of transport"), not what changes ("add HTTP transport"). Projects describe the path to the outcome. Design happens during development, not in the roadmap.
- **Update roadmap status at story boundaries**, not after every card. Mark a project done when all its features are done. Mark a story done when all projects are done.
- **Use `node_counts` to gauge depth.** If a milestone shows `total_descendants: 66`, don't read the whole milestone — drill into specific stories or projects.
- **Link documents via `docs_ref`.** Every level supports an optional `docs_ref` field pointing to the node's primary reference document. When creating or updating roadmap items that have associated docs, set this field. This is how the roadmap connects to its static documentation — the roadmap stays lean (titles, statuses, sequencing) while `docs_ref` points to the depth.
- **Link gitban cards and sprints via `sprints_ref` and `cards_ref`.** Capture sprints and cards that have already been created to the right node to track it and avoid duplication.


## MCP Resources (read-only context)

These are available via MCP resource reads if you need reference material:

- **Compact schema reference (current: `schema_version: 3.1.0`)**

```yaml
# Root required:
schema_version: string
document_version: string
last_updated: YYYY-MM-DD
metadata:
  maintained_by: string
  review_frequency: string
  related_docs: [string]
  tools:
    roadmap_tracking: string
    task_tracking: string
    Gitban_mcp: uri
milestones:                     # keys: m1, m2, ...
  mN:
    id: string                  # required
    title: string               # required
    description: string         # required
    status: todo|in_progress|verifying|done   # required
    docs_ref: string            # optional
    sprints_ref: string         # optional (back-ref to sprint tags)
    cards_ref: string           # optional (back-ref to card IDs)
    start_date: YYYY-MM-DD      # optional
    target_completion: YYYY-MM-DD # optional
    stories:                    # required, keys: s1, s2, ...
      sN:
        id: string              # required
        title: string           # required
        description: string     # required
        status: todo|in_progress|verifying|done # required
        success_criteria: [string] # required
        docs_ref: string        # optional
        sprints_ref: string     # optional
        cards_ref: string       # optional
        due_date: YYYY-MM-DD    # optional
        depends_on: [string]    # optional
        projects:               # required, kebab-case keys
          some-project:
            id: string          # required
            title: string       # required
            description: string # required
            status: todo|in_progress|verifying|done # required
            docs_ref: string    # optional
            sprints_ref: string # optional
            cards_ref: string   # optional
            features:           # required, kebab-case keys
              some-feature:
                id: string      # required
                title: string   # required
                description: string # required
                sequence: int   # required
                status: todo|in_progress|verifying|done # required
                owner: string   # optional
                tdd_spec: string # optional
                docs_ref: string # optional
                sprints_ref: string # optional
                cards_ref: string # optional
                depends_on: [string] # optional
```

- `.gitban/roadmap/roadmap_schema.json` — canonical schema file
- `roadmap://schema` — JSON schema with required fields per level
- `roadmap://usage-guide` — comprehensive usage documentation
- `roadmap://current` — raw YAML (caution: can be very large, prefer tools)
