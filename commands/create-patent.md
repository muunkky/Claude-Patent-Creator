---
description: Create a complete patent application from invention disclosure through USPTO-ready filing package
allowed-tools: Bash, Read, Write
---

# Create Patent Application

Guides you through creating a complete patent application using the full workflow.

## What This Command Does

Orchestrates the complete patent application creation process:

1. **Prior Art Search** (15-30 min)
2. **Claims Drafting** (30-60 min)
3. **Specification Writing** (60-120 min)
4. **Diagrams Generation** (15-30 min)
5. **Compliance Checking** (15-20 min)
6. **Final Assembly** (10-15 min)

**Total Time**: 2.5-4.5 hours for complete utility patent application

## Process

### Step 1: Gather Invention Information

I'll interview you about your invention:
- What problem does it solve?
- How does it work (high-level)?
- What are the key components or steps?
- What makes it novel/different?
- Are there any working prototypes or examples?

### Step 2: Prior Art Search

I'll use the **Patent Researcher** agent to:
- Conduct systematic 7-step search
- Search BigQuery (76M+ patents)
- Identify top 10 most relevant prior art
- Assess patentability (novelty + obviousness)
- Recommend claim strategy

**Deliverable**: Prior art search report with patentability assessment

### Step 3: Draft Claims

I'll use the **Patent Drafter** agent to:
- Write 1-3 independent claims
- Add 10-20 dependent claims
- Distinguish from prior art
- Check antecedent basis and definiteness
- Validate claim structure

**Deliverable**: Complete claims section (20-25 claims)

### Step 4: Write Specification

I'll use the **Patent Drafter** agent to:
- Create title and abstract
- Write field and background sections
- Draft summary of invention
- Write detailed description with embodiments
- Include examples and advantages
- Verify all claims are supported

**Deliverable**: Complete specification (20-50 pages)

### Step 5: Generate Diagrams

I'll use the **Patent Illustrator** agent to:
- Create flowcharts for method claims
- Generate block diagrams for system claims
- Add patent-style reference numbers (10, 20, 30...)
- Export in USPTO-compatible formats

**Deliverable**: 3-10 patent figures (SVG/PNG/PDF)

### Step 6: Compliance Check

I'll validate the application:
- Run claims analyzer (35 USC 112(b))
- Check specification support (35 USC 112(a))
- Verify formalities (MPEP 608)
- Fix any critical issues found

**Deliverable**: Compliance report + fixes

### Step 7: Assemble Filing Package

I'll create the final package:
- Specification document (with all sections)
- Claims document
- Figures (separate files)
- Abstract
- IDS list (prior art for disclosure)

**Deliverable**: USPTO-ready filing package

## Output Structure

All files will be organized as:

```
patent-application-[date]/
├── 01-research/
│   ├── invention-disclosure.md
│   ├── prior-art-search-report.md
│   ├── top-10-patents.md
│   └── patentability-assessment.md
├── 02-claims/
│   ├── claims-draft.md
│   ├── claims-final.md
│   └── claims-analysis.md
├── 03-specification/
│   ├── title-abstract.md
│   ├── specification-full.md
│   └── specification-analysis.md
├── 04-figures/
│   ├── fig1-system-diagram.svg
│   ├── fig2-method-flowchart.svg
│   ├── fig3-component-detail.svg
│   └── figures-description.md
├── 05-compliance/
│   ├── claims-compliance.md
│   ├── spec-compliance.md
│   └── formalities-check.md
└── 06-filing-package/
    ├── complete-application.pdf
    ├── ids-list.md
    └── filing-checklist.md
```

## Requirements

Before running this command:

1. **MPEP Index Built**:
   - Run `/setup-patent-system` first (one-time)
   - Or manually: `cd ${CLAUDE_PLUGIN_ROOT} && python mcp_server/server.py --rebuild-index`

2. **BigQuery Configured** (for patent search):
   - Google Cloud project created
   - BigQuery API enabled
   - Authenticated: `gcloud auth application-default login`
   - Environment variable: `GOOGLE_CLOUD_PROJECT=your-project-id`

3. **Graphviz Installed** (for diagrams):
   - Windows: `choco install graphviz`
   - Linux: `sudo apt install graphviz`
   - Mac: `brew install graphviz`

## Options

You can customize the process:

**Type of Application**:
- **Provisional**: Lighter requirements, faster (90-120 min)
- **Utility** (default): Full formal requirements (2.5-4 hours)

**Scope**:
- **Quick**: Minimal claims + specification outline
- **Standard** (default): Complete application
- **Comprehensive**: Multiple embodiments + extensive examples

**Prior Art Depth**:
- **Basic**: Keywords only (15 min)
- **Standard** (default): 7-step methodology (30 min)
- **Thorough**: Extended CPC search (60 min)

## Example Usage

```
/create-patent

> I'll guide you through creating a patent application.
>
> What type of application?
> 1. Provisional (faster, lighter requirements)
> 2. Utility (complete, USPTO-ready)
>
> [Select option]
>
> Tell me about your invention...
> [You describe your invention]
>
> [I'll proceed through all 7 steps...]
```

## Tips

- **Prepare in advance**: Have invention description ready
- **Be specific**: More detail = better patent
- **Review drafts**: I'll pause for your review at key points
- **Ask questions**: Any time during the process
- **Save frequently**: Each section saved as we complete it

## What You'll Have at the End

A complete, USPTO-ready patent application package including:
- ✓ Prior art search with top 10 references
- ✓ Patentability assessment
- ✓ 20-25 claims (validated for 112(b))
- ✓ 20-50 page specification (validated for 112(a))
- ✓ 3-10 professional figures with reference numbers
- ✓ Abstract (50-150 words)
- ✓ IDS list for USPTO disclosure
- ✓ Compliance reports (all checks passed)
- ✓ Complete filing package ready to submit

## Next Steps After Command

1. **Review** complete application
2. **Make edits** if needed (I can help)
3. **File provisional** (if applicable)
4. **File utility** application
5. **Respond to office actions** (I can help with that too)
