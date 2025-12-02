"""
Pydantic models for input validation of MCP tools.

Provides type-safe validation with clear error messages.
"""

# pyright: reportCallInDefaultInitializer=false

from typing import Optional, Literal, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import BaseModel, Field, field_validator, conint, constr

    PYDANTIC_AVAILABLE = True
else:
    try:
        from pydantic import BaseModel, Field, field_validator, conint, constr

        PYDANTIC_AVAILABLE = True
    except ImportError:
        PYDANTIC_AVAILABLE = False

        # Fallback when Pydantic not available
        class BaseModel:
            pass

        def Field(*args: Any, **kwargs: Any) -> Any:
            return None

        def field_validator(*args: Any, **kwargs: Any) -> Any:
            def decorator(f: Any) -> Any:
                return f

            return decorator

        def conint(**kwargs: Any) -> type:
            return int

        def constr(**kwargs: Any) -> type:
            return str


if PYDANTIC_AVAILABLE:
    # Search Input Models

    class SearchMPEPInput(BaseModel):  # type: ignore[misc]
        """Input validation for MPEP search."""

        query: constr(min_length=1, max_length=1000) = Field(  # type: ignore[valid-type]
            ..., description="Search query text", examples=["35 USC 112 enablement requirements"]
        )
        top_k: conint(ge=1, le=20) = Field(  # type: ignore[valid-type]
            default=5, description="Number of results to return (1-20)"
        )
        retrieve_k: Optional[conint(ge=1, le=100)] = Field(  # type: ignore[valid-type]
            default=None, description="Number of candidates to retrieve before reranking"
        )
        source_filter: Optional[str] = Field(
            default=None, description="Filter by source (MPEP, 35_USC, 37_CFR, SUBSEQUENT)"
        )
        is_statute: Optional[bool] = Field(default=None, description="Filter for statutes only")
        is_regulation: Optional[bool] = Field(
            default=None, description="Filter for regulations only"
        )
        is_update: Optional[bool] = Field(default=None, description="Filter for updates only")

        @field_validator("source_filter")
        @classmethod
        def validate_source_filter(cls, v: Optional[str]) -> Optional[str]:
            """Validate source filter."""
            if v is not None:
                valid_sources = {"MPEP", "35_USC", "37_CFR", "SUBSEQUENT"}
                if v not in valid_sources:
                    raise ValueError(f"source_filter must be one of {valid_sources}")
            return v

    class SearchBigQueryInput(BaseModel):  # type: ignore[misc]
        """Input validation for BigQuery patent search."""

        query: constr(min_length=1, max_length=500) = Field(  # type: ignore[valid-type]
            ...,
            description="Search query keywords",
            examples=["machine learning image recognition"],
        )
        limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
            default=20, description="Maximum number of results (1-100)"
        )
        country: constr(min_length=2, max_length=2) = Field(  # type: ignore[valid-type]
            default="US", description="Two-letter country code"
        )
        start_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
            default=None, description="Filter patents filed on or after this year"
        )
        end_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
            default=None, description="Filter patents filed on or before this year"
        )

        @field_validator("end_year")
        @classmethod
        def validate_year_range(cls, v: Optional[int], info) -> Optional[int]:
            """Validate year range."""
            if v is not None and "start_year" in info.data:
                start_year = info.data["start_year"]
                if start_year is not None and v < start_year:
                    raise ValueError("end_year must be >= start_year")
            return v

        @field_validator("country")
        @classmethod
        def validate_country_code(cls, v: str) -> str:
            """Validate country code format."""
            return v.upper()

    class SearchUSPTOInput(BaseModel):  # type: ignore[misc]
        """Input validation for USPTO API search."""

        query: constr(min_length=1, max_length=500) = Field(..., description="Search query text")  # type: ignore[valid-type]
        limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
            default=25, description="Maximum number of results (1-100)"
        )
        start_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
            default=None, description="Filter by filing year start"
        )
        end_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
            default=None, description="Filter by filing year end"
        )
        application_type: Optional[str] = Field(
            default=None, description="Filter by application type (e.g., 'Utility')"
        )
        status: Optional[str] = Field(default=None, description="Filter by patent status")

    class GetPatentInput(BaseModel):  # type: ignore[misc]
        """Input validation for getting patent details."""

        patent_number: constr(min_length=1, max_length=50) = Field(  # type: ignore[valid-type]
            ...,
            description="Patent number (e.g., '10123456', 'US10123456')",
            examples=["10123456", "US10123456B2"],
        )

        @field_validator("patent_number")
        @classmethod
        def sanitize_patent_number(cls, v: str) -> str:
            """Remove common formatting characters."""
            # Remove commas, spaces, hyphens
            return v.replace(",", "").replace(" ", "").replace("-", "").strip()

    class CPCSearchInput(BaseModel):  # type: ignore[misc]
        """Input validation for CPC code search."""

        cpc_code: constr(min_length=1, max_length=50) = Field(  # type: ignore[valid-type]
            ...,
            description="CPC classification code or prefix",
            examples=["G06F", "G06F16/", "H04L29/06"],
        )
        limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
            default=20, description="Maximum number of results (1-100)"
        )
        country: constr(min_length=2, max_length=2) = Field(  # type: ignore[valid-type]
            default="US", description="Two-letter country code"
        )

    # Review Input Models

    class ReviewClaimsInput(BaseModel):  # type: ignore[misc]
        """Input validation for patent claims review."""

        claims_text: constr(min_length=10, max_length=50000) = Field(  # type: ignore[valid-type]
            ..., description="Patent claims text to analyze"
        )

        @field_validator("claims_text")
        @classmethod
        def validate_claims_format(cls, v: str) -> str:
            """Basic validation of claims text."""
            v = v.strip()
            if not v:
                raise ValueError("claims_text cannot be empty or whitespace")
            return v

    class ReviewSpecificationInput(BaseModel):  # type: ignore[misc]
        """Input validation for specification review."""

        claims_text: constr(min_length=10, max_length=50000) = Field(  # type: ignore[valid-type]
            ..., description="Patent claims text"
        )
        specification: constr(min_length=100, max_length=200000) = Field(  # type: ignore[valid-type]
            ..., description="Patent specification text"
        )

    class CheckFormalitiesInput(BaseModel):  # type: ignore[misc]
        """Input validation for formalities checking."""

        title: Optional[constr(max_length=500)] = Field(  # type: ignore[valid-type]
            default=None, description="Patent application title"
        )
        abstract: Optional[constr(max_length=5000)] = Field(  # type: ignore[valid-type]
            default=None, description="Patent abstract"
        )
        specification: Optional[constr(max_length=200000)] = Field(  # type: ignore[valid-type]
            default=None, description="Patent specification"
        )
        drawings_present: bool = Field(default=False, description="Whether drawings are included")

    # Diagram Input Models

    class RenderDiagramInput(BaseModel):  # type: ignore[misc]
        """Input validation for diagram rendering."""

        dot_code: constr(min_length=10, max_length=50000) = Field(  # type: ignore[valid-type]
            ..., description="Graphviz DOT code for the diagram"
        )
        filename: constr(min_length=1, max_length=100) = Field(  # type: ignore[valid-type]
            default="diagram", description="Output filename (without extension)"
        )
        output_format: Literal["svg", "png", "pdf"] = Field(
            default="svg", description="Output format"
        )
        engine: Literal["dot", "neato", "fdp", "circo", "twopi"] = Field(
            default="dot", description="Graphviz layout engine"
        )

        @field_validator("filename")
        @classmethod
        def sanitize_filename(cls, v: str) -> str:
            """Sanitize filename to prevent path traversal."""
            # Remove path separators and dangerous characters
            dangerous_chars = ["/", "\\", "..", "<", ">", ":", '"', "|", "?", "*"]
            for char in dangerous_chars:
                v = v.replace(char, "_")
            return v.strip()

    class CreateBlockDiagramInput(BaseModel):  # type: ignore[misc]
        """Input validation for block diagram creation."""

        blocks: list = Field(..., description="List of block definitions")
        connections: list = Field(..., description="List of connections between blocks")
        filename: constr(min_length=1, max_length=100) = Field(  # type: ignore[valid-type]
            default="block_diagram", description="Output filename"
        )
        output_format: Literal["svg", "png", "pdf"] = Field(
            default="svg", description="Output format"
        )

    # Helper function for validation

    def validate_input(model_class: type[BaseModel], **kwargs):  # type: ignore[no-redef]
        """
        Validate input using a Pydantic model.

        Args:
            model_class: Pydantic model class to use for validation
            **kwargs: Input parameters to validate

        Returns:
            Validated model instance

        Raises:
            ValueError: If validation fails with details
        """
        try:
            return model_class(**kwargs)
        except Exception as e:
            # Convert Pydantic validation error to user-friendly message
            if hasattr(e, "errors"):
                errors = e.errors()  # type: ignore[attr-defined]
                error_messages = []
                for error in errors:
                    field = " -> ".join(str(loc) for loc in error["loc"])
                    msg = error["msg"]
                    error_messages.append(f"{field}: {msg}")
                raise ValueError("Input validation failed:\n" + "\n".join(error_messages))
            else:
                raise ValueError(f"Input validation failed: {str(e)}")

else:
    # Fallback when Pydantic not available
    # Define empty classes for import compatibility
    class SearchMPEPInput:  # type: ignore[no-redef]
        pass

    class SearchBigQueryInput:  # type: ignore[no-redef]
        pass

    class SearchUSPTOInput:  # type: ignore[no-redef]
        pass

    class GetPatentInput:  # type: ignore[no-redef]
        pass

    class CPCSearchInput:  # type: ignore[no-redef]
        pass

    class ReviewClaimsInput:  # type: ignore[no-redef]
        pass

    class ReviewSpecificationInput:  # type: ignore[no-redef]
        pass

    class CheckFormalitiesInput:  # type: ignore[no-redef]
        pass

    class RenderDiagramInput:  # type: ignore[no-redef]
        pass

    class CreateBlockDiagramInput:  # type: ignore[no-redef]
        pass

    def validate_input(model_class, **kwargs):  # type: ignore[no-redef]
        """Fallback validation that does basic checks."""
        # Just return kwargs as-is since we can't validate without Pydantic
        return type("obj", (object,), kwargs)()
