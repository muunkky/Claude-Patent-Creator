#!/usr/bin/env python3
"""Fix all paths in skills to use plugin-relative paths"""
import re
from pathlib import Path

plugin_root = Path(__file__).parent

# Find all SKILL.md files
skill_files = list(plugin_root.glob("skills/*/SKILL.md"))
agent_files = list(plugin_root.glob("agents/*.md"))
command_files = list(plugin_root.glob("commands/*.md"))

all_files = skill_files + agent_files + command_files

# Replacements to make
replacements = [
    (
        r"sys\.path\.insert\(0, r'C:\\Users\\<YOUR_USER>\\Desktop\\FINAL'\)",
        "sys.path.insert(0, os.path.join(os.environ.get('CLAUDE_PLUGIN_ROOT', '.'), 'python'))",
    ),
    (r"from mcp_server\.", "from python."),
    (r"C:\\Users\\<YOUR_USER>\\Desktop\\FINAL\\mcp_server", "${CLAUDE_PLUGIN_ROOT}/python"),
    (r"C:\\Users\\<YOUR_USER>\\Desktop\\FINAL\\pdfs", "${CLAUDE_PLUGIN_ROOT}/pdfs"),
    (r"C:\\Users\\<YOUR_USER>\\Desktop\\FINAL", "${CLAUDE_PLUGIN_ROOT}"),
]

for file_path in all_files:
    print(f"Processing {file_path}")
    content = file_path.read_text(encoding="utf-8")

    for old, new in replacements:
        content = re.sub(old, new, content)

    file_path.write_text(content, encoding="utf-8")
    print(f"  Updated {file_path.name}")

print(f"\nFixed {len(all_files)} files")
