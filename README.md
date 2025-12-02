# Claude Patent Creator

An MCP server and Claude Code plugin for USPTO patent creation guidance using RAG (Retrieval Augmented Generation) over the Manual of Patent Examining Procedure (MPEP).

## Project Status

**This project is a work in progress and is not fully functional.**

Contributions, issues, and pull requests are welcome. Feel free to explore, experiment, or build upon the code. No guarantees of stability or completeness are provided.

## What It Does

Claude Patent Creator helps with patent application drafting and review by providing:

- **MPEP Search** - Hybrid RAG search across the Manual of Patent Examining Procedure, 35 USC, and 37 CFR regulations
- **Patent Search** - Search 76M+ worldwide patents via Google BigQuery
- **Claims Review** - Automated 35 USC 112(b) compliance checking for claim definiteness
- **Specification Review** - Written description, enablement, and best mode analysis per 35 USC 112(a)
- **Formalities Check** - MPEP 608 compliance (abstract length, title format, drawings)
- **Diagram Generation** - Patent-style technical diagrams using Graphviz
- **Patent Creation Workflow** - Guided process for drafting complete patent applications

## Technology Stack

```
FastMCP (MCP Server Framework)
+- RAG Pipeline: FAISS + BM25 + HyDE + Cross-Encoder Reranking
+- Embeddings: BGE-base-en-v1.5 (768-dim)
+- Reranker: MS-MARCO MiniLM-L-6-v2
+- Patent Search: Google BigQuery (patents-public-data)
+- Validation: Pydantic v2
+- GPU Acceleration: PyTorch CUDA 12.8 (optional)
```

## Installation

### Quick Start (if functional)

```bash
pip install git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git
patent-creator setup
```

### Plugin Installation (Claude Code)

```bash
/plugin marketplace add C:\Users\<YOUR_USER>\Desktop
/plugin install claude-patent-creator-standalone
/setup-patent-system
```

## Requirements

**Minimum:**
- Python 3.9+
- 8GB RAM

**Optional (for full features):**
- NVIDIA GPU with CUDA 12.8 (5-10x faster indexing)
- Google Cloud project with BigQuery access (for patent search)
- Graphviz (for diagram generation)

## Commands

| Command | Description |
|---------|-------------|
| `/create-patent` | Complete patent application drafting workflow |
| `/search-prior-art` | Search 76M+ patents via BigQuery |
| `/review-claims` | 35 USC 112(b) compliance check |
| `/setup-patent-system` | Initial setup and configuration |

## Credits and Attribution

### Open Source Dependencies

This project builds upon the work of many open source projects:

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

## Privacy and Security

- This repository has been checked for common PII patterns and obvious secrets
- Do not commit API keys, OAuth client secrets, private keys, or personal information
- Use environment variables or local `.env` files to store secrets
- If you find any personal information in files, please open an issue

## Trademark and Attribution

- This project uses factual references to USPTO public resources (MPEP, Open Data Portal APIs) for functionality and documentation
- "USPTO" is a registered trademark of the United States Patent and Trademark Office
- This project is not affiliated with, endorsed by, or sponsored by the USPTO

## Security Reporting

If you discover a security issue or accidental leak of secrets/PII:
1. Open an issue on the project's issue tracker marked as `security`
2. For accidentally committed secrets, remove from repo history and rotate immediately

## License

MIT License - See LICENSE file for details.

## Contributing

This project is open to contributions. Since it's a work in progress:
- Expect breaking changes
- Documentation may be incomplete or outdated
- Some features may not work as described
- Issues and PRs are welcome

See CLAUDE.md for development guidance and architecture details.
