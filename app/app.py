#!/usr/bin/env python3
"""
Highway DSL Generator API
A Flask API that generates Highway DSL workflows using Ollama LLM.
Uses MCP server functions for comprehensive DSL reference and validation.

Endpoint: GET /api/v1/generate_dsl?input=<workflow_description>
Port: 7291
"""

import os
import tempfile
import py_compile

import requests
from flask import Flask, request, jsonify, Response

# Import MCP server functions for DSL reference and validation
from highway_dsl.mcp_server import (
    HIGHWAY_DSL_INSTRUCTIONS,
    get_dsl_reference,
    get_example_patterns,
    list_available_tools,
    get_operator_reference,
    validate_workflow,
)

app = Flask(__name__)
# CORS is now handled by nginx

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3-vl:235b-instruct-cloud")


def build_agent_prompt():
    """Build comprehensive agent prompt from MCP server functions."""
    # Start with the main instructions
    prompt = HIGHWAY_DSL_INSTRUCTIONS

    # Add example patterns for reference
    patterns = get_example_patterns()
    prompt += "\n\n## READY-TO-USE EXAMPLE PATTERNS\n\n"
    for name, code in list(patterns.items())[:5]:  # Include top 5 examples
        prompt += f"### {name.replace('_', ' ').title()}\n```python\n{code}\n```\n\n"

    return prompt


# Build prompt at startup using MCP functions
AGENT_PROMPT = build_agent_prompt()
print(f"✓ Built agent prompt from MCP server ({len(AGENT_PROMPT)} chars)")
print("  - DSL instructions: included")
print(f"  - Example patterns: {len(get_example_patterns())} patterns")
print(f"  - Available tools: {len(list_available_tools())} tools")
print(f"  - Operators: {len(get_operator_reference())} operators")


def call_ollama(user_input):
    """
    Call Ollama API with the MCP-powered agent prompt and user input.

    Args:
        user_input: User's workflow description

    Returns:
        Generated Python code from the LLM

    Raises:
        Exception: If Ollama API call fails
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": AGENT_PROMPT},
            {"role": "user", "content": user_input},
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,  # Low temperature for more deterministic output
            "top_p": 0.9,
        },
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()
        generated_code = result.get("message", {}).get("content", "")

        if not generated_code:
            raise Exception("Empty response from Ollama")

        return generated_code

    except requests.exceptions.Timeout:
        raise Exception("Ollama API request timed out after 120 seconds")
    except requests.exceptions.ConnectionError:
        raise Exception(
            f"Cannot connect to Ollama at {OLLAMA_BASE_URL}. Is Ollama running?"
        )
    except requests.exceptions.HTTPError as e:
        raise Exception(f"Ollama API returned error: {e}")
    except Exception as e:
        raise Exception(f"Ollama API call failed: {str(e)}")


def clean_generated_code(code):
    """
    Clean the generated code by removing markdown formatting and trailing text.

    Args:
        code: Raw generated code from LLM

    Returns:
        Cleaned Python code
    """
    lines = code.strip().split("\n")

    # Remove markdown code fences if present
    if lines and lines[0].strip().startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]

    # Remove "python" language identifier if present
    if lines and lines[0].strip() == "python":
        lines = lines[1:]

    # Find where the Python code ends (look for the main block ending)
    code_end_idx = len(lines)
    for i, line in enumerate(lines):
        # If we find text after the main block, truncate there
        if "print(get_workflow().to_json())" in line:
            code_end_idx = i + 1
            break

    lines = lines[:code_end_idx]
    cleaned = "\n".join(lines).strip()

    # Fix common LLM mistakes
    # Replace model_dump with to_json
    if "model_dump" in cleaned or "import json" in cleaned:
        # Replace the entire main block
        if "if __name__" in cleaned:
            main_start = cleaned.find("if __name__")
            cleaned = (
                cleaned[:main_start]
                + """if __name__ == "__main__":
    print(get_workflow().to_json())
