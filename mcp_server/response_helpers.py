"""
Response helper functions for MCP tools.

Provides consistent response formats across all MCP tools with standardized
success and error structures.

Usage:
    from response_helpers import success_response, error_response

    @mcp.tool()
    def my_tool(param: str):
        try:
            result = do_work(param)
            return success_response(result, "Operation completed")
        except ValueError as e:
            return error_response(e, {"param": param})
"""

from typing import Any, Optional, Union


def success_response(data: Any = None, message: str = "", **extra_fields: Any) -> dict[str, Any]:
    """Create a standardized success response for MCP tools.

    Args:
        data: The main response data (results, output, etc.)
        message: Human-readable success message
        **extra_fields: Additional fields to include in response

    Returns:
        Dictionary with success=True, data, message, and any extra fields

    Example:
        >>> result = success_response(
        ...     data={"results": [1, 2, 3]},
        ...     message="Found 3 results",
        ...     count=3
        ... )
        >>> print(result)
        {
            "success": True,
            "data": {"results": [1, 2, 3]},
            "message": "Found 3 results",
            "count": 3
        }
    """
    response = {"success": True, "message": message}

    if data is not None:
        response["data"] = data

    response.update(extra_fields)

    return response


def error_response(
    error: Union[Exception, str],
    context: Optional[dict[str, Any]] = None,
    error_type: Optional[str] = None,
) -> dict[str, Any]:
    """Create a standardized error response for MCP tools.

    Args:
        error: Exception object or error message string
        context: Optional context dict with debugging information
        error_type: Optional explicit error type override

    Returns:
        Dictionary with success=False, error message, type, and context

    Example:
        >>> try:
        ...     raise ValueError("Invalid input")
        ... except ValueError as e:
        ...     result = error_response(e, {"input": "bad_value"})
        >>> print(result)
        {
            "success": False,
            "error": "Invalid input",
            "error_type": "ValueError",
            "context": {"input": "bad_value"}
        }
    """
    if isinstance(error, Exception):
        error_message = str(error)
        error_type_name = error_type or type(error).__name__
    else:
        error_message = str(error)
        error_type_name = error_type or "Error"

    response = {"success": False, "error": error_message, "error_type": error_type_name}

    if context:
        response["context"] = context

    return response


def partial_success_response(
    data: Any, warnings: list[str], message: str = "", **extra_fields: Any
) -> dict[str, Any]:
    """Create a response for operations that partially succeeded.

    Use when an operation completes but with warnings or partial failures.

    Args:
        data: The partial results
        warnings: List of warning messages
        message: Human-readable summary message
        **extra_fields: Additional fields to include

    Returns:
        Dictionary with success=True, data, warnings, and message

    Example:
        >>> result = partial_success_response(
        ...     data={"processed": 8, "failed": 2},
        ...     warnings=["Item 3 failed", "Item 7 failed"],
        ...     message="Processed 8 of 10 items"
        ... )
        >>> print(result["success"], len(result["warnings"]))
        True 2
    """
    response = {"success": True, "data": data, "warnings": warnings, "message": message}

    response.update(extra_fields)

    return response


def validation_error_response(field: str, issue: str, value: Any = None) -> dict[str, Any]:
    """Create a response for validation errors.

    Args:
        field: Name of the field that failed validation
        issue: Description of the validation issue
        value: Optional value that failed validation

    Returns:
        Dictionary with success=False and validation details

    Example:
        >>> result = validation_error_response(
        ...     field="email",
        ...     issue="Invalid email format",
        ...     value="not-an-email"
        ... )
        >>> print(result["error_type"])
        ValidationError
    """
    response = {
        "success": False,
        "error": f"Validation failed for '{field}': {issue}",
        "error_type": "ValidationError",
        "field": field,
        "issue": issue,
    }

    if value is not None:
        response["value"] = value

    return response


def not_found_response(resource_type: str, identifier: Any, suggestion: str = "") -> dict[str, Any]:
    """Create a response for resource not found errors.

    Args:
        resource_type: Type of resource (e.g., "MPEP section", "patent", "file")
        identifier: The identifier that was not found
        suggestion: Optional suggestion for the user

    Returns:
        Dictionary with success=False and not found details

    Example:
        >>> result = not_found_response(
        ...     resource_type="MPEP section",
        ...     identifier="9999",
        ...     suggestion="Try section 2173 for definiteness"
        ... )
        >>> print(result["error"])
        MPEP section not found: 9999
    """
    error_message = f"{resource_type} not found: {identifier}"

    if suggestion:
        error_message += f". {suggestion}"

    return {
        "success": False,
        "error": error_message,
        "error_type": "NotFoundError",
        "resource_type": resource_type,
        "identifier": identifier,
    }
