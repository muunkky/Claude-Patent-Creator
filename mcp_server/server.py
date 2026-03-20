#!/usr/bin/env python3
"""
MPEP RAG MCP Server
Provides intelligent retrieval from the Manual of Patent Examining Procedure

This is the main entry point for the MCP server. Tool definitions are organized
in the tools/ subdirectory for better maintainability.
"""

import os
import platform
import shutil
import site
import sys
import zipfile
from pathlib import Path
from typing import Dict, Optional

# macOS Apple Silicon: prevent FAISS OpenMP segfault (must precede torch/faiss imports)
# See: https://github.com/RobThePCGuy/Claude-Patent-Creator/issues/1
if platform.system() == "Darwin":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Load environment variables from .env file FIRST
try:
    from dotenv import load_dotenv

    # Load from mcp_server/.env file
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path, override=True)
except ImportError:
    pass  # dotenv not required

# CRITICAL: Disable user site-packages BEFORE importing third-party packages
site.ENABLE_USER_SITE = False
user_site = site.getusersitepackages()
if user_site in sys.path:
    sys.path.remove(user_site)

# FastMCP for building MCP servers
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Import best practice modules
try:
    from logging_config import get_logger
    from monitoring import track_performance, log_operation_result
    from validation import (
        SearchMPEPInput,
        SearchBigQueryInput,
        SearchUSPTOInput,
        GetPatentInput,
        CPCSearchInput,
        ReviewClaimsInput,
        ReviewSpecificationInput,
        CheckFormalitiesInput,
        RenderDiagramInput,
        validate_input,
        PYDANTIC_AVAILABLE,
    )

    BEST_PRACTICES_AVAILABLE = True
except ImportError as e:
    BEST_PRACTICES_AVAILABLE = False
    get_logger = None  # type: ignore[assignment]
    track_performance = None  # type: ignore[assignment]
    log_operation_result = None  # type: ignore[assignment]
    validate_input = None  # type: ignore[assignment]
    SearchMPEPInput = None  # type: ignore[assignment]
    SearchBigQueryInput = None  # type: ignore[assignment]
    SearchUSPTOInput = None  # type: ignore[assignment]
    GetPatentInput = None  # type: ignore[assignment]
    CPCSearchInput = None  # type: ignore[assignment]
    ReviewClaimsInput = None  # type: ignore[assignment]
    ReviewSpecificationInput = None  # type: ignore[assignment]
    CheckFormalitiesInput = None  # type: ignore[assignment]
    RenderDiagramInput = None  # type: ignore[assignment]
    PYDANTIC_AVAILABLE = False
    print(f"Warning: Best practices modules not available: {e}", file=sys.stderr)

# Import health check system
try:
    from health_check import SystemHealthChecker
except ImportError:
    SystemHealthChecker = None

# Import automated patent analyzers
try:
    from claims_analyzer import ClaimsAnalyzer
    from formalities_checker import FormalitiesChecker
    from specification_analyzer import SpecificationAnalyzer
except ImportError:
    ClaimsAnalyzer = None
    FormalitiesChecker = None
    SpecificationAnalyzer = None

# Import MPEP index from mpep_search module
try:
    from mpep_search import MPEPIndex
except ImportError:
    from mpep_search import MPEPIndex

# Import downloaders
try:
    from downloaders import FileDownloader
except ImportError:
    from downloaders import FileDownloader

# Initialize MCP server
mcp = FastMCP("claude-patent-creator")

# Initialize logger
if BEST_PRACTICES_AVAILABLE:
    logger = get_logger()  # type: ignore[misc]
else:
    logger = None

# Global variables
MPEP_DIR = Path(__file__).parent.parent / "pdfs"
INDEX_DIR = Path(__file__).parent / "index"
patent_corpus_index = None
mpep_index: Optional[MPEPIndex] = None

