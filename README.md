# Claude Patent Creator

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![MCP Server](https://img.shields.io/badge/MCP-FastMCP-purple.svg)](https://github.com/jlowin/fastmcp)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.9+-red.svg)](https://pytorch.org/)

USPTO patent creation and analysis system with dual-mode architecture: MCP server for programmatic access + Claude Code plugin with skills, autonomous agents, and slash commands. Features hybrid RAG search (FAISS+BM25+reranking) over MPEP/USC/CFR, BigQuery access to 76M+ patents, automated compliance checking, prior art search, and diagram generation.

## Project Status

**This project is a work in progress and is not fully functional.**

Contributions, issues, and pull requests are welcome. Feel free to explore, experiment, or build upon the code. No guarantees of stability or completeness are provided.

---

## Features

### Dual-Mode Architecture

| Mode | Use Case | Components | Access Method |
|------|----------|------------|---------------|
| **MCP Server** | Programmatic API access | 20 MCP tools | Any MCP client (Claude Code, Claude Desktop, etc.) |
| **Claude Code Plugin** | Interactive workflows | 15 skills + 10 agents + slash commands + hooks | Claude Code IDE |

### Core Capabilities

**Search & Retrieval (20 MCP Tools)**
- **MPEP/USC/CFR Search** - Hybrid RAG (FAISS vector + BM25 lexical + cross-encoder reranking) across 500MB of USPTO regulations
- **Patent Search** - BigQuery access to 76M+ worldwide patents with full-text search and CPC classification
- **USPTO API Integration** - Real-time patent data retrieval and recent filings
- **Prior Art Discovery** - Automated novelty and freedom-to-operate analysis

**Automated Analysis**
- **Claims Review** - 35 USC 112(b) compliance: definiteness, antecedent basis, indefinite terms, claim structure
- **Specification Review** - 35 USC 112(a) adequacy: written description, enablement, best mode
- **Formalities Check** - MPEP 608 compliance: abstract length, title format, drawings, required sections

**Content Generation**
- **Diagram Generator** - Patent-style technical diagrams using Graphviz (block diagrams, flowcharts, system architectures)
- **Patent Creation** - Guided workflow for drafting complete USPTO-ready applications

**Claude Code Plugin Features**
- **15 Skills** - Specialized expertise modules (setup, development, index management, troubleshooting, testing, patent review, search, diagrams, prior art)
- **10 Autonomous Agents** - Long-running workflows (patent-creator, prior-art-searcher, mpep-expert, patent-drafter, etc.)
- **Slash Commands** - Quick-access workflows (`/create-patent`, `/search-prior-art`, `/review-claims`, `/full-review`, etc.)
- **Hooks System** - Custom event-driven automation

---

## Technology Stack

```
Architecture:
  FastMCP (MCP Server Framework)
  +-- 20 MCP Tools (search, analysis, generation)
  +-- Claude Code Plugin (skills, agents, commands, hooks)

RAG Pipeline:
  FAISS Vector Search (BGE-base-en-v1.5, 768-dim embeddings)
  + BM25 Lexical Search (rank-bm25)
  + Cross-Encoder Reranking (MS-MARCO MiniLM-L-6-v2)
  + HyDE Query Expansion (optional, API-based)

Data Sources:
  - MPEP (Manual of Patent Examining Procedure)
  - 35 USC (Patent Statutes)
  - 37 CFR (Patent Regulations)
  - Subsequent Publications (USPTO updates)
  - BigQuery patents-public-data (76M+ patents)

ML Stack:
  PyTorch 2.9+ (CUDA 12.8 for GPU acceleration)
  Sentence Transformers 5.1+
  HuggingFace Transformers 4.57+
  FAISS 1.12+ (CPU/GPU)

Validation & Monitoring:
  Pydantic v2 (type safety + input validation)
  Structured logging (JSON/human formats)
  Performance tracking (@track_performance)
  Health check system
```

---

## Installation

### Option 1: One-Line Install (Recommended)

```bash
# Installs package, detects GPU, downloads MPEP, builds index, registers MCP server
pip install git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git && patent-creator setup

# Restart Claude Code after completion
```

**What happens automatically:**
1. Installs Python package dependencies
2. Detects hardware (NVIDIA GPU/Apple Silicon/CPU)
3. Uninstalls CPU-only PyTorch if GPU detected
4. Installs correct PyTorch (CUDA 12.8/MPS/CPU)
5. Restarts setup with GPU-enabled PyTorch
6. Downloads MPEP PDFs (500MB) from USPTO
7. Builds hybrid index with GPU acceleration
8. Registers MCP server with Claude Code

### Option 2: Manual Installation

```bash
# Clone repository
git clone https://github.com/RobThePCGuy/Claude-Patent-Creator.git
cd Claude-Patent-Creator

# Optional: Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Install package
pip install -e .

# Run setup wizard
patent-creator setup
```

### Option 3: Claude Code Plugin (Standalone Mode)

```bash
# In Claude Code — add the marketplace and install the plugin
/plugin marketplace add RobThePCGuy/Claude-Patent-Creator
/plugin install claude-patent-creator-standalone@claude-patent-creator

# Run setup command
/claude-patent-creator-standalone:setup-patent-system
```

For local development, you can load the plugin directly without installing:

```bash
claude --plugin-dir ./Claude-Patent-Creator
```

---

## Quick Start

### Using MCP Tools

```python
# Search MPEP for claim definiteness requirements
search_mpep("claim definiteness 35 USC 112(b)", top_k=5)

# Search 76M+ patents for prior art
search_patents_bigquery("neural network training", limit=10)

# Analyze claims for compliance
review_patent_claims(claims_text)

# Generate patent diagram
render_diagram("block", components, connections)
```

### Using Claude Code Skills

Skills activate automatically based on your task:

- `"Install the system"` → **setup-assistant** skill
- `"Search for patents about AI"` → **patent-search** skill
- `"Review my claims for compliance"` → **patent-reviewer** skill
- `"Find MPEP section on enablement"` → **mpep-search** skill
- `"Build the index"` → **index-manager** skill
- `"Something is broken"` → **troubleshooting-assistant** skill

### Using Slash Commands

```
/create-patent          # Complete patent creation workflow (55-80 min)
/search-prior-art       # Prior art search with novelty analysis
/review-claims          # Claims-only 35 USC 112(b) analysis
/review-specification   # Specification-only 35 USC 112(a) analysis
/review-formalities     # MPEP 608 formalities check
/full-review            # Parallel review (claims + spec + formalities)
```

### Using Autonomous Agents

```
# Long-running workflows that work independently
"Create a patent for my invention, use the patent-creator agent"
"Conduct prior art search for my invention, use the prior-art-searcher agent"
```

---

## CLI Commands

```bash
# Setup MPEP/USC/CFR sources
patent-creator setup

# Show installation status
patent-creator status

# System health check (alias for status)
patent-creator health

# Verify Claude Code MCP configuration
patent-creator verify-config

# Run the MCP server
patent-creator serve

# Rebuild MPEP index
patent-creator rebuild-index

# Download MPEP PDFs only
patent-creator download-mpep

# Download all sources (MPEP + 35 USC + 37 CFR)
patent-creator download-all

# Check BigQuery connection
patent-creator check-bigquery

# Download PatentsView corpus (9.2M+ patents)
patent-creator download-patents

# Build or rebuild patent search index
patent-creator build-patent-index

# Show patent corpus status
patent-creator patents-status
```

---

## Requirements

### Minimum
- **Python:** 3.9 - 3.13 (3.14 experimental)
- **RAM:** 8GB
- **Disk:** 2GB (MPEP PDFs + index)

### Optional (Recommended)
- **GPU:** NVIDIA GPU with CUDA 12.8 (5-10x faster indexing and search)
- **Google Cloud:** Project with BigQuery enabled (for patent search)
- **Graphviz:** System package (for diagram generation)

### Python Dependencies
- `mcp>=1.21.0` - MCP server framework
- `sentence-transformers>=5.1.2` - Embeddings
- `faiss-cpu>=1.12.0` - Vector search
- `numpy>=1.26.0,<2.0.0` - Array operations (CRITICAL: <2.0 for FAISS compatibility)
- `rank-bm25>=0.2.2` - Lexical search
- `google-cloud-bigquery>=3.38.0` - Patent search
- `pydantic>=2.10.0` - Validation
- `graphviz>=0.21` - Diagram generation
- `PyMuPDF>=1.26.0` - PDF processing

See `pyproject.toml` for complete dependency list.

---

## MCP Tools Reference

### MPEP Search Tools (2)
- `search_mpep` - Hybrid RAG search with filters
- `get_mpep_section` - Retrieve full section content

### Patent Search Tools (7)
- `check_bigquery_status` - Verify BigQuery configuration
- `search_patents_bigquery` - Search 76M+ patents
- `get_patent_bigquery` - Get full patent details
- `search_patents_by_cpc_bigquery` - Search by CPC classification
- `search_uspto_api` - USPTO API search
- `get_uspto_patent` - Get USPTO patent details
- `get_recent_uspto_patents` - Recent filings

### Analysis Tools (3)
- `review_patent_claims` - 35 USC 112(b) compliance
- `review_specification` - 35 USC 112(a) adequacy
- `check_formalities` - MPEP 608 compliance

### Diagram Tools (2)
- `render_diagram` - Generate patent diagrams
- `get_diagram_templates` - List available templates

### Prior Art Tools (1)
- `search_prior_art` - Automated prior art discovery

### System Tools (5)
- `get_index_stats` - Index statistics
- `check_diagram_tools_status` - Graphviz status
- `check_patent_corpus_status` - Corpus availability
- `check_uspto_api_status` - API connectivity
- `get_patent_details` - Combined patent retrieval

---

## Configuration

### Environment Variables

Create `.env` file in the project root:

```bash
# Required for BigQuery patent search
GOOGLE_CLOUD_PROJECT=your-project-id

# Optional API keys (for HyDE query expansion)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Optional settings
PATENT_LOG_LEVEL=INFO              # Logging verbosity
PATENT_LOG_FORMAT=human            # Log format (json/human)
PATENT_ENABLE_METRICS=true         # Performance tracking
PATENT_MPEP_USE_HYDE=false         # HyDE query expansion
PATENT_MPEP_DEVICE=gpu             # Device (gpu/cpu)
PATENT_OPERATION_TIMEOUT=300       # Timeout (seconds)

# Windows only (for Git Bash)
CLAUDE_CODE_GIT_BASH_PATH=C:\dev\Git\bin\bash.exe
```

### BigQuery Setup (Optional)

```bash
# 1. Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# 2. Authenticate
gcloud auth application-default login

# 3. Set the quota project (Replace with your project ID)
gcloud auth application-default set-quota-project your-project-id

# 4. Set the project environment variable
# Windows:
$env:GOOGLE_CLOUD_PROJECT="your-project-id"
# Linux/macOS:
export GOOGLE_CLOUD_PROJECT="your-project-id"

# 5. Test connection
patent-creator check-bigquery
```

---

## Skills System

Claude automatically activates specialized skills based on your task:

| Skill | Triggers | What It Does |
|-------|----------|--------------|
| **setup-assistant** | Installation, configuration, authentication | Complete setup lifecycle |
| **development-assistant** | Adding features, creating tools | Feature development workflows |
| **index-manager** | Building, rebuilding, optimizing index | MPEP index management |
| **troubleshooting-assistant** | Errors, performance issues | 6-step diagnostic methodology |
| **testing-assistant** | Running tests, validation | Test suite execution |
| **patent-reviewer** | Reviewing applications for compliance | Expert review with compliance checking |
| **patent-search** | Searching patents, prior art | BigQuery + PatentsView search |
| **mpep-search** | Finding MPEP sections, regulations | Hybrid RAG search |
| **patent-diagrams** | Creating technical diagrams | Graphviz diagram generation |
| **prior-art-search** | Novelty/FTO analysis | Prior art discovery workflows |

Each skill includes comprehensive reference documentation in `skills/[skill-name]/reference/`.

---

## Autonomous Agents

For long-running workflows requiring uninterrupted focus:

| Agent | Use Case | Duration | Output |
|-------|----------|----------|--------|
| **patent-creator** | Create complete USPTO-ready application | 55-80 min | Specification, claims, abstract, diagrams, validation report |
| **prior-art-searcher** | Comprehensive prior art search | 15-30 min | Patentability report, top 10 prior art, claim strategy, IDS list |

**Usage:**
```
"Create a patent for [invention], use the patent-creator agent"
"Search prior art for [invention], use the prior-art-searcher agent"
```

Agents work independently while you continue other tasks.

---

## Plugin Installation

This project is available as a Claude Code plugin from the GitHub marketplace:

```
/plugin marketplace add RobThePCGuy/Claude-Patent-Creator
/plugin install claude-patent-creator-standalone@claude-patent-creator
```

Once installed, all skills are namespaced under `claude-patent-creator-standalone:` (e.g., `/claude-patent-creator-standalone:create-patent`).

To submit to the official Anthropic marketplace, visit [claude.ai/settings/plugins/submit](https://claude.ai/settings/plugins/submit) or [platform.claude.com/plugins/submit](https://platform.claude.com/plugins/submit).

---

## Architecture

```
claude-patent-creator/
├── .claude-plugin/          # Plugin marketplace + manifest
│   ├── plugin.json          # Plugin identity and component paths
│   └── marketplace.json     # Marketplace catalog for distribution
├── mcp_server/              # MCP server core
│   ├── server.py            # FastMCP entry point
│   ├── mpep_search.py       # Hybrid RAG search engine
│   ├── bigquery_search.py   # BigQuery patent search
│   ├── claims_analyzer.py   # 35 USC 112(b) analyzer
│   ├── specification_analyzer.py  # 112(a) analyzer
│   ├── formalities_checker.py     # MPEP 608 checker
│   ├── diagram_generator.py       # Graphviz diagrams
│   ├── tools/               # MCP tool definitions
│   │   ├── mpep_tools.py
│   │   ├── analyzer_tools.py
│   │   ├── bigquery_tools.py
│   │   ├── uspto_search_tools.py
│   │   ├── diagram_tools.py
│   │   ├── prior_art_tools.py
│   │   └── system_tools.py
│   └── index/               # FAISS + BM25 index (git-ignored)
├── skills/                  # Claude Code skills (15)
│   ├── setup-assistant/
│   ├── patent-reviewer/
│   ├── patent-search/
│   └── ...
├── agents/                  # Autonomous agents (10)
│   ├── patent-creator.md
│   ├── prior-art-searcher.md
│   └── ...
├── commands/                # Slash commands
│   ├── create-patent.md
│   ├── search-prior-art.md
│   └── ...
├── hooks/                   # Event-driven automation
├── scripts/                 # Testing and utilities
├── pdfs/                    # MPEP PDFs (git-ignored)
└── CLAUDE.md                # Project documentation
```

---

## Performance

### Index Build Times
- **CPU-only:** 25-35 minutes (MPEP + 35 USC + 37 CFR)
- **GPU (CUDA):** 3-5 minutes (5-10x faster)
- **GPU (Apple Silicon MPS):** 8-12 minutes (2-3x faster)

### Search Performance
- **MPEP Search:** 50-200ms (hybrid FAISS + BM25)
- **BigQuery Search:** 1-3 seconds (76M+ patents)
- **USPTO API:** 500ms - 2s (rate-limited)

### Resource Usage
- **Index Size:** 500MB - 1GB (FAISS + BM25)
- **RAM Usage:** 2-4GB (loaded index)
- **GPU VRAM:** 1-2GB (optional acceleration)

---

## Known Issues & Limitations

### Critical Compatibility Issues

1. **NumPy 2.x Incompatibility** - `faiss-cpu 1.12.0` is NOT compatible with `numpy>=2.0`. Pin to `numpy<2.0`.
2. **PyTorch Installation Order** - Install PyTorch BEFORE `sentence-transformers` to avoid CPU-only installation.
3. **Windows Path Handling** - Use forward slashes in MCP config paths.
4. **Git Bash Required** - Windows users need Git Bash for `claude mcp add` command.

See `CLAUDE.md` for complete troubleshooting guide.

### Current Limitations

- Project is work-in-progress, not all features fully functional
- BigQuery requires Google Cloud project with billing enabled
- GPU acceleration requires NVIDIA GPU with CUDA 12.8 (Linux/Windows) or Apple Silicon (macOS)
- Some diagram types require system Graphviz installation
- HyDE query expansion requires API keys (Anthropic/OpenAI)

---

## Credits and Attribution

### Open Source Dependencies

This project builds upon excellent open source work:

- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server framework
- [FAISS](https://github.com/facebookresearch/faiss) - Vector similarity search (Meta AI Research)
- [Sentence Transformers](https://www.sbert.net/) - Text embeddings (UKP Lab, TU Darmstadt)
- [HuggingFace Transformers](https://huggingface.co/transformers/) - ML models
- [PyTorch](https://pytorch.org/) - ML framework
- [rank-bm25](https://github.com/dorianbrown/rank-bm25) - BM25 lexical search
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing
- [Graphviz](https://graphviz.org/) - Diagram generation
- [Pydantic](https://docs.pydantic.dev/) - Data validation
- [Google Cloud BigQuery](https://cloud.google.com/bigquery) - Patent database access

### Data Sources

- **MPEP** - Manual of Patent Examining Procedure, published by the USPTO
- **35 USC** - United States Code Title 35 (Patents)
- **37 CFR** - Code of Federal Regulations Title 37 (Patents, Trademarks, and Copyrights)
- **patents-public-data** - Google BigQuery public dataset containing 76M+ patents

### Embedding Models

- **BGE-base-en-v1.5** by BAAI (Beijing Academy of Artificial Intelligence)
- **MS-MARCO MiniLM-L-6-v2** cross-encoder by Microsoft

---

## Privacy and Security

- This repository has been checked for common PII patterns and obvious secrets
- Do not commit API keys, OAuth client secrets, private keys, or personal information
- Use environment variables or local `.env` files to store secrets
- If you find any personal information in files, please open an issue

### Security Reporting

If you discover a security issue or accidental leak of secrets/PII:

1. Open an issue on the project's issue tracker marked as `security`
2. For accidentally committed secrets, remove from repo history and rotate immediately

---

## Trademark and Attribution

- This project uses factual references to USPTO public resources (MPEP, Open Data Portal APIs) for functionality and documentation
- "USPTO" is a registered trademark of the United States Patent and Trademark Office
- This project is not affiliated with, endorsed by, or sponsored by the USPTO

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Contributing

This project is open to contributions. Since it's a work in progress:

- Expect breaking changes
- Documentation may be incomplete or outdated
- Some features may not work as described
- Issues and PRs are welcome

### Development Guide

See [CLAUDE.md](CLAUDE.md) for:
- Complete architecture documentation
- Development workflows and patterns
- Skills and agents reference
- Testing procedures
- Troubleshooting guides
- Version compatibility matrix

---

## Support

- **Issues:** [GitHub Issues](https://github.com/RobThePCGuy/Claude-Patent-Creator/issues)
- **Documentation:** [CLAUDE.md](CLAUDE.md)
- **Examples:** See `skills/` and `agents/` directories

---

## Roadmap

- [ ] Complete implementation of all MCP tools
- [ ] Add evaluation metrics for RAG performance
- [ ] Support for international patent offices (EPO, WIPO)
- [ ] Web interface for non-Claude Code users
- [ ] Advanced claim dependency graph visualization
- [ ] Automated obviousness analysis (35 USC 103)
- [ ] Patent portfolio analysis tools
- [ ] Integration with patent drafting software

---

**Built with Claude Code** - This project demonstrates the full capabilities of the Claude Code plugin system, including skills, autonomous agents, slash commands, and MCP server integration.
