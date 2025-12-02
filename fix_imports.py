#!/usr/bin/env python3
"""Fix all mcp_server imports to be relative"""
import re
from pathlib import Path

python_dir = Path(__file__).parent / "python"

# Get all .py files
py_files = list(python_dir.glob("*.py")) + list(python_dir.glob("**/*.py"))

print(f"Found {len(py_files)} Python files")

for file_path in py_files:
    content = file_path.read_text(encoding="utf-8")
    original = content

    # Replace all mcp_server imports with relative imports
    # from mcp_server.X import Y -> from X import Y
    content = re.sub(r"from mcp_server\.", "from ", content)

    # import mcp_server.X -> import X
    content = re.sub(r"import mcp_server\.", "import ", content)

    if content != original:
        file_path.write_text(content, encoding="utf-8")
        print(f"Fixed: {file_path.name}")

print("\nDone fixing imports")
