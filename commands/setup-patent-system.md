---
description: One-time setup for the patent creator system - downloads MPEP, builds search index, configures BigQuery
allowed-tools: Bash, Read, Write
---

# Setup Patent Creator System

Complete one-time setup for all patent creator capabilities.

## What This Does

Sets up the complete patent creator system:

1. **Download MPEP PDFs** (500MB) - USPTO examination manual
2. **Download Legal Sources** - 35 USC, 37 CFR, Federal Register updates
3. **Build Search Index** - FAISS + BM25 hybrid search (5-65 min depending on GPU)
4. **Configure BigQuery** (optional) - Access to 76M+ patents
5. **Install Dependencies** - Graphviz for diagrams
6. **Verify Installation** - Run test suite

**Total Time**: 30-90 minutes (most time is index building)

## Requirements

Before running:
- **Python 3.9-3.12** (3.11 recommended)
- **8GB+ RAM** (16GB for index building)
- **5GB free disk space**
- **Internet connection** (for downloads)
- **Optional**: NVIDIA GPU (10x faster index building)

## Process

### Step 1: Verify Prerequisites

I'll check:
```bash
python --version  # Must be 3.9-3.12
pip --version
```

If Python not found or wrong version, I'll provide install instructions.

### Step 2: Install Python Dependencies

I'll install required packages:
```bash
cd ${CLAUDE_PLUGIN_ROOT}
pip install -e .
```

**Dependencies installed**:
- PyTorch (GPU or CPU version based on hardware)
- FAISS (vector search)
- Sentence Transformers (embeddings)
- Rank-BM25 (keyword search)
- Pydantic (validation)
- Google Cloud BigQuery (optional)
- Graphviz Python bindings

**GPU Detection**:
- Checks for NVIDIA CUDA
- Checks for Apple Silicon MPS
- Falls back to CPU if neither found
- Installs appropriate PyTorch version

### Step 3: Download MPEP PDFs

I'll download USPTO examination manual:
```bash
cd ${CLAUDE_PLUGIN_ROOT}
python mcp_server/server.py --download-mpep
```

**What downloads**:
- MPEP ZIP file (500MB)
- Extracts to 29 PDF files (mpep-0100 through mpep-2900)
- Location: `${CLAUDE_PLUGIN_ROOT}/pdfs\`

**Time**: 5-10 minutes depending on connection

### Step 4: Download Additional Legal Sources

I'll download supplementary sources:
```bash
python mcp_server/server.py --download-all
```

**Downloads**:
- 35 USC Consolidated Patent Laws PDF
- 37 CFR Consolidated Patent Rules PDF
- Federal Register Subsequent Publications PDF

**Time**: 2-3 minutes

### Step 5: Build Search Index

I'll build the hybrid search index:
```bash
python mcp_server/server.py --rebuild-index
```

**What happens**:
1. Load all MPEP PDFs
2. Extract and chunk text (12,543 chunks)
3. Generate embeddings (BGE-base-en-v1.5, 768-dim)
4. Build FAISS vector index
5. Build BM25 keyword index
6. Save indexes to disk

**Time**:
- With NVIDIA GPU: 5-15 minutes
- With Apple Silicon: 10-25 minutes
- CPU only: 35-65 minutes

**Index location**: `${CLAUDE_PLUGIN_ROOT}/python\index\`

**Disk space**: ~1-2 GB for complete index

### Step 6: Configure BigQuery (Optional)

For access to 76M+ patents, I'll help configure Google Cloud:

**Prerequisites**:
- Google account (free)
- Google Cloud project (free to create)

**Setup steps**:
```bash
# Install Google Cloud SDK
# (I'll provide OS-specific instructions)

# Authenticate
gcloud auth application-default login

# Set project ID
export GOOGLE_CLOUD_PROJECT=your-project-id
```

**Configuration file**:
I'll create/update `.env` file:
```
GOOGLE_CLOUD_PROJECT=your-project-id
PATENT_LOG_LEVEL=WARNING
```

**Cost**: BigQuery is FREE for first 1TB/month (>20,000 patent searches)

### Step 7: Install Graphviz

For patent diagram generation:

**Windows**:
```bash
choco install graphviz
pip install graphviz
```

**Linux**:
```bash
sudo apt install graphviz
pip install graphviz
```

**Mac**:
```bash
brew install graphviz
pip install graphviz
```

### Step 8: Verify Installation

I'll run the test suite:
```bash
cd ${CLAUDE_PLUGIN_ROOT}
python scripts/test_install.py
```

**Tests**:
- [OK] Python version
- [OK] MPEP PDFs present (29 files)
- [OK] Search index built
- [OK] GPU detected (if available)
- [OK] Embeddings model loaded
- [OK] BigQuery configured (if applicable)
- [OK] Graphviz installed
- [OK] All Python dependencies

## Setup Status

After setup completes, you'll see:

```
PATENT CREATOR SYSTEM - SETUP COMPLETE
======================================

Core Components:
  [OK] MPEP Search Index (12,543 chunks indexed)
  [OK] GPU Acceleration (NVIDIA CUDA 12.1)
  [OK] Embedding Model (BGE-base-en-v1.5)
  [OK] Hybrid Search (FAISS + BM25)