# Ensure directories exist
MPEP_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# USPTO download URLs
MPEP_DOWNLOAD_URL = "https://www.uspto.gov/web/offices/pac/mpep/e9r-01-2024.zip"
USC_35_DOWNLOAD_URL = "https://www.uspto.gov/web/offices/pac/mpep/consolidated_laws.pdf"
CFR_37_DOWNLOAD_URL = "https://www.uspto.gov/web/offices/pac/mpep/consolidated_rules.pdf"
SUBSEQUENT_PUBS_URL = "https://www.uspto.gov/web/offices/pac/mpep/subsequent-publications.pdf"
USC_35_FILE = "consolidated_laws.pdf"
CFR_37_FILE = "consolidated_rules.pdf"
SUBSEQUENT_PUBS_FILE = "subsequent_publications.pdf"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _log_info(message: str, **kwargs):
    """Log info message with fallback to stderr."""
    if logger:
        logger.info(message, extra=kwargs)
    else:
        print(message, file=sys.stderr)


def _log_warning(message: str, **kwargs):
    """Log warning message with fallback to stderr."""
    if logger:
        logger.warning(message, extra=kwargs)
    else:
        print(f"WARNING: {message}", file=sys.stderr)


def _log_error(message: str, exc_info: bool = False, **kwargs):
    """Log error message with fallback to stderr."""
    if logger:
        logger.error(message, extra=kwargs, exc_info=exc_info)
    else:
        print(f"ERROR: {message}", file=sys.stderr)


def _log_debug(message: str, **kwargs):
    """Log debug message with fallback to stderr."""
    if logger:
        logger.debug(message, extra=kwargs)


def download_mpep_pdfs(url: str = MPEP_DOWNLOAD_URL, dest_dir: Path = MPEP_DIR) -> bool:
    """Download MPEP PDFs from USPTO website"""
    zip_path = dest_dir / "mpep-pdfs.zip"
    manual_instructions = (
        "1. Go to https://www.uspto.gov/web/offices/pac/mpep/index.html\n"
        "2. Download MPEP PDF files (mpep-0100.pdf through mpep-2900.pdf)\n"
        f"3. Place them in: {dest_dir.absolute()}"
    )
    return FileDownloader.download_with_progress(
        url=url,
        dest_path=zip_path,
        file_description="MPEP PDFs",
        timeout_seconds=300,
        use_mb=True,
        manual_instructions=manual_instructions,
    )


def extract_mpep_pdfs(dest_dir: Path = MPEP_DIR) -> bool:
    """Extract MPEP PDFs from downloaded zip file"""
    zip_path = dest_dir / "mpep-pdfs.zip"
    if not zip_path.exists():
        print(f"[X] Zip file not found: {zip_path}", file=sys.stderr)
        return False

    print(f"\nExtracting MPEP PDFs to {dest_dir.absolute()}", file=sys.stderr)
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            pdf_files = [f for f in zip_ref.namelist() if f.endswith(".pdf")]
            for i, file in enumerate(pdf_files, 1):
                zip_ref.extract(file, dest_dir)
                print(f"\rExtracting: {i}/{len(pdf_files)} files", end="", file=sys.stderr)
            print(f"\n[OK] Extracted {len(pdf_files)} PDF files", file=sys.stderr)
        zip_path.unlink()
        return True
    except Exception as e:
        print(f"\n[X] Extraction failed: {e}", file=sys.stderr)
        return False


def check_mpep_pdfs(dest_dir: Path = MPEP_DIR) -> int:
    """Check how many MPEP PDFs are available"""
    return len(list(dest_dir.glob("mpep-*.pdf")))


def download_35_usc(dest_dir: Path = MPEP_DIR) -> bool:
    """Download 35 USC Consolidated Patent Laws PDF"""
    return FileDownloader.download_with_progress(
        url=USC_35_DOWNLOAD_URL,
        dest_path=dest_dir / USC_35_FILE,
        file_description="35 USC Consolidated Patent Laws",
        timeout_seconds=120,
        use_mb=False,
    )


def download_37_cfr(dest_dir: Path = MPEP_DIR) -> bool:
    """Download 37 CFR Consolidated Patent Rules PDF"""
    return FileDownloader.download_with_progress(
        url=CFR_37_DOWNLOAD_URL,
        dest_path=dest_dir / CFR_37_FILE,
        file_description="37 CFR Consolidated Patent Rules",
        timeout_seconds=120,
        use_mb=False,
    )


