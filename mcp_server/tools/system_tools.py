"""
System Configuration and Utilities Tools

Provides MCP tools for system configuration management and index statistics:
- setup_claude_config: Copy .claude configuration to project directories
- get_index_stats: Retrieve statistics about the MPEP index

Tools:
    - setup_claude_config: Deploy .claude folder with commands and skills
    - get_index_stats: Get MPEP index statistics and metadata

Dependencies:
    - Path, shutil from standard library
    - mpep_index: MPEPIndex instance for statistics
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict


def register_system_tools(
    mcp,
    mpep_index,
    patent_corpus_index,
    log_info,
    log_error,
    BEST_PRACTICES_AVAILABLE,
):
    """Register system configuration and utility tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mpep_index: Initialized MPEPIndex for index statistics
        patent_corpus_index: Patent corpus index instance
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        BEST_PRACTICES_AVAILABLE: Flag indicating if best practices modules are available
    """

    @mcp.tool()
    def setup_claude_config(project_directory: str) -> Dict[str, Any]:
        """
        Copy .claude configuration (commands and skills) to a project directory.

        This tool copies the patent creator's .claude folder (containing slash commands
        and skills) to the specified project directory, making the commands available
        for that project.

        Args:
            project_directory: Absolute path to the project directory where .claude should be copied

        Returns:
            Dictionary with success status, message, and list of items copied

        Example:
            setup_claude_config("/path/to/my/project")
        """
        try:
            # Get the source .claude directory (from the MCP server package)
            server_root = Path(__file__).parent.parent.resolve()
            source_claude = server_root / ".claude"

            # Validate source exists
            if not source_claude.exists():
                return {
                    "success": False,
                    "error": f".claude directory not found at {source_claude}",
                    "message": "Source .claude directory is missing from the MCP server installation",
                }

            # Validate and create destination path
            try:
                dest_path = Path(project_directory).resolve()
                if not dest_path.exists():
                    return {
                        "success": False,
                        "error": f"Project directory does not exist: {project_directory}",
                        "message": "Please provide a valid existing directory path",
                    }

                # Reject system directories to prevent writing to sensitive locations
                dest_resolved = dest_path.resolve()
                if sys.platform == "win32":
                    restricted = [
                        os.environ.get("SystemRoot", r"C:\Windows"),
                        os.environ.get("ProgramFiles", r"C:\Program Files"),
                        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                    ]
                    for r in restricted:
                        r_resolved = Path(r).resolve()
                        try:
                            dest_resolved.relative_to(r_resolved)
                            # dest_path is inside a restricted directory
                            return {
                                "success": False,
                                "error": f"Cannot write to system directory: {dest_path}",
                                "message": "Please provide a project directory, not a system directory",
                            }
                        except ValueError:
                            pass  # Not inside this restricted path
                else:
                    restricted_posix = ["/etc", "/usr", "/bin", "/sbin", "/var", "/boot", "/lib", "/proc", "/sys"]
                    dest_str = str(dest_resolved)
                    if dest_str == "/" or any(
                        dest_str == r or dest_str.startswith(r + "/")
                        for r in restricted_posix
                    ):
                        return {
                            "success": False,
                            "error": f"Cannot write to system directory: {dest_path}",
                            "message": "Please provide a project directory, not a system directory",
                        }

                dest_claude = dest_path / ".claude"

            except Exception as e:
                return {
                    "success": False,
                    "error": f"Invalid project directory path: {e}",
                    "message": "Please provide a valid absolute path to the project directory",
                }

            # Track what we copy
            copied_items = []
            skipped_items = []

            # Create destination .claude directory if it doesn't exist
            dest_claude.mkdir(parents=True, exist_ok=True)

            # Copy each item from source .claude to destination
            for item in source_claude.iterdir():
                item_name = item.name
                dest_item = dest_claude / item_name

                try:
                    if item.is_dir():
                        # Remove existing directory if present
                        if dest_item.exists() and dest_item.is_dir():
                            shutil.rmtree(dest_item)
                        elif dest_item.exists():
                            dest_item.unlink()

                        # Copy directory recursively
                        shutil.copytree(item, dest_item)
                        copied_items.append(f"{item_name}/ (directory)")

                    elif item.is_file():
                        # Copy file, overwriting if exists
                        shutil.copy2(item, dest_item)
                        copied_items.append(f"{item_name} (file)")

                except Exception as e:
                    skipped_items.append(f"{item_name}: {str(e)}")

            # Build result message
            if not copied_items and not skipped_items:
                return {
                    "success": False,
                    "message": "No items found in source .claude directory",
                    "destination": str(dest_claude),
                }

            result = {
                "success": True,
                "message": f"Successfully copied .claude configuration to {dest_claude}",
                "destination": str(dest_claude),
                "items_copied": len(copied_items),
                "copied_items": copied_items,
            }

            if skipped_items:
                result["items_skipped"] = len(skipped_items)
                result["skipped_items"] = skipped_items
                result["message"] += f" ({len(skipped_items)} items skipped)"

            return result

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Failed to copy .claude configuration: {str(e)}",
            }

    @mcp.resource("mpep://index/stats")
    def get_index_stats() -> str:
        """Get statistics about the MPEP index"""
        stats = {
            "total_chunks": len(mpep_index.chunks),
            "total_metadata": len(mpep_index.metadata),
            "index_exists": mpep_index.index is not None,
            "sections": len(set(m["section"] for m in mpep_index.metadata)),
        }
        return json.dumps(stats, indent=2)
