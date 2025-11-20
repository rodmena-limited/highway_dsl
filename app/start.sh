#!/bin/bash
# Quick start script for Highway DSL Generator API

cd "$(dirname "$0")"

echo "=========================================="
echo "Highway DSL Generator API"
echo "=========================================="
echo

# Check if Ollama is running
echo "🔍 Checking Ollama server..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✓ Ollama is running"
else
    echo "❌ Error: Ollama is not running"
    echo "   Please start Ollama first"
    exit 1
fi

# Check dependencies
if ! python3 -c "import flask, requests" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

echo
echo "Starting API on port 7291..."
echo
python3 app.py