def download_subsequent_publications(dest_dir: Path = MPEP_DIR) -> bool:
    """Download Subsequent Publications PDF"""
    return FileDownloader.download_with_progress(
        url=SUBSEQUENT_PUBS_URL,
        dest_path=dest_dir / SUBSEQUENT_PUBS_FILE,
        file_description="Subsequent Publications",
        timeout_seconds=120,
        use_mb=False,
    )


def check_all_sources(dest_dir: Path = MPEP_DIR) -> Dict[str, bool]:
    """Check which source documents are available"""
    return {
        "mpep": check_mpep_pdfs(dest_dir) > 0,
        "35_usc": (dest_dir / USC_35_FILE).exists(),
        "37_cfr": (dest_dir / CFR_37_FILE).exists(),
        "subsequent_pubs": (dest_dir / SUBSEQUENT_PUBS_FILE).exists(),
    }


# ============================================================================
# TOOL REGISTRATION
# ============================================================================

# Import tool registration functions
from tools.mpep_tools import register_mpep_tools  # noqa: E402
from tools.analyzer_tools import register_analyzer_tools  # noqa: E402
from tools.uspto_search_tools import register_uspto_tools  # noqa: E402
from tools.bigquery_tools import register_bigquery_tools  # noqa: E402
from tools.prior_art_tools import register_prior_art_tools  # noqa: E402
from tools.diagram_tools import register_diagram_tools  # noqa: E402
from tools.system_tools import register_system_tools  # noqa: E402

# Note: Tool registration happens in main() after mpep_index is initialized


# ============================================================================
# CLI ARGUMENT PARSING AND HANDLERS
# ============================================================================


def _parse_args():
    """Parse command line arguments"""
    import argparse

    parser = argparse.ArgumentParser(description="MPEP RAG MCP Server")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild of the index")
    parser.add_argument(
        "--download-mpep", action="store_true", help="Download MPEP PDFs from USPTO"
    )
    parser.add_argument("--download-all", action="store_true", help="Download all sources")
    parser.add_argument("--download-statutes", action="store_true", help="Download 35 USC")
    parser.add_argument("--download-regulations", action="store_true", help="Download 37 CFR")
    parser.add_argument(
        "--download-updates", action="store_true", help="Download Subsequent Publications"
    )
    parser.add_argument(
        "--mpep-url", type=str, default=MPEP_DOWNLOAD_URL, help="Custom MPEP download URL"
    )
    parser.add_argument("--no-hyde", action="store_true", help="Disable HyDE query expansion")
    return parser.parse_args()


def _handle_mpep_download(mpep_url):
    """Handle MPEP PDF download"""
    pdf_count = check_mpep_pdfs()
    if pdf_count > 0:
        response = input(f"\n{pdf_count} MPEP PDFs already exist. Download anyway? (y/N): ")
        if response.lower() != "y":
            print("Skipping download", file=sys.stderr)
            pdf_count = check_mpep_pdfs()
            print(f"\n[OK] Found {pdf_count} MPEP PDF files", file=sys.stderr)
            print("\nReady to build index. Run with --rebuild-index to continue.", file=sys.stderr)
            sys.exit(0)
    if download_mpep_pdfs(mpep_url):
        extract_mpep_pdfs()
    pdf_count = check_mpep_pdfs()
    print(f"\n[OK] Found {pdf_count} MPEP PDF files", file=sys.stderr)
    if pdf_count == 0:
        print("\n[X] No MPEP PDFs found. Cannot build index.", file=sys.stderr)
        sys.exit(1)
    print("\nReady to build index. Run with --rebuild-index to continue.", file=sys.stderr)
    sys.exit(0)