"""
            )

    return cleaned


def validate_python_syntax(code):
    """
    Validate Python code syntax using py_compile.

    Args:
        code: Python code string to validate

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Create a temporary file to compile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        tmp_file.write(code)

    try:
        # Attempt to compile the code
        py_compile.compile(tmp_path, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        # Extract error message
        error_msg = str(e)
        return False, error_msg
    except Exception as e:
        return False, f"Unexpected error during validation: {str(e)}"
    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def validate_with_mcp(code):
    """
    Validate workflow code using MCP server's validate_workflow function.

    Args:
        code: Python code string to validate

    Returns:
        tuple: (is_valid: bool, errors: list, warnings: list, info: dict)
    """
    try:
        result = validate_workflow(code)
        return (
            result.get("valid", False),
            result.get("errors", []),
            result.get("warnings", []),
            result.get("workflow_info", {}),
        )
    except Exception as e:
        return False, [str(e)], [], {}


@app.route("/api/v1/generate_dsl", methods=["GET"])
def generate_dsl():
    """
    Generate Highway DSL workflow from natural language description.

    Query Parameters:
        input: Workflow description in natural language

    Returns:
        200: Valid Python code for Highway DSL workflow
        400: Invalid request (missing input parameter)
        500: Generation failed (LLM error, syntax error, etc.)
    """
    # Get user input from query parameter
    user_input = request.args.get("input")

    if not user_input:
        return jsonify(
            {
                "error": "Missing 'input' query parameter",
                "usage": "/api/v1/generate_dsl?input=<workflow_description>",
            }
        ), 400

    try:
        print(f"📝 Generating DSL for: {user_input[:100]}...")

        # Call Ollama to generate code
        generated_code = call_ollama(user_input)

        # Clean the code (remove markdown formatting, fix common mistakes)
        cleaned_code = clean_generated_code(generated_code)

        # Validate Python syntax first
        is_valid_syntax, syntax_error = validate_python_syntax(cleaned_code)

        if not is_valid_syntax:
            print(f"❌ Syntax validation failed: {syntax_error}")
            return jsonify(
                {
                    "error": "Generated code has syntax errors",
                    "details": syntax_error,
                    "generated_code": cleaned_code,
                }
            ), 500

        # Validate with MCP server (checks workflow structure)
        is_valid_workflow, errors, warnings, workflow_info = validate_with_mcp(
            cleaned_code
        )

        if not is_valid_workflow:
            print(f"❌ Workflow validation failed: {errors}")
            return jsonify(
                {
                    "error": "Generated workflow has structural errors",
                    "details": errors,
                    "warnings": warnings,
                    "generated_code": cleaned_code,
                }
            ), 500

        # Log warnings but don't fail
        if warnings:
            print(f"⚠️ Workflow warnings: {warnings}")

        print("✓ Generated valid Highway DSL workflow")
        print(f"  - Name: {workflow_info.get('name', 'unknown')}")
        print(f"  - Tasks: {workflow_info.get('task_count', 0)}")
        print(f"  - Size: {len(cleaned_code)} bytes")

        # Return the valid Python code as plain text
        return Response(
            cleaned_code,
            mimetype="text/plain",
            headers={
                "Content-Disposition": "inline; filename=workflow.py",
                "X-Syntax-Valid": "true",
                "X-Workflow-Valid": "true",
                "X-Workflow-Name": workflow_info.get("name", ""),
                "X-Task-Count": str(workflow_info.get("task_count", 0)),
            },
        )

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": "Failed to generate DSL", "details": str(e)}), 500


@app.route("/api/v1/dsl-context", methods=["GET"])
def dsl_context():
    """
    Get the DSL reference context for code completion.

    This endpoint returns the comprehensive Highway DSL documentation
    that can be used as context for code completion models.

    Returns:
        200: DSL reference documentation as plain text
    """
    context = get_dsl_reference()
    return Response(context, mimetype="text/plain")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    try:
        # Check if Ollama is reachable
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        ollama_healthy = response.status_code == 200
    except Exception:
        ollama_healthy = False

    return jsonify(
        {
            "status": "healthy" if ollama_healthy else "degraded",
            "ollama_url": OLLAMA_BASE_URL,
            "ollama_model": OLLAMA_MODEL,
            "ollama_reachable": ollama_healthy,
            "mcp_enabled": True,
            "prompt_source": "mcp_server",
            "prompt_size": len(AGENT_PROMPT),
        }
    )


@app.route("/", methods=["GET"])
def index():
    """Root endpoint with API documentation."""
    return jsonify(
        {
            "service": "Highway DSL Generator API",
            "version": "2.0.0",  # Updated version for MCP integration
            "mcp_enabled": True,
            "endpoints": {
                "/api/v1/generate_dsl": {
                    "method": "GET",
                    "description": "Generate Highway DSL workflow from natural language",
                    "parameters": {"input": "Workflow description (required)"},
                    "example": "/api/v1/generate_dsl?input=Create a workflow that fetches data from an API and processes it",
                },
                "/api/v1/dsl-context": {
                    "method": "GET",
                    "description": "Get DSL reference context for code completion",
                },
                "/health": {"method": "GET", "description": "Health check endpoint"},
            },
            "configuration": {
                "ollama_url": OLLAMA_BASE_URL,
                "ollama_model": OLLAMA_MODEL,
                "port": 7291,
                "prompt_source": "MCP Server (highway_dsl.mcp_server)",
            },
        }
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Highway DSL Generator API (MCP-Powered)")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_BASE_URL}")
    print(f"Ollama Model: {OLLAMA_MODEL}")
    print("Prompt Source: MCP Server")
    print(f"Prompt Size: {len(AGENT_PROMPT)} chars")
    print("Port: 7291")
    print("=" * 60)
    print()
    print("Starting Flask server...")

    # Run Flask app
    app.run(host="0.0.0.0", port=7291, debug=False, threaded=True)
