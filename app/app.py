#!/usr/bin/env python3
"""
Highway DSL Generator API
A Flask API that generates Highway DSL workflows using Ollama LLM.

Endpoint: GET /api/v1/generate_dsl?input=<workflow_description>
Port: 7291
"""

import os
import sys
import tempfile
import py_compile
from pathlib import Path

import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
# CORS is now handled by nginx

# Configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud")
AGENT_PROMPT_PATH = Path(__file__).parent / "AGENT_PROMPT.md"


def load_agent_prompt():
    """Load the agent prompt from AGENT_PROMPT.md file."""
    try:
        with open(AGENT_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(
            f"ERROR: Agent prompt file not found at {AGENT_PROMPT_PATH}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load agent prompt: {e}", file=sys.stderr)
        sys.exit(1)


# Load prompt at startup
AGENT_PROMPT = load_agent_prompt()
print(f"✓ Loaded agent prompt from {AGENT_PROMPT_PATH}")


def call_ollama(user_input):
    """
    Call Ollama API with the agent prompt and user input.

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
            "temperature": 0.1,  # Low temperature for more deterministic output
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
    Clean the generated code by removing markdown formatting if present.

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

    cleaned = "\n".join(lines).strip()
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

        # Clean the code (remove markdown formatting)
        cleaned_code = clean_generated_code(generated_code)

        # Validate Python syntax
        is_valid, error_message = validate_python_syntax(cleaned_code)

        if not is_valid:
            print(f"❌ Syntax validation failed: {error_message}")
            return jsonify(
                {
                    "error": "Generated code has syntax errors",
                    "details": error_message,
                    "generated_code": cleaned_code,
                }
            ), 500

        print(f"✓ Generated valid Highway DSL workflow ({len(cleaned_code)} bytes)")

        # Return the valid Python code as plain text
        return Response(
            cleaned_code,
            mimetype="text/plain",
            headers={
                "Content-Disposition": "inline; filename=workflow.py",
                "X-Syntax-Valid": "true",
            },
        )

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": "Failed to generate DSL", "details": str(e)}), 500


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
            "agent_prompt_loaded": AGENT_PROMPT is not None,
        }
    )


@app.route("/", methods=["GET"])
def index():
    """Root endpoint with API documentation."""
    return jsonify(
        {
            "service": "Highway DSL Generator API",
            "version": "1.0.0",
            "endpoints": {
                "/api/v1/generate_dsl": {
                    "method": "GET",
                    "description": "Generate Highway DSL workflow from natural language",
                    "parameters": {"input": "Workflow description (required)"},
                    "example": "/api/v1/generate_dsl?input=Create a workflow that fetches data from an API and processes it",
                },
                "/health": {"method": "GET", "description": "Health check endpoint"},
            },
            "configuration": {
                "ollama_url": OLLAMA_BASE_URL,
                "ollama_model": OLLAMA_MODEL,
                "port": 7291,
            },
        }
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Highway DSL Generator API")
    print("=" * 60)
    print(f"Ollama URL: {OLLAMA_BASE_URL}")
    print(f"Ollama Model: {OLLAMA_MODEL}")
    print(f"Agent Prompt: {AGENT_PROMPT_PATH}")
    print("Port: 7291")
    print("=" * 60)
    print()
    print("Starting Flask server...")

    # Run Flask app
    app.run(host="0.0.0.0", port=7291, debug=False, threaded=True)