def _handle_additional_downloads(args):
    """Handle downloads for 35 USC, 37 CFR, and Subsequent Publications"""
    sources_status = check_all_sources()
    downloads_performed = []

    if args.download_all or args.download_statutes:
        if sources_status["35_usc"]:
            print(f"\n35 USC already exists at {MPEP_DIR / USC_35_FILE}", file=sys.stderr)
        if download_35_usc():
            downloads_performed.append("35 USC")

    if args.download_all or args.download_regulations:
        if sources_status["37_cfr"]:
            print(f"\n37 CFR already exists at {MPEP_DIR / CFR_37_FILE}", file=sys.stderr)
        if download_37_cfr():
            downloads_performed.append("37 CFR")

    if args.download_all or args.download_updates:
        if sources_status["subsequent_pubs"]:
            print(
                f"\nSubsequent Publications already exists at {MPEP_DIR / SUBSEQUENT_PUBS_FILE}",
                file=sys.stderr,
            )
        if download_subsequent_publications():
            downloads_performed.append("Subsequent Publications")

    if downloads_performed:
        print(f"\n[OK] Successfully downloaded: {', '.join(downloads_performed)}", file=sys.stderr)
        print(
            "\nNote: These sources are not yet indexed. Run with --rebuild-index to include them.",
            file=sys.stderr,
        )
    else:
        print("\n[OK] All requested sources already present", file=sys.stderr)

    print("\nCurrent source status:", file=sys.stderr)
    print(f"  MPEP PDFs: {'[OK]' if sources_status['mpep'] else '[X]'}", file=sys.stderr)
    print(f"  35 USC:    {'[OK]' if sources_status['35_usc'] else '[X]'}", file=sys.stderr)
    print(f"  37 CFR:    {'[OK]' if sources_status['37_cfr'] else '[X]'}", file=sys.stderr)
    print(f"  Updates:   {'[OK]' if sources_status['subsequent_pubs'] else '[X]'}", file=sys.stderr)
    sys.exit(0)


