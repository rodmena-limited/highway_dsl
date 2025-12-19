"""Graphviz DOT file generation for Highway workflows.

This module provides functionality to generate Graphviz DOT files from Highway workflow
definitions using the robust DiagramGenerator.
"""

from typing import Any, Dict, List, Optional

from highway_dsl.diagrams import DiagramGenerator
from highway_dsl.workflow_dsl import Workflow


def generate_dot(
    workflow_definition: dict[str, Any],
    execution_steps: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate a Graphviz DOT file from a workflow definition.

    Args:
        workflow_definition: Workflow definition dict (from WorkflowBuilder.build().model_dump())
        execution_steps: Optional list of execution steps (currently unused in new generator).

    Returns:
        DOT file content as a string
    """
    # Convert dictionary to Workflow object
    try:
        workflow = Workflow.model_validate(workflow_definition)
    except Exception as e:
        # Fallback for error message in the graph itself if validation fails
        return f"""digraph error {{
            node [shape=box, style=filled, fillcolor=\"#ffcccc\", color=\"#ff0000\"];
            error [label=\"Error parsing workflow definition:\\n{str(e)}\"];
        }}"""

    generator = DiagramGenerator(workflow)
    return generator.to_graphviz()
