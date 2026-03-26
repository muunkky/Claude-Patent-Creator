"""
Patent Diagrams Skill
Provides diagram generation operations for patent-style technical illustrations.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add mcp_server to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from mcp_server.diagram_generator import PatentDiagramGenerator, check_graphviz_installed
except ImportError as e:
    raise ImportError(
        f"Could not import diagram generator from mcp_server: {e}\n"
        "Make sure mcp_server is installed."
    )


# Global generator instance (lazy-loaded)
_diagram_generator: "PatentDiagramGenerator | None" = None


def _get_generator() -> PatentDiagramGenerator:
    """Get or initialize the diagram generator singleton."""
    global _diagram_generator
    if _diagram_generator is None:
        # Create diagrams directory in project root
        diagrams_dir = PROJECT_ROOT / "diagrams"
        diagrams_dir.mkdir(exist_ok=True)
        _diagram_generator = PatentDiagramGenerator(output_dir=diagrams_dir)
    return _diagram_generator


def _timestamp_filename(base_name: str) -> str:
    """Generate a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}"


def create_flowchart(steps: list[str]) -> dict[str, Any]:
    """
    Create a flowchart from an ordered list of steps.

    Args:
        steps: List of step descriptions (strings)

    Returns:
        Dictionary with success status and SVG path, or error information
    """
    # Input validation
    if not steps or not isinstance(steps, list):
        return {"success": False, "error": "Steps must be a non-empty list of strings"}

    if len(steps) == 0:
        return {"success": False, "error": "Steps list cannot be empty"}

    # Convert simple list to flowchart format
    flowchart_steps = []

    # Add start node
    flowchart_steps.append(
        {
            "id": "start",
            "label": "Start",
            "shape": "ellipse",
            "next": ["step_0"] if len(steps) > 0 else ["end"],
        }
    )

    # Add step nodes
    for i, step in enumerate(steps):
        step_id = f"step_{i}"
        next_id = f"step_{i+1}" if i < len(steps) - 1 else "end"

        flowchart_steps.append(
            {"id": step_id, "label": str(step), "shape": "box", "next": [next_id]}
        )

    # Add end node
    flowchart_steps.append({"id": "end", "label": "End", "shape": "ellipse", "next": []})

    # Generate filename
    filename = _timestamp_filename("flowchart")

    try:
        # Check Graphviz availability
        graphviz_status = check_graphviz_installed()
        if not graphviz_status.get("ready", False):
            return {
                "success": False,
                "error": "Graphviz is not properly installed",
                "graphviz_check": graphviz_status,
            }

        # Create the diagram
        generator = _get_generator()
        svg_path = generator.create_flowchart(
            steps=flowchart_steps, filename=filename, output_format="svg"
        )

        return {
            "success": True,
            "svg_path": str(svg_path.absolute()),
            "filename": svg_path.name,
            "message": f"Flowchart created successfully with {len(steps)} steps",
        }

    except ImportError as e:
        graphviz_status = check_graphviz_installed()
        return {"success": False, "error": str(e), "graphviz_check": graphviz_status}
    except Exception as e:
        return {"success": False, "error": f"Failed to create flowchart: {str(e)}"}


def create_block_diagram(blocks: list[dict], connections: list[dict]) -> dict[str, Any]:
    """
    Create a block diagram showing components and connections.

    Args:
        blocks: List of block definitions, each with:
                - id (str): Unique identifier
                - label (str): Display text
                - type (str, optional): Block type (input/output/process/storage/decision/default)
        connections: List of connection definitions, each with:
                     - from_id (str): Source block ID
                     - to_id (str): Target block ID
                     - label (str, optional): Connection label

    Returns:
        Dictionary with success status and SVG path, or error information
    """
    # Input validation
    if not blocks or not isinstance(blocks, list):
        return {"success": False, "error": "Blocks must be a non-empty list"}

    if not connections or not isinstance(connections, list):
        return {"success": False, "error": "Connections must be a non-empty list"}

    # Validate block structure
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            return {"success": False, "error": f"Block {i} must be a dictionary"}
        if "id" not in block:
            return {"success": False, "error": f"Block {i} missing required 'id' field"}
        if "label" not in block:
            return {
                "success": False,
                "error": f"Block {i} (id={block.get('id')}) missing required 'label' field",
            }

    # Validate connection structure
    block_ids = {block["id"] for block in blocks}
    for i, conn in enumerate(connections):
        if not isinstance(conn, dict):
            return {"success": False, "error": f"Connection {i} must be a dictionary"}
        if "from_id" not in conn:
            return {"success": False, "error": f"Connection {i} missing required 'from_id' field"}
        if "to_id" not in conn:
            return {"success": False, "error": f"Connection {i} missing required 'to_id' field"}

        # Check that referenced blocks exist
        if conn["from_id"] not in block_ids:
            return {
                "success": False,
                "error": f"Connection {i}: from_id '{conn['from_id']}' references non-existent block",
            }
        if conn["to_id"] not in block_ids:
            return {
                "success": False,
                "error": f"Connection {i}: to_id '{conn['to_id']}' references non-existent block",
            }

    # Convert connections to tuple format expected by generator
    connection_tuples = []
    for conn in connections:
        from_id = conn["from_id"]
        to_id = conn["to_id"]
        label = conn.get("label", "")
        connection_tuples.append((from_id, to_id, label if label else None))

    # Generate filename
    filename = _timestamp_filename("block_diagram")

    try:
        # Check Graphviz availability
        graphviz_status = check_graphviz_installed()
        if not graphviz_status.get("ready", False):
            return {
                "success": False,
                "error": "Graphviz is not properly installed",
                "graphviz_check": graphviz_status,
            }

        # Create the diagram
        generator = _get_generator()
        svg_path = generator.create_block_diagram(
            blocks=blocks, connections=connection_tuples, filename=filename, output_format="svg"
        )

        return {
            "success": True,
            "svg_path": str(svg_path.absolute()),
            "filename": svg_path.name,
            "message": f"Block diagram created with {len(blocks)} blocks and {len(connections)} connections",
        }

    except ImportError as e:
        graphviz_status = check_graphviz_installed()
        return {"success": False, "error": str(e), "graphviz_check": graphviz_status}
    except Exception as e:
        return {"success": False, "error": f"Failed to create block diagram: {str(e)}"}


