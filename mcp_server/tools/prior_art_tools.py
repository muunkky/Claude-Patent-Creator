"""
Local Patent Corpus Prior Art Search Tools (Legacy)

Provides MCP tools for searching local patent corpus and retrieving patent details.
Uses a local FAISS index with hybrid retrieval (HyDE support).

Tools:
    - search_prior_art: Search local patent corpus by description, with CPC filters and date ranges
    - get_patent_details: Retrieve complete patent information with all text chunks by patent number
    - check_patent_corpus_status: Check status of patent corpus download and search index

Dependencies:
    - PatentCorpusIndex from patent_index module
    - Local FAISS index from patent_corpus module
    - Logging and monitoring from logging_config.py and monitoring.py
"""

from typing import Any, Optional


def register_prior_art_tools(
    mcp,
    patent_corpus_index,
    log_info,
    log_error,
    log_warning,
    track_performance,
    BEST_PRACTICES_AVAILABLE,
):
    """Register prior art search tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        patent_corpus_index: Global PatentCorpusIndex instance (may be None initially)
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        log_warning: Logging function for warning messages
        track_performance: Performance tracking decorator
        BEST_PRACTICES_AVAILABLE: Flag indicating if best practices modules are available
    """

    def _ensure_patent_index():
        """Lazy load patent corpus index"""
        nonlocal patent_corpus_index
        if patent_corpus_index is None:
            try:
                from patent_corpus import PATENT_INDEX_DIR
                from patent_index import PatentCorpusIndex

                # Check if index exists
                if not (PATENT_INDEX_DIR / "patent_index.faiss").exists():
                    raise ValueError(
                        "Patent corpus index not built. "
                        "Run 'patent-creator download-patents --build-index' first."
                    )

                patent_corpus_index = PatentCorpusIndex(use_hyde=True)
                patent_corpus_index.build_index(force_rebuild=False)
            except ImportError as e:
                raise ValueError(f"Patent corpus module not available: {e}")

        return patent_corpus_index

    @mcp.tool()
    @track_performance("tool_search_prior_art") if BEST_PRACTICES_AVAILABLE else lambda f: f
    def search_prior_art(
        description: str,
        top_k: int = 10,
        retrieve_k: Optional[int] = None,
        cpc_filter: Optional[str] = None,
        years_back: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """Search local patent corpus for prior art. Supports CPC code filters (e.g., "G06F") and year range limits."""
        try:
            index = _ensure_patent_index()
        except ValueError as e:
            return [{"error": str(e)}]

        # Cap top_k
        top_k = min(top_k, 20)

        # Calculate date range if years_back specified
        date_range = None
        if years_back:
            from datetime import datetime, timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=years_back * 365)
            date_range = (start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"))

        # Search
        results = index.search(
            query=description,
            top_k=top_k,
            retrieve_k=retrieve_k,
            cpc_filter=cpc_filter,
            date_range=date_range,
        )

        return results

    @mcp.tool()
    @track_performance("tool_get_patent_details") if BEST_PRACTICES_AVAILABLE else lambda f: f
    def get_patent_details(patent_id: str) -> dict[str, Any]:
        """Get complete patent information with all text chunks by patent number (e.g., "10123456" or "US10123456")."""
        try:
            index = _ensure_patent_index()
        except ValueError as e:
            return {"error": str(e)}

        # Clean patent ID (remove "US" prefix if present)
        clean_id = patent_id.replace("US", "").replace("us", "")

        # Get all chunks for this patent
        chunks = index.get_patent_chunks(clean_id)

        if not chunks:
            return {"error": f"Patent {patent_id} not found in corpus"}

        # Organize by section
        sections = {}
        metadata = chunks[0]["metadata"] if chunks else {}

        for chunk in chunks:
            section = chunk["section"]
            if section not in sections:
                sections[section] = []
            sections[section].append(chunk["text"])

        return {
            "patent_id": clean_id,
            "cpc_codes": metadata.get("cpc_codes", []),
            "filing_date": metadata.get("filing_date"),
            "grant_date": metadata.get("grant_date"),
            "inventors": metadata.get("inventors", []),
            "assignee": metadata.get("assignee"),
            "sections": sections,
            "total_chunks": len(chunks),
        }

    @mcp.tool()
    @(
        track_performance("tool_check_patent_corpus_status")
        if BEST_PRACTICES_AVAILABLE
        else lambda f: f
    )
    def check_patent_corpus_status() -> dict[str, Any]:
        """Check status of patent corpus download and search index."""
        try:
            from patent_corpus import check_patent_corpus_status as check_status

            return check_status()
        except ImportError:
            return {"error": "Patent corpus module not available"}
