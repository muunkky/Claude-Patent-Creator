"""
BigQuery Patent Search Tools

Provides MCP tools for fast, cloud-based patent searching using Google BigQuery.
Searches across 76M+ worldwide patents or 12M+ US patents with full text indexing.

Tools:
    - check_bigquery_status: Verify BigQuery availability and configuration
    - search_patents_bigquery: Fast keyword search across patent database
    - get_patent_bigquery: Retrieve full patent details by publication number
    - search_patents_by_cpc_bigquery: Search patents by CPC classification code

Dependencies:
    - BigQueryPatentSearch from bigquery_search module
    - Validation models from validation.py
    - Logging and monitoring from logging_config.py and monitoring.py
"""

from typing import Any, Dict, List, Optional


def register_bigquery_tools(
    mcp,
    log_info,
    log_error,
    log_warning,
    validate_input,
    SearchBigQueryInput,
    GetPatentInput,
    CPCSearchInput,
    track_performance,
    PYDANTIC_AVAILABLE,
    BEST_PRACTICES_AVAILABLE,
):
    """Register BigQuery patent search tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        log_warning: Logging function for warning messages
        validate_input: Input validation function
        SearchBigQueryInput: Pydantic model for BigQuery search validation
        GetPatentInput: Pydantic model for get patent validation
        CPCSearchInput: Pydantic model for CPC search validation
        track_performance: Performance tracking decorator
        PYDANTIC_AVAILABLE: Flag indicating if Pydantic is available
        BEST_PRACTICES_AVAILABLE: Flag indicating if best practices modules are available
    """

    # State variable for lazy-loaded BigQuery searcher
    bigquery_searcher = None

    def _ensure_bigquery_searcher():
        """Lazy load BigQuery patent searcher"""
        nonlocal bigquery_searcher
        if bigquery_searcher is None:
            try:
                from bigquery_search import BigQueryPatentSearch

                bigquery_searcher = BigQueryPatentSearch()
            except ImportError as e:
                raise ValueError(
                    f"BigQuery not available: {e}. "
                    "Install with: pip install google-cloud-bigquery db-dtypes"
                )
            except Exception as e:
                raise ValueError(f"Failed to initialize BigQuery: {e}")

        return bigquery_searcher

    @mcp.tool()
    def check_bigquery_status() -> Dict[str, Any]:
        """Check if Google BigQuery patent search is available and configured."""
        log_info("check_bigquery_status called")
        try:
            from bigquery_search import check_bigquery_available

            result = check_bigquery_available()
            log_info(
                "check_bigquery_status result",
                available=result.get("available"),
                keys=list(result.keys()),
            )
            return result
        except ImportError as e:
            log_error("check_bigquery_status import error", exc_info=True, error=str(e))
            return {
                "available": False,
                "error": "google-cloud-bigquery not installed",
                "install_command": "pip install google-cloud-bigquery db-dtypes",
            }
        except Exception as e:
            log_error("check_bigquery_status exception", exc_info=True, error=str(e))
            return {"available": False, "error": str(e)}

    @mcp.tool()
    @track_performance("tool_search_patents_bigquery") if BEST_PRACTICES_AVAILABLE else lambda f: f
    def search_patents_bigquery(
        query: str,
        limit: int = 20,
        country: str = "US",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search patents using Google BigQuery (fast, cloud-based, 76M+ patents).

        This is the RECOMMENDED method for patent prior art search. No local indexing required.
        Searches across 76M+ worldwide patents or 12M+ US patents with full text.

        Args:
            query: Search keywords or phrase
            limit: Maximum results to return (default 20, max 100)
            country: Country code (US, EP, JP, CN, etc.)
            start_year: Filter by filing year >= start_year
            end_year: Filter by filing year <= end_year

        Returns:
            List of matching patents with title, abstract, dates, etc.
        """
        log_info(
            "search_patents_bigquery called",
            query=query,
            limit=limit,
            country=country,
            start_year=start_year,
            end_year=end_year,
        )
        try:
            # Validate inputs
            if PYDANTIC_AVAILABLE:
                validated = validate_input(
                    SearchBigQueryInput,
                    query=query,
                    limit=limit,
                    country=country,
                    start_year=start_year,
                    end_year=end_year,
                )
                query = validated.query
                limit = validated.limit
                country = validated.country
                start_year = validated.start_year
                end_year = validated.end_year

            log_info("search_patents_bigquery: ensuring bigquery searcher")
            searcher = _ensure_bigquery_searcher()
            log_info("search_patents_bigquery: searcher obtained, calling search_by_keywords")
            results = searcher.search_by_keywords(
                query=query,
                country=country,
                limit=min(limit, 100),
                start_year=start_year,
                end_year=end_year,
            )
            log_info(
                "search_patents_bigquery: got results",
                count=len(results),
                first_patent=results[0].get("patent_number") if results else None,
            )
            return results

        except ValueError as e:
            log_error("search_patents_bigquery ValueError", exc_info=True, error=str(e))
            return [{"error": str(e)}]
        except Exception as e:
            log_error("search_patents_bigquery exception", exc_info=True, error=str(e))
            return [{"error": f"BigQuery search failed: {str(e)}"}]

    @mcp.tool()
    @track_performance("tool_get_patent_bigquery") if BEST_PRACTICES_AVAILABLE else lambda f: f
    def get_patent_bigquery(patent_number: str) -> Dict[str, Any]:
        """
        Get full patent details from BigQuery by publication number.

        Args:
            patent_number: Patent publication number (e.g., "US10123456B2", "EP1234567A1")

        Returns:
            Patent details including title, abstract, claims, description, CPC codes
        """
        log_info("get_patent_bigquery called", patent_number=patent_number)
        try:
            # Validate inputs
            if PYDANTIC_AVAILABLE:
                validated = validate_input(GetPatentInput, patent_number=patent_number)
                patent_number = validated.patent_number

            log_info("get_patent_bigquery: ensuring bigquery searcher")
            searcher = _ensure_bigquery_searcher()
            log_info("get_patent_bigquery: searcher obtained, calling get_patent_details")
            result = searcher.get_patent_details(patent_number)

            if not result:
                log_info("get_patent_bigquery: no result found")
                return {"error": f"Patent {patent_number} not found in BigQuery"}

            log_info("get_patent_bigquery: got result", title=result.get("title", "")[:50])
            return result

        except ValueError as e:
            log_error("get_patent_bigquery ValueError", exc_info=True, error=str(e))
            return {"error": str(e)}
        except Exception as e:
            log_error("get_patent_bigquery exception", exc_info=True, error=str(e))
            return {"error": f"Failed to retrieve patent: {str(e)}"}

    @mcp.tool()
    @(
        track_performance("tool_search_patents_by_cpc_bigquery")
        if BEST_PRACTICES_AVAILABLE
        else lambda f: f
    )
    def search_patents_by_cpc_bigquery(
        cpc_code: str, limit: int = 20, country: str = "US"
    ) -> List[Dict[str, Any]]:
        """
        Search patents by CPC classification code using BigQuery.

        Args:
            cpc_code: CPC code or prefix (e.g., "G06F", "G06F16/", "H04L29/06")
            limit: Maximum results (default 20, max 100)
            country: Country code filter

        Returns:
            List of patents matching the CPC code
        """
        log_info(
            "search_patents_by_cpc_bigquery called", cpc_code=cpc_code, limit=limit, country=country
        )
        try:
            # Validate inputs
            if PYDANTIC_AVAILABLE:
                validated = validate_input(
                    CPCSearchInput, cpc_code=cpc_code, limit=limit, country=country
                )
                cpc_code = validated.cpc_code
                limit = validated.limit
                country = validated.country

            log_info("search_patents_by_cpc_bigquery: ensuring bigquery searcher")
            searcher = _ensure_bigquery_searcher()
            log_info("search_patents_by_cpc_bigquery: searcher obtained, calling search_by_cpc")
            results = searcher.search_by_cpc(
                cpc_code=cpc_code, limit=min(limit, 100), country=country
            )
            log_info("search_patents_by_cpc_bigquery: got results", count=len(results))
            return results

        except ValueError as e:
            log_error("search_patents_by_cpc_bigquery ValueError", exc_info=True, error=str(e))
            return [{"error": str(e)}]
        except Exception as e:
            log_error("search_patents_by_cpc_bigquery exception", exc_info=True, error=str(e))
            return [{"error": f"CPC search failed: {str(e)}"}]
