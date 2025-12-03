"""Highway DSL MCP Server - Wraps the dsl.rodmena.app API.

This MCP server exposes the Highway DSL generation service to MCP clients,
allowing LLMs to generate workflows via natural language.

Usage:
    # Run as stdio server (for Claude Desktop)
    highway-dsl-client

    # Or directly
    python -m highway_dsl.mcp_client_server
"""

import os
import requests
from typing import Any

from mcp.server.fastmcp import FastMCP

# Configuration
DSL_API_URL = os.getenv("DSL_API_URL", "https://dsl.rodmena.app")

# Initialize MCP server
mcp = FastMCP(
    "Highway DSL Generator",
    instructions="""You are a Highway Workflow Engine expert.

Use the generate_workflow tool to create workflows from natural language descriptions.
The tool returns pure Python code that defines a Highway DSL workflow.

Example usage:
- "Create a workflow that fetches data from an API and sends an email"
- "Build a parallel workflow with 3 branches that process files"
- "Make a workflow with retry logic for flaky HTTP requests"
""",
)


@mcp.tool()
def generate_workflow(description: str) -> dict[str, Any]:
    """Generate a Highway DSL workflow from natural language description.

    This tool calls the Highway DSL generation service to convert your
    natural language workflow description into valid, executable Python code.

    Args:
        description: Natural language description of the workflow you want to create.
                    Be specific about:
                    - What tasks should run (shell commands, HTTP requests, etc.)
                    - Whether tasks should run in parallel or sequentially
                    - Any conditions, loops, or error handling needed

    Returns:
        Dictionary with:
        - success: bool - Whether generation succeeded
        - code: str - The generated Python code (if successful)
        - error: str - Error message (if failed)

    Examples:
        - "Create a workflow that runs 3 shell commands in parallel"
        - "Build a workflow that fetches JSON from an API, processes it with Python, and sends an email"
        - "Make a data pipeline that extracts, transforms, and loads data with retry logic"
    """
    try:
        # Call the DSL generation API
        response = requests.get(
            f"{DSL_API_URL}/api/v1/generate_dsl",
            params={"input": description},
            timeout=120,
        )

        if response.status_code == 200:
            return {
                "success": True,
                "code": response.text,
                "message": "Workflow generated successfully. The code is ready to execute.",
            }
        else:
            error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"error": response.text}
            return {
                "success": False,
                "error": error_data.get("error", "Unknown error"),
                "details": error_data.get("details", ""),
            }

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timed out after 120 seconds",
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": f"Cannot connect to DSL service at {DSL_API_URL}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def check_service_health() -> dict[str, Any]:
    """Check if the Highway DSL generation service is available.

    Returns:
        Dictionary with service health status and configuration.
    """
    try:
        response = requests.get(f"{DSL_API_URL}/health", timeout=10)
        if response.status_code == 200:
            return {
                "healthy": True,
                "service_url": DSL_API_URL,
                **response.json(),
            }
        else:
            return {
                "healthy": False,
                "service_url": DSL_API_URL,
                "error": f"Service returned status {response.status_code}",
            }
    except Exception as e:
        return {
            "healthy": False,
            "service_url": DSL_API_URL,
            "error": str(e),
        }


@mcp.resource("highway://service-info")
def service_info() -> str:
    """Information about the Highway DSL generation service."""
    return f"""# Highway DSL Generation Service

**Service URL:** {DSL_API_URL}

## Available Tools

### generate_workflow
Generate a Highway DSL workflow from natural language.

**Usage:** Describe what you want the workflow to do, and the service will generate valid Python code.

**Example descriptions:**
- "Create a workflow with 3 parallel tasks that run shell commands"
- "Build an ETL pipeline that fetches data, transforms it, and loads to database"
- "Make a workflow that calls an LLM to summarize text and emails the result"

### check_service_health
Check if the generation service is online and available.

## Notes
- Generated code uses Highway DSL (from highway_dsl import WorkflowBuilder)
- Code ends with: print(get_workflow().to_json())
- Parallel workflows include explicit wait tasks
"""


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