Optional Components:
  [OK] BigQuery Patent Search (76M+ patents)
  [OK] Diagram Generation (Graphviz)
  [X] USPTO API (not configured)
  [X] Local Patent Corpus (not downloaded)

System Ready!

Available Commands:
  /create-patent          - Create complete patent application
  /search-prior-art       - Search 76M+ patents for prior art
  /review-claims          - Analyze claims for 112(b) compliance
  /research-mpep          - Search MPEP/USC/CFR

Available Skills:
  - mpep-search           - MPEP/USC/CFR research
  - patent-claims-analyzer - Claims compliance checking
  - bigquery-patent-search - Patent search across 76M+ patents
  - patent-diagram-generator - Technical diagrams
  - prior-art-search      - 7-step search methodology
  - patent-application-creator - Complete patent creation

Available Agents:
  - patent-researcher     - Prior art search specialist
  - patent-drafter        - Claims and specification drafting
  - mpep-expert          - USPTO law and regulations
  - patent-illustrator    - Technical diagram creation

Try it:
  /search-prior-art
  [Describe your invention]
```

## Troubleshooting

### MPEP Download Fails

**Problem**: Download timeout or connection error

**Solution 1**: Retry with longer timeout
```bash
python mcp_server/server.py --download-mpep
```

**Solution 2**: Manual download
1. Visit: https://www.uspto.gov/web/offices/pac/mpep/index.html
2. Download MPEP PDF files
3. Place in: `${CLAUDE_PLUGIN_ROOT}/pdfs\`

### Index Building Fails

**Problem**: Out of memory during index building

**Solution 1**: Close other applications
**Solution 2**: Increase system memory
**Solution 3**: Use CPU-only mode (slower but less memory)
```bash
PATENT_MPEP_DEVICE=cpu python mcp_server/server.py --rebuild-index
```

### GPU Not Detected

**Problem**: Have GPU but using CPU

**Solution 1**: Check CUDA installation
```bash
nvidia-smi  # Should show GPU
```

**Solution 2**: Reinstall PyTorch with CUDA
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### BigQuery Not Working

**Problem**: BigQuery searches fail

**Solution 1**: Check authentication
```bash
gcloud auth application-default login
```

**Solution 2**: Verify project ID
```bash
echo $GOOGLE_CLOUD_PROJECT  # Should show your project ID
```

**Solution 3**: Check API enabled
Visit: https://console.cloud.google.com/apis/library/bigquery.googleapis.com

## Configuration Options

Create `.env` file in `${CLAUDE_PLUGIN_ROOT}\`:

```bash
# Google Cloud (for BigQuery patent search)
GOOGLE_CLOUD_PROJECT=your-project-id

# USPTO API (optional)
PATENT_USPTO_API_KEY=your-api-key-from-data.uspto.gov

# Search Configuration
PATENT_MPEP_USE_HYDE=true        # Use HyDE query expansion
PATENT_MPEP_DEVICE=cuda          # cuda, mps, or cpu
PATENT_LOG_LEVEL=WARNING         # DEBUG, INFO, WARNING, ERROR

# Performance
PATENT_MPEP_BATCH_SIZE=32        # Embedding batch size
PATENT_MPEP_MAX_LENGTH=512       # Max token length
```

## What Gets Installed

**Directory Structure**:
```
${CLAUDE_PLUGIN_ROOT}\
├── pdfs/                          # Source documents
│   ├── mpep-0100.pdf
│   ├── mpep-0200.pdf
│   ├── ...
│   ├── mpep-2900.pdf
│   ├── consolidated_laws.pdf      # 35 USC
│   ├── consolidated_rules.pdf     # 37 CFR
│   └── subsequent_publications.pdf # Updates
├── mcp_server/
│   ├── index/                     # Search indexes
│   │   ├── mpep_index.faiss      # Vector index
│   │   └── mpep_metadata.json    # Metadata + BM25
│   ├── server.py                 # Main server
│   ├── mpep_search.py            # Search implementation
│   ├── claims_analyzer.py        # Claims checker
│   ├── bigquery_search.py        # BigQuery integration
│   └── diagram_generator.py      # Diagram creation
└── .env                          # Configuration
```

## After Setup

You're ready to:

1. **Search MPEP**: Use `/research-mpep` or MPEP Search skill
2. **Search Patents**: Use `/search-prior-art` command
3. **Review Claims**: Use `/review-claims` command
4. **Create Patents**: Use `/create-patent` command
5. **Generate Diagrams**: Use Patent Illustrator agent

## Next Steps

Try it out:
```
/research-mpep

> Search MPEP for claim definiteness requirements

---

/search-prior-art

> I have a blockchain-based authentication system...

---

/review-claims

> [Paste your claims]

---

/create-patent

> I'll create a complete patent application...
```

## Re-Running Setup

Safe to run multiple times:
- Won't re-download if files exist
- Won't rebuild index unless forced
- Updates configuration if changed

Force rebuild:
```bash
python mcp_server/server.py --rebuild-index
```

## Uninstall

To remove:
```bash
# Remove downloaded files
rm -rf ${CLAUDE_PLUGIN_ROOT}/pdfs\
rm -rf ${CLAUDE_PLUGIN_ROOT}/python\index\

# Remove package
pip uninstall claude-patent-creator
```
