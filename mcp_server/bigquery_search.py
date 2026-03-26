#!/usr/bin/env python3
"""
BigQuery Patent Search
Fast, cloud-based patent search using Google's Patents Public Data
"""

import os
import platform
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery
    from google.cloud.exceptions import GoogleCloudError

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    bigquery = None
    GoogleCloudError = Exception
    NotFound = Exception

# Import logging and monitoring with fallback
try:
    from logging_config import get_logger
    from monitoring import OperationTimer, track_performance

    logger = get_logger()
    LOGGING_AVAILABLE = True
except ImportError:
    logger = None
    track_performance = None
    OperationTimer = None
    LOGGING_AVAILABLE = False


def _get_gcloud_credentials_path():
    """
    Get the correct gcloud application default credentials path for the current OS

    Returns:
        Path: Platform-specific credentials path
    """
    if platform.system() == "Windows":
        # Windows: %APPDATA%\gcloud\application_default_credentials.json
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "gcloud" / "application_default_credentials.json"
        else:
            return (
                Path.home()
                / "AppData"
                / "Roaming"
                / "gcloud"
                / "application_default_credentials.json"
            )
    else:
        # Linux/macOS: $HOME/.config/gcloud/application_default_credentials.json
        return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


class BigQueryPatentSearch:
    """
    Search patents using Google BigQuery Patents Public Data

    This provides access to 76M+ worldwide patents and 12M+ US patents
    with full-text search capabilities. Much faster than local indexing.
    """

    PROJECT_ID = "patents-public-data"
    DATASET_ID = "patents"
    TABLE_ID = "publications"
    FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize BigQuery client

        Args:
            project_id: Optional GCP project ID for billing. If not provided,
                       will use GOOGLE_CLOUD_PROJECT env var or default credentials.
        """
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "google-cloud-bigquery not installed. "
                "Install with: pip install google-cloud-bigquery db-dtypes"
            )

        # Determine project for billing
        self.billing_project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")

        # Try to get project from credentials file if not provided
        if not self.billing_project:
            try:
                import json

                creds_path = _get_gcloud_credentials_path()
                if creds_path.exists():
                    with creds_path.open() as f:
                        creds_data = json.load(f)
                        self.billing_project = creds_data.get("quota_project_id")
            except Exception:
                pass

        # Initialize client
        try:
            if self.billing_project:
                self.client = bigquery.Client(project=self.billing_project)  # type: ignore[union-attr]
            else:
                # Try default credentials
                self.client = bigquery.Client()  # type: ignore[union-attr]
                self.billing_project = self.client.project

            if LOGGING_AVAILABLE and logger:
                logger.info(
                    "bigquery_client_initialized", extra={"billing_project": self.billing_project}
                )
        except Exception as e:
            error_msg = f"Warning: Could not initialize BigQuery client: {e}"
            setup_msg = (
                "\n"
                "Setup required (5 minutes, no credit card):\n"
                "  1. Install gcloud: https://cloud.google.com/sdk/docs/install\n"
                "  2. Run: gcloud auth application-default login\n"
                "  3. Sign in with Google in the browser that opens\n"
                "\n"
                "Free tier: 1TB queries/month\n"
            )

            if LOGGING_AVAILABLE and logger:
                logger.error(
                    "bigquery_client_init_failed",
                    extra={"error_type": type(e).__name__, "setup_instructions": setup_msg},
                    exc_info=True,
                )
            else:
                print(error_msg, file=sys.stderr)
                print(setup_msg, file=sys.stderr)

            self.client = None
            self.billing_project = None

    def check_availability(self) -> dict[str, Any]:
        """
        Check if BigQuery is available and credentials are configured

        Returns:
            Dictionary with status information
        """
        if not BIGQUERY_AVAILABLE:
            return {
                "available": False,
                "error": "google-cloud-bigquery not installed",
                "install_command": "pip install google-cloud-bigquery db-dtypes",
            }

        if not self.client:
            return {
                "available": False,
                "error": "BigQuery client not initialized",
                "message": "Set GOOGLE_CLOUD_PROJECT environment variable or configure gcloud auth",
            }

        # Try a simple query to verify access
        try:
            query = f"""
            SELECT COUNT(*) as total
            FROM `{self.FULL_TABLE_ID}`
            WHERE country_code = 'US'
            LIMIT 1
            """
            result = self.client.query(query).result(timeout=30)
            total = 0
            for row in result:
                total = row.total

            return {
                "available": True,
                "project": self.billing_project,
                "message": "BigQuery patent search ready",
                "us_patents": total,
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "message": "Could not access patents public data",
            }

    def search_by_keywords(
        self,
        query: str,
        country: str = "US",
        limit: int = 20,
        offset: int = 0,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        search_fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Search patents by keyword matching in abstract, title, or claims

        Args:
            query: Search query string
            country: Country code (US, EP, JP, CN, etc.)
            limit: Maximum number of results
            offset: Number of results to skip
            start_year: Filter by filing year >= start_year
            end_year: Filter by filing year <= end_year
            search_fields: Which fields to search in

        Returns:
            List of patent dictionaries
        """
        if search_fields is None:
            search_fields = ["abstract", "title", "claims"]

        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        # Log search start
        log_extra = {
            "query": query[:100] if query else "",
            "query_length": len(query) if query else 0,
            "country": country,
            "limit": limit,
            "offset": offset,
            "start_year": start_year,
            "end_year": end_year,
            "search_fields": search_fields,
        }

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_search_started", extra=log_extra)

        # Build WHERE conditions
        conditions = [f"country_code = '{country}'"]

        # Add search conditions
        search_conditions = []
        if "abstract" in search_fields:
            search_conditions.append("LOWER(abstract_localized[SAFE_OFFSET(0)].text) LIKE @query")
        if "title" in search_fields:
            search_conditions.append("LOWER(title_localized[SAFE_OFFSET(0)].text) LIKE @query")
        if "claims" in search_fields and country == "US":
            search_conditions.append("LOWER(claims_localized[SAFE_OFFSET(0)].text) LIKE @query")

        if search_conditions:
            conditions.append(f"({' OR '.join(search_conditions)})")

        # Add date filters
        if start_year:
            conditions.append(f"CAST(filing_date AS INT64) >= {start_year}0101")
        if end_year:
            conditions.append(f"CAST(filing_date AS INT64) <= {end_year}1231")

        where_clause = " AND ".join(conditions)

        # Build query
        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(grant_date AS STRING) AS grant_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            family_id,
            country_code
        FROM `{self.FULL_TABLE_ID}`
        WHERE {where_clause}
        ORDER BY publication_date DESC
        LIMIT @limit
        OFFSET @offset
        """

        job_config = bigquery.QueryJobConfig(  # type: ignore[union-attr]
            query_parameters=[
                bigquery.ScalarQueryParameter("query", "STRING", f"%{query.lower()}%"),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("offset", "INT64", offset),  # type: ignore[union-attr]
            ]
        )

        try:
            # Execute query with timing and timeout (30 seconds)
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            # Process results
            patents = []
            for row in results:
                patents.append(
                    {
                        "patent_number": row.publication_number,
                        "application_number": row.application_number,
                        "title": row.title or "",
                        "abstract": row.abstract or "",
                        "filing_date": self._format_date(row.filing_date),
                        "grant_date": self._format_date(row.grant_date),
                        "publication_date": self._format_date(row.publication_date),
                        "country": row.country_code,
                        "family_id": row.family_id,
                    }
                )

            # Log completion with metrics
            completion_extra = {
                **log_extra,
                "results_count": len(patents),
                "bytes_processed": (
                    results.total_bytes_processed
                    if hasattr(results, "total_bytes_processed")
                    else 0
                ),
                "bytes_billed": (
                    results.total_bytes_billed if hasattr(results, "total_bytes_billed") else 0  # type: ignore[attr-defined]
                ),
            }

            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_search_completed", extra=completion_extra)

            return patents

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_search_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery search error: {e}", file=sys.stderr)

            raise

    def get_patent_details(self, patent_number: str) -> Optional[dict[str, Any]]:
        """
        Get full details for a specific patent by publication number

        Args:
            patent_number: Patent publication number (e.g., "US10123456B2")

        Returns:
            Patent details dictionary or None if not found
        """
        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        # Log retrieval start
        log_extra = {"patent_number": patent_number}

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_get_patent_started", extra=log_extra)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            claims_localized[SAFE_OFFSET(0)].text AS claims,
            description_localized[SAFE_OFFSET(0)].text AS description,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(grant_date AS STRING) AS grant_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            family_id,
            country_code,
            cpc
        FROM `{self.FULL_TABLE_ID}`
        WHERE publication_number = @patent_number
        LIMIT 1
        """

        job_config = bigquery.QueryJobConfig(  # type: ignore[union-attr]
            query_parameters=[
                bigquery.ScalarQueryParameter("patent_number", "STRING", patent_number),  # type: ignore[union-attr]
            ]
        )

        try:
            # Execute query with timing and timeout (30 seconds)
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            # Process results
            for row in results:
                # Extract CPC codes
                cpc_codes = []
                if row.cpc:
                    for cpc in row.cpc:
                        if hasattr(cpc, "code"):
                            cpc_codes.append(cpc.code)

                patent_data = {
                    "patent_number": row.publication_number,
                    "application_number": row.application_number,
                    "title": row.title or "",
                    "abstract": row.abstract or "",
                    "claims": row.claims or "",
                    "description": row.description or "",
                    "filing_date": self._format_date(row.filing_date),
                    "grant_date": self._format_date(row.grant_date),
                    "publication_date": self._format_date(row.publication_date),
                    "country": row.country_code,
                    "family_id": row.family_id,
                    "cpc_codes": cpc_codes,
                }

                # Log successful retrieval
                completion_extra = {
                    **log_extra,
                    "found": True,
                    "cpc_codes_count": len(cpc_codes),
                    "has_claims": bool(row.claims),
                    "has_description": bool(row.description),
                    "bytes_processed": (
                        results.total_bytes_processed
                        if hasattr(results, "total_bytes_processed")
                        else 0
                    ),
                }

                if LOGGING_AVAILABLE and logger:
                    logger.info("bigquery_get_patent_completed", extra=completion_extra)

                return patent_data

            # Patent not found
            if LOGGING_AVAILABLE and logger:
                logger.warning("bigquery_get_patent_not_found", extra={**log_extra, "found": False})

            return None

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_get_patent_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery get patent error: {e}", file=sys.stderr)

            return None

    def search_by_cpc(
        self, cpc_code: str, limit: int = 20, country: str = "US"
    ) -> list[dict[str, Any]]:
        """
        Search patents by CPC classification code

        Args:
            cpc_code: CPC code prefix (e.g., "G06F" or "G06F16/")
            limit: Maximum number of results
            country: Country code filter

        Returns:
            List of patent dictionaries
        """
        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        # Log CPC search start
        log_extra = {"cpc_code": cpc_code, "limit": limit, "country": country}

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_cpc_search_started", extra=log_extra)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            country_code
        FROM `{self.FULL_TABLE_ID}`,
        UNNEST(cpc) AS cpc_entry
        WHERE
            country_code = @country
            AND STARTS_WITH(cpc_entry.code, @cpc_code)
        ORDER BY publication_date DESC
        LIMIT @limit
        """

        job_config = bigquery.QueryJobConfig(  # type: ignore[union-attr]
            query_parameters=[
                bigquery.ScalarQueryParameter("cpc_code", "STRING", cpc_code),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
            ]
        )

        try:
            # Execute query with timing and timeout (30 seconds)
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            # Process results
            patents = []
            for row in results:
                patents.append(
                    {
                        "patent_number": row.publication_number,
                        "application_number": row.application_number,
                        "title": row.title or "",
                        "abstract": row.abstract or "",
                        "filing_date": self._format_date(row.filing_date),
                        "publication_date": self._format_date(row.publication_date),
                        "country": row.country_code,
                    }
                )

            # Log completion with metrics
            completion_extra = {
                **log_extra,
                "results_count": len(patents),
                "bytes_processed": (
                    results.total_bytes_processed
                    if hasattr(results, "total_bytes_processed")
                    else 0
                ),
                "bytes_billed": (
                    results.total_bytes_billed if hasattr(results, "total_bytes_billed") else 0  # type: ignore[attr-defined]
                ),
            }

            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_cpc_search_completed", extra=completion_extra)

            return patents

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_cpc_search_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery CPC search error: {e}", file=sys.stderr)

            raise

    def _format_date(self, date_int: Optional[int]) -> Optional[str]:
        """Convert YYYYMMDD integer to YYYY-MM-DD string"""
        if not date_int:
            return None

        try:
            date_str = str(date_int)
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return date_str
        except Exception:
            return None


def check_bigquery_available() -> dict[str, Any]:
    """
    Check if BigQuery is available and configured

    Returns:
        Status dictionary
    """
    if not BIGQUERY_AVAILABLE:
        return {
            "available": False,
            "error": "google-cloud-bigquery not installed",
            "install_command": "pip install google-cloud-bigquery db-dtypes",
        }

    try:
        searcher = BigQueryPatentSearch()
        return searcher.check_availability()
    except Exception as e:
        return {"available": False, "error": str(e)}
