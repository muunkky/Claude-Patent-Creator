---
description: One-time setup for the patent creator system - downloads MPEP, builds search index, configures BigQuery
allowed-tools: Bash, Read, Write
---

# Setup Patent Creator System

Complete one-time setup for all patent creator capabilities.

## What This Does

The `patent-creator setup` CLI handles everything automatically:

1. **Detect GPU** and install PyTorch with correct CUDA version
2. **Download MPEP PDFs** (500MB) - USPTO examination manual
3. **Download Legal Sources** - 35 USC, 37 CFR, Federal Register updates
4. **Build Search Index** - FAISS + BM25 hybrid search (5-65 min depending on GPU)
5. **Configure MCP server** registration with Claude Code

**Total Time**: 30-90 minutes (most time is MPEP download and index building)

## Requirements

- **Python 3.9-3.12** (3.11 recommended). Python 3.13+ may lack wheels for PyTorch/FAISS.
- **8GB+ RAM** (16GB for index building)
- **5GB free disk space**
- **Internet connection** (for downloads)
- **Optional**: NVIDIA GPU (10x faster index building)

## Process

### Step 1: Find Compatible Python

**Python 3.13+ will NOT work** — PyTorch and FAISS may not have wheels. Find 3.9-3.12:

```bash
# Check default
python --version 2>&1

# If 3.13+, look for compatible versions:
# Windows (py launcher):
py -3.12 --version 2>&1
py -3.11 --version 2>&1
py -3.10 --version 2>&1

# Linux/macOS:
python3.12 --version 2>&1
python3.11 --version 2>&1
```

Use the first compatible version found (3.9-3.12). Remember this as `PYTHON_CMD` for all remaining steps.

If no compatible Python is found, tell the user to install Python 3.12 from python.org.

### Step 2: Create venv and Install Package

```bash
cd ${CLAUDE_PLUGIN_ROOT}
${PYTHON_CMD} -m venv venv
```

Use the venv Python for all remaining commands:
- **Windows**: `${CLAUDE_PLUGIN_ROOT}/venv/Scripts/python`
- **Linux/macOS**: `${CLAUDE_PLUGIN_ROOT}/venv/bin/python`

Install the package:
```bash
${VENV_PYTHON} -m pip install --upgrade pip
${VENV_PYTHON} -m pip install -e .
```

### Step 3: Run Automated Setup

The `patent-creator setup` CLI handles GPU detection, PyTorch installation, MPEP downloads, and index building automatically:

```bash
cd ${CLAUDE_PLUGIN_ROOT}
${VENV_PYTHON} -m mcp_server.cli setup --non-interactive
```

**What this does automatically:**
1. Detects GPU hardware (NVIDIA CUDA, Apple MPS, or CPU)
2. Installs correct PyTorch version (uninstalls CPU version if GPU detected, restarts itself)
3. Downloads MPEP PDFs if missing (~500MB)
4. Downloads 35 USC, 37 CFR, Federal Register updates
5. Builds FAISS + BM25 hybrid search index (5-65 min)
6. Verifies BigQuery configuration (reports if project ID is missing)
7. Registers MCP server with Claude Code

**This command is long-running** (30-90 minutes). Use a timeout of at least 600000ms (10 minutes) for the Bash call and check output periodically.

### Step 4: Verify Installation

After setup completes, verify:

```bash
${VENV_PYTHON} -c "import torch; print(f'PyTorch {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"
```

```bash
cd ${CLAUDE_PLUGIN_ROOT}
${VENV_PYTHON} -m mcp_server.cli health
```

### Step 5: Configure BigQuery (Required for patent search)

BigQuery provides access to 76M+ patents. It requires a Google Cloud project ID for billing (free tier: 1TB/month, no credit card).

**Check if the setup output showed a BigQuery warning.** If it said `[WARNING] BigQuery not configured` or `No Google Cloud project ID found`, the user needs to set up a project.

**Step 5a: Check gcloud CLI**
```bash
gcloud --version 2>&1
```

If not installed, tell the user to install it from https://cloud.google.com/sdk/docs/install

**Step 5b: Authenticate and set project**

Tell the user to run these interactively (requires browser):
```
! gcloud auth login
! gcloud auth application-default login
```

Then check for existing projects:
```bash
gcloud projects list 2>&1
```

If they have a project, set it:
```bash
gcloud config set project PROJECT_ID
```

If they don't have a project, tell them to create one at https://console.cloud.google.com/projectcreate

**Step 5c: Verify BigQuery works**
```bash
cd ${CLAUDE_PLUGIN_ROOT}
${VENV_PYTHON} -c "from mcp_server.bigquery_search import BigQueryPatentSearch; s = BigQueryPatentSearch(); print(f'BigQuery OK (project: {s.billing_project})')"
```

If this fails with "No Google Cloud project ID found", the project wasn't set. Create a `.env` file as fallback:
```bash
echo "GOOGLE_CLOUD_PROJECT=their-project-id" > ${CLAUDE_PLUGIN_ROOT}/.env
```

Then create/update `.env` file in `${CLAUDE_PLUGIN_ROOT}`:
```
GOOGLE_CLOUD_PROJECT=their-project-id
```

## Troubleshooting

### PyTorch CPU-Only Despite GPU

The most common issue. `patent-creator setup` handles this automatically by detecting GPU and reinstalling PyTorch. If it still fails:

```bash
${VENV_PYTHON} -m pip uninstall -y torch torchvision torchaudio
# For RTX 5090/5080 (compute capability >= 10.0):
${VENV_PYTHON} -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
# For older NVIDIA GPUs:
${VENV_PYTHON} -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### MPEP Download Fails

Retry:
```bash
${VENV_PYTHON} -m mcp_server.cli setup --non-interactive
```
Won't re-download files that already exist. Only downloads missing sources.

### Index Building Out of Memory

Use CPU mode (slower but less memory):
```bash
PATENT_MPEP_DEVICE=cpu ${VENV_PYTHON} -m mcp_server.cli setup --rebuild --non-interactive
```

### BigQuery Not Working

```bash
gcloud auth application-default login
```

## After Setup

The system is ready. Available capabilities:

- `/create-patent` - Create complete patent application
- `/search-prior-art` - Search 76M+ patents
- `/review-claims` - Analyze claims for 112(b) compliance
- `/review-specification` - Check specification for 112(a) support
- `/review-formalities` - Verify MPEP 608 formalities

Tell the user to try: "Search MPEP for claim definiteness requirements"