def render_diagram(dot: str) -> dict[str, Any]:
    """
    Render arbitrary Graphviz DOT code into a diagram.

    Args:
        dot: Graphviz DOT language code (complete digraph/graph definition)

    Returns:
        Dictionary with success status and SVG path, or error information
    """
    # Input validation
    if not dot or not isinstance(dot, str):
        return {"success": False, "error": "DOT code must be a non-empty string"}

    dot = dot.strip()

    if not dot:
        return {"success": False, "error": "DOT code cannot be empty"}

    # Basic validation that it looks like DOT code
    if not (dot.startswith("digraph") or dot.startswith("graph")):
        return {"success": False, "error": "DOT code must start with 'digraph' or 'graph'"}

    # Generate filename
    filename = _timestamp_filename("diagram")

    try:
        # Check Graphviz availability
        graphviz_status = check_graphviz_installed()
        if not graphviz_status.get("ready", False):
            return {
                "success": False,
                "error": "Graphviz is not properly installed",
                "graphviz_check": graphviz_status,
            }

        # Render the diagram
        generator = _get_generator()
        svg_path = generator.render_dot_diagram(
            dot_code=dot, filename=filename, output_format="svg"
        )

        return {
            "success": True,
            "svg_path": str(svg_path.absolute()),
            "filename": svg_path.name,
            "message": "Diagram rendered successfully",
        }

    except ImportError as e:
        graphviz_status = check_graphviz_installed()
        return {"success": False, "error": str(e), "graphviz_check": graphviz_status}
    except Exception as e:
        return {"success": False, "error": f"Failed to render diagram: {str(e)}"}


def add_diagram_references(svg_path: str, reference_map: "dict[str, int]") -> dict[str, Any]:
    """
    Add patent-style reference numbers to an existing SVG diagram.

    Args:
        svg_path: Path to the input SVG file
        reference_map: Mapping of element text to reference number
                      (e.g., {"Input Sensor": 10, "Processor": 20})

    Returns:
        Dictionary with success status and annotated SVG path, or error information
    """
    # Input validation
    if not svg_path or not isinstance(svg_path, str):
        return {"success": False, "error": "svg_path must be a non-empty string"}

    if not reference_map or not isinstance(reference_map, dict):
        return {"success": False, "error": "reference_map must be a non-empty dictionary"}

    # Convert string path to Path object
    svg_path_obj = Path(svg_path)

    if not svg_path_obj.exists():
        return {"success": False, "error": f"SVG file not found: {svg_path}"}

    if svg_path_obj.suffix.lower() != ".svg":
        return {"success": False, "error": f"File must be an SVG file, got: {svg_path_obj.suffix}"}

    try:
        # Add reference numbers
        generator = _get_generator()
        annotated_path = generator.add_reference_numbers(
            svg_path=svg_path_obj, reference_map=reference_map
        )

        return {
            "success": True,
            "svg_path": str(annotated_path.absolute()),
            "original_path": str(svg_path_obj.absolute()),
            "filename": annotated_path.name,
            "references_added": len(reference_map),
            "message": f"Added {len(reference_map)} reference numbers to diagram",
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to add references: {str(e)}"}


def get_diagram_templates() -> dict[str, Any]:
    """
    Get pre-built diagram templates for common patent illustration patterns.

    Returns:
        Dictionary with success status and template information
    """
    try:
        generator = _get_generator()
        templates_dict = generator.get_templates()

        # Enrich with descriptions
        template_info = {
            "simple_flowchart": {
                "name": "Simple Flowchart",
                "description": "Basic method flow with start/end, steps, and a decision point",
                "dot_code": templates_dict["simple_flowchart"],
            },
            "system_block": {
                "name": "System Block Diagram",
                "description": "System architecture with input/controller/processor/memory/output components",
                "dot_code": templates_dict["system_block"],
            },
            "method_steps": {
                "name": "Method Steps",
                "description": "Patent method claims with numbered steps (101, 102, 103...)",
                "dot_code": templates_dict["method_steps"],
            },
            "component_hierarchy": {
                "name": "Component Hierarchy",
                "description": "Hierarchical system/subsystem/component tree structure",
                "dot_code": templates_dict["component_hierarchy"],
            },
        }

        return {
            "success": True,
            "templates": template_info,
            "template_names": list(template_info.keys()),
            "message": f"Retrieved {len(template_info)} diagram templates",
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to get templates: {str(e)}"}


def check_graphviz_status() -> dict[str, Any]:
    """
    Check Graphviz installation status.

    Returns:
        Dictionary with installation status and instructions
    """
    try:
        status = check_graphviz_installed()
        return {"success": True, **status}
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to check Graphviz status: {str(e)}",
            "ready": False,
        }