def _check_prerequisites(rebuild_index):
    """Check that prerequisites are met before starting server"""
    pdf_count = check_mpep_pdfs()
    index_exists = (INDEX_DIR / "mpep_index.faiss").exists() and (
        INDEX_DIR / "mpep_metadata.json"
    ).exists()

    if not index_exists and pdf_count == 0:
        print("\n[X] No MPEP PDFs and no existing index found.", file=sys.stderr)
        print("\nTo get started:", file=sys.stderr)
        print("  1. python mcp_server/server.py --download-mpep", file=sys.stderr)
        print("  2. python mcp_server/server.py --rebuild-index", file=sys.stderr)
        sys.exit(1)

    if pdf_count == 0 and rebuild_index:
        print("\n[X] No MPEP PDFs found.", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("1. Run with --download-mpep to download automatically", file=sys.stderr)
        print("2. Manually download PDFs and place in project root", file=sys.stderr)
        sys.exit(1)


def _run_health_checks():
    """Run pre-flight health checks and display warnings"""
    if not SystemHealthChecker:
        return

    print("\nRunning pre-flight health checks...", file=sys.stderr)
    checker = SystemHealthChecker()
    health_status = checker.check_all_dependencies(verbose=False)

    warnings = []
    if not health_status["patent_corpus"].get("ready", False):
        warnings.append("Patent corpus not available - prior art search will be limited")
    if not health_status["uspto_api"].get("available", False):
        warnings.append("USPTO API not configured - live patent search disabled")
    if health_status["gpu_status"].get("status") != "available":
        warnings.append(
            f"GPU not available: {health_status['gpu_status'].get('details', 'Using CPU mode')}"
        )

    if warnings:
        print("\n[WARNING] Warnings:", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)
        print("\nServer will start with limited functionality.", file=sys.stderr)
        print("Run 'patent-creator status --verbose' for details.\n", file=sys.stderr)
    else:
        print("[OK] All systems operational\n", file=sys.stderr)


def _auto_copy_claude_config():
    """Automatically copy .claude config to current working directory if not present"""
    try:
        cwd = Path(os.getcwd()).resolve()
        dest_claude = cwd / ".claude"
        server_root = Path(__file__).parent.resolve()
        source_claude = server_root / ".claude"

        if not source_claude.exists():
            _log_warning(
                f".claude directory not found in MCP server installation at {source_claude}"
            )
            return

        if dest_claude.exists():
            _log_info(f".claude configuration already exists at {dest_claude}")
            return

        _log_info(f"Copying .claude configuration to {dest_claude}...")
        dest_claude.mkdir(parents=True, exist_ok=True)
        copied_count = 0

        for item in source_claude.iterdir():
            dest_item = dest_claude / item.name
            try:
                if item.is_dir():
                    shutil.copytree(item, dest_item)
                elif item.is_file():
                    shutil.copy2(item, dest_item)
                copied_count += 1
            except Exception as e:
                _log_warning(f"Failed to copy {item.name}: {e}")

        _log_info(f"Successfully copied .claude configuration ({copied_count} items)")
    except Exception as e:
        _log_warning(f"Failed to auto-copy .claude configuration: {e}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    """Main entry point"""
    args = _parse_args()

    # Handle download requests
    if args.download_mpep:
        _handle_mpep_download(args.mpep_url)

    if (
        args.download_all
        or args.download_statutes
        or args.download_regulations
        or args.download_updates
    ):
        _handle_additional_downloads(args)

    # Check prerequisites
    _check_prerequisites(args.rebuild_index)

    # Initialize MPEP index
    global mpep_index
    use_hyde = not args.no_hyde
    _log_info("Initializing MPEP index...", use_hyde=use_hyde)
    mpep_index = MPEPIndex(use_hyde=use_hyde)
    mpep_index.build_index(force_rebuild=args.rebuild_index)

    # Register all MCP tools (now that mpep_index is initialized)
    register_mpep_tools(
        mcp=mcp,
        mpep_index=mpep_index,
        log_info=_log_info,
        log_error=_log_error,
        validate_input=validate_input,
        SearchMPEPInput=SearchMPEPInput,
        track_performance=track_performance,
        log_operation_result=log_operation_result,
        PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    register_analyzer_tools(
        mcp=mcp,
        mpep_index=mpep_index,
        ClaimsAnalyzer=ClaimsAnalyzer,
        SpecificationAnalyzer=SpecificationAnalyzer,
        FormalitiesChecker=FormalitiesChecker,
        log_info=_log_info,
        log_warning=_log_warning,
        log_error=_log_error,
        validate_input=validate_input,
        ReviewClaimsInput=ReviewClaimsInput,
        ReviewSpecificationInput=ReviewSpecificationInput,
        CheckFormalitiesInput=CheckFormalitiesInput,
        track_performance=track_performance,
        log_operation_result=log_operation_result,
        PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    register_uspto_tools(
        mcp=mcp,
        log_info=_log_info,
        log_error=_log_error,
        validate_input=validate_input,
        SearchUSPTOInput=SearchUSPTOInput,
        GetPatentInput=GetPatentInput,
        track_performance=track_performance,
        PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    register_bigquery_tools(
        mcp=mcp,
        log_info=_log_info,
        log_error=_log_error,
        log_warning=_log_warning,
        validate_input=validate_input,
        SearchBigQueryInput=SearchBigQueryInput,
        GetPatentInput=GetPatentInput,
        CPCSearchInput=CPCSearchInput,
        track_performance=track_performance,
        PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    register_prior_art_tools(
        mcp=mcp,
        patent_corpus_index=patent_corpus_index,
        log_info=_log_info,
        log_error=_log_error,
        log_warning=_log_warning,
        track_performance=track_performance,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    register_diagram_tools(
        mcp=mcp,
        log_info=_log_info,
        log_error=_log_error,
        log_warning=_log_warning,
        validate_input=validate_input,
        RenderDiagramInput=RenderDiagramInput,
        track_performance=track_performance,
        PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    register_system_tools(
        mcp=mcp,
        mpep_index=mpep_index,
        patent_corpus_index=patent_corpus_index,
        log_info=_log_info,
        log_error=_log_error,
        BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
    )

    # Run health checks
    _run_health_checks()

    # Auto-copy .claude configuration to current working directory
    _auto_copy_claude_config()

    # Run the MCP server
    _log_info("Starting MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
